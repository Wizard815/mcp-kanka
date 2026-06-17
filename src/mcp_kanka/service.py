"""Service layer for Kanka API operations."""

# mypy: warn_return_any=False

import logging
import os
import time
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
        "event": "events",
        "family": "families",
        "ability": "abilities",
        "conversation": "conversations",
        "location": "locations",
        "map": "maps",
        "organization": "organisations",  # API uses British spelling
        "dice_roll": "dice_rolls",
        "race": "races",
        "note": "notes",
        "journal": "journals",
        "quest": "quests",
        "tag": "tags",
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
        """Global search across entity types (GET search/{search_term}).

        Uses the raw HTTP response instead of ``KankaClient.search()`` so rows
        without ``entity_id`` (e.g. some maps/calendars) do not fail pydantic
        validation for the entire result set.
        """
        raw = self.client._request(
            "GET", f"search/{search_term}", params={"page": page}
        )
        rows = raw.get("data", raw)
        results = rows if isinstance(rows, list) else []

        formatted: list[dict[str, Any]] = []
        for r in results:
            row = r if isinstance(r, dict) else None
            entity_id = getattr(r, "entity_id", None)
            if entity_id is None and row is not None:
                entity_id = row.get("entity_id")
            if entity_id is None and row is not None:
                # Some search payloads only expose `id`; degrade gracefully.
                entity_id = row.get("id")

            # Skip malformed or unsupported result shapes instead of failing the entire search.
            if entity_id is None:
                logger.warning(
                    "Skipping malformed global search result without entity_id: %s", r
                )
                continue

            created_at = getattr(r, "created_at", None)
            if created_at is None and row is not None:
                created_at = row.get("created_at")

            updated_at = getattr(r, "updated_at", None)
            if updated_at is None and row is not None:
                updated_at = row.get("updated_at")

            formatted.append(
                {
                    "id": getattr(r, "id", row.get("id") if row else None),
                    "entity_id": entity_id,
                    "name": getattr(r, "name", row.get("name") if row else None),
                    "image": getattr(r, "image", row.get("image") if row else None),
                    "type": getattr(r, "type", row.get("type") if row else None),
                    "tooltip": getattr(
                        r, "tooltip", row.get("tooltip") if row else None
                    ),
                    "url": getattr(r, "url", row.get("url") if row else None),
                    "is_private": getattr(
                        r, "is_private", row.get("is_private") if row else None
                    ),
                    "created_at": (
                        created_at.isoformat()
                        if hasattr(created_at, "isoformat") and created_at
                        else created_at
                    ),
                    "updated_at": (
                        updated_at.isoformat()
                        if hasattr(updated_at, "isoformat") and updated_at
                        else updated_at
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
            if entity_type == "timeline":
                return self._list_timelines_as_entity_dicts(
                    page=page,
                    limit=limit,
                    last_sync=last_sync,
                    related=related,
                    tag_ids=tag_ids,
                )

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
        self,
        entity_id: int,
        include_posts: bool = False,
        _allow_child_id_fallback: bool = True,
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
                if _allow_child_id_fallback:
                    resolved_entity_id = self._resolve_entity_id_from_child_id(entity_id)
                    if (
                        resolved_entity_id is not None
                        and resolved_entity_id != entity_id
                    ):
                        logger.info(
                            "Resolved child id %s to entity_id %s",
                            entity_id,
                            resolved_entity_id,
                        )
                        return self.get_entity_by_id(
                            resolved_entity_id,
                            include_posts=include_posts,
                            _allow_child_id_fallback=False,
                        )
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

            # SDK module objects often omit entity-level nesting; merge from /entities payload.
            if result is not None and isinstance(found_entity, dict):
                if "parent_id" in found_entity:
                    result["parent_id"] = found_entity.get("parent_id")

            return result

        except Exception as e:
            logger.error(f"Get entity failed for {entity_id}: {e}")
            return None

    def get_entities_bulk(
        self, entity_ids: list[int], include_posts: bool = False
    ) -> dict[int, dict[str, Any]]:
        """Fetch multiple entities in one request using ids[] filters."""
        if not entity_ids:
            return {}

        params: dict[str, Any] = {"ids[]": entity_ids}
        if include_posts:
            params["related"] = 1

        resp = self.client._request("GET", "entities", params=params)
        rows = resp.get("data", [])
        if not isinstance(rows, list):
            return {}

        mapped: dict[int, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue

            entity_id = row.get("entity_id")
            if not isinstance(entity_id, int):
                continue

            row_type = row.get("type") or row.get("entity_type")
            if not isinstance(row_type, str):
                continue
            our_type = "organization" if row_type == "organisation" else row_type

            if our_type not in self.API_ENDPOINT_MAP:
                # Keep bulk fetch tolerant if Kanka returns an unsupported type.
                continue

            mapped[entity_id] = self._entity_dict_to_dict(row, our_type)

        return mapped

    def _resolve_entity_id_from_child_id(self, child_id: int) -> int | None:
        """Best-effort fallback to map module child ids to global entity_ids."""
        for manager_name in self.API_ENDPOINT_MAP.values():
            try:
                manager = getattr(self.client, manager_name, None)
                if manager is None:
                    continue
                candidate = manager.get(child_id)
                resolved_id = getattr(candidate, "entity_id", None)
                if isinstance(resolved_id, int):
                    return resolved_id
            except Exception:
                continue
        return None

    def create_entity(
        self,
        entity_type: EntityType,
        name: str,
        type: str | None = None,
        entry: str | None = None,
        tags: list[str] | None = None,
        is_hidden: bool | None = None,
        parent_id: int | None = None,
        location_id: int | None = None,
        parent_location_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
        age: str | None = None,
        sex: str | None = None,
        pronouns: str | None = None,
        race_id: int | None = None,
        family_id: int | None = None,
        is_dead: bool | None = None,
        is_map_private: bool | None = None,
        creature_id: int | None = None,
        is_extinct: bool | None = None,
        locations: list[int] | None = None,
        note_id: int | None = None,
        is_pinned: bool | None = None,
        journal_id: int | None = None,
        date: str | None = None,
        character_id: int | None = None,
        quest_id: int | None = None,
        ability_id: int | None = None,
        charges: int | None = None,
        organisation_id: int | None = None,
        is_defunct: bool | None = None,
        map_id: int | None = None,
        is_real: bool | None = None,
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
        calendar_id: int | None = None,
        calendar_year: int | None = None,
        calendar_month: int | None = None,
        calendar_day: int | None = None,
        event_parent_id: int | None = None,
        event_locations: list[int] | None = None,
        icon: str | None = None,
        colour: str | None = None,
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
            parent_id: Parent's global ``entity_id`` (URL ``/entities/{id}``). For **events**, applied with
            ``PATCH events/{child_id}`` and ``{"parent_id": ...}`` after create (``child_id`` from
            ``GET entities/{new_id}``). For **custom** entity types, ``PATCH entities/{id}``.
            parent_location_id: Parent **location** module row id → resolved to global entity id (same nesting rules by type).
            event_parent_id: Parent **event** module row id → resolved to global entity id, then same as ``parent_id``.
            Other module-specific parent fields (``organisation_id``, ``map_id``, etc.) resolve to global id and use the same paths.
            is_completed: Whether quest is completed (quests only)
            image_uuid: Image gallery UUID for entity image
            header_uuid: Image gallery UUID for entity header
            calendar_id: Calendar child id (events only)
            calendar_year: In-world year on that calendar (events only)
            calendar_month: In-world month (events only)
            calendar_day: In-world day (events only)
            event_parent_id: See above (legacy alias for parent event module id).

        Returns:
            Created entity data
        """
        try:
            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            nest_parent_global: int | None = parent_id
            if nest_parent_global is None and parent_location_id is not None:
                nest_parent_global = self.module_child_id_to_global_entity(
                    "location", parent_location_id
                )
            if nest_parent_global is None and event_parent_id is not None:
                nest_parent_global = self.module_child_id_to_global_entity(
                    "event", event_parent_id
                )
            if nest_parent_global is None:
                if entity_type == "location" and location_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "location", location_id
                    )
                elif entity_type == "organization" and organisation_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "organization", organisation_id
                    )
                elif entity_type == "map" and map_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "map", map_id
                    )
                elif entity_type == "note" and note_id is not None:
                    # Kanka breaking change: nesting via PATCH entities/{id} parent_id.
                    nest_parent_global = self.module_child_id_to_global_entity("note", note_id)
                elif entity_type == "journal" and journal_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "journal", journal_id
                    )
                elif entity_type == "quest" and quest_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "quest", quest_id
                    )
                elif entity_type == "race" and race_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "race", race_id
                    )
                elif entity_type == "creature" and creature_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "creature", creature_id
                    )
                elif entity_type == "family" and family_id is not None:
                    nest_parent_global = self.module_child_id_to_global_entity(
                        "family", family_id
                    )

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

            if entity_type == "character":
                if status is not None:
                    data["status"] = status
                if title is not None:
                    data["title"] = title
                if age is not None:
                    data["age"] = age
                if sex is not None:
                    data["sex"] = sex
                if pronouns is not None:
                    data["pronouns"] = pronouns
                if location_id is not None:
                    data["location_id"] = location_id
                if is_dead is not None:
                    data["is_dead"] = is_dead
                if race_id is not None:
                    data["race_id"] = race_id
                if family_id is not None:
                    data["family_id"] = family_id

            if entity_type == "location":
                if is_map_private is not None:
                    data["is_map_private"] = is_map_private

            if entity_type == "creature":
                if is_extinct is not None:
                    data["is_extinct"] = is_extinct
                if is_dead is not None:
                    data["is_dead"] = is_dead
                if locations is not None:
                    data["locations"] = locations

            if entity_type == "note":
                if is_pinned is not None:
                    data["is_pinned"] = is_pinned

            if entity_type == "journal":
                if date is not None:
                    data["date"] = date
                if character_id is not None:
                    data["character_id"] = character_id

            if entity_type == "quest":
                if character_id is not None:
                    data["character_id"] = character_id
                if status is not None:
                    data["status"] = status
                if is_completed is not None:
                    data["is_completed"] = is_completed

            if entity_type == "ability":
                if ability_id is not None:
                    data["ability_id"] = ability_id
                if charges is not None:
                    data["charges"] = charges

            if entity_type == "organization":
                if location_id is not None:
                    data["location_id"] = location_id
                if is_defunct is not None:
                    data["is_defunct"] = is_defunct

            if entity_type == "family":
                if location_id is not None:
                    data["location_id"] = location_id

            # Handle event-specific calendar placement (Kanka Events API)
            if entity_type == "event":
                if date is not None:
                    data["date"] = date
                if location_id is not None:
                    data["location_id"] = location_id
                if event_locations is not None:
                    data["locations"] = event_locations
                if calendar_id is not None:
                    data["calendar_id"] = calendar_id
                if calendar_year is not None:
                    data["calendar_year"] = calendar_year
                if calendar_month is not None:
                    data["calendar_month"] = calendar_month
                if calendar_day is not None:
                    data["calendar_day"] = calendar_day

            if entity_type == "map":
                if location_id is not None:
                    data["location_id"] = location_id
                if is_real is not None:
                    data["is_real"] = is_real

            if entity_type == "tag":
                if icon is not None:
                    data["icon"] = icon
                if colour is not None:
                    data["colour"] = colour

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

            if nest_parent_global is not None:
                self._set_entity_parent(
                    entity.entity_id,
                    nest_parent_global,
                    entity.name,
                    entity_type_hint=entity_type,
                    child_module_id=entity.id,
                )
            known_p, pid = self.read_entity_parent_global_id(entity.entity_id)
            result["parent_id"] = pid if known_p else nest_parent_global

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
        parent_id: int | None = None,
        parent_id_set: bool = False,
        location_id: int | None = None,
        parent_location_id: int | None = None,
        status: int | None = None,
        title: str | None = None,
        age: str | None = None,
        sex: str | None = None,
        pronouns: str | None = None,
        race_id: int | None = None,
        family_id: int | None = None,
        is_dead: bool | None = None,
        is_map_private: bool | None = None,
        creature_id: int | None = None,
        is_extinct: bool | None = None,
        locations: list[int] | None = None,
        note_id: int | None = None,
        is_pinned: bool | None = None,
        journal_id: int | None = None,
        date: str | None = None,
        character_id: int | None = None,
        quest_id: int | None = None,
        ability_id: int | None = None,
        charges: int | None = None,
        organisation_id: int | None = None,
        is_defunct: bool | None = None,
        map_id: int | None = None,
        is_real: bool | None = None,
        is_completed: bool | None = None,
        image_uuid: str | None = None,
        header_uuid: str | None = None,
        event_parent_id: int | None = None,
        event_parent_id_set: bool = False,
        event_locations: list[int] | None = None,
        calendar_id: int | None = None,
        calendar_id_set: bool = False,
        calendar_year: int | None = None,
        calendar_month: int | None = None,
        calendar_day: int | None = None,
        icon: str | None = None,
        colour: str | None = None,
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
            parent_id: Parent's global ``entity_id``. For **events**, persisted via ``PATCH events/{child_id}``;
            for custom modules, ``PATCH entities/{id}``.
            parent_id_set: Whether ``parent_id`` was explicitly provided by caller (including null to detach).
            is_completed: Whether quest is completed (quests only)
            image_uuid: Image gallery UUID for entity image
            header_uuid: Image gallery UUID for entity header
            event_parent_id: Parent **event** module row id; resolved to global entity id, then applied like ``parent_id``.
            event_parent_id_set: Whether ``event_parent_id`` was explicitly provided (including null to detach).
            calendar_id: Calendar child id for events. Can be None when detaching.
            calendar_id_set: Whether ``calendar_id`` was explicitly provided by caller.
            calendar_year: In-world year on that calendar (events only).
            calendar_month: In-world month (events only).
            calendar_day: In-world day (events only).

        Returns:
            True if successful
        """
        try:
            # First get the entity to find its type
            entity_data = self.get_entity_by_id(entity_id)
            if not entity_data:
                raise ValueError(f"Entity {entity_id} not found")

            entity_type = entity_data["entity_type"]

            def looks_like_name_required_error(exc: Exception) -> bool:
                text = str(exc).lower()
                return "name" in text and (
                    "required" in text or "missing" in text or "must" in text
                )

            # Timelines are not exposed on KankaClient; PATCH timelines/{module_id}.
            if entity_type == "timeline":
                module_id = self.resolve_timeline_module_id(entity_id)
                data_tl: dict[str, Any] = {}
                if name is not None:
                    data_tl["name"] = name
                if type is not None:
                    data_tl["type"] = type
                if entry is not None:
                    data_tl["entry"] = self.converter.markdown_to_html(entry)
                if is_hidden is not None:
                    data_tl["is_private"] = is_hidden
                if tags is not None:
                    data_tl["tags"] = self._get_or_create_tag_ids(tags)
                if image_uuid is not None:
                    data_tl["entity_image_uuid"] = image_uuid
                if header_uuid is not None:
                    data_tl["entity_header_uuid"] = header_uuid
                if data_tl:
                    try:
                        self.client._request(
                            "PATCH", f"timelines/{module_id}", json=data_tl
                        )
                    except KankaException as exc:
                        if name is None and looks_like_name_required_error(exc):
                            retry_tl = dict(data_tl)
                            retry_tl["name"] = entity_data["name"]
                            self.client._request(
                                "PATCH", f"timelines/{module_id}", json=retry_tl
                            )
                        else:
                            raise
                if parent_id_set:
                    self._set_entity_parent(
                        entity_id,
                        parent_id,
                        entity_data.get("name"),
                        entity_type_hint="timeline",
                    )
                return True

            manager = getattr(self.client, self.API_ENDPOINT_MAP[entity_type])

            apply_entity_parent = False
            entity_parent_val: int | None = None
            # Legacy event module id wins over global parent_id when both are sent.
            if event_parent_id_set:
                apply_entity_parent = True
                entity_parent_val = (
                    self.module_child_id_to_global_entity("event", event_parent_id)
                    if event_parent_id is not None
                    else None
                )
            elif event_parent_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "event", event_parent_id
                )
            elif parent_id_set:
                apply_entity_parent = True
                entity_parent_val = parent_id
            elif parent_location_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "location", parent_location_id
                )
            elif entity_type == "location" and location_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "location", location_id
                )
            elif entity_type == "organization" and organisation_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "organization", organisation_id
                )
            elif entity_type == "map" and map_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "map", map_id
                )
            elif entity_type == "note" and note_id is not None:
                apply_entity_parent = True
                # Kanka breaking change: nesting now via PATCH entities/{id} parent_id.
                # note_id is the parent's module id; convert to global entity_id.
                entity_parent_val = self.module_child_id_to_global_entity("note", note_id)
            elif entity_type == "journal" and journal_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "journal", journal_id
                )
            elif entity_type == "quest" and quest_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "quest", quest_id
                )
            elif entity_type == "race" and race_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "race", race_id
                )
            elif entity_type == "creature" and creature_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "creature", creature_id
                )
            elif entity_type == "family" and family_id is not None:
                apply_entity_parent = True
                entity_parent_val = self.module_child_id_to_global_entity(
                    "family", family_id
                )

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

            if entity_type == "character":
                if status is not None:
                    data["status"] = status
                if title is not None:
                    data["title"] = title
                if age is not None:
                    data["age"] = age
                if sex is not None:
                    data["sex"] = sex
                if pronouns is not None:
                    data["pronouns"] = pronouns
                if location_id is not None:
                    data["location_id"] = location_id
                if is_dead is not None:
                    data["is_dead"] = is_dead
                if race_id is not None:
                    data["race_id"] = race_id
                if family_id is not None:
                    data["family_id"] = family_id

            if entity_type == "location":
                if is_map_private is not None:
                    data["is_map_private"] = is_map_private

            if entity_type == "creature":
                if is_extinct is not None:
                    data["is_extinct"] = is_extinct
                if is_dead is not None:
                    data["is_dead"] = is_dead
                if locations is not None:
                    data["locations"] = locations

            if entity_type == "note":
                if is_pinned is not None:
                    data["is_pinned"] = is_pinned

            if entity_type == "journal":
                if date is not None:
                    data["date"] = date
                if character_id is not None:
                    data["character_id"] = character_id

            if entity_type == "event" and calendar_id_set:
                data["calendar_id"] = calendar_id

            # Handle quest-specific field
            if entity_type == "quest":
                if character_id is not None:
                    data["character_id"] = character_id
                if status is not None:
                    data["status"] = status
                if is_completed is not None:
                    data["is_completed"] = is_completed

            if entity_type == "ability":
                if ability_id is not None:
                    data["ability_id"] = ability_id
                if charges is not None:
                    data["charges"] = charges

            if entity_type == "organization":
                if location_id is not None:
                    data["location_id"] = location_id
                if is_defunct is not None:
                    data["is_defunct"] = is_defunct

            if entity_type == "family":
                if location_id is not None:
                    data["location_id"] = location_id

            if entity_type == "event":
                if date is not None:
                    data["date"] = date
                if location_id is not None:
                    data["location_id"] = location_id
                if event_locations is not None:
                    data["locations"] = event_locations
                if calendar_year is not None:
                    data["calendar_year"] = calendar_year
                if calendar_month is not None:
                    data["calendar_month"] = calendar_month
                if calendar_day is not None:
                    data["calendar_day"] = calendar_day

            if entity_type == "map":
                if location_id is not None:
                    data["location_id"] = location_id
                if is_real is not None:
                    data["is_real"] = is_real

            if entity_type == "tag":
                if icon is not None:
                    data["icon"] = icon
                if colour is not None:
                    data["colour"] = colour

            # Handle image fields
            if image_uuid is not None:
                data["image_uuid"] = image_uuid
            if header_uuid is not None:
                data["header_uuid"] = header_uuid

            # Update module row only when module fields are present.
            if data:
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

            if apply_entity_parent:
                self._set_entity_parent(
                    entity_id,
                    entity_parent_val,
                    name if name is not None else entity_data.get("name"),
                    entity_type_hint=entity_type,
                    child_module_id=entity_data.get("id"),
                )

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
            if entity_type == "timeline":
                module_id = self.resolve_timeline_module_id(entity_id)
                self.client._request("DELETE", f"timelines/{module_id}")
                return True

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
    def resolve_timeline_module_id(self, campaign_entity_id: int) -> int:
        """
        Map a timeline's global campaign entity id to the timelines API child id.

        Sub-resources (eras, elements) use ``timelines/{timeline_module_id}/…``, not
        ``/entities/{entity_id}``. The module id is returned on ``GET entities/{id}``
        as ``child.id`` when the entity type is ``timeline``.
        """
        resp = self.client._request("GET", f"entities/{campaign_entity_id}")
        payload = resp.get("data", resp)
        api_type = payload.get("type") or payload.get("entity_type")
        if api_type != "timeline":
            raise ValueError(
                f"Entity {campaign_entity_id} is not a timeline (type={api_type!r})"
            )
        child = payload.get("child") or {}
        tid = child.get("id")
        if not isinstance(tid, int):
            raise ValueError(
                f"Could not resolve timeline module id for entity {campaign_entity_id}"
            )
        return tid

    def resolve_timeline_subresource_id(self, timeline_id: int) -> int:
        """Map a value for ``timelines/{id}/…`` API calls.

        If ``timeline_id`` is a **campaign entity id** for a timeline (from
        ``GET entities/{id}`` with ``type: timeline``), returns ``child.id``
        (the timelines module row id). Otherwise returns ``timeline_id``
        unchanged so callers may still pass the module id directly.
        """
        try:
            resp = self.client._request("GET", f"entities/{timeline_id}")
        except Exception:
            return timeline_id
        payload = resp.get("data", resp)
        if not isinstance(payload, dict):
            return timeline_id
        api_type = payload.get("type") or payload.get("entity_type")
        if api_type != "timeline":
            return timeline_id
        child = payload.get("child") or {}
        tid = child.get("id")
        return tid if isinstance(tid, int) else timeline_id

    def _timeline_api_row_to_entity_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Shape a ``GET timelines`` row into the dict used by ``_entity_dict_to_dict``."""
        mod_id = row.get("id")
        ent_id = row.get("entity_id")
        if not isinstance(ent_id, int):
            ent_id = None
        shaped: dict[str, Any] = {
            **row,
            "type": "timeline",
            "entity_type": "timeline",
            "entity_id": ent_id if ent_id is not None else mod_id,
            "name": row.get("name"),
            "entry": row.get("entry"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
            "is_private": row.get("is_private"),
        }
        if isinstance(mod_id, int):
            shaped["child"] = {"id": mod_id}
        return self._entity_dict_to_dict(shaped, "timeline")

    def _list_timelines_as_entity_dicts(
        self,
        page: int,
        limit: int,
        last_sync: str | None,
        related: bool,
        tag_ids: list[int] | None,
    ) -> list[dict[str, Any]]:
        """List timelines via ``GET timelines`` (not ``GET entities`` type_id filter)."""
        merged: list[dict[str, Any]] = []
        cur = 1
        last_page = 1
        api_limit = 100
        while cur <= last_page:
            params: dict[str, Any] = {"page": cur, "limit": api_limit}
            if related:
                params["related"] = 1
            resp = self.client._request("GET", "timelines", params=params)
            batch = resp.get("data", [])
            if not isinstance(batch, list):
                batch = []
            for row in batch:
                if not isinstance(row, dict):
                    continue
                if tag_ids:
                    raw_tags = row.get("tags") or []
                    if not isinstance(raw_tags, list):
                        raw_tags = []
                    have: set[int] = set()
                    for t in raw_tags:
                        if isinstance(t, int):
                            have.add(t)
                        elif isinstance(t, str) and t.isdigit():
                            have.add(int(t))
                        elif isinstance(t, dict) and isinstance(t.get("id"), int):
                            have.add(t["id"])
                    if not set(tag_ids).issubset(have):
                        continue
                entity = self._timeline_api_row_to_entity_dict(row)
                if last_sync:
                    u = entity.get("updated_at")
                    if u is not None and str(u) < last_sync:
                        continue
                merged.append(entity)
            meta = resp.get("meta") or {}
            lp = meta.get("last_page") or meta.get("lastPage")
            if isinstance(lp, int) and lp > 0:
                last_page = lp
            if not batch:
                break
            cur += 1
            if cur > 50:
                logger.warning("Hit safety limit of 50 pages for GET timelines")
                break

        if limit == 0:
            return merged
        start = max(0, (page - 1) * limit)
        return merged[start : start + limit]

    def list_timeline_elements(
        self, timeline_id: int, page: int = 1, limit: int = 15
    ) -> dict[str, Any]:
        """List timeline elements for a timeline (paginated; returns links/meta)."""
        endpoint = f"timelines/{timeline_id}/timeline_elements"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.client._request("GET", endpoint, params=params)

    def list_timeline_elements_all(
        self, timeline_id: int, limit: int = 15, max_pages: int = 200
    ) -> dict[str, Any]:
        """List all timeline elements by paginating until last page or empty batch."""
        merged: list[Any] = []
        page = 1
        last_page = 1
        while page <= max_pages:
            resp = self.list_timeline_elements(timeline_id, page=page, limit=limit)
            batch = resp.get("data")
            if not isinstance(batch, list):
                batch = []
            merged.extend(batch)
            meta = resp.get("meta") or {}
            lp = meta.get("last_page") or meta.get("lastPage")
            if isinstance(lp, int) and lp > 0:
                last_page = lp
                if page >= lp:
                    break
            elif not batch:
                break
            page += 1

        return {
            "data": merged,
            "links": {},
            "meta": {"fetch_all": True, "total": len(merged), "last_page": last_page},
        }

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
    # Timeline era operations
    # ----------------------------
    def list_timeline_eras(
        self, timeline_id: int, page: int = 1, limit: int = 15
    ) -> dict[str, Any]:
        """List timeline eras for a timeline (paginated; returns links/meta)."""
        endpoint = f"timelines/{timeline_id}/eras"
        params: dict[str, Any] = {"page": page, "limit": limit}
        return self.client._request("GET", endpoint, params=params)

    def create_timeline_era(
        self, timeline_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a timeline era."""
        endpoint = f"timelines/{timeline_id}/eras"
        return self.client._request("POST", endpoint, json=payload)

    def update_timeline_era(
        self, timeline_id: int, era_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a timeline era using PATCH with an explicit payload."""
        endpoint = f"timelines/{timeline_id}/eras/{era_id}"
        return self.client._request("PATCH", endpoint, json=payload)

    def delete_timeline_era(
        self, timeline_id: int, era_id: int
    ) -> dict[str, Any]:
        """Delete a timeline era."""
        endpoint = f"timelines/{timeline_id}/eras/{era_id}"
        self.client._request("DELETE", endpoint)
        return {"success": True}

    # ----------------------------
    # Entity row parent (Kanka API: nesting on entities.parent_id)
    # ----------------------------
    def module_child_id_to_global_entity(
        self, entity_type: str, module_child_id: int
    ) -> int | None:
        """Map a module row id (e.g. locations/5 id) to global ``entity_id``."""
        manager_name = self.API_ENDPOINT_MAP.get(entity_type)
        if not manager_name:
            return None
        try:
            manager = getattr(self.client, manager_name)
            row = manager.get(module_child_id)
            eid = getattr(row, "entity_id", None)
            return eid if isinstance(eid, int) else None
        except Exception:
            return None

    def _read_entity_parent_id_raw(self, entity_id: int) -> tuple[bool, int | None]:
        """Read parent global entity id from GET ``entities/{entity_id}``.

        Kanka may expose nesting as top-level ``parent_id`` and/or a nested ``parent``
        object (e.g. ``{"entity_id": ...}``).
        """
        try:
            response = self.client._request(
                "GET", f"entities/{entity_id}", params={"related": 1}
            )
        except Exception:
            return (False, None)
        if not isinstance(response, dict):
            return (False, None)
        data = response.get("data", response)
        if not isinstance(data, dict):
            return (False, None)
        pid = data.get("parent_id")
        if isinstance(pid, int):
            return (True, pid)
        if isinstance(pid, str) and pid.strip().isdigit():
            return (True, int(pid.strip()))
        if pid is None:
            parent = data.get("parent")
            if isinstance(parent, dict):
                peid = parent.get("entity_id")
                if isinstance(peid, int):
                    return (True, peid)
                if isinstance(peid, str) and peid.strip().isdigit():
                    return (True, int(peid.strip()))
            parents = data.get("parents")
            if isinstance(parents, list) and parents:
                # EntityResource (related=1): ancestor entity ids; immediate parent first.
                for cand in (parents[0], parents[-1]):
                    if isinstance(cand, int):
                        return (True, cand)
                    if isinstance(cand, str) and cand.strip().isdigit():
                        return (True, int(cand.strip()))
                    if isinstance(cand, dict):
                        peid2 = cand.get("entity_id")
                        if isinstance(peid2, int):
                            return (True, peid2)
                        if isinstance(peid2, str) and peid2.strip().isdigit():
                            return (True, int(peid2.strip()))
            return (True, None)
        return (False, None)

    def read_entity_parent_global_id(self, entity_id: int) -> tuple[bool, int | None]:
        """Resolve the immediate parent's global ``entity_id`` from ``GET entities/{id}``.

        Uses ``parent_id`` and, with ``related=1``, the ``parents`` list (immediate
        parent is first). Event hierarchy is *written* via ``PATCH events/{child_id}``
        (see ``_set_entity_parent``).
        """
        return self._read_entity_parent_id_raw(entity_id)

    def _entity_row_minimal(self, entity_id: int) -> dict[str, Any]:
        """Raw ``GET entities/{entity_id}`` ``data`` object (no related)."""
        try:
            response = self.client._request("GET", f"entities/{entity_id}")
        except Exception:
            return {}
        data = response.get("data", response)
        return data if isinstance(data, dict) else {}

    def _entity_row_with_related(self, entity_id: int) -> dict[str, Any]:
        """``GET entities/{entity_id}?related=1`` for nested fields used in parent ops."""
        try:
            response = self.client._request(
                "GET", f"entities/{entity_id}", params={"related": 1}
            )
        except Exception:
            return {}
        data = response.get("data", response)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_parent_id_from_payload(obj: Any) -> int | None:
        """Extract ``parent_id`` from a PATCH/GET ``data`` object if present."""
        if not isinstance(obj, dict):
            return None
        pid = obj.get("parent_id")
        if isinstance(pid, int):
            return pid
        if isinstance(pid, str) and pid.strip().isdigit():
            return int(pid.strip())
        return None

    @staticmethod
    def _is_location_entity_row(row: dict[str, Any]) -> bool:
        """True if this entity row is the location module (not the user subtype)."""
        if row.get("entity_type") == "location":
            return True
        if row.get("type") == "location":
            return True
        return False

    @staticmethod
    def _location_module_id_from_entity_row(row: dict[str, Any]) -> int | None:
        """``locations/{id}`` row id from an entity payload."""
        cid = row.get("child_id")
        if isinstance(cid, int):
            return cid
        child = row.get("child")
        if isinstance(child, dict):
            mid = child.get("id")
            if isinstance(mid, int):
                return mid
        return None

    def _global_entity_to_location_module_id(self, global_entity_id: int) -> int | None:
        """Map a location entity's global id to ``locations/{id}`` module row id."""
        for row in (
            self._entity_row_with_related(global_entity_id),
            self._entity_row_minimal(global_entity_id),
        ):
            mod = self._location_module_id_from_entity_row(row)
            if isinstance(mod, int):
                return mod
        return None

    def _set_entity_parent(
        self,
        entity_id: int,
        parent_id: int | None,
        current_name: str | None = None,
        *,
        entity_type_hint: str | None = None,
        child_module_id: int | None = None,
    ) -> None:
        """Persist entity nesting via module-specific endpoints.

        Kanka 3.10+ requires PATCH {module}/{child_id} with {"parent_id": parent_global_entity_id}
        for all entity types. The parent_id is always the parent's global entity_id.

        PATCH entities/{id} with parent_id is silently ignored by Kanka for most types.
        Verification is skipped for journals/notes due to API propagation lag.
        """
        row = self._entity_row_minimal(entity_id)
        entity_type = row.get("type")
        is_event = entity_type == "event"
        is_note = entity_type == "note"
        is_journal = entity_type == "journal"
        event_child_id = row.get("child_id")

        if is_event and not isinstance(event_child_id, int):
            raise ValueError(
                f"Cannot set parent for event entity {entity_id}: "
                "missing child_id (events row id) on entity payload"
            )

        # child_module_id is entity_data["id"] passed from caller (avoids extra API call)
        module_child_id: int | None = child_module_id

        def patch_events_row(body: dict[str, Any]) -> None:
            self.client._request("PATCH", f"events/{event_child_id}", json=body)

        def _get_module_child_id() -> int | None:
            """Resolve the module row id from the entity row (child_id field)."""
            cid = module_child_id or row.get("child_id")
            if isinstance(cid, int):
                return cid
            detail = self._entity_row_with_related(entity_id)
            cid = detail.get("child_id") or detail.get("id")
            return cid if isinstance(cid, int) else None

        if is_event:
            patch_events_row({"parent_id": parent_id})
        elif is_journal or is_note:
            # Kanka 3.10+: PATCH {module}/{child_id} with {"parent_id": global_entity_id}
            # parent_id is already the parent's global entity_id — no module id lookup needed.
            module_type = "journals" if is_journal else "notes"
            child_mod = _get_module_child_id()
            if not isinstance(child_mod, int):
                raise ValueError(
                    f"Cannot nest {entity_type} {entity_id}: no module child_id found"
                )
            body: dict[str, Any] = {"parent_id": parent_id}
            if current_name:
                body["name"] = current_name
            self.raw_request("PATCH", f"{module_type}/{child_mod}", json=body)
            time.sleep(1.0)
            return
        else:
            et = entity_type or entity_type_hint
            if et == "organisation":
                et = "organization"
            module_ep = self.API_ENDPOINT_MAP.get(et or "")
            child_mod_id = _get_module_child_id()

            if module_ep and isinstance(child_mod_id, int) and et != "location":
                # Kanka 3.10+: use module endpoint for all non-location types
                wr = self.raw_request(
                    "PATCH", f"{module_ep}/{child_mod_id}", json={"parent_id": parent_id}
                )
            else:
                wr = self.raw_request(
                    "PATCH", f"entities/{entity_id}", json={"parent_id": parent_id}
                )
            if self._parse_parent_id_from_payload(wr.get("data")) == parent_id:
                return
            time.sleep(1.0)

        read_back = (
            self.read_entity_parent_global_id
            if parent_id is not None
            else self._read_entity_parent_id_raw
        )

        def matches() -> bool:
            known, actual = read_back(entity_id)
            return bool(known and actual == parent_id)

        if matches():
            return
        if current_name:
            if is_event:
                patch_events_row({"name": current_name, "parent_id": parent_id})
            else:
                wr2 = self.raw_request(
                    "PATCH",
                    f"entities/{entity_id}",
                    json={"name": current_name, "parent_id": parent_id},
                )
                if self._parse_parent_id_from_payload(wr2.get("data")) == parent_id:
                    return
                time.sleep(1.0)
            if matches():
                return

        hint = entity_type_hint
        if hint == "organisation":
            hint = "organization"

        if not is_event:
            detail = self._entity_row_with_related(entity_id)
            treat_as_location = hint == "location" or (
                hint is None and self._is_location_entity_row(detail)
            )
            if treat_as_location:
                child_mod = self._location_module_id_from_entity_row(
                    detail
                ) or self._location_module_id_from_entity_row(row)
                if isinstance(child_mod, int):
                    if parent_id is not None:

                        def _location_patch_trust(loc_resp: dict[str, Any]) -> bool:
                            if self._parse_parent_id_from_payload(
                                loc_resp.get("data")
                            ) == parent_id:
                                return True
                            time.sleep(0.05)
                            if matches():
                                return True
                            logger.info(
                                "Location nested via PATCH locations/%s "
                                "(entity_id=%s -> parent entity %s); "
                                "GET entities did not echo parent_id yet.",
                                child_mod,
                                entity_id,
                                parent_id,
                            )
                            return True

                        # Kanka 3.10+: parent nesting for locations is written on the
                        # ``locations/{id}`` row with ``parent_id`` = parent's **global**
                        # ``entity_id`` (verified live API). ``location_id`` (module id)
                        # is not the correct write shape for this campaign/API version.
                        try:
                            loc_resp = self.client._request(
                                "PATCH",
                                f"locations/{child_mod}",
                                json={"parent_id": parent_id},
                            )
                            if _location_patch_trust(loc_resp):
                                return
                        except KankaException as exc:
                            logger.debug(
                                "PATCH locations/{child} parent_id=%s failed: %s",
                                parent_id,
                                exc,
                            )
                            parent_mod = self._global_entity_to_location_module_id(
                                parent_id
                            )
                            if parent_mod is not None:
                                try:
                                    loc_resp = self.client._request(
                                        "PATCH",
                                        f"locations/{child_mod}",
                                        json={"location_id": parent_mod},
                                    )
                                    if _location_patch_trust(loc_resp):
                                        return
                                except KankaException as exc2:
                                    logger.debug(
                                        "Legacy PATCH locations location_id failed: %s",
                                        exc2,
                                    )
                    else:
                        try:
                            self.client._request(
                                "PATCH",
                                f"locations/{child_mod}",
                                json={"location_id": None},
                            )
                            time.sleep(0.05)
                            if matches():
                                return
                        except KankaException as exc:
                            logger.debug(
                                "Location detach via PATCH locations failed: %s", exc
                            )

        known_f, actual_f = read_back(entity_id)
        raise ValueError(
            f"Parent update did not persist for entity {entity_id}: "
            f"expected {parent_id}, got {actual_f!r}"
        )

    # ----------------------------
    # Entity attribute properties
    # ----------------------------
    @staticmethod
    def _normalize_attribute_checkbox_values(response: dict[str, Any]) -> dict[str, Any]:
        """Normalize checkbox attribute values (API may return bool or legacy strings)."""
        rows = response.get("data")
        if not isinstance(rows, list):
            return response
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("type_id") != 3:
                continue
            value = row.get("value")
            if isinstance(value, bool):
                continue
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    row["value"] = True
                    continue
                if lowered in {"0", "false", "no", "off", ""}:
                    row["value"] = False
                    continue
            if isinstance(value, int):
                row["value"] = value != 0
        return response

    def list_attributes(
        self, entity_id: int, page: int = 1, limit: int = 30
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/attributes"
        params: dict[str, Any] = {"page": page, "limit": limit}
        response = self.raw_request("GET", endpoint, params=params)
        return self._normalize_attribute_checkbox_values(response)

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

    def list_calendars(self, page: int = 1, limit: int = 15) -> dict[str, Any]:
        endpoint = "calendars"
        params = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

    def create_calendar(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "calendars"
        return self.raw_request("POST", endpoint, json=payload)

    def update_calendar(self, calendar_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}"
        return self.raw_request("PATCH", endpoint, json=payload)

    def delete_calendar(self, calendar_id: int) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}"
        url = f"{self.client.BASE_URL}/campaigns/{self.client.campaign_id}/{endpoint}"
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

    def list_calendar_events(
        self, calendar_id: int, page: int = 1, limit: int = 15
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/reminders"
        params = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

    def list_calendar_events_all(
        self, calendar_id: int, limit: int = 15, max_pages: int = 200
    ) -> dict[str, Any]:
        """List all calendar reminders by paginating until the last page or empty batch."""
        merged: list[Any] = []
        page = 1
        last_page = 1

        while page <= max_pages:
            resp = self.list_calendar_events(calendar_id, page=page, limit=limit)
            batch = resp.get("data")
            if not isinstance(batch, list):
                batch = []
            merged.extend(batch)

            meta = resp.get("meta") or {}
            lp = meta.get("last_page") or meta.get("lastPage")
            if isinstance(lp, int) and lp > 0:
                last_page = lp
                if page >= lp:
                    break
            elif not batch:
                break

            page += 1

        return {
            "data": merged,
            "links": {},
            "meta": {
                "fetch_all": True,
                "total": len(merged),
                "last_page": last_page,
            },
        }

    def create_calendar_event(
        self, calendar_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/reminders"
        return self.client._request("POST", endpoint, json=payload)

    def update_calendar_event(
        self, calendar_id: int, calendar_event_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/reminders/{calendar_event_id}"
        return self.client._request("PATCH", endpoint, json=payload)

    def delete_calendar_event(
        self, calendar_id: int, calendar_event_id: int
    ) -> dict[str, Any]:
        endpoint = f"calendars/{calendar_id}/reminders/{calendar_event_id}"
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

    def create_entity_reminder(
        self, entity_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/reminders"
        return self.raw_request("POST", endpoint, json=payload)

    def update_entity_reminder(
        self, entity_id: int, reminder_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/reminders/{reminder_id}"
        return self.raw_request("PATCH", endpoint, json=payload)

    def delete_entity_reminder(self, entity_id: int, reminder_id: int) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/reminders/{reminder_id}"
        url = f"{self.client.BASE_URL}/campaigns/{self.client.campaign_id}/{endpoint}"
        resp = self.client.session.request("DELETE", url)
        if not resp.text:
            return {"success": True}
        try:
            return resp.json()
        except Exception:
            return {"success": True, "raw": resp.text}

    def list_entity_reminders(
        self, entity_id: int, page: int = 1, limit: int = 15
    ) -> dict[str, Any]:
        endpoint = f"entities/{entity_id}/reminders"
        params = {"page": page, "limit": limit}
        return self.raw_request("GET", endpoint, params=params)

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
            if isinstance(tag_item, str) and not tag_item.isdigit():
                # API sometimes returns tag names directly (e.g. timelines / related payloads).
                tag_names.append(tag_item)
                continue

            if isinstance(tag_item, int) or (
                isinstance(tag_item, str) and tag_item.isdigit()
            ):
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
            result["status"] = getattr(entity, "status", None)

        if entity_type == "character":
            result["status"] = getattr(entity, "status", None)
            result["title"] = getattr(entity, "title", None)

        if entity_type == "location":
            result["title"] = getattr(entity, "title", None)

        if entity_type == "event":
            result["locations"] = getattr(entity, "locations", None)

        if entity_type == "tag":
            result["icon"] = getattr(entity, "icon", None)
            result["colour"] = getattr(entity, "colour", None)

        if hasattr(entity, "parent_id"):
            result["parent_id"] = getattr(entity, "parent_id", None)

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
            result["status"] = entity.get("status")

        if entity_type == "character":
            result["status"] = entity.get("status")
            result["title"] = entity.get("title")

        if entity_type == "location":
            result["title"] = entity.get("title")

        if entity_type == "event":
            result["locations"] = entity.get("locations")

        if entity_type == "tag":
            result["icon"] = entity.get("icon")
            result["colour"] = entity.get("colour")

        if "parent_id" in entity:
            result["parent_id"] = entity.get("parent_id")

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
