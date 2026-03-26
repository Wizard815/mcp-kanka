"""Service layer for Kanka API operations."""

# mypy: warn_return_any=False

import logging
import os
from typing import Any

from kanka import KankaClient
from kanka.exceptions import KankaException
from kanka.models import (
    Character,
    Creature,
    Entity,
    Journal,
    Location,
    Note,
    Organisation,
    Quest,
    Race,
    Tag,
)

from .converter import ContentConverter
from .types import EntityType

logger = logging.getLogger(__name__)


class KankaService:
    """Service layer wrapping the python-kanka client."""

    # Map entity types to their model classes
    ENTITY_TYPE_MAP = {
        "character": Character,
        "creature": Creature,
        "location": Location,
        "organization": Organisation,  # Note: Kanka uses "organisation"
        "race": Race,
        "note": Note,
        "journal": Journal,
        "quest": Quest,
    }

    # Map entity types to their Kanka API endpoints
    API_ENDPOINT_MAP = {
        "character": "characters",
        "creature": "creatures",
        "ability": "abilities",
        "conversation": "conversations",
        "location": "locations",
        "organization": "organisations",  # API uses British spelling
        "dice_roll": "dice_rolls",
        "race": "races",
        "note": "notes",
        "journal": "journals",
        "quest": "quests",
        "bookmark": "bookmarks",
        "attribute": "attributes",
    }

    def __init__(self) -> None:
        """Initialize the service with Kanka client."""
        token = os.getenv("KANKA_TOKEN")
        campaign_id = os.getenv("KANKA_CAMPAIGN_ID")

        if not token or not campaign_id:
            raise ValueError(
                "KANKA_TOKEN and KANKA_CAMPAIGN_ID environment variables are required"
            )

        self.client = KankaClient(token=token, campaign_id=int(campaign_id))
        self.converter = ContentConverter()
        self._tag_cache: dict[str, Tag] = {}
        # Cached mapping from Kanka entity_type codes -> numeric type_id used by /entities filters.
        self._entity_type_code_to_id_cache: dict[str, int] = {}

    def search_entities(
        self,
        query: str,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for entities by name using list endpoints with filtering.

        This uses the list endpoints with name filtering instead of the search API,
        as they provide the same partial matching capability but with more control.

        Args:
            query: Search query (matches partial names)
            entity_type: Optional entity type filter
            limit: Maximum results

        Returns:
            List of minimal entity data
        """
        try:
            entities = []

            if entity_type:
                # Search specific entity type
                manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

                # Use name filter to search - it does partial matching!
                results = manager.list(name=query, limit=limit)

                for entity in results:
                    entities.append(
                        {
                            "entity_id": entity.entity_id,
                            "name": entity.name,
                            "entity_type": entity_type,
                        }
                    )
            else:
                # Search across all entity types
                # We'll need to query each type separately
                remaining_limit = limit

                for our_type, manager_name in self.API_ENDPOINT_MAP.items():
                    if remaining_limit <= 0:
                        break

                    manager = getattr(self.client, manager_name)

                    # Get up to remaining_limit results from this type
                    type_limit = min(remaining_limit, 100)  # API max is 100

                    try:
                        results = manager.list(name=query, limit=type_limit)

                        for entity in results:
                            entities.append(
                                {
                                    "entity_id": entity.entity_id,
                                    "name": entity.name,
                                    "entity_type": our_type,
                                }
                            )

                        remaining_limit -= len(results)

                    except Exception as e:
                        # Some entity types might not be available in the campaign
                        logger.debug(f"Could not search {our_type}: {e}")
                        continue

            return entities

        except KankaException as e:
            logger.error(f"Search failed: {e}")
            raise

    def global_search_entities(
        self, search_term: str, page: int = 1
    ) -> list[dict[str, Any]]:
        """Global search across entity types (GET search/{search_term})."""
        results = self.client.search(search_term, page=page)

        formatted: list[dict[str, Any]] = []
        for r in results:
            formatted.append(
                {
                    "id": r.id,
                    "entity_id": r.entity_id,
                    "name": r.name,
                    "image": r.image,
                    "type": r.type,
                    "tooltip": r.tooltip,
                    "url": r.url,
                    "is_private": r.is_private,
                    "created_at": (
                        r.created_at.isoformat() if r.created_at else None
                    ),
                    "updated_at": (
                        r.updated_at.isoformat() if r.updated_at else None
                    ),
                }
            )
        return formatted

    def list_entities(
        self,
        entity_type: EntityType,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
        tag_ids: list[int] | None = None,
    ) -> list[Any]:
        """
        List entities of a specific type.

        Args:
            entity_type: Entity type to list
            page: Page number
            limit: Results per page (0 for all)
            last_sync: ISO 8601 timestamp to get only entities modified after this time
            related: Include related data (posts, attributes, etc.)

        Returns:
            List of entity objects
        """
        try:
            # The Kanka API filters entities tags via `tags[]` (array-style) on the
            # `GET /entities` endpoint. The python-kanka SDK managers pass a `tags=...`
            # filter (often comma-joined), which doesn't reliably match `tags[]`.
            # To ensure doc-verified tag filtering, always use the raw endpoint
            # when `tag_ids` are provided.
            if tag_ids:
                return self._list_entities_raw(
                    entity_type=entity_type,
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                    tag_ids=tag_ids,
                )

            try:
                manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])
            except Exception:
                # Fallback for entity types not covered by the python-kanka SDK managers.
                return self._list_entities_raw(
                    entity_type=entity_type,
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                    tag_ids=tag_ids,
                )

            # Build filters
            filters = {}
            if last_sync:
                filters["lastSync"] = last_sync
            if tag_ids:
                # python-kanka managers accept `tags` as a list[int] tag-id filter.
                filters["tags"] = tag_ids

            if limit == 0:
                # Get all results by paginating through all API pages
                # Use the proper pagination info from the SDK
                all_entities = []
                current_page = 1
                logger.debug(
                    f"Starting pagination for {entity_type} with related={related}"
                )

                while True:
                    logger.debug(f"Fetching page {current_page}")
                    try:
                        batch = manager.list(
                            page=current_page, related=related, **filters
                        )
                        logger.debug(
                            f"Page {current_page} returned {len(batch)} entities"
                        )

                        # Add current page results
                        all_entities.extend(batch)

                        # Check if there's a next page using SDK pagination info
                        if not manager.has_next_page:
                            logger.debug("No more pages, stopping pagination")
                            break

                        current_page += 1

                        # Safety limit to prevent infinite loops
                        if current_page > 50:
                            logger.warning(
                                f"Hit safety limit of 50 pages for {entity_type}"
                            )
                            break

                    except Exception as e:
                        logger.error(
                            f"Error fetching page {current_page} for {entity_type}: {e}"
                        )
                        break

                logger.debug(
                    f"Pagination complete for {entity_type}: {len(all_entities)} total entities"
                )
                entities = all_entities
            else:
                # Get limited results (client-side limiting)
                # Fetch pages until we have enough entities
                all_entities = []
                current_page = page  # Start from requested page
                logger.debug(
                    f"Fetching for client-side limit of {limit} {entity_type}s starting from page {page}"
                )

                while len(all_entities) < limit:
                    try:
                        batch = manager.list(
                            page=current_page, related=related, **filters
                        )

                        all_entities.extend(batch)

                        # Stop if no more pages or we have enough
                        if not manager.has_next_page or len(all_entities) >= limit:
                            break

                        current_page += 1

                        # Safety limit
                        if current_page > 50:
                            logger.warning(
                                f"Hit safety limit of 50 pages for {entity_type}"
                            )
                            break

                    except Exception as e:
                        logger.error(
                            f"Error fetching page {current_page} for {entity_type}: {e}"
                        )
                        break

                # Apply client-side limit
                entities = all_entities[:limit]

            return list(entities)

        except KankaException as e:
            logger.error(f"List entities failed: {e}")
            raise

    def _normalize_entity_type_code(self, entity_type: str) -> str:
        """Normalize MCP/internal entity_type codes to Kanka's entity_types codes."""
        if entity_type == "organization":
            return "organisation"  # Kanka uses British spelling
        return entity_type

    def _load_entity_type_code_to_id_cache(self) -> None:
        """Load entity type code -> type_id mapping from the API once."""
        if self._entity_type_code_to_id_cache:
            return

        try:
            resp = self.client._request("GET", "entity_types")
            data = resp.get("data", [])
            for item in data:
                code = item.get("code")
                type_id = item.get("id")
                if isinstance(code, str) and isinstance(type_id, int):
                    self._entity_type_code_to_id_cache[code] = type_id
        except Exception as e:
            logger.warning(f"Failed to load entity_types cache: {e}")

    def _get_entity_type_id(
        self, entity_type: EntityType
    ) -> int | None:
        self._load_entity_type_code_to_id_cache()
        api_code = self._normalize_entity_type_code(entity_type)
        return self._entity_type_code_to_id_cache.get(api_code)

    def _list_entities_raw(
        self,
        entity_type: EntityType,
        page: int,
        limit: int,
        last_sync: str | None,
        related: bool,
        tag_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Raw /entities listing fallback for entity types not in python-kanka managers."""
        type_id = self._get_entity_type_id(entity_type)
        if type_id is None:
            return []

        all_entities: list[dict[str, Any]] = []
        current_page = page

        while True:
            params: dict[str, Any] = {
                "page": current_page,
                "type_id[]": [type_id],
            }
            if last_sync:
                params["lastSync"] = last_sync
            if related:
                params["related"] = 1
            if tag_ids:
                # Kanka entity filter uses tags[] for tag IDs.
                params["tags[]"] = tag_ids

            resp = self.client._request("GET", "entities", params=params)
            batch = resp.get("data", [])
            if not isinstance(batch, list):
                batch = []
            all_entities.extend(batch)

            if limit != 0 and len(all_entities) >= limit:
                return all_entities[:limit]

            meta = resp.get("meta") or {}
            last_page = meta.get("last_page") or meta.get("lastPage")
            if isinstance(last_page, int) and current_page >= last_page:
                break

            # If the API doesn't provide meta, stop when a page returns no data.
            if not batch:
                break

            current_page += 1
            if current_page > 50:
                logger.warning(
                    f"Hit safety limit of 50 pages for raw entity listing ({entity_type})"
                )
                break

        return all_entities

    def get_entity_by_id(
        self, entity_id: int, include_posts: bool = False
    ) -> dict[str, Any] | None:
        """
        Get a specific entity by its entity_id.

        Args:
            entity_id: Entity ID
            include_posts: Whether to include posts

        Returns:
            Entity data with converted content
        """
        try:
            # Use the direct entity endpoint
            found_entity = self.client.entity(entity_id)

            if not found_entity:
                # Entity not found
                return None

            # Get entity type - it's in the 'type' field
            entity_type = found_entity.get("type") or found_entity.get("entity_type")

            # Normalize to MCP/internal entity_type codes
            our_type = (
                "organization" if entity_type == "organisation" else entity_type
            )

            from typing import get_args

            if our_type not in set(get_args(EntityType)):
                return None

            # Determine the type-specific module ID needed by SDK managers.
            # Prefer the nested "child" object if present; otherwise fall back to top-level "id".
            type_id = None
            child_data = found_entity.get("child")
            if isinstance(child_data, dict):
                type_id = child_data.get("id")
            if type_id is None:
                type_id = found_entity.get("id")

            result: dict[str, Any] | None = None

            # First try the SDK manager (when available) for consistent conversion.
            try:
                manager_name = self.API_ENDPOINT_MAP.get(our_type)
                if manager_name and type_id is not None:
                    manager = getattr(self.client, manager_name)
                    entity = manager.get(type_id)
                    result = self._entity_to_dict(entity, our_type)
            except Exception as e:
                logger.debug(f"SDK get_entity fallback for {our_type} failed: {e}")

            # Fallback: use raw /entities/{entity_id} data (works for SDK-missing entity types).
            if result is None:
                raw_params = {"related": 1} if include_posts else None
                if raw_params is not None:
                    raw_resp = self.client._request(
                        "GET", f"entities/{entity_id}", params=raw_params
                    )
                    raw_data = raw_resp.get("data", raw_resp)
                else:
                    raw_data = found_entity

                result = self._entity_to_dict(raw_data, our_type)

            # Get posts if requested and we used the SDK manager path.
            if include_posts and "posts" not in result:
                try:
                    manager_name = self.API_ENDPOINT_MAP.get(our_type)
                    if manager_name:
                        manager = getattr(self.client, manager_name)
                        posts = manager.list_posts(entity_id, limit=100)
                        result["posts"] = [
                            self._post_to_dict(post) for post in posts
                        ]
                except Exception as e:
                    logger.warning(
                        f"Failed to get posts for entity {entity_id}: {e}"
                    )
                    result["posts"] = []

            return result

        except Exception as e:
            logger.error(f"Get entity failed for {entity_id}: {e}")
            return None

    def create_entity(
        self,
        entity_type: EntityType,
        name: str,
        type: str | None = None,
        entry: str | None = None,
        tags: list[str] | None = None,
        is_hidden: bool | None = None,
        location_id: int | None = None,
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new entity.

        Args:
            entity_type: Type of entity
            name: Entity name
            type: Entity subtype
            entry: Description in Markdown
            tags: List of tag names
            is_hidden: Whether entity should be hidden from players (admin-only)
            is_completed: Whether quest is completed (quests only)
            image_uuid: Image gallery UUID for entity image
            header_uuid: Image gallery UUID for entity header

        Returns:
            Created entity data
        """
        try:
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Prepare data
            data: dict[str, Any] = {"name": name}

            if type is not None:
                data["type"] = type

            if entry is not None:
                # Convert markdown to HTML
                data["entry"] = self.converter.markdown_to_html(entry)

            # Set privacy based on is_hidden
            # For entities, use is_private (not visibility_id)
            if is_hidden is not None:
                data["is_private"] = is_hidden
            elif entity_type == "note":
                # Notes default to private
                data["is_private"] = True
            else:
                # Default to public
                data["is_private"] = False

            # Handle tags
            if tags:
                tag_ids = self._get_or_create_tag_ids(tags)
                data["tags"] = tag_ids

            # Handle location parent
            if entity_type == "location" and location_id is not None:
                data["location_id"] = location_id

            # Handle quest-specific field
            if entity_type == "quest" and is_completed is not None:
                data["is_completed"] = is_completed

            # Handle image fields
            if image_uuid is not None:
                data["image_uuid"] = image_uuid
            if header_uuid is not None:
                data["header_uuid"] = header_uuid

            # Create entity
            entity = manager.create(**data)

            # Convert to our format
            result = self._entity_to_dict(entity, entity_type)
            result["mention"] = f"[entity:{entity.entity_id}]"

            # If we explicitly set privacy, ensure it's reflected in the result
            # The API might not return is_private in the create response
            if "is_private" in data:
                result["is_hidden"] = data["is_private"]

            return result

        except KankaException as e:
            logger.error(f"Create entity failed: {e}")
            raise

    def update_entity(
        self,
        entity_id: int,
        name: str | None = None,
        type: str | None = None,
        entry: str | None = None,
        tags: list[str] | None = None,
        is_hidden: bool | None = None,
        location_id: int | None = None,
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
    ) -> bool:
        """
        Update an existing entity.

        Args:
            entity_id: Entity ID
            name: Entity name (optional for PATCH; if omitted and API requires it, MCP will retry with the current name)
            type: Entity subtype
            entry: Description in Markdown
            tags: List of tag names
            is_hidden: Whether entity should be hidden from players (admin-only)
            is_completed: Whether quest is completed (quests only)
            image_uuid: Image gallery UUID for entity image
            header_uuid: Image gallery UUID for entity header

        Returns:
            True if successful
        """
        try:
            # First get the entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Prepare update data
            data: dict[str, Any] = {}
            if name is not None:
                data["name"] = name

            if type is not None:
                data["type"] = type

            if entry is not None:
                # Convert markdown to HTML
                data["entry"] = self.converter.markdown_to_html(entry)

            # Handle privacy
            # For entities, use is_private (not visibility_id)
            if is_hidden is not None:
                data["is_private"] = is_hidden

            # Handle tags
            if tags is not None:
                tag_ids = self._get_or_create_tag_ids(tags)
                data["tags"] = tag_ids

            # Handle location parent
            if entity_type == "location" and location_id is not None:
                data["location_id"] = location_id

            # Handle quest-specific field
            if entity_type == "quest" and is_completed is not None:
                data["is_completed"] = is_completed

            # Handle image fields
            if image_uuid is not None:
                data["image_uuid"] = image_uuid
            if header_uuid is not None:
                data["header_uuid"] = header_uuid

            def looks_like_name_required_error(exc: Exception) -> bool:
                text = str(exc).lower()
                return "name" in text and (
                    "required" in text or "missing" in text or "must" in text
                )

            # Update entity
            try:
                manager.update(entity_data["id"], **data)
            except KankaException as exc:
                # Fallback: some endpoints may still validate `name` even when PATCH is used.
                if name is None and looks_like_name_required_error(exc):
                    retry_data = dict(data)
                    retry_data["name"] = entity_data["name"]
                    manager.update(entity_data["id"], **retry_data)
                else:
                    raise
            return True

        except Exception as e:
            logger.error(f"Update entity failed for {entity_id}: {e}")
            raise

    def delete_entity(self, entity_id: int) -> bool:
        """
        Delete an entity.

        Args:
            entity_id: Entity ID

        Returns:
            True if successful
        """
        try:
            # First get the entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Delete entity
            manager.delete(entity_data["id"])
            return True

        except Exception as e:
            logger.error(f"Delete entity failed for {entity_id}: {e}")
            raise

    def create_post(
        self,
        entity_id: int,
        name: str,
        entry: str | None = None,
        is_hidden: bool = False,
    ) -> dict[str, Any]:
        """
        Create a post on an entity.

        Args:
            entity_id: Entity ID
            name: Post title
            entry: Post content in Markdown
            is_hidden: Whether post should be hidden from players (admin-only)

        Returns:
            Created post data
        """
        try:
            # Get entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Convert markdown to HTML if entry provided
            html_entry = self.converter.markdown_to_html(entry) if entry else None

            # Set visibility based on is_hidden
            visibility_id = 2 if is_hidden else 1

            # Create post - use entity_id, not the type-specific id
            post = manager.create_post(
                entity_id,
                name=name,
                entry=html_entry or "",
                visibility_id=visibility_id,
            )

            return {
                "post_id": post.id,
                "entity_id": entity_id,
            }

        except Exception as e:
            logger.error(f"Create post failed: {e}")
            raise

    def update_post(
        self,
        entity_id: int,
        post_id: int,
        name: str | None = None,
        entry: str | None = None,
        is_hidden: bool | None = None,
    ) -> bool:
        """
        Update a post.

        Args:
            entity_id: Entity ID
            post_id: Post ID
            name: Post title (optional for PATCH; if omitted and API requires it, MCP will retry with the current title)
            entry: Post content in Markdown
            is_hidden: Whether post should be hidden from players (admin-only)

        Returns:
            True if successful
        """
        try:
            # Get entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Prepare update data
            kwargs: dict[str, Any] = {}
            if name is not None:
                kwargs["name"] = name

            if entry is not None:
                kwargs["entry"] = self.converter.markdown_to_html(entry)

            # Handle visibility
            # For posts, use visibility_id
            visibility_id = None
            if is_hidden is not None:
                visibility_id = 2 if is_hidden else 1

            def looks_like_name_required_error(exc: Exception) -> bool:
                text = str(exc).lower()
                return "name" in text and (
                    "required" in text or "missing" in text or "must" in text
                )

            # Update post - use entity_id, not the type-specific id
            try:
                manager.update_post(
                    entity_id, post_id, visibility_id=visibility_id, **kwargs
                )
            except KankaException as exc:
                # Fallback: some endpoints may still validate `name` even when PATCH is used.
                if name is None and looks_like_name_required_error(exc):
                    current_post = manager.get_post(entity_id, post_id)
                    retry_kwargs = dict(kwargs)
                    retry_kwargs["name"] = current_post.name
                    manager.update_post(
                        entity_id,
                        post_id,
                        visibility_id=visibility_id,
                        **retry_kwargs,
                    )
                else:
                    raise
            return True

        except Exception as e:
            logger.error(f"Update post failed: {e}")
            raise

    def delete_post(self, entity_id: int, post_id: int) -> bool:
        """
        Delete a post.

        Args:
            entity_id: Entity ID
            post_id: Post ID

        Returns:
            True if successful
        """
        try:
            # Get entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Delete post - use entity_id, not the type-specific id
            manager.delete_post(entity_id, post_id)
            return True

        except Exception as e:
            logger.error(f"Delete post failed: {e}")
            raise

    def raw_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a raw Kanka API request and normalize the response shape.

        Kanka list endpoints typically return `{data, links, meta}`. For non-list
        endpoints, we still return the same wrapper keys for consistency.
        """
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        if json is not None:
            kwargs["json"] = json

        resp = self.client._request(method, endpoint, **kwargs)
        return {
            "data": resp.get("data", resp),
            "links": resp.get("links", {}),
            "meta": resp.get("meta", {}),
        }

    # ----------------------------
    # Map marker operations
    # ----------------------------
    def list_map_markers(
        self, map_id: int, page: int = 1, limit: int = 30
    ) -> dict[str, Any]:
        """List map markers for a map (paginated; returns links/meta)."""
        endpoint = f"maps/{map_id}/map_markers"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.client._request("GET", endpoint, params=params)

    def create_map_marker(self, map_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a map marker under the given map."""
        endpoint = f"maps/{map_id}/map_markers"
        # The API docs require map_id in the body as well.
        body = dict(payload)
        body.setdefault("map_id", map_id)
        return self.client._request("POST", endpoint, json=body)

    def get_map_marker(self, map_id: int, marker_id: int) -> dict[str, Any]:
        """Return one map marker (GET maps/{map_id}/map_markers/{marker_id})."""
        resp = self.client._request("GET", f"maps/{map_id}/map_markers/{marker_id}")
        data = resp.get("data", resp)
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected map marker response for {map_id}/{marker_id}")
        return data

    def update_map_marker(
        self, map_id: int, marker_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a map marker using PATCH with an explicit field payload.

        Kanka validates that when ``entity_id`` is cleared (JSON null), ``name`` must
        still be present. If the caller omits ``name`` while sending ``entity_id`` as
        null, we merge the current marker's name from GET so PATCH does not 422.
        """
        endpoint = f"maps/{map_id}/map_markers/{marker_id}"
        body = dict(payload)
        body.setdefault("map_id", map_id)
        if "entity_id" in body and body.get("entity_id") is None and not body.get(
            "name"
        ):
            current = self.get_map_marker(map_id, marker_id)
            nm = current.get("name")
            if nm is not None and str(nm).strip() != "":
                body["name"] = nm
            else:
                raise ValueError(
                    "Cannot clear entity_id without a marker name: pass `name` in the "
                    f"payload or set a non-empty name on marker {map_id}/{marker_id} first."
                )
        return self.client._request("PATCH", endpoint, json=body)

    def delete_map_marker(self, map_id: int, marker_id: int) -> dict[str, Any]:
        """Delete a map marker."""
        endpoint = f"maps/{map_id}/map_markers/{marker_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Relation operations
    # ----------------------------
    def list_relations(
        self, entity_id: int, page: int = 1, limit: int = 30
    ) -> dict[str, Any]:
        """List relations attached to an entity (paginated; returns links/meta)."""
        endpoint = f"entities/{entity_id}/relations"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.client._request("GET", endpoint, params=params)

    def create_relation(
        self, entity_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a relation under an entity."""
        endpoint = f"entities/{entity_id}/relations"
        return self.client._request("POST", endpoint, json=payload)

    def update_relation(
        self, entity_id: int, relation_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a relation under an entity (PATCH with explicit payload)."""
        endpoint = f"entities/{entity_id}/relations/{relation_id}"
        return self.client._request("PATCH", endpoint, json=payload)

    def delete_relation(
        self, entity_id: int, relation_id: int
    ) -> dict[str, Any]:
        """Delete a relation under an entity."""
        endpoint = f"entities/{entity_id}/relations/{relation_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Timeline element operations
    # ----------------------------
    def list_timeline_elements(
        self, timeline_id: int, page: int = 1, limit: int = 15
    ) -> dict[str, Any]:
        """List timeline elements for a timeline (paginated; returns links/meta)."""
        endpoint = f"timelines/{timeline_id}/timeline_elements"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.client._request("GET", endpoint, params=params)

    def create_timeline_element(
        self, timeline_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a timeline element."""
        endpoint = f"timelines/{timeline_id}/timeline_elements"
        return self.client._request("POST", endpoint, json=payload)

    def update_timeline_element(
        self, timeline_id: int, element_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a timeline element using PATCH with an explicit payload."""
        endpoint = f"timelines/{timeline_id}/timeline_elements/{element_id}"
        return self.client._request("PATCH", endpoint, json=payload)

    def delete_timeline_element(
        self, timeline_id: int, element_id: int
    ) -> dict[str, Any]:
        """Delete a timeline element."""
        endpoint = f"timelines/{timeline_id}/timeline_elements/{element_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Entity attribute properties
    # ----------------------------
    def list_attributes(
        self, entity_id: int, page: int = 1, limit: int = 30
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/attributes"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

    def create_attribute(
        self, entity_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/attributes"
        return self.raw_request("POST", endpoint, json=payload)

    def update_attribute(
        self,
        entity_id: int,
        attribute_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/attributes/{attribute_id}"
        return self.raw_request("PATCH", endpoint, json=payload)

    def delete_attribute(
        self, entity_id: int, attribute_id: int
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/attributes/{attribute_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Entity tags (entity_tags)
    # ----------------------------
    def list_entity_tags(self, entity_id: int) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/entity_tags"
        return self.raw_request("GET", endpoint)

    def add_entity_tag(self, entity_id: int, tag_id: int) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/entity_tags"
        body = {"tag_id": tag_id}
        return self.raw_request("POST", endpoint, json=body)

    def remove_entity_tag(
        self, entity_id: int, entity_tag_id: int
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/entity_tags/{entity_tag_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Entity inventory
    # ----------------------------
    def list_inventory(
        self, entity_id: int, page: int = 1, limit: int = 30
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/inventory"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

    def create_inventory(
        self, entity_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/inventory"
        # Endpoint docs require entity_id in the body.
        body = dict(payload)
        body.setdefault("entity_id", entity_id)
        return self.raw_request("POST", endpoint, json=body)

    def update_inventory(
        self,
        entity_id: int,
        inventory_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/inventory/{inventory_id}"
        body = dict(payload)
        body.setdefault("entity_id", entity_id)
        return self.raw_request("PATCH", endpoint, json=body)

    def delete_inventory(
        self, entity_id: int, inventory_id: int
    ) -> dict[str, Any]:
        # Docs use a different path segment: entity_inventory.
        endpoint = f"entities/{entity_id}/entity_inventory/{inventory_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Entity permissions (entity_permissions)
    # ----------------------------
    def list_permissions(self, entity_id: int) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/entity_permissions"
        return self.raw_request("GET", endpoint)

    def create_permission(
        self, entity_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/entity_permissions"
        return self.raw_request("POST", endpoint, json=payload)

    # ----------------------------
    # Archives + media + calendar
    # ----------------------------
    def get_archives(self) -> dict[str, Any]:
        """Retrieve all archived entities."""
        # Docs response is { "data": [...] } (no pagination wrapper keys).
        return self.client._request("GET", "entities/archived")

    def get_entity_image(self, entity_id: int) -> dict[str, Any]:
        """Get an entity's image and header image uuids/urls."""
        endpoint = f"entities/{entity_id}/image"
        # Docs response is { "image": {...}, "header": {...} } (no `data` wrapper).
        return self.client._request("GET", endpoint)

    def upload_entity_image_from_file(
        self, entity_id: int, file_path: str, is_header: bool = False
    ) -> dict[str, Any]:
        """Upload/replace an entity image using a local file path."""
        # Build absolute URL because Kanka requires multipart/form-data.
        endpoint = f"entities/{entity_id}/image"
        url = (
            f"{self.client.BASE_URL}/campaigns/{self.client.campaign_id}/{endpoint}"
        )

        filename = os.path.basename(file_path) or "upload"
        with open(file_path, "rb") as f:
            data = {"is_header": str(bool(is_header)).lower()}
            files = {"file": (filename, f)}
            resp = self.client.session.post(url, data=data, files=files)
            resp.raise_for_status()
            return resp.json()

    def remove_entity_image(
        self, entity_id: int, is_header: bool = False
    ) -> dict[str, Any]:
        """Unlink an entity's image (won't delete from gallery)."""
        endpoint = f"entities/{entity_id}/image"
        url = (
            f"{self.client.BASE_URL}/campaigns/{self.client.campaign_id}/{endpoint}"
        )
        resp = self.client.session.request(
            "DELETE",
            url,
            params={"is_header": str(bool(is_header)).lower()},
        )
        # Some DELETE endpoints respond with an empty body.
        if not resp.text:
            return {"success": True}
        try:
            return resp.json()
        except Exception:
            return {"success": True, "raw": resp.text}

    def list_calendar_weather(
        self,
        calendar_id: int,
        page: int = 1,
        limit: int = 15,
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/calendar_weather"
        params = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

    def create_calendar_weather(
        self, calendar_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/calendar_weather"
        # Docs response is {success: ...} without pagination wrapper keys.
        return self.client._request("POST", endpoint, json=payload)

    def update_calendar_weather(
        self,
        calendar_id: int,
        calendar_weather_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint = (
            f"calendars/{calendar_id}/calendar_weather/{calendar_weather_id}"
        )
        return self.client._request("PATCH", endpoint, json=payload)

    def delete_calendar_weather(
        self, calendar_id: int, calendar_weather_id: int
    ) -> dict[str, Any]:
        endpoint = (
            f"calendars/{calendar_id}/calendar_weather/{calendar_weather_id}"
        )
        url = (
            f"{self.client.BASE_URL}/campaigns/{self.client.campaign_id}/{endpoint}"
        )
        resp = self.client.session.request("DELETE", url)
        if not resp.text:
            return {"success": True}
        try:
            return resp.json()
        except Exception:
            return {"success": True, "raw": resp.text}

    def calendar_advance_date(self, calendar_id: int) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/advance"
        return self.client._request("POST", endpoint)

    def calendar_retreat_date(self, calendar_id: int) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/retreat"
        return self.client._request("POST", endpoint)

    def _get_or_create_tag_ids(self, tag_names: list[str]) -> list[int]:
        """
        Get or create tags by name.

        Args:
            tag_names: List of tag names

        Returns:
            List of tag IDs
        """
        # Load tag cache if needed
        if not self._tag_cache:
            self._load_tag_cache()

        tag_ids = []
        for name in tag_names:
            name_lower = name.lower()

            # Check cache
            if name_lower in self._tag_cache:
                tag_ids.append(self._tag_cache[name_lower].id)
            else:
                # Create new tag
                try:
                    tag = self.client.tags.create(name=name)
                    self._tag_cache[name_lower] = tag
                    tag_ids.append(tag.id)
                except Exception as e:
                    logger.warning(f"Failed to create tag '{name}': {e}")

        return tag_ids

    def _load_tag_cache(self) -> None:
        """Load all tags into cache."""
        self._tag_cache = {}
        try:
            # Get all tags by paginating through them
            current_page = 1
            while True:
                batch = self.client.tags.list(page=current_page, limit=100)
                if not batch:
                    break
                for tag in batch:
                    self._tag_cache[tag.name.lower()] = tag
                if len(batch) < 100:
                    break
                current_page += 1
        except Exception as e:
            logger.warning(f"Failed to load tag cache: {e}")

    def _resolve_tag_names(self, raw_tags: list[Any]) -> list[str]:
        """
        Resolve tag IDs to tag names.

        Args:
            raw_tags: List of tag IDs or tag objects

        Returns:
            List of tag names
        """
        if not raw_tags or not isinstance(raw_tags, list):
            return []

        # Ensure tag cache is loaded
        if not self._tag_cache:
            self._load_tag_cache()

        tag_names = []
        for tag_item in raw_tags:
            if isinstance(tag_item, int | str):
                # It's a tag ID, need to look it up
                tag_id = int(tag_item) if isinstance(tag_item, str) else tag_item

                # Check cache first
                tag_name = None
                for _cached_name, cached_tag in self._tag_cache.items():
                    if cached_tag.id == tag_id:
                        tag_name = cached_tag.name
                        break

                if tag_name:
                    tag_names.append(tag_name)
                else:
                    # Not in cache, try to fetch it
                    try:
                        tag = self.client.tags.get(tag_id)
                        tag_names.append(tag.name)
                        # Add to cache for future lookups
                        self._tag_cache[tag.name.lower()] = tag
                    except Exception as e:
                        logger.warning(f"Failed to resolve tag ID {tag_id}: {e}")
                        # If we can't resolve it, keep the ID as string
                        tag_names.append(str(tag_id))
            elif isinstance(tag_item, dict) and "name" in tag_item:
                # Already expanded tag object.
                tag_names.append(str(tag_item["name"]))
            elif hasattr(tag_item, "name"):
                # It's a tag object
                tag_names.append(tag_item.name)
            else:
                # Unknown format, keep as string
                tag_names.append(str(tag_item))

        return tag_names

    def _entity_to_dict(
        self, entity: Any, entity_type: str
    ) -> dict[str, Any]:
        """
        Convert entity object to dictionary.

        Args:
            entity: Entity object
            entity_type: Our entity type string

        Returns:
            Dictionary representation
        """
        if isinstance(entity, dict):
            return self._entity_dict_to_dict(entity, entity_type)

        result = {
            "id": entity.id,
            "entity_id": entity.entity_id,
            "name": entity.name,
            "entity_type": entity_type,
            "type": getattr(entity, "type", None),
            "tags": [],
            "created_at": (
                entity.created_at.isoformat()
                if hasattr(entity, "created_at") and entity.created_at
                else None
            ),
            "updated_at": (
                entity.updated_at.isoformat()
                if hasattr(entity, "updated_at") and entity.updated_at
                else None
            ),
        }

        # Handle visibility - translate is_private to is_hidden
        # Entities use is_private field
        is_private = getattr(entity, "is_private", None)
        if is_private is not None:
            result["is_hidden"] = is_private
        else:
            # Default to visible if no is_private field
            result["is_hidden"] = False

        # Convert HTML entry to Markdown
        if hasattr(entity, "entry") and entity.entry:
            result["entry"] = self.converter.html_to_markdown(entity.entry)
        else:
            result["entry"] = None

        # Extract tag names using helper method
        if hasattr(entity, "tags"):
            result["tags"] = self._resolve_tag_names(entity.tags)

        # Handle posts if present (when related=True)
        if hasattr(entity, "posts") and entity.posts is not None:
            result["posts"] = [self._post_to_dict(post) for post in entity.posts]

        # Handle quest-specific fields
        if entity_type == "quest":
            result["is_completed"] = getattr(entity, "is_completed", None)

        # Handle image fields - always include all 5 fields
        result["image"] = getattr(entity, "image", None)
        result["image_full"] = getattr(entity, "image_full", None)
        result["image_thumb"] = getattr(entity, "image_thumb", None)
        result["image_uuid"] = getattr(entity, "image_uuid", None)
        result["header_uuid"] = getattr(entity, "header_uuid", None)

        return result

    def _post_dict_to_dict(self, post: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw post dict to the MCP post dict shape."""
        result = {
            "id": post.get("id"),
            "name": post.get("name"),
        }

        visibility_id = post.get("visibility_id")
        if visibility_id is not None:
            # visibility_id 2 = admin only (hidden from players)
            result["is_hidden"] = visibility_id == 2
        else:
            result["is_hidden"] = False

        entry_html = post.get("entry")
        if entry_html:
            result["entry"] = self.converter.html_to_markdown(entry_html)
        else:
            result["entry"] = None

        return result

    def _entity_dict_to_dict(
        self, entity: dict[str, Any], entity_type: str
    ) -> dict[str, Any]:
        """Convert a raw /entities payload dict to the MCP entity dict shape."""
        entity_id = entity.get("entity_id")
        if entity_id is None:
            # Common fallback from list endpoints.
            entity_id = entity.get("child_id") or entity.get("id")

        result: dict[str, Any] = {
            "id": entity.get("id"),
            "entity_id": entity_id,
            "name": entity.get("name"),
            "entity_type": entity_type,
            "type": entity.get("type"),
            "entry": None,
            "tags": [],
            "created_at": entity.get("created_at"),
            "updated_at": entity.get("updated_at"),
        }

        # Translate is_private to is_hidden
        is_private = entity.get("is_private")
        result["is_hidden"] = bool(is_private) if is_private is not None else False

        entry_html = entity.get("entry")
        if entry_html:
            result["entry"] = self.converter.html_to_markdown(entry_html)

        raw_tags = entity.get("tags") or []
        if isinstance(raw_tags, list):
            result["tags"] = self._resolve_tag_names(raw_tags)
        else:
            # Be defensive if the API returns a non-list shape
            result["tags"] = self._resolve_tag_names([raw_tags])

        # Handle related posts when ?related=1 was used.
        posts = entity.get("posts")
        if isinstance(posts, list) and posts is not None:
            result["posts"] = [
                self._post_dict_to_dict(p) if isinstance(p, dict) else self._post_to_dict(p)
                for p in posts
            ]

        # Handle quest-specific fields
        if entity_type == "quest":
            result["is_completed"] = entity.get("is_completed")

        # Image fields
        result["image"] = entity.get("image")
        result["image_full"] = entity.get("image_full")
        result["image_thumb"] = entity.get("image_thumb")
        result["image_uuid"] = entity.get("image_uuid")
        result["header_uuid"] = entity.get("header_uuid")

        return result

    def _post_to_dict(self, post: Any) -> dict[str, Any]:
        """
        Convert post object to dictionary.

        Args:
            post: Post object

        Returns:
            Dictionary representation
        """
        result = {
            "id": post.id,
            "name": post.name,
        }

        # Handle visibility - translate visibility_id to is_hidden
        # Posts use visibility_id field
        visibility_id = getattr(post, "visibility_id", None)
        if visibility_id is not None:
            # visibility_id 2 = admin only (hidden from players)
            result["is_hidden"] = visibility_id == 2
        else:
            # Default to visible if no visibility_id
            result["is_hidden"] = False

        # Convert HTML entry to Markdown
        if hasattr(post, "entry") and post.entry:
            result["entry"] = self.converter.html_to_markdown(post.entry)
        else:
            result["entry"] = None

        return result


# Global service instance (initialized on first use)
_service: KankaService | None = None


def get_service() -> KankaService:
    """Get or create the Kanka service instance."""
    global _service
    if _service is None:
        _service = KankaService()
    return _service
