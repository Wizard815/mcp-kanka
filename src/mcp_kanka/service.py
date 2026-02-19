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
    Family,
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

    # Map entity types to their model classes (None = no SDK model, use direct API)
    ENTITY_TYPE_MAP: dict[str, type[Entity] | None] = {
        "calendar": None,
        "character": Character,
        "creature": Creature,
        "event": None,
        "family": Family,
        "item": None,
        "location": Location,
        "map": None,
        "organization": Organisation,  # Note: Kanka uses "organisation"
        "race": Race,
        "note": Note,
        "journal": Journal,
        "quest": Quest,
        "tag": Tag,
        "timeline": None,
    }

    # Map entity types to their Kanka API endpoints
    API_ENDPOINT_MAP = {
        "calendar": "calendars",
        "character": "characters",
        "creature": "creatures",
        "event": "events",
        "family": "families",
        "item": "items",
        "location": "locations",
        "map": "maps",
        "organization": "organisations",  # API uses British spelling
        "race": "races",
        "note": "notes",
        "journal": "journals",
        "quest": "quests",
        "tag": "tags",
        "timeline": "timelines",
    }

    # Map entity types to their parent ID field name in the Kanka API
    PARENT_ID_FIELD_MAP = {
        "calendar": None,
        "character": None,
        "creature": "creature_id",
        "event": None,
        "family": "family_id",
        "item": "item_id",
        "location": "location_id",  # Kanka API uses location_id for parent
        "map": "map_id",  # maps can be nested under parent map
        "organization": "organisation_id",
        "race": "race_id",
        "note": "note_id",
        "journal": "journal_id",
        "quest": "quest_id",
        "tag": "tag_id",
        "timeline": None,
    }

    # Map Kanka API type names to our internal type names
    API_TYPE_TO_INTERNAL = {
        "calendar": "calendar",
        "Calendar": "calendar",
        "character": "character",
        "creature": "creature",
        "event": "event",
        "Event": "event",
        "family": "family",
        "item": "item",
        "location": "location",
        "map": "map",
        "organisation": "organization",
        "race": "race",
        "note": "note",
        "journal": "journal",
        "quest": "quest",
        "tag": "tag",
        "timeline": "timeline",
        "Timeline": "timeline",
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
                if entity_type == "item":
                    results = self._item_list(name=query, limit=limit)
                    for item_data in results:
                        entities.append(
                            {
                                "entity_id": item_data["entity_id"],
                                "name": item_data["name"],
                                "entity_type": "item",
                            }
                        )
                elif entity_type == "map":
                    results = self._map_list(name=query, limit=limit)
                    for map_data in results:
                        entities.append(
                            {
                                "entity_id": map_data["entity_id"],
                                "name": map_data["name"],
                                "entity_type": "map",
                            }
                        )
                elif entity_type == "calendar":
                    results = self._calendar_list(name=query, limit=limit)
                    for data in results:
                        entities.append(
                            {
                                "entity_id": data["entity_id"],
                                "name": data["name"],
                                "entity_type": "calendar",
                            }
                        )
                elif entity_type == "event":
                    results = self._event_list(name=query, limit=limit)
                    for data in results:
                        entities.append(
                            {
                                "entity_id": data["entity_id"],
                                "name": data["name"],
                                "entity_type": "event",
                            }
                        )
                elif entity_type == "timeline":
                    results = self._timeline_list(name=query, limit=limit)
                    for data in results:
                        entities.append(
                            {
                                "entity_id": data["entity_id"],
                                "name": data["name"],
                                "entity_type": "timeline",
                            }
                        )
                else:
                    manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])
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

                for our_type, endpoint in self.API_ENDPOINT_MAP.items():
                    if remaining_limit <= 0:
                        break

                    # Use direct API for item and map (no SDK manager)
                    if our_type == "item":
                        try:
                            results = self._item_list(
                                name=query, limit=min(remaining_limit, 100)
                            )
                            for item_data in results:
                                entities.append(
                                    {
                                        "entity_id": item_data["entity_id"],
                                        "name": item_data["name"],
                                        "entity_type": "item",
                                    }
                                )
                            remaining_limit -= len(results)
                        except Exception as e:
                            logger.debug(f"Could not search items: {e}")
                        continue
                    if our_type == "map":
                        try:
                            results = self._map_list(
                                name=query, limit=min(remaining_limit, 100)
                            )
                            for map_data in results:
                                entities.append(
                                    {
                                        "entity_id": map_data["entity_id"],
                                        "name": map_data["name"],
                                        "entity_type": "map",
                                    }
                                )
                            remaining_limit -= len(results)
                        except Exception as e:
                            logger.debug(f"Could not search maps: {e}")
                        continue
                    if our_type == "calendar":
                        try:
                            results = self._calendar_list(
                                name=query, limit=min(remaining_limit, 100)
                            )
                            for data in results:
                                entities.append(
                                    {
                                        "entity_id": data["entity_id"],
                                        "name": data["name"],
                                        "entity_type": "calendar",
                                    }
                                )
                            remaining_limit -= len(results)
                        except Exception as e:
                            logger.debug(f"Could not search calendars: {e}")
                        continue
                    if our_type == "event":
                        try:
                            results = self._event_list(
                                name=query, limit=min(remaining_limit, 100)
                            )
                            for data in results:
                                entities.append(
                                    {
                                        "entity_id": data["entity_id"],
                                        "name": data["name"],
                                        "entity_type": "event",
                                    }
                                )
                            remaining_limit -= len(results)
                        except Exception as e:
                            logger.debug(f"Could not search events: {e}")
                        continue
                    if our_type == "timeline":
                        try:
                            results = self._timeline_list(
                                name=query, limit=min(remaining_limit, 100)
                            )
                            for data in results:
                                entities.append(
                                    {
                                        "entity_id": data["entity_id"],
                                        "name": data["name"],
                                        "entity_type": "timeline",
                                    }
                                )
                            remaining_limit -= len(results)
                        except Exception as e:
                            logger.debug(f"Could not search timelines: {e}")
                        continue

                    manager = getattr(self.client, endpoint)

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

    def list_entities(
        self,
        entity_type: EntityType,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
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
            # Items and maps use direct API (no SDK manager)
            if entity_type == "item":
                return self._item_list_entities(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                )
            if entity_type == "map":
                return self._map_list_entities(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                )
            if entity_type == "calendar":
                return self._calendar_list_entities(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                )
            if entity_type == "event":
                return self._event_list_entities(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                )
            if entity_type == "timeline":
                return self._timeline_list_entities(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                )

            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Build filters
            filters = {}
            if last_sync:
                filters["lastSync"] = last_sync

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
            api_type = found_entity.get("type")
            our_type = self.API_TYPE_TO_INTERNAL.get(api_type or "")
            if not our_type:
                return None

            # The entity endpoint returns the data in 'child' field
            child_data = found_entity.get("child")
            if not child_data:
                return None

            # Get the type-specific ID
            type_id = child_data.get("id")
            if not type_id:
                return None

            # Items and maps have no SDK manager -- use direct API response
            if our_type == "item":
                result = self._item_response_to_dict(child_data, entity_id)
            elif our_type == "map":
                result = self._map_response_to_dict(child_data, entity_id)
            elif our_type == "calendar":
                result = self._calendar_response_to_dict(child_data, entity_id)
            elif our_type == "event":
                result = self._event_response_to_dict(child_data, entity_id)
            elif our_type == "timeline":
                result = self._timeline_response_to_dict(child_data, entity_id)
            else:
                manager = getattr(self.client, self.API_ENDPOINT_MAP[our_type])
                entity = manager.get(type_id)
                result = self._entity_to_dict(entity, our_type)

            # Get posts if requested
            if include_posts:
                try:
                    if our_type in ("item", "map", "calendar", "event", "timeline"):
                        posts = self._entity_posts_list(entity_id, limit=100)
                        result["posts"] = posts
                    else:
                        manager = getattr(self.client, self.API_ENDPOINT_MAP[our_type])
                        posts = manager.list_posts(entity_id, limit=100)
                        result["posts"] = [self._post_to_dict(post) for post in posts]
                except Exception as e:
                    logger.warning(f"Failed to get posts for entity {entity_id}: {e}")
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
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
        parent_id: int | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """Create a new entity with all supported fields."""
        try:
            data: dict[str, Any] = {"name": name}

            if type is not None:
                data["type"] = type
            if entry is not None:
                data["entry"] = self.converter.markdown_to_html(entry)

            if is_hidden is not None:
                data["is_private"] = is_hidden
            elif entity_type == "note":
                data["is_private"] = True
            else:
                data["is_private"] = False

            if tags:
                tag_ids = self._get_or_create_tag_ids(tags)
                data["tags"] = tag_ids

            # Parent nesting
            if parent_id is not None:
                parent_field = self.PARENT_ID_FIELD_MAP.get(entity_type)
                if parent_field:
                    data[parent_field] = parent_id

            # Quest-specific
            if entity_type == "quest" and is_completed is not None:
                data["is_completed"] = is_completed

            # Image fields (API uses entity_image_uuid / entity_header_uuid)
            if image_uuid is not None:
                data["entity_image_uuid"] = image_uuid
            if header_uuid is not None:
                data["entity_header_uuid"] = header_uuid

            # Calendar: convert structural fields (months/moons) to API format
            _cal_structural = {
                "months",
                "weekdays",
                "weekday",
                "month_name",
                "month_length",
                "month_type",
                "moon_name",
                "moon_fullmoon",
                "moons",
            }
            if entity_type == "calendar":
                structural = self._prepare_calendar_structural_fields(
                    dict(extra_fields), for_create=True
                )
                data.update(structural)
                extra_fields = {
                    k: v for k, v in extra_fields.items() if k not in _cal_structural
                }

            # Entity-specific fields passed via extra_fields
            self._apply_entity_specific_fields(entity_type, data, extra_fields)

            # Use direct API for all entity types to ensure all fields
            # (parent_id, entity-specific fields) are passed through.
            # SDK managers silently drop unknown kwargs.
            endpoint = self.API_ENDPOINT_MAP[entity_type]
            resp = self.client._request("POST", endpoint, json=data)
            raw = resp.get("data", resp) if isinstance(resp, dict) else resp

            eid = raw.get("entity_id")
            result: dict[str, Any] = {
                "id": raw.get("id"),
                "entity_id": eid,
                "name": raw.get("name"),
                "entity_type": entity_type,
                "type": raw.get("type"),
                "mention": f"[entity:{eid}]",
                "is_hidden": data.get("is_private", False),
            }

            return result

        except KankaException as e:
            logger.error(f"Create entity failed: {e}")
            raise

    def update_entity(
        self,
        entity_id: int,
        name: str,
        type: str | None = None,
        entry: str | None = None,
        tags: list[str] | None = None,
        is_hidden: bool | None = None,
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
        parent_id: int | None = None,
        **extra_fields: Any,
    ) -> bool:
        """Update an existing entity with all supported fields."""
        try:
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]
            data: dict[str, Any] = {"name": name}

            if type is not None:
                data["type"] = type
            if entry is not None:
                data["entry"] = self.converter.markdown_to_html(entry)
            if is_hidden is not None:
                data["is_private"] = is_hidden
            if tags is not None:
                tag_ids = self._get_or_create_tag_ids(tags)
                data["tags"] = tag_ids

            # Parent nesting
            if parent_id is not None:
                parent_field = self.PARENT_ID_FIELD_MAP.get(entity_type)
                if parent_field:
                    data[parent_field] = parent_id

            if entity_type == "quest" and is_completed is not None:
                data["is_completed"] = is_completed
            if image_uuid is not None:
                data["entity_image_uuid"] = image_uuid
            if header_uuid is not None:
                data["entity_header_uuid"] = header_uuid

            # Calendar update: use object arrays (months, moons)
            _cal_structural = {
                "months",
                "weekdays",
                "weekday",
                "month_name",
                "month_length",
                "month_type",
                "moon_name",
                "moon_fullmoon",
                "moons",
            }
            if entity_type == "calendar":
                structural = self._prepare_calendar_structural_fields(
                    dict(extra_fields), for_create=False
                )
                data.update(structural)
                extra_fields = {
                    k: v for k, v in extra_fields.items() if k not in _cal_structural
                }

            self._apply_entity_specific_fields(entity_type, data, extra_fields)

            # Use direct API for all entity types to ensure all fields
            # (parent_id, entity-specific fields) are passed through.
            # SDK managers silently drop unknown kwargs.
            endpoint = self.API_ENDPOINT_MAP[entity_type]
            self.client._request("PATCH", f"{endpoint}/{entity_data['id']}", json=data)
            return True

        except Exception as e:
            logger.error(f"Update entity failed for {entity_id}: {e}")
            raise

    def delete_entity(self, entity_id: int) -> bool:
        """Delete an entity."""
        try:
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]

            if entity_type == "item":
                return self._item_delete(entity_data["id"])
            if entity_type == "map":
                return self._map_delete(entity_data["id"])
            if entity_type == "calendar":
                return self._calendar_delete(entity_data["id"])
            if entity_type == "event":
                return self._event_delete(entity_data["id"])
            if entity_type == "timeline":
                return self._timeline_delete(entity_data["id"])

            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])
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
            if entity_type in ("item", "map", "calendar", "event", "timeline"):
                return self._entity_post_create(entity_id, name, entry, is_hidden)

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
        name: str,
        entry: str | None = None,
        is_hidden: bool | None = None,
    ) -> bool:
        """
        Update a post.

        Args:
            entity_id: Entity ID
            post_id: Post ID
            name: Post title (required by API)
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
            if entity_type in ("item", "map", "calendar", "event", "timeline"):
                return self._entity_post_update(
                    entity_id, post_id, name, entry, is_hidden
                )

            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Prepare update data
            kwargs: dict[str, Any] = {"name": name}

            if entry is not None:
                kwargs["entry"] = self.converter.markdown_to_html(entry)

            # Handle visibility
            # For posts, use visibility_id
            visibility_id = None
            if is_hidden is not None:
                visibility_id = 2 if is_hidden else 1

            # Update post - use entity_id, not the type-specific id
            manager.update_post(
                entity_id, post_id, visibility_id=visibility_id, **kwargs
            )
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
            if entity_type in ("item", "map", "calendar", "event", "timeline"):
                return self._entity_post_delete(entity_id, post_id)

            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            # Delete post - use entity_id, not the type-specific id
            manager.delete_post(entity_id, post_id)
            return True

        except Exception as e:
            logger.error(f"Delete post failed: {e}")
            raise

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
            elif hasattr(tag_item, "name"):
                # It's a tag object
                tag_names.append(tag_item.name)
            else:
                # Unknown format, keep as string
                tag_names.append(str(tag_item))

        return tag_names

    @staticmethod
    def _normalize_timestamp(value: Any) -> str | None:
        """Convert datetime or string to ISO string; return None if empty."""
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value) if value else None

    def _entity_to_dict(self, entity: Entity, entity_type: str) -> dict[str, Any]:
        """Convert entity object to dictionary with all type-specific fields."""
        result: dict[str, Any] = {
            "id": entity.id,
            "entity_id": entity.entity_id,
            "name": entity.name,
            "entity_type": entity_type,
            "type": getattr(entity, "type", None),
            "tags": [],
            "created_at": self._normalize_timestamp(
                getattr(entity, "created_at", None)
            ),
            "updated_at": self._normalize_timestamp(
                getattr(entity, "updated_at", None)
            ),
        }

        is_private = getattr(entity, "is_private", None)
        result["is_hidden"] = is_private if is_private is not None else False

        if hasattr(entity, "entry") and entity.entry:
            result["entry"] = self.converter.html_to_markdown(entity.entry)
        else:
            result["entry"] = None

        if hasattr(entity, "tags"):
            result["tags"] = self._resolve_tag_names(entity.tags)

        if hasattr(entity, "posts") and entity.posts is not None:
            result["posts"] = [self._post_to_dict(post) for post in entity.posts]

        # Parent ID extraction
        parent_field = self.PARENT_ID_FIELD_MAP.get(entity_type)
        if parent_field:
            result["parent_id"] = getattr(entity, parent_field, None)

        # Character-specific fields
        if entity_type == "character":
            result["location_id"] = getattr(entity, "location_id", None)
            result["title"] = getattr(entity, "title", None)
            result["age"] = getattr(entity, "age", None)
            result["sex"] = getattr(entity, "sex", None)
            result["pronouns"] = getattr(entity, "pronouns", None)
            result["is_dead"] = getattr(entity, "is_dead", None)
            result["races"] = getattr(entity, "races", None)
            result["families"] = getattr(entity, "families", None)

        # Organisation-specific
        elif entity_type == "organization":
            result["location_id"] = getattr(entity, "location_id", None)
            # is_defunct is not a standard Kanka field; skip for now

        # Journal-specific
        elif entity_type == "journal":
            result["date"] = getattr(entity, "date", None)
            result["character_id"] = getattr(entity, "character_id", None)

        # Quest-specific
        elif entity_type == "quest":
            result["is_completed"] = getattr(entity, "is_completed", None)
            result["character_id"] = getattr(entity, "character_id", None)

        # Family-specific
        elif entity_type == "family":
            result["location_id"] = getattr(entity, "location_id", None)
            result["is_extinct"] = getattr(entity, "is_extinct", None)

        # Tag-specific
        elif entity_type == "tag":
            result["colour"] = getattr(entity, "colour", None)

        # Map-specific
        elif entity_type == "map":
            result["location_id"] = getattr(entity, "location_id", None)
            result["center_marker_id"] = getattr(entity, "center_marker_id", None)
            result["center_x"] = getattr(entity, "center_x", None)
            result["center_y"] = getattr(entity, "center_y", None)
            result["is_real"] = getattr(entity, "is_real", None)

        # Event-specific
        elif entity_type == "event":
            result["location_id"] = getattr(entity, "location_id", None)
            result["date"] = getattr(entity, "date", None)
            result["calendar_id"] = getattr(entity, "calendar_id", None)
            result["calendar_year"] = getattr(entity, "calendar_year", None)
            result["calendar_month"] = getattr(entity, "calendar_month", None)
            result["calendar_day"] = getattr(entity, "calendar_day", None)

        # Calendar-specific
        elif entity_type == "calendar":
            result["date"] = getattr(entity, "date", None)

        # Timeline-specific (eras are in response, no simple attr)
        elif entity_type == "timeline":
            result["eras"] = getattr(entity, "eras", None)

        # Image fields
        result["image"] = getattr(entity, "image", None)
        result["image_full"] = getattr(entity, "image_full", None)
        result["image_thumb"] = getattr(entity, "image_thumb", None)
        result["image_uuid"] = getattr(entity, "image_uuid", None)
        result["header_uuid"] = getattr(entity, "header_uuid", None)

        return result

    def _post_to_dict(self, post: Any) -> dict[str, Any]:
        """Convert post object to dictionary."""
        result: dict[str, Any] = {
            "id": post.id,
            "name": post.name,
        }

        visibility_id = getattr(post, "visibility_id", None)
        result["is_hidden"] = visibility_id == 2 if visibility_id is not None else False

        if hasattr(post, "entry") and post.entry:
            result["entry"] = self.converter.html_to_markdown(post.entry)
        else:
            result["entry"] = None

        return result

    # ---- Entity-specific field helpers ----

    @staticmethod
    def _prepare_calendar_structural_fields(
        extra: dict[str, Any], for_create: bool
    ) -> dict[str, Any]:
        """Convert calendar months/weekdays/moons to API-expected format.

        Kanka API uses different formats for create vs update:
        - Create: flat arrays (month_name, month_length, month_type, weekday,
          moon_name, moon_fullmoon)
        - Update: object arrays (months, weekdays, moons)
        """
        result: dict[str, Any] = {}

        if for_create:
            # ---- CREATE: use flat arrays ----
            weekday = extra.get("weekdays") or extra.get("weekday")
            if isinstance(weekday, list | tuple) and len(weekday) >= 2:
                result["weekday"] = list(weekday)

            months = extra.get("months")
            if isinstance(months, list | tuple) and months:
                # Convert objects -> flat arrays
                mn, ml, mt = [], [], []
                for m in months:
                    if isinstance(m, dict):
                        mn.append(m.get("name", ""))
                        ml.append(m.get("length", 30))
                        mt.append(m.get("type", "standard"))
                if mn:
                    result["month_name"] = mn
                    result["month_length"] = ml
                    result["month_type"] = mt
            elif extra.get("month_name") and extra.get("month_length"):
                result["month_name"] = list(extra["month_name"])
                result["month_length"] = [int(x) for x in extra["month_length"]]
                result["month_type"] = list(
                    extra.get("month_type") or ["standard"] * len(extra["month_name"])
                )
                if len(result["month_type"]) < len(result["month_name"]):
                    result["month_type"].extend(
                        ["standard"]
                        * (len(result["month_name"]) - len(result["month_type"]))
                    )

            moons = extra.get("moons")
            if isinstance(moons, list | tuple) and moons:
                # Convert objects -> flat arrays; fullmoon must be string
                mn, mf = [], []
                for m in moons:
                    if isinstance(m, dict):
                        mn.append(m.get("name", ""))
                        fm = m.get("fullmoon")
                        mf.append(str(fm) if fm is not None else "30")
                if mn:
                    result["moon_name"] = mn
                    result["moon_fullmoon"] = mf
            elif extra.get("moon_name"):
                moon_names = extra["moon_name"]
                mf_vals = extra.get("moon_fullmoon")
                mn_list: list[str] = (
                    [str(moon_names)]
                    if isinstance(moon_names, str)
                    else [str(x) for x in (moon_names or [])]
                )
                if mf_vals is None:
                    mf_list: list[str] = ["30"]
                elif not isinstance(mf_vals, list | tuple):
                    mf_list = [str(mf_vals)]
                else:
                    mf_list = [str(x) for x in mf_vals]
                if len(mf_list) < len(mn_list):
                    mf_list.extend(["30"] * (len(mn_list) - len(mf_list)))
                result["moon_name"] = [str(x) for x in mn_list]
                result["moon_fullmoon"] = mf_list[: len(mn_list)]

        else:
            # ---- UPDATE: use object arrays ----
            weekday = extra.get("weekday") or extra.get("weekdays")
            if isinstance(weekday, list | tuple) and len(weekday) >= 2:
                result["weekdays"] = list(weekday)

            months = extra.get("months")
            if (
                isinstance(months, list | tuple)
                and months
                and isinstance(months[0], dict)
            ):
                result["months"] = list(months)
            elif extra.get("month_name") and extra.get("month_length"):
                months_arr = []
                ml = list(extra["month_length"])
                mt = list(
                    extra.get("month_type") or ["standard"] * len(extra["month_name"])
                )
                for i, name in enumerate(extra["month_name"]):
                    months_arr.append(
                        {
                            "name": str(name),
                            "length": int(ml[i]) if i < len(ml) else 30,
                            "type": str(mt[i]) if i < len(mt) else "standard",
                        }
                    )
                result["months"] = months_arr

            moons = extra.get("moons")
            if (
                isinstance(moons, list | tuple)
                and moons
                and isinstance(moons[0], dict)
            ):
                result["moons"] = list(moons)
            elif extra.get("moon_name"):
                moons_arr = []
                mf_raw = extra.get("moon_fullmoon")
                if mf_raw is None:
                    mf_list = ["30"]
                elif not isinstance(mf_raw, list | tuple):
                    mf_list = [str(mf_raw)]
                else:
                    mf_list = [str(x) for x in mf_raw]
                mn_list = (
                    list(extra["moon_name"])
                    if isinstance(extra["moon_name"], list | tuple)
                    else [str(extra["moon_name"])]
                )
                for i, name in enumerate(mn_list):
                    fm = mf_list[i] if i < len(mf_list) else "30"
                    moons_arr.append(
                        {
                            "name": str(name),
                            "fullmoon": fm,
                            "offset": 0,
                            "colour": "",
                        }
                    )
                result["moons"] = moons_arr

        return result

    @staticmethod
    def _apply_entity_specific_fields(
        entity_type: str, data: dict[str, Any], extra: dict[str, Any]
    ) -> None:
        """Apply entity-type-specific optional fields to the API payload."""
        _FIELDS_BY_TYPE: dict[str, list[str]] = {
            "character": [
                "location_id",
                "title",
                "age",
                "sex",
                "pronouns",
                "is_dead",
                "races",
                "families",
            ],
            "organization": ["location_id", "is_defunct"],
            "journal": ["date"],
            "family": ["location_id", "is_extinct"],
            "item": ["location_id", "creator_id", "price", "size", "weight"],
            "tag": ["colour"],
            "quest": ["location_id"],
            "creature": ["location_id"],
            "map": [
                "location_id",
                "center_marker_id",
                "center_x",
                "center_y",
                "is_real",
            ],
            "event": [
                "location_id",
                "date",
                "calendar_id",
                "calendar_year",
                "calendar_month",
                "calendar_day",
            ],
            "calendar": [
                "date",
                "weekday",
                "month_name",
                "month_length",
                "month_type",
                "moon_name",
                "moon_fullmoon",
                "season_name",
                "season_month",
                "season_day",
                "year_name",
                "year_number",
                "current_year",
                "current_month",
                "current_day",
                "format",
                "has_leap_year",
                "leap_year_amount",
                "leap_year_month",
                "leap_year_offset",
                "leap_year_start",
                "skip_year_zero",
                "suffix",
            ],
        }
        # API field mapping: our internal name -> API name
        _FIELD_ALIASES: dict[str, dict[str, str]] = {
            "journal": {"character_id": "author_id"},  # API uses author_id
            "quest": {"character_id": "instigator_id"},  # API uses instigator_id
        }
        allowed = _FIELDS_BY_TYPE.get(entity_type, [])
        for field in allowed:
            if field in extra and extra[field] is not None:
                data[field] = extra[field]
        # Apply aliased fields (our name -> API name)
        for our_field, api_field in _FIELD_ALIASES.get(entity_type, {}).items():
            if our_field in extra and extra[our_field] is not None:
                data[api_field] = extra[our_field]

    # ---- Item direct-API methods (no SDK manager) ----

    def _item_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a direct API request for items."""
        response = self.client._request(method, endpoint, **kwargs)
        if isinstance(response, dict):
            return response.get("data", response)
        return response

    def _item_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an item via direct API."""
        resp = self._item_request("POST", "items", json=data)
        return self._item_response_to_dict(resp)

    def _item_update(self, item_id: int, data: dict[str, Any]) -> bool:
        """Update an item via direct API."""
        self._item_request("PATCH", f"items/{item_id}", json=data)
        return True

    def _item_delete(self, item_id: int) -> bool:
        """Delete an item via direct API."""
        self._item_request("DELETE", f"items/{item_id}")
        return True

    def _item_list(
        self, name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List items via direct API with optional name filter."""
        params: dict[str, Any] = {"limit": limit}
        if name:
            params["name"] = name
        resp = self.client._request("GET", "items", params=params)
        if isinstance(resp, dict):
            return resp.get("data", [])
        return resp

    def _item_list_entities(
        self,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
        """List items as pseudo-Entity objects for compatibility with list_entities."""
        # Items are returned as dicts; wrap them for _entity_to_dict compatibility
        from types import SimpleNamespace

        params: dict[str, Any] = {"page": page}
        if last_sync:
            params["lastSync"] = last_sync
        if related:
            params["related"] = 1

        if limit == 0:
            all_items: list[Any] = []
            current_page = 1
            while True:
                params["page"] = current_page
                resp = self.client._request("GET", "items", params=params)
                batch = resp.get("data", []) if isinstance(resp, dict) else resp
                all_items.extend(batch)
                meta = resp.get("meta", {}) if isinstance(resp, dict) else {}
                if not batch or current_page >= meta.get("last_page", current_page):
                    break
                current_page += 1
                if current_page > 50:
                    break
            return [SimpleNamespace(**item) for item in all_items]  # type: ignore[misc]
        else:
            resp = self.client._request("GET", "items", params=params)
            batch = resp.get("data", []) if isinstance(resp, dict) else resp
            return [SimpleNamespace(**item) for item in batch[:limit]]  # type: ignore[misc]

    def _item_response_to_dict(
        self, data: dict[str, Any], entity_id: int | None = None
    ) -> dict[str, Any]:
        """Convert an item API response dict to our standard entity dict."""
        result: dict[str, Any] = {
            "id": data.get("id"),
            "entity_id": entity_id or data.get("entity_id"),
            "name": data.get("name"),
            "entity_type": "item",
            "type": data.get("type"),
            "tags": self._resolve_tag_names(data.get("tags", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "is_hidden": data.get("is_private", False),
            "parent_id": data.get("item_id"),
            "location_id": data.get("location_id"),
            "creator_id": data.get("creator_id"),
            "price": data.get("price"),
            "size": data.get("size"),
            "weight": data.get("weight"),
            "image": data.get("image"),
            "image_full": data.get("image_full"),
            "image_thumb": data.get("image_thumb"),
            "image_uuid": data.get("image_uuid"),
            "header_uuid": data.get("header_uuid"),
            "mention": f"[entity:{entity_id or data.get('entity_id')}]",
        }
        html_entry = data.get("entry")
        result["entry"] = (
            self.converter.html_to_markdown(html_entry) if html_entry else None
        )
        return result

    # ---- Map direct-API methods (no SDK manager) ----

    def _map_request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a direct API request for maps."""
        response = self.client._request(method, endpoint, **kwargs)
        if isinstance(response, dict):
            return response.get("data", response)
        return response

    def _map_list(
        self, name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List maps via direct API with optional name filter."""
        params: dict[str, Any] = {"limit": limit}
        if name:
            params["name"] = name
        resp = self.client._request("GET", "maps", params=params)
        if isinstance(resp, dict):
            return resp.get("data", [])
        return resp

    def _map_list_entities(
        self,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
        """List maps as pseudo-Entity objects for compatibility with list_entities."""
        from types import SimpleNamespace

        params: dict[str, Any] = {"page": page}
        if last_sync:
            params["lastSync"] = last_sync
        if related:
            params["related"] = 1

        if limit == 0:
            all_maps: list[Any] = []
            current_page = 1
            while True:
                params["page"] = current_page
                resp = self.client._request("GET", "maps", params=params)
                batch = resp.get("data", []) if isinstance(resp, dict) else resp
                all_maps.extend(batch)
                meta = resp.get("meta", {}) if isinstance(resp, dict) else {}
                if not batch or current_page >= meta.get("last_page", current_page):
                    break
                current_page += 1
                if current_page > 50:
                    break
            return [SimpleNamespace(**m) for m in all_maps]  # type: ignore[misc]
        resp = self.client._request("GET", "maps", params=params)
        batch = resp.get("data", []) if isinstance(resp, dict) else resp
        return [SimpleNamespace(**m) for m in batch[:limit]]  # type: ignore[misc]

    def _map_response_to_dict(
        self, data: dict[str, Any], entity_id: int | None = None
    ) -> dict[str, Any]:
        """Convert a map API response dict to our standard entity dict."""
        result: dict[str, Any] = {
            "id": data.get("id"),
            "entity_id": entity_id or data.get("entity_id"),
            "name": data.get("name"),
            "entity_type": "map",
            "type": data.get("type"),
            "tags": self._resolve_tag_names(data.get("tags", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "is_hidden": data.get("is_private", False),
            "parent_id": data.get("map_id"),
            "location_id": data.get("location_id"),
            "center_marker_id": data.get("center_marker_id"),
            "center_x": data.get("center_x"),
            "center_y": data.get("center_y"),
            "is_real": data.get("is_real"),
            "image": data.get("image"),
            "image_full": data.get("image_full"),
            "image_thumb": data.get("image_thumb"),
            "image_uuid": data.get("image_uuid"),
            "header_uuid": data.get("header_uuid"),
            "mention": f"[entity:{entity_id or data.get('entity_id')}]",
        }
        html_entry = data.get("entry")
        result["entry"] = (
            self.converter.html_to_markdown(html_entry) if html_entry else None
        )
        return result

    def _map_delete(self, map_id: int) -> bool:
        """Delete a map via direct API."""
        self.client._request("DELETE", f"maps/{map_id}")
        return True

    # ---- Calendar direct-API methods ----

    def _calendar_list(
        self, name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List calendars via direct API."""
        params: dict[str, Any] = {"limit": limit}
        if name:
            params["name"] = name
        resp = self.client._request("GET", "calendars", params=params)
        if isinstance(resp, dict):
            return resp.get("data", [])
        return resp

    def _calendar_list_entities(
        self,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
        """List calendars as pseudo-Entity objects."""
        from types import SimpleNamespace

        params: dict[str, Any] = {"page": page}
        if last_sync:
            params["lastSync"] = last_sync
        if related:
            params["related"] = 1

        if limit == 0:
            all_data: list[Any] = []
            current_page = 1
            while True:
                params["page"] = current_page
                resp = self.client._request("GET", "calendars", params=params)
                batch = resp.get("data", []) if isinstance(resp, dict) else resp
                all_data.extend(batch)
                meta = resp.get("meta", {}) if isinstance(resp, dict) else {}
                if not batch or current_page >= meta.get("last_page", current_page):
                    break
                current_page += 1
                if current_page > 50:
                    break
            return [SimpleNamespace(**d) for d in all_data]  # type: ignore[misc]
        resp = self.client._request("GET", "calendars", params=params)
        batch = resp.get("data", []) if isinstance(resp, dict) else resp
        return [SimpleNamespace(**d) for d in batch[:limit]]  # type: ignore[misc]

    def _calendar_response_to_dict(
        self, data: dict[str, Any], entity_id: int | None = None
    ) -> dict[str, Any]:
        """Convert calendar API response to our entity dict."""
        result: dict[str, Any] = {
            "id": data.get("id"),
            "entity_id": entity_id or data.get("entity_id"),
            "name": data.get("name"),
            "entity_type": "calendar",
            "type": data.get("type"),
            "tags": self._resolve_tag_names(data.get("tags", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "is_hidden": data.get("is_private", False),
            "date": data.get("date"),
            "months": data.get("months"),
            "weekdays": data.get("weekdays"),
            "moons": data.get("moons"),
            "seasons": data.get("seasons"),
            "years": data.get("years"),
            "format": data.get("format"),
            "has_leap_year": data.get("has_leap_year"),
            "mention": f"[entity:{entity_id or data.get('entity_id')}]",
        }
        html_entry = data.get("entry")
        result["entry"] = (
            self.converter.html_to_markdown(html_entry) if html_entry else None
        )
        return result

    def _calendar_delete(self, calendar_id: int) -> bool:
        """Delete a calendar via direct API."""
        self.client._request("DELETE", f"calendars/{calendar_id}")
        return True

    def _get_calendar_type_id(self, calendar_entity_id: int) -> int:
        """Resolve calendar entity_id to type-specific id for API URLs."""
        entity_data = self.get_entity_by_id(calendar_entity_id)
        if not entity_data or entity_data["entity_type"] != "calendar":
            raise ValueError(f"Entity {calendar_entity_id} is not a calendar")
        return entity_data["id"]

    def list_calendar_reminders(self, calendar_id: int) -> list[dict[str, Any]]:
        """List reminders (events) on a calendar. calendar_id is entity_id."""
        type_id = self._get_calendar_type_id(calendar_id)
        resp = self.client._request("GET", f"calendars/{type_id}/reminders")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._calendar_reminder_to_dict(r) for r in items]

    def create_calendar_reminder(
        self,
        entity_id: int,
        calendar_id: int,
        year: int,
        month: int,
        day: int,
        length: int = 1,
        name: str | None = None,
        comment: str | None = None,
        colour: str | None = None,
        is_recurring: bool | None = None,
        recurring_periodicity: str | None = None,
        recurring_until: int | None = None,
        is_hidden: bool | None = None,
    ) -> dict[str, Any]:
        """Add an entity to a calendar date (creates reminder)."""
        data: dict[str, Any] = {
            "calendar_id": self._get_calendar_type_id(calendar_id),
            "year": year,
            "month": month,
            "day": day,
            "length": length,
        }
        if name:
            data["name"] = name
        if comment:
            data["comment"] = comment
        if colour:
            data["colour"] = colour
        if is_recurring is not None:
            data["is_recurring"] = is_recurring
        if recurring_periodicity:
            data["recurring_periodicity"] = recurring_periodicity
        if recurring_until is not None:
            data["recurring_until"] = recurring_until
        if is_hidden is not None:
            data["visibility_id"] = 2 if is_hidden else 1
        resp = self.client._request(
            "POST", f"entities/{entity_id}/entity_events", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._calendar_reminder_to_dict(raw)

    def update_calendar_reminder(
        self, entity_id: int, reminder_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a calendar reminder."""
        data: dict[str, Any] = {}
        for k, v in fields.items():
            if v is not None:
                if k == "is_hidden":
                    data["visibility_id"] = 2 if v else 1
                else:
                    data[k] = v
        resp = self.client._request(
            "PATCH",
            f"entities/{entity_id}/entity_events/{reminder_id}",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._calendar_reminder_to_dict(raw)

    def delete_calendar_reminder(self, entity_id: int, reminder_id: int) -> bool:
        """Remove a reminder from a calendar."""
        self.client._request(
            "DELETE", f"entities/{entity_id}/entity_events/{reminder_id}"
        )
        return True

    def _calendar_reminder_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert reminder/entity_event to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        return {
            "id": data.get("id"),
            "entity_id": data.get("entity_id") or data.get("remindable_id"),
            "calendar_id": data.get("calendar_id"),
            "date": data.get("date"),
            "year": data.get("year"),
            "month": data.get("month"),
            "day": data.get("day"),
            "length": data.get("length", 1),
            "comment": data.get("comment"),
            "colour": data.get("colour"),
            "is_recurring": data.get("is_recurring", False),
            "recurring_periodicity": data.get("recurring_periodicity"),
            "recurring_until": data.get("recurring_until"),
            "is_hidden": vis in (2, 3) if vis is not None else False,
        }

    # ---- Event direct-API methods ----

    def _event_list(
        self, name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List events via direct API."""
        params: dict[str, Any] = {"limit": limit}
        if name:
            params["name"] = name
        resp = self.client._request("GET", "events", params=params)
        if isinstance(resp, dict):
            return resp.get("data", [])
        return resp

    def _event_list_entities(
        self,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
        """List events as pseudo-Entity objects."""
        from types import SimpleNamespace

        params: dict[str, Any] = {"page": page}
        if last_sync:
            params["lastSync"] = last_sync
        if related:
            params["related"] = 1

        if limit == 0:
            all_data = []
            current_page = 1
            while True:
                params["page"] = current_page
                resp = self.client._request("GET", "events", params=params)
                batch = resp.get("data", []) if isinstance(resp, dict) else resp
                all_data.extend(batch)
                meta = resp.get("meta", {}) if isinstance(resp, dict) else {}
                if not batch or current_page >= meta.get("last_page", current_page):
                    break
                current_page += 1
                if current_page > 50:
                    break
            return [SimpleNamespace(**d) for d in all_data]  # type: ignore[misc]
        resp = self.client._request("GET", "events", params=params)
        batch = resp.get("data", []) if isinstance(resp, dict) else resp
        return [SimpleNamespace(**d) for d in batch[:limit]]  # type: ignore[misc]

    def _event_response_to_dict(
        self, data: dict[str, Any], entity_id: int | None = None
    ) -> dict[str, Any]:
        """Convert event API response to our entity dict."""
        result: dict[str, Any] = {
            "id": data.get("id"),
            "entity_id": entity_id or data.get("entity_id"),
            "name": data.get("name"),
            "entity_type": "event",
            "type": data.get("type"),
            "tags": self._resolve_tag_names(data.get("tags", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "is_hidden": data.get("is_private", False),
            "date": data.get("date"),
            "location_id": data.get("location_id"),
            "calendar_id": data.get("calendar_id"),
            "calendar_year": data.get("calendar_year"),
            "calendar_month": data.get("calendar_month"),
            "calendar_day": data.get("calendar_day"),
            "image": data.get("image"),
            "image_full": data.get("image_full"),
            "image_thumb": data.get("image_thumb"),
            "image_uuid": data.get("image_uuid"),
            "header_uuid": data.get("header_uuid"),
            "mention": f"[entity:{entity_id or data.get('entity_id')}]",
        }
        html_entry = data.get("entry")
        result["entry"] = (
            self.converter.html_to_markdown(html_entry) if html_entry else None
        )
        return result

    def _event_delete(self, event_id: int) -> bool:
        """Delete an event via direct API."""
        self.client._request("DELETE", f"events/{event_id}")
        return True

    # ---- Timeline direct-API methods ----

    def _timeline_list(
        self, name: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List timelines via direct API."""
        params: dict[str, Any] = {"limit": limit}
        if name:
            params["name"] = name
        resp = self.client._request("GET", "timelines", params=params)
        if isinstance(resp, dict):
            return resp.get("data", [])
        return resp

    def _timeline_list_entities(
        self,
        page: int = 1,
        limit: int = 100,
        last_sync: str | None = None,
        related: bool = False,
    ) -> list[Entity]:
        """List timelines as pseudo-Entity objects."""
        from types import SimpleNamespace

        params: dict[str, Any] = {"page": page}
        if last_sync:
            params["lastSync"] = last_sync
        if related:
            params["related"] = 1

        if limit == 0:
            all_data = []
            current_page = 1
            while True:
                params["page"] = current_page
                resp = self.client._request("GET", "timelines", params=params)
                batch = resp.get("data", []) if isinstance(resp, dict) else resp
                all_data.extend(batch)
                meta = resp.get("meta", {}) if isinstance(resp, dict) else {}
                if not batch or current_page >= meta.get("last_page", current_page):
                    break
                current_page += 1
                if current_page > 50:
                    break
            return [SimpleNamespace(**d) for d in all_data]  # type: ignore[misc]
        resp = self.client._request("GET", "timelines", params=params)
        batch = resp.get("data", []) if isinstance(resp, dict) else resp
        return [SimpleNamespace(**d) for d in batch[:limit]]  # type: ignore[misc]

    def _timeline_response_to_dict(
        self, data: dict[str, Any], entity_id: int | None = None
    ) -> dict[str, Any]:
        """Convert timeline API response to our entity dict."""
        result: dict[str, Any] = {
            "id": data.get("id"),
            "entity_id": entity_id or data.get("entity_id"),
            "name": data.get("name"),
            "entity_type": "timeline",
            "type": data.get("type"),
            "tags": self._resolve_tag_names(data.get("tags", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "is_hidden": data.get("is_private", False),
            "eras": data.get("eras", []),
            "image": data.get("image"),
            "image_full": data.get("image_full"),
            "image_thumb": data.get("image_thumb"),
            "image_uuid": data.get("image_uuid"),
            "header_uuid": data.get("header_uuid"),
            "mention": f"[entity:{entity_id or data.get('entity_id')}]",
        }
        html_entry = data.get("entry")
        result["entry"] = (
            self.converter.html_to_markdown(html_entry) if html_entry else None
        )
        return result

    def _timeline_delete(self, timeline_id: int) -> bool:
        """Delete a timeline via direct API."""
        self.client._request("DELETE", f"timelines/{timeline_id}")
        return True

    # ---- Entity posts (direct API for item/map) ----

    def _entity_posts_list(
        self, entity_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List posts for an entity via direct API (used for item/map)."""
        resp = self.client._request(
            "GET", f"entities/{entity_id}/posts", params={"limit": limit}
        )
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._post_data_to_dict(p) for p in items]

    def _post_data_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert post API response (dict) to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        result: dict[str, Any] = {
            "id": data.get("id"),
            "name": data.get("name"),
            "is_hidden": vis == 2 if vis is not None else False,
        }
        if data.get("entry"):
            result["entry"] = self.converter.html_to_markdown(data["entry"])
        else:
            result["entry"] = None
        return result

    def _entity_post_create(
        self,
        entity_id: int,
        name: str,
        entry: str | None,
        is_hidden: bool,
    ) -> dict[str, Any]:
        """Create a post via direct API (used for item/map)."""
        data: dict[str, Any] = {"name": name}
        if entry:
            data["entry"] = self.converter.markdown_to_html(entry)
        data["visibility_id"] = 2 if is_hidden else 1
        resp = self.client._request("POST", f"entities/{entity_id}/posts", json=data)
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return {"post_id": raw.get("id"), "entity_id": entity_id}

    def _entity_post_update(
        self,
        entity_id: int,
        post_id: int,
        name: str,
        entry: str | None,
        is_hidden: bool | None,
    ) -> bool:
        """Update a post via direct API (used for item/map)."""
        data: dict[str, Any] = {"name": name}
        if entry is not None:
            data["entry"] = self.converter.markdown_to_html(entry)
        if is_hidden is not None:
            data["visibility_id"] = 2 if is_hidden else 1
        self.client._request(
            "PATCH", f"entities/{entity_id}/posts/{post_id}", json=data
        )
        return True

    def _entity_post_delete(self, entity_id: int, post_id: int) -> bool:
        """Delete a post via direct API (used for item/map)."""
        self.client._request("DELETE", f"entities/{entity_id}/posts/{post_id}")
        return True

    # ---- Sub-resource: Relations ----

    def list_relations(self, entity_id: int) -> list[dict[str, Any]]:
        """List all relations for an entity."""
        resp = self.client._request("GET", f"entities/{entity_id}/relations")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._relation_to_dict(r) for r in items]

    def create_relation(
        self,
        entity_id: int,
        target_id: int,
        relation: str,
        attitude: int | None = None,
        two_way: bool | None = None,
        colour: str | None = None,
        is_pinned: bool | None = None,
        is_hidden: bool | None = None,
    ) -> dict[str, Any]:
        """Create a relation on an entity."""
        data: dict[str, Any] = {
            "owner_id": entity_id,
            "target_id": target_id,
            "relation": relation,
        }
        if attitude is not None:
            data["attitude"] = attitude
        if two_way is not None:
            data["two_way"] = two_way
        if colour is not None:
            data["colour"] = colour
        if is_pinned is not None:
            data["is_pinned"] = is_pinned
        if is_hidden is not None:
            # Relations use visibility_id: 1=all, 3=admin
            data["visibility_id"] = 3 if is_hidden else 1

        resp = self.client._request(
            "POST", f"entities/{entity_id}/relations", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._relation_to_dict(raw)

    def update_relation(
        self,
        entity_id: int,
        relation_id: int,
        **fields: Any,
    ) -> dict[str, Any]:
        """Update a relation."""
        data: dict[str, Any] = {}
        for key in ("relation", "target_id", "attitude", "colour", "is_pinned"):
            if key in fields and fields[key] is not None:
                data[key] = fields[key]
        if "two_way" in fields and fields["two_way"] is not None:
            data["two_way"] = fields["two_way"]
        if "is_hidden" in fields and fields["is_hidden"] is not None:
            data["visibility_id"] = 3 if fields["is_hidden"] else 1

        resp = self.client._request(
            "PATCH", f"entities/{entity_id}/relations/{relation_id}", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._relation_to_dict(raw)

    def delete_relation(self, entity_id: int, relation_id: int) -> bool:
        """Delete a relation."""
        self.client._request("DELETE", f"entities/{entity_id}/relations/{relation_id}")
        return True

    def _relation_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert a relation API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        return {
            "id": data.get("id"),
            "owner_id": data.get("owner_id"),
            "target_id": data.get("target_id"),
            "relation": data.get("relation"),
            "attitude": data.get("attitude"),
            "is_pinned": data.get("is_pinned", False),
            "is_hidden": vis in (2, 3) if vis is not None else False,
            "colour": data.get("colour"),
        }

    # ---- Sub-resource: Attributes ----

    def list_attributes(self, entity_id: int) -> list[dict[str, Any]]:
        """List all attributes for an entity."""
        resp = self.client._request("GET", f"entities/{entity_id}/attributes")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._attribute_to_dict(a) for a in items]

    def create_attribute(
        self,
        entity_id: int,
        name: str,
        value: str | None = None,
        type_id: int | None = None,
        is_pinned: bool | None = None,
        is_hidden: bool | None = None,
        api_key: str | None = None,
        default_order: int | None = None,
    ) -> dict[str, Any]:
        """Create an attribute on an entity."""
        data: dict[str, Any] = {"name": name}
        if value is not None:
            data["value"] = value
        if type_id is not None:
            data["type_id"] = type_id
        if is_pinned is not None:
            data["is_pinned"] = is_pinned
        if is_hidden is not None:
            data["is_private"] = is_hidden
        if api_key is not None:
            data["api_key"] = api_key
        if default_order is not None:
            data["default_order"] = default_order

        resp = self.client._request(
            "POST", f"entities/{entity_id}/attributes", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._attribute_to_dict(raw)

    def update_attribute(
        self,
        entity_id: int,
        attribute_id: int,
        **fields: Any,
    ) -> dict[str, Any]:
        """Update an attribute."""
        data: dict[str, Any] = {}
        for key in ("name", "value", "type_id", "api_key", "default_order"):
            if key in fields and fields[key] is not None:
                data[key] = fields[key]
        if "is_pinned" in fields and fields["is_pinned"] is not None:
            data["is_pinned"] = fields["is_pinned"]
        if "is_hidden" in fields and fields["is_hidden"] is not None:
            data["is_private"] = fields["is_hidden"]

        resp = self.client._request(
            "PATCH",
            f"entities/{entity_id}/attributes/{attribute_id}",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._attribute_to_dict(raw)

    def delete_attribute(self, entity_id: int, attribute_id: int) -> bool:
        """Delete an attribute."""
        self.client._request(
            "DELETE", f"entities/{entity_id}/attributes/{attribute_id}"
        )
        return True

    def bulk_patch_attributes(
        self, entity_id: int, attributes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Bulk patch attributes (add/update without deleting others)."""
        # Convert is_hidden -> is_private in each attribute
        api_attrs = []
        for attr in attributes:
            a = dict(attr)
            if "is_hidden" in a:
                a["is_private"] = a.pop("is_hidden")
            api_attrs.append(a)

        resp = self.client._request(
            "PATCH",
            f"entities/{entity_id}/attributes",
            json={"attribute": api_attrs},
        )
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._attribute_to_dict(a) for a in items]

    def _attribute_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert an attribute API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        return {
            "id": data.get("id"),
            "entity_id": data.get("entity_id"),
            "name": data.get("name"),
            "value": data.get("value"),
            "type_id": data.get("type_id", 1),
            "is_pinned": data.get("is_pinned", False),
            "is_hidden": data.get("is_private", False),
            "api_key": data.get("api_key"),
            "default_order": data.get("default_order", 0),
            "parsed": data.get("parsed"),
        }

    # ---- Sub-resource: Organisation Members ----

    def list_org_members(self, organisation_id: int) -> list[dict[str, Any]]:
        """List members of an organisation. organisation_id is the type-specific ID."""
        entity_data = self.get_entity_by_id(organisation_id)
        if not entity_data or entity_data["entity_type"] != "organization":
            raise ValueError(f"Entity {organisation_id} is not an organisation")
        org_type_id = entity_data["id"]
        resp = self.client._request(
            "GET", f"organisations/{org_type_id}/organisation_members"
        )
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._org_member_to_dict(m) for m in items]

    def create_org_member(
        self,
        organisation_id: int,
        character_id: int,
        role: str | None = None,
        is_hidden: bool | None = None,
        status_id: int | None = None,
        parent_id: int | None = None,
        pin_id: int | None = None,
    ) -> dict[str, Any]:
        """Add a member to an organisation. organisation_id is entity_id."""
        entity_data = self.get_entity_by_id(organisation_id)
        if not entity_data or entity_data["entity_type"] != "organization":
            raise ValueError(f"Entity {organisation_id} is not an organisation")
        org_type_id = entity_data["id"]

        data: dict[str, Any] = {
            "organisation_id": org_type_id,
            "character_id": character_id,
        }
        if role is not None:
            data["role"] = role
        if is_hidden is not None:
            data["is_private"] = is_hidden
        if status_id is not None:
            data["status_id"] = status_id
        if parent_id is not None:
            data["parent_id"] = parent_id
        if pin_id is not None:
            data["pin_id"] = pin_id

        resp = self.client._request(
            "POST",
            f"organisations/{org_type_id}/organisation_members",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._org_member_to_dict(raw)

    def update_org_member(
        self,
        organisation_id: int,
        member_id: int,
        **fields: Any,
    ) -> dict[str, Any]:
        """Update an organisation member."""
        entity_data = self.get_entity_by_id(organisation_id)
        if not entity_data or entity_data["entity_type"] != "organization":
            raise ValueError(f"Entity {organisation_id} is not an organisation")
        org_type_id = entity_data["id"]

        data: dict[str, Any] = {}
        for key in ("character_id", "role", "status_id", "parent_id", "pin_id"):
            if key in fields and fields[key] is not None:
                data[key] = fields[key]
        if "is_hidden" in fields and fields["is_hidden"] is not None:
            data["is_private"] = fields["is_hidden"]

        resp = self.client._request(
            "PATCH",
            f"organisations/{org_type_id}/organisation_members/{member_id}",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._org_member_to_dict(raw)

    def delete_org_member(self, organisation_id: int, member_id: int) -> bool:
        """Remove a member from an organisation."""
        entity_data = self.get_entity_by_id(organisation_id)
        if not entity_data or entity_data["entity_type"] != "organization":
            raise ValueError(f"Entity {organisation_id} is not an organisation")
        org_type_id = entity_data["id"]

        self.client._request(
            "DELETE",
            f"organisations/{org_type_id}/organisation_members/{member_id}",
        )
        return True

    def _org_member_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert an org member API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        return {
            "id": data.get("id"),
            "character_id": data.get("character_id"),
            "organisation_id": data.get("organisation_id"),
            "role": data.get("role"),
            "is_hidden": data.get("is_private", False),
            "status_id": data.get("status_id"),
            "pin_id": data.get("pin_id"),
            "parent_id": data.get("parent_id"),
        }

    # ---- Sub-resource: Map Markers ----

    def _get_map_type_id(self, map_entity_id: int) -> int:
        """Resolve map entity_id to type-specific map id for API URLs."""
        entity_data = self.get_entity_by_id(map_entity_id)
        if not entity_data or entity_data["entity_type"] != "map":
            raise ValueError(f"Entity {map_entity_id} is not a map")
        return entity_data["id"]

    def list_map_markers(self, map_id: int) -> list[dict[str, Any]]:
        """List all map markers. map_id is the map's entity_id."""
        type_id = self._get_map_type_id(map_id)
        resp = self.client._request("GET", f"maps/{type_id}/map_markers")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._map_marker_to_dict(m) for m in items]

    def create_map_marker(
        self,
        map_id: int,
        name: str | None = None,
        entity_id: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        shape_id: int | None = None,
        icon: str | int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a map marker. Requires name or entity_id, and latitude/longitude."""
        type_id = self._get_map_type_id(map_id)
        data: dict[str, Any] = {"map_id": type_id}
        if name is not None:
            data["name"] = name
        if entity_id is not None:
            data["entity_id"] = entity_id
        if latitude is not None:
            data["latitude"] = latitude
        if longitude is not None:
            data["longitude"] = longitude
        if shape_id is not None:
            data["shape_id"] = shape_id
        if icon is not None:
            data["icon"] = str(icon) if isinstance(icon, int) else icon
        for k, v in kwargs.items():
            if v is not None:
                data[k] = v
        resp = self.client._request("POST", f"maps/{type_id}/map_markers", json=data)
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_marker_to_dict(raw)

    def update_map_marker(
        self, map_id: int, marker_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a map marker."""
        type_id = self._get_map_type_id(map_id)
        data = {k: v for k, v in fields.items() if v is not None}
        if "is_hidden" in data:
            data["visibility_id"] = 2 if data.pop("is_hidden") else 1
        resp = self.client._request(
            "PATCH", f"maps/{type_id}/map_markers/{marker_id}", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_marker_to_dict(raw)

    def delete_map_marker(self, map_id: int, marker_id: int) -> bool:
        """Delete a map marker."""
        type_id = self._get_map_type_id(map_id)
        self.client._request("DELETE", f"maps/{type_id}/map_markers/{marker_id}")
        return True

    def _map_marker_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert map marker API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        return {
            "id": data.get("id"),
            "map_id": data.get("map_id"),
            "name": data.get("name"),
            "entity_id": data.get("entity_id"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "shape_id": data.get("shape_id"),
            "icon": data.get("icon"),
            "group_id": data.get("group_id"),
            "is_hidden": vis in (2, 3) if vis is not None else False,
        }

    # ---- Sub-resource: Map Groups ----

    def list_map_groups(self, map_id: int) -> list[dict[str, Any]]:
        """List all map groups. map_id is the map's entity_id."""
        type_id = self._get_map_type_id(map_id)
        resp = self.client._request("GET", f"maps/{type_id}/map_groups")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._map_group_to_dict(g) for g in items]

    def create_map_group(
        self,
        map_id: int,
        name: str,
        parent_id: int | None = None,
        is_shown: bool | None = None,
        position: int | None = None,
        is_hidden: bool | None = None,
    ) -> dict[str, Any]:
        """Create a map group."""
        type_id = self._get_map_type_id(map_id)
        data: dict[str, Any] = {"map_id": type_id, "name": name}
        if parent_id is not None:
            data["parent_id"] = parent_id
        if is_shown is not None:
            data["is_shown"] = is_shown
        if position is not None:
            data["position"] = position
        if is_hidden is not None:
            data["visibility_id"] = 2 if is_hidden else 1
        resp = self.client._request("POST", f"maps/{type_id}/map-groups", json=data)
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_group_to_dict(raw)

    def update_map_group(
        self, map_id: int, group_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a map group."""
        type_id = self._get_map_type_id(map_id)
        data = {k: v for k, v in fields.items() if v is not None}
        if "is_hidden" in data:
            data["visibility_id"] = 2 if data.pop("is_hidden") else 1
        resp = self.client._request(
            "PATCH", f"maps/{type_id}/map-groups/{group_id}", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_group_to_dict(raw)

    def delete_map_group(self, map_id: int, group_id: int) -> bool:
        """Delete a map group."""
        type_id = self._get_map_type_id(map_id)
        self.client._request("DELETE", f"maps/{type_id}/map-groups/{group_id}")
        return True

    def _map_group_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert map group API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        return {
            "id": data.get("id"),
            "map_id": data.get("map_id"),
            "name": data.get("name"),
            "parent_id": data.get("parent_id"),
            "is_shown": data.get("is_shown", True),
            "position": data.get("position"),
            "is_hidden": vis in (2, 3) if vis is not None else False,
        }

    # ---- Sub-resource: Map Layers ----

    def list_map_layers(self, map_id: int) -> list[dict[str, Any]]:
        """List all map layers. map_id is the map's entity_id."""
        type_id = self._get_map_type_id(map_id)
        resp = self.client._request("GET", f"maps/{type_id}/map_layers")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._map_layer_to_dict(layer) for layer in items]

    def create_map_layer(
        self,
        map_id: int,
        name: str,
        image_url: str | None = None,
        entry: str | None = None,
        type_id: int | None = None,
        position: int | None = None,
        is_hidden: bool | None = None,
    ) -> dict[str, Any]:
        """Create a map layer."""
        type_id_map = self._get_map_type_id(map_id)
        data: dict[str, Any] = {"map_id": type_id_map, "name": name}
        if image_url:
            data["image_url"] = image_url
        if entry:
            data["entry"] = self.converter.markdown_to_html(entry)
        if type_id is not None:
            data["type_id"] = type_id
        if position is not None:
            data["position"] = position
        if is_hidden is not None:
            data["visibility_id"] = 2 if is_hidden else 1
        resp = self.client._request("POST", f"maps/{type_id_map}/map-layers", json=data)
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_layer_to_dict(raw)

    def update_map_layer(
        self, map_id: int, layer_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a map layer."""
        type_id = self._get_map_type_id(map_id)
        data = {k: v for k, v in fields.items() if v is not None}
        if "entry" in data:
            data["entry"] = self.converter.markdown_to_html(str(data["entry"]))
        if "is_hidden" in data:
            data["visibility_id"] = 2 if data.pop("is_hidden") else 1
        resp = self.client._request(
            "PATCH", f"maps/{type_id}/map-layers/{layer_id}", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._map_layer_to_dict(raw)

    def delete_map_layer(self, map_id: int, layer_id: int) -> bool:
        """Delete a map layer."""
        type_id = self._get_map_type_id(map_id)
        self.client._request("DELETE", f"maps/{type_id}/map-layers/{layer_id}")
        return True

    def _map_layer_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert map layer API response to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id")
        return {
            "id": data.get("id"),
            "map_id": data.get("map_id"),
            "name": data.get("name"),
            "image_url": data.get("image_url"),
            "entry": data.get("entry"),
            "type_id": data.get("type_id"),
            "position": data.get("position"),
            "is_hidden": vis in (2, 3) if vis is not None else False,
        }

    # ---- Sub-resource: Timeline Eras ----

    def _get_timeline_type_id(self, timeline_entity_id: int) -> int:
        """Resolve timeline entity_id to type-specific id for API URLs."""
        entity_data = self.get_entity_by_id(timeline_entity_id)
        if not entity_data or entity_data["entity_type"] != "timeline":
            raise ValueError(f"Entity {timeline_entity_id} is not a timeline")
        return entity_data["id"]

    def list_timeline_eras(self, timeline_id: int) -> list[dict[str, Any]]:
        """List timeline eras. timeline_id is the timeline's entity_id."""
        type_id = self._get_timeline_type_id(timeline_id)
        resp = self.client._request("GET", f"timelines/{type_id}/timeline_eras")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._timeline_era_to_dict(e) for e in items]

    def create_timeline_era(
        self,
        timeline_id: int,
        name: str,
        abbreviation: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        visibility: str | None = None,
    ) -> dict[str, Any]:
        """Create a timeline era. API uses 'era' for name."""
        type_id = self._get_timeline_type_id(timeline_id)
        data: dict[str, Any] = {"era": name}
        if abbreviation is not None:
            data["abbreviation"] = abbreviation
        if start_year is not None:
            data["start_year"] = start_year
        if end_year is not None:
            data["end_year"] = end_year
        if visibility is not None:
            data["visiblity"] = visibility  # API typo
        resp = self.client._request(
            "POST", f"timelines/{type_id}/timeline_eras", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._timeline_era_to_dict(raw)

    def update_timeline_era(
        self, timeline_id: int, era_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a timeline era."""
        type_id = self._get_timeline_type_id(timeline_id)
        data = {}
        if "name" in fields and fields["name"] is not None:
            data["era"] = fields["name"]
        for k in ("abbreviation", "start_year", "end_year", "visibility"):
            if k in fields and fields[k] is not None:
                data["visiblity" if k == "visibility" else k] = fields[k]
        resp = self.client._request(
            "PATCH",
            f"timelines/{type_id}/timeline_eras/{era_id}",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._timeline_era_to_dict(raw)

    def delete_timeline_era(self, timeline_id: int, era_id: int) -> bool:
        """Delete a timeline era."""
        type_id = self._get_timeline_type_id(timeline_id)
        self.client._request("DELETE", f"timelines/{type_id}/timeline_eras/{era_id}")
        return True

    def _timeline_era_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert timeline era to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        return {
            "id": data.get("id"),
            "timeline_id": data.get("timeline_id"),
            "name": data.get("name") or data.get("era"),
            "abbreviation": data.get("abbreviation"),
            "start_year": data.get("start_year"),
            "end_year": data.get("end_year"),
            "position": data.get("position"),
        }

    # ---- Sub-resource: Timeline Elements ----

    def list_timeline_elements(self, timeline_id: int) -> list[dict[str, Any]]:
        """List timeline elements. timeline_id is the timeline's entity_id."""
        type_id = self._get_timeline_type_id(timeline_id)
        resp = self.client._request("GET", f"timelines/{type_id}/timeline_elements")
        items = resp.get("data", []) if isinstance(resp, dict) else resp
        return [self._timeline_element_to_dict(el) for el in items]

    def create_timeline_element(
        self,
        timeline_id: int,
        era_id: int,
        name: str | None = None,
        entity_id: int | None = None,
        entry: str | None = None,
        date: str | None = None,
        colour: str | None = None,
        position: int | None = None,
        is_hidden: bool | None = None,
    ) -> dict[str, Any]:
        """Create a timeline element. Requires name or entity_id."""
        type_id = self._get_timeline_type_id(timeline_id)
        data: dict[str, Any] = {"era_id": era_id}
        if name is not None:
            data["name"] = name
        if entity_id is not None:
            data["entity_id"] = entity_id
        if entry:
            data["entry"] = self.converter.markdown_to_html(entry)
        if date is not None:
            data["date"] = date
        if colour is not None:
            data["colour"] = colour
        if position is not None:
            data["position"] = position
        if is_hidden is not None:
            data["visibility_id"] = 2 if is_hidden else 1
        resp = self.client._request(
            "POST", f"timelines/{type_id}/timeline_elements", json=data
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._timeline_element_to_dict(raw)

    def update_timeline_element(
        self, timeline_id: int, element_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Update a timeline element."""
        type_id = self._get_timeline_type_id(timeline_id)
        data: dict[str, Any] = {}
        for k, v in fields.items():
            if v is not None:
                if k == "entry":
                    data[k] = self.converter.markdown_to_html(str(v))
                elif k == "is_hidden":
                    data["visibility_id"] = 2 if v else 1
                else:
                    data[k] = v
        resp = self.client._request(
            "PATCH",
            f"timelines/{type_id}/timeline_elements/{element_id}",
            json=data,
        )
        raw = resp.get("data", resp) if isinstance(resp, dict) else resp
        return self._timeline_element_to_dict(raw)

    def delete_timeline_element(self, timeline_id: int, element_id: int) -> bool:
        """Delete a timeline element."""
        type_id = self._get_timeline_type_id(timeline_id)
        self.client._request(
            "DELETE",
            f"timelines/{type_id}/timeline_elements/{element_id}",
        )
        return True

    def _timeline_element_to_dict(self, data: dict[str, Any] | Any) -> dict[str, Any]:
        """Convert timeline element to our format."""
        if not isinstance(data, dict):
            data = vars(data) if hasattr(data, "__dict__") else {"id": data}
        vis = data.get("visibility_id") or data.get("visibilility_id")
        return {
            "id": data.get("id"),
            "timeline_id": data.get("timeline_id"),
            "era_id": data.get("era_id"),
            "name": data.get("name"),
            "entity_id": data.get("entity_id"),
            "entry": data.get("entry"),
            "date": data.get("date"),
            "colour": data.get("colour"),
            "position": data.get("position"),
            "is_hidden": vis in (2, 3) if vis is not None else False,
        }


# Global service instance (initialized on first use)
_service: KankaService | None = None


def get_service() -> KankaService:
    """Get or create the Kanka service instance."""
    global _service
    if _service is None:
        _service = KankaService()
    return _service
