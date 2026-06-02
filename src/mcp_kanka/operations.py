"""High-level operations layer for Kanka functionality.

This module provides a reusable operations layer that can be used by both
MCP tools and external scripts, ensuring consistent behavior and type safety.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, get_args

from .service import KankaService, get_service
from .types import (
    CheckEntityUpdatesResult,
    CreateEntityResult,
    CreatePostResult,
    DeleteEntityResult,
    DeletePostResult,
    GetEntityResult,
    UpdateEntityResult,
    UpdatePostResult,
)
from .utils import (
    filter_entities_by_name,
    filter_entities_by_tags,
    filter_entities_by_type,
    filter_journals_by_date_range,
    paginate_results,
    search_in_content,
)

logger = logging.getLogger(__name__)


# Result classes with to_dict() methods for MCP compatibility
@dataclass
class FindEntitiesResult:
    """Structured result for find_entities operation."""

    entities: list[dict[str, Any]]
    sync_info: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP response format."""
        return {"entities": self.entities, "sync_info": self.sync_info}


@dataclass
class OperationResult:
    """Generic result for operations that return lists."""

    results: list[dict[str, Any]]

    def to_list(self) -> list[dict[str, Any]]:
        """Convert to MCP response format."""
        return self.results


class KankaOperationsError(Exception):
    """Base exception for operations layer."""

    pass


class PartialSuccessError(KankaOperationsError):
    """Some operations succeeded, some failed."""

    def __init__(self, successes: list[Any], failures: list[Any]):
        self.successes = successes
        self.failures = failures
        super().__init__(
            f"Partial success: {len(successes)} succeeded, {len(failures)} failed"
        )


class KankaOperations:
    """High-level operations for Kanka, used by both MCP tools and external scripts."""

    def __init__(self, service: KankaService | None = None):
        """Initialize operations with optional service instance.

        Args:
            service: Optional KankaService instance. If not provided, creates a new one.
        """
        self.service = service or KankaService()

    async def find_entities(
        self,
        query: str | None = None,
        entity_type: str | None = None,
        name: str | None = None,
        name_exact: bool = False,
        name_fuzzy: bool = False,
        type: str | None = None,
        tags: list[str] | None = None,
        tag_id: list[int] | None = None,
        date_range: dict[str, str] | None = None,
        include_full: bool = True,
        page: int = 1,
        limit: int = 25,
        last_synced: str | None = None,
    ) -> dict[str, Any]:
        """Find entities with search and filtering capabilities.

        Args:
            query: Search term for full-text search across names and content
            entity_type: Type of entity to search for
            name: Filter by entity name
            name_exact: Use exact name matching (case-insensitive)
            name_fuzzy: Use fuzzy name matching (typo-tolerant)
            type: Filter by custom type field
            tags: Filter by tags (must have all specified tags)
            tag_id: Filter by tag IDs (must have all specified tags)
            date_range: Date range filter for journals
            include_full: Whether to include full entity details
            page: Page number for pagination
            limit: Number of results per page (0 for all)
            last_synced: ISO timestamp to get only entities modified after this time

        Returns:
            Dictionary with entities and sync_info
        """
        # Validate entity type if provided
        from .types import EntityType

        valid_types = list(get_args(EntityType))
        if entity_type and entity_type not in valid_types:
            logger.error(
                f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(valid_types)}"
            )
            return {"entities": [], "sync_info": {}}

        # Resolve tags for API-side filtering (Kanka expects tag IDs).
        combined_tag_ids: list[int] | None = None
        client_tag_names: list[str] | None = None
        if tags:
            combined_tag_ids = self.service._get_or_create_tag_ids(tags)
        if tag_id:
            combined_tag_ids = (combined_tag_ids or []) + tag_id

        if combined_tag_ids:
            # Ensure uniqueness while preserving order.
            seen: set[int] = set()
            combined_tag_ids = [
                tid for tid in combined_tag_ids if not (tid in seen or seen.add(tid))
            ]
            client_tag_names = self.service._resolve_tag_names(combined_tag_ids)

        try:
            # Step 1: Get entities
            if query:
                # For content search, we need full entities
                entities = []

                if entity_type:
                    # Search specific entity type
                    # Cast to EntityType since we validated it above
                    from typing import cast

                    from .types import EntityType

                    entity_objects = self.service.list_entities(
                        cast(EntityType, entity_type),
                        page=1,
                        limit=0,
                        last_sync=last_synced,
                        related=include_full,
                        tag_ids=combined_tag_ids,
                    )
                    for obj in entity_objects:
                        entity_dict = self.service._entity_to_dict(obj, entity_type)
                        entities.append(entity_dict)
                else:
                    # Search across all entity types
                    entity_types = valid_types
                    for et in entity_types:
                        try:
                            entity_objects = self.service.list_entities(
                                et,
                                page=1,
                                limit=0,
                                last_sync=last_synced,
                                related=include_full,
                                tag_ids=combined_tag_ids,
                            )
                            for obj in entity_objects:
                                entity_dict = self.service._entity_to_dict(obj, et)
                                entities.append(entity_dict)
                        except Exception as e:
                            logger.debug(f"Could not search {et}: {e}")
                            continue

                # Apply content search
                entities = search_in_content(entities, query)

                # If not including full details, strip to minimal data
                if not include_full:
                    minimal_entities = []
                    for entity in entities:
                        minimal_entities.append(
                            {
                                "entity_id": entity["entity_id"],
                                "name": entity["name"],
                                "entity_type": entity["entity_type"],
                            }
                        )
                    entities = minimal_entities
            else:
                # List entities of specific type (no search)
                if not entity_type:
                    # No entity type specified, can't list all
                    return {"entities": [], "sync_info": {}}

                # Get all entities of this type
                # Cast to EntityType since we validated it above
                from typing import cast

                from .types import EntityType

                entity_objects = self.service.list_entities(
                    cast(EntityType, entity_type),
                    page=1,
                    limit=0,
                    last_sync=last_synced,
                    related=include_full,
                    tag_ids=combined_tag_ids,
                )

                # Convert to dictionaries
                entities = []
                for obj in entity_objects:
                    entity_dict = self.service._entity_to_dict(obj, entity_type)
                    entities.append(entity_dict)

            # Step 2: Apply client-side filters
            if name:
                entities = filter_entities_by_name(
                    entities, name, exact=name_exact, fuzzy=name_fuzzy
                )

            if type:
                entities = filter_entities_by_type(entities, type)

            if client_tag_names:
                entities = filter_entities_by_tags(entities, client_tag_names)

            if date_range and entity_type == "journal":
                start = date_range.get("start")
                end = date_range.get("end")
                if start and end:
                    entities = filter_journals_by_date_range(entities, start, end)

            # Don't apply content search if we already used the search API
            # The search API already searched content

            # Step 3: Paginate results
            paginated, total_pages, total_items = paginate_results(
                entities, page, limit
            )

            # Step 4: Calculate sync metadata
            # Find newest updated_at timestamp
            newest_updated_at = None
            for entity in paginated:
                if entity.get("updated_at") and (
                    newest_updated_at is None
                    or entity["updated_at"] > newest_updated_at
                ):
                    newest_updated_at = entity["updated_at"]

            # Build sync info
            sync_info = {
                "request_timestamp": datetime.now(timezone.utc).isoformat(),
                "newest_updated_at": newest_updated_at,
                "total_count": total_items,
                "last_page": total_pages,
                "returned_count": len(paginated),
            }

            # Step 5: Format results based on include_full
            if not include_full:
                # Return minimal data
                formatted_entities = [
                    {
                        "entity_id": e["entity_id"],
                        "name": e["name"],
                        "entity_type": e["entity_type"],
                    }
                    for e in paginated
                ]
            else:
                # Return full data
                formatted_entities = paginated

            # Return the new response structure
            return {
                "entities": formatted_entities,
                "sync_info": sync_info,
            }

        except Exception as e:
            logger.error(f"find_entities failed: {e}")
            raise

    async def search_entities(
        self, search_term: str, page: int = 1
    ) -> list[dict[str, Any]]:
        """Search across all entity types (global search endpoint)."""
        if not search_term:
            return []
        return self.service.global_search_entities(search_term, page=page)

    async def create_entities(
        self, entities: list[dict[str, Any]]
    ) -> list[CreateEntityResult]:
        """Create one or more entities.

        Args:
            entities: List of entity data to create

        Returns:
            List of results, one per entity (success or failure)
        """
        results = []
        from .types import EntityType

        valid_types = list(get_args(EntityType))

        for entity_input in entities:
            entity_type = entity_input.get("entity_type")
            entity_name = entity_input.get("name", "")

            # Validate entity type
            if not entity_type or entity_type not in valid_types:
                logger.error(
                    f"Invalid entity_type '{entity_type}' for entity '{entity_name}'"
                )
                error_result: CreateEntityResult = {
                    "id": None,
                    "entity_id": None,
                    "name": entity_name,
                    "mention": None,
                    "success": False,
                    "error": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(valid_types)}",
                }
                results.append(error_result)
                continue

            # Validate required fields
            if not entity_name:
                name_error: CreateEntityResult = {
                    "id": None,
                    "entity_id": None,
                    "name": "",
                    "mention": None,
                    "success": False,
                    "error": "Name is required",
                }
                results.append(name_error)
                continue

            try:
                # Create entity
                created = self.service.create_entity(
                    entity_type=entity_type,
                    name=entity_name,
                    type=entity_input.get("type"),
                    entry=entity_input.get("entry"),
                    tags=entity_input.get("tags"),
                    is_hidden=entity_input.get("is_hidden"),
                    parent_id=entity_input.get("parent_id"),
                    location_id=entity_input.get("location_id"),
                    parent_location_id=entity_input.get("parent_location_id"),
                    status=entity_input.get("status"),
                    title=entity_input.get("title"),
                    age=entity_input.get("age"),
                    sex=entity_input.get("sex"),
                    pronouns=entity_input.get("pronouns"),
                    race_id=entity_input.get("race_id"),
                    family_id=entity_input.get("family_id"),
                    is_dead=entity_input.get("is_dead"),
                    is_map_private=entity_input.get("is_map_private"),
                    creature_id=entity_input.get("creature_id"),
                    is_extinct=entity_input.get("is_extinct"),
                    locations=entity_input.get("locations"),
                    note_id=entity_input.get("note_id"),
                    is_pinned=entity_input.get("is_pinned"),
                    journal_id=entity_input.get("journal_id"),
                    date=entity_input.get("date"),
                    character_id=entity_input.get("character_id"),
                    quest_id=entity_input.get("quest_id"),
                    ability_id=entity_input.get("ability_id"),
                    charges=entity_input.get("charges"),
                    organisation_id=entity_input.get("organisation_id"),
                    is_defunct=entity_input.get("is_defunct"),
                    map_id=entity_input.get("map_id"),
                    is_real=entity_input.get("is_real"),
                    is_completed=entity_input.get("is_completed"),
                    image_uuid=entity_input.get("image_uuid"),
                    header_uuid=entity_input.get("header_uuid"),
                    calendar_id=entity_input.get("calendar_id"),
                    calendar_year=entity_input.get("calendar_year"),
                    calendar_month=entity_input.get("calendar_month"),
                    calendar_day=entity_input.get("calendar_day"),
                    event_parent_id=entity_input.get("event_parent_id"),
                    event_locations=entity_input.get("event_locations"),
                    icon=entity_input.get("icon"),
                    colour=entity_input.get("colour"),
                )

                result: CreateEntityResult = {
                    "id": created["id"],
                    "entity_id": created["entity_id"],
                    "name": created["name"],
                    "mention": created["mention"],
                    "success": True,
                    "error": None,
                }
                results.append(result)

            except Exception as e:
                logger.error(
                    f"Failed to create entity '{entity_input.get('name')}': {e}"
                )
                create_error: CreateEntityResult = {
                    "id": None,
                    "entity_id": None,
                    "name": entity_input.get("name", ""),
                    "mention": None,
                    "success": False,
                    "error": str(e),
                }
                results.append(create_error)

        return results

    async def update_entities(
        self, updates: list[dict[str, Any]]
    ) -> list[UpdateEntityResult]:
        """Update one or more entities.

        Args:
            updates: List of entity updates to apply

        Returns:
            List of results, one per entity (success or failure)
        """
        results = []
        for update in updates:
            entity_id = update.get("entity_id")
            name = update.get("name")  # Optional for PATCH-like updates

            # Validate required fields
            if not entity_id:
                id_error: UpdateEntityResult = {
                    "entity_id": 0,
                    "success": False,
                    "error": "entity_id is required",
                }
                results.append(id_error)
                continue

            try:
                # Update entity
                success = self.service.update_entity(
                    entity_id=entity_id,
                    name=name,
                    type=update.get("type"),
                    entry=update.get("entry"),
                    tags=update.get("tags"),
                    is_hidden=update.get("is_hidden"),
                    parent_id=update.get("parent_id"),
                    parent_id_set=("parent_id" in update),
                    location_id=update.get("location_id"),
                    parent_location_id=update.get("parent_location_id"),
                    status=update.get("status"),
                    title=update.get("title"),
                    age=update.get("age"),
                    sex=update.get("sex"),
                    pronouns=update.get("pronouns"),
                    race_id=update.get("race_id"),
                    family_id=update.get("family_id"),
                    is_dead=update.get("is_dead"),
                    is_map_private=update.get("is_map_private"),
                    creature_id=update.get("creature_id"),
                    is_extinct=update.get("is_extinct"),
                    locations=update.get("locations"),
                    note_id=update.get("note_id"),
                    is_pinned=update.get("is_pinned"),
                    journal_id=update.get("journal_id"),
                    date=update.get("date"),
                    character_id=update.get("character_id"),
                    quest_id=update.get("quest_id"),
                    ability_id=update.get("ability_id"),
                    charges=update.get("charges"),
                    organisation_id=update.get("organisation_id"),
                    is_defunct=update.get("is_defunct"),
                    map_id=update.get("map_id"),
                    is_real=update.get("is_real"),
                    is_completed=update.get("is_completed"),
                    image_uuid=update.get("image_uuid"),
                    header_uuid=update.get("header_uuid"),
                    event_parent_id=update.get("event_parent_id"),
                    event_parent_id_set=("event_parent_id" in update),
                    event_locations=update.get("event_locations"),
                    calendar_id=update.get("calendar_id"),
                    calendar_id_set=("calendar_id" in update),
                    calendar_year=update.get("calendar_year"),
                    calendar_month=update.get("calendar_month"),
                    calendar_day=update.get("calendar_day"),
                    icon=update.get("icon"),
                    colour=update.get("colour"),
                )

                error_message: str | None = None
                # note_id nesting is verified inside KankaService._set_entity_parent
                # via PATCH notes/{child_id} + GET notes/{child_id} read-back.
                # Skip the generic parent_id verification for notes.
                _is_note_update = "note_id" in update
                if success and not _is_note_update and (
                    "parent_id" in update
                    or "event_parent_id" in update
                    or "parent_location_id" in update
                ):
                    try:
                        expected_parent: int | None = None
                        # Match KankaService.update_entity: event module id before global parent_id.
                        if "event_parent_id" in update:
                            evp = update.get("event_parent_id")
                            if evp is None:
                                expected_parent = None
                            else:
                                expected_parent = (
                                    self.service.module_child_id_to_global_entity(
                                        "event", int(evp)
                                    )
                                )
                        elif "parent_id" in update:
                            v = update["parent_id"]
                            expected_parent = int(v) if v is not None else None
                        elif "parent_location_id" in update:
                            pl = update.get("parent_location_id")
                            if pl is None:
                                expected_parent = None
                            else:
                                expected_parent = (
                                    self.service.module_child_id_to_global_entity(
                                        "location", int(pl)
                                    )
                                )
                        known_parent, actual_parent = (
                            self.service.read_entity_parent_global_id(entity_id)
                        )
                        if not known_parent:
                            raise ValueError("could not read parent_id from entity row")

                        if expected_parent is not None:
                            if actual_parent != expected_parent:
                                success = False
                                error_message = (
                                    "Parent verification failed: "
                                    f"expected entity parent_id {expected_parent}, "
                                    f"got {actual_parent!r}"
                                )
                        else:
                            if actual_parent is not None:
                                success = False
                                error_message = (
                                    "Parent verification failed: "
                                    f"expected no parent, got parent_id={actual_parent!r}"
                                )
                    except Exception as ver_exc:
                        success = False
                        error_message = f"Parent verification failed: {ver_exc}"

                result: UpdateEntityResult = {
                    "entity_id": update["entity_id"],
                    "success": success,
                    "error": error_message,
                }
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to update entity {update['entity_id']}: {e}")
                update_error: UpdateEntityResult = {
                    "entity_id": update["entity_id"],
                    "success": False,
                    "error": str(e),
                }
                results.append(update_error)

        return results

    async def get_entities(
        self, entity_ids: list[int], include_posts: bool = False
    ) -> list[GetEntityResult]:
        """Get specific entities by ID.

        Args:
            entity_ids: List of entity IDs to retrieve
            include_posts: Whether to include posts for each entity

        Returns:
            List of results, one per entity
        """
        per_entity_timeout_s = 15.0
        bulk_by_id: dict[int, dict[str, Any]] = {}

        # Fast path for multi-id fetches to reduce sequential round-trip costs.
        if len(entity_ids) > 1:
            try:
                bulk_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.service.get_entities_bulk, entity_ids, include_posts
                    ),
                    timeout=per_entity_timeout_s,
                )
                bulk_by_id = bulk_result if isinstance(bulk_result, dict) else {}
            except Exception as e:
                logger.warning("Bulk get_entities fallback failed: %s", e)
                bulk_by_id = {}

        async def fetch_one(
            entity_id: int,
        ) -> tuple[int, dict[str, Any] | None, str | None]:
            if entity_id in bulk_by_id:
                return (entity_id, bulk_by_id[entity_id], None)
            try:
                entity = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.service.get_entity_by_id, entity_id, include_posts
                    ),
                    timeout=per_entity_timeout_s,
                )
                return (entity_id, entity, None)
            except TimeoutError:
                return (
                    entity_id,
                    None,
                    f"Timed out after {int(per_entity_timeout_s)}s while fetching entity {entity_id}",
                )
            except Exception as e:
                logger.error(f"Failed to get entity {entity_id}: {e}")
                return (entity_id, None, str(e))

        fetched = await asyncio.gather(*(fetch_one(eid) for eid in entity_ids))
        results: list[GetEntityResult] = []
        for entity_id, entity, fetch_error in fetched:
            if fetch_error is not None:
                results.append(
                    {"entity_id": entity_id, "success": False, "error": fetch_error}
                )
                continue

            if entity:
                result: GetEntityResult = {
                    "id": entity["id"],
                    "entity_id": entity["entity_id"],
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "type": entity.get("type"),
                    "entry": entity.get("entry"),
                    "tags": entity.get("tags", []),
                    "is_hidden": entity.get("is_hidden", False),
                    "created_at": entity.get("created_at"),
                    "updated_at": entity.get("updated_at"),
                    "success": True,
                    "error": None,
                }

                if entity.get("entity_type") == "quest":
                    result["is_completed"] = entity.get("is_completed")

                result["image"] = entity.get("image")
                result["image_full"] = entity.get("image_full")
                result["image_thumb"] = entity.get("image_thumb")
                result["image_uuid"] = entity.get("image_uuid")
                result["header_uuid"] = entity.get("header_uuid")

                if "parent_id" in entity:
                    result["parent_id"] = entity.get("parent_id")

                if "locations" in entity:
                    result["locations"] = entity.get("locations")

                if include_posts:
                    result["posts"] = entity.get("posts", [])

                results.append(result)
            else:
                results.append(
                    {
                        "entity_id": entity_id,
                        "success": False,
                        "error": (
                            f"Entity {entity_id} not found. Expected MCP entity_id (global /entities id), "
                            "not a module child id from URLs like /timelines/{id} or /calendars/{id}. "
                            "Resolve ids with `find_entities` or `search_entities` first."
                        ),
                    }
                )

        return results

    @staticmethod
    def _clamp_delete_batch_size(batch_size: int | None) -> int:
        """Cap concurrent delete waves at 1–15 (default 12) to avoid long sequential chains."""
        if batch_size is None:
            return 12
        try:
            b = int(batch_size)
        except (TypeError, ValueError):
            return 12
        return max(1, min(15, b))

    @staticmethod
    def _clamp_delete_delay_ms(delay_ms: int | None) -> int:
        """Pause between waves in ms (default 500, max 60000)."""
        if delay_ms is None:
            return 500
        try:
            d = int(delay_ms)
        except (TypeError, ValueError):
            return 500
        return max(0, min(60000, d))

    async def delete_entities(
        self,
        entity_ids: list[int],
        batch_size: int | None = None,
        delay_ms: int | None = None,
        dry_run: bool | None = None,
    ) -> list[DeleteEntityResult]:
        """Delete one or more entities in bounded concurrent waves.

        Large ID lists are split into waves of at most ``batch_size`` (default 12,
        max 15). Within each wave, deletes run concurrently to reduce wall-clock time
        and MCP timeouts from a single long sequential chain. Between waves, an
        optional delay reduces API rate-limit pressure.

        Args:
            entity_ids: List of entity IDs to delete
            batch_size: Max deletes per wave (1–15; default 12)
            delay_ms: Milliseconds to wait after each wave except the last (0–60000; default 500)
            dry_run: If true, only report what would be deleted without deleting

        Returns:
            List of results, one per entity (same order as ``entity_ids``)
        """
        bs = self._clamp_delete_batch_size(batch_size)
        pause_ms = self._clamp_delete_delay_ms(delay_ms)
        is_dry_run = bool(dry_run)
        results: list[DeleteEntityResult] = []
        warning_text = (
            "Event entity has calendar_id set — deleting will orphan its calendar reminder "
            "which cannot be deleted via API. Set calendar_id to null first via "
            "update_entities, then delete."
        )

        async def _delete_one(entity_id: int) -> DeleteEntityResult:
            try:
                warning: str | None = None
                entity_data = await asyncio.to_thread(self.service.get_entity_by_id, entity_id)
                if (
                    isinstance(entity_data, dict)
                    and entity_data.get("entity_type") == "event"
                    and entity_data.get("calendar_id") is not None
                ):
                    warning = warning_text

                if is_dry_run:
                    result: DeleteEntityResult = {
                        "entity_id": entity_id,
                        "success": True,
                        "error": None,
                        "dry_run": True,
                    }
                    if warning:
                        result["warning"] = warning
                    return result

                success = await asyncio.to_thread(
                    self.service.delete_entity, entity_id
                )
                result: DeleteEntityResult = {
                    "entity_id": entity_id,
                    "success": success,
                    "error": None,
                }
                if warning:
                    result["warning"] = warning
                return result
            except Exception as e:
                logger.error(f"Failed to delete entity {entity_id}: {e}")
                return {
                    "entity_id": entity_id,
                    "success": False,
                    "error": str(e),
                }

        wave_index = 0
        total_waves = (len(entity_ids) + bs - 1) // bs if entity_ids else 0
        for i in range(0, len(entity_ids), bs):
            chunk = entity_ids[i : i + bs]
            wave = await asyncio.gather(*(_delete_one(eid) for eid in chunk))
            results.extend(wave)
            wave_index += 1
            if pause_ms > 0 and wave_index < total_waves:
                await asyncio.sleep(pause_ms / 1000.0)

        return results

    async def create_posts(self, posts: list[dict[str, Any]]) -> list[CreatePostResult]:
        """Create posts on entities.

        Args:
            posts: List of post data to create

        Returns:
            List of results, one per post
        """
        results = []
        for post_input in posts:
            try:
                # Create post
                created = self.service.create_post(
                    entity_id=post_input["entity_id"],
                    name=post_input["name"],
                    entry=post_input.get("entry"),
                    is_hidden=post_input.get("is_hidden", False),
                )

                result: CreatePostResult = {
                    "post_id": created["post_id"],
                    "entity_id": created["entity_id"],
                    "success": True,
                    "error": None,
                }
                results.append(result)

            except Exception as e:
                logger.error(
                    f"Failed to create post on entity {post_input['entity_id']}: {e}"
                )
                error_result: CreatePostResult = {
                    "post_id": None,
                    "entity_id": post_input["entity_id"],
                    "success": False,
                    "error": str(e),
                }
                results.append(error_result)

        return results

    async def update_posts(
        self, updates: list[dict[str, Any]]
    ) -> list[UpdatePostResult]:
        """Update existing posts.

        Args:
            updates: List of post updates to apply

        Returns:
            List of results, one per post
        """
        results = []
        for update in updates:
            try:
                # Update post
                entity_id = update.get("entity_id")
                post_id = update.get("post_id")
                name = update.get("name")  # Optional for PATCH-like updates

                if not entity_id or not post_id:
                    result: UpdatePostResult = {
                        "entity_id": entity_id or 0,
                        "post_id": post_id or 0,
                        "success": False,
                        "error": "entity_id and post_id are required",
                    }
                    results.append(result)
                    continue

                success = self.service.update_post(
                    entity_id=entity_id,
                    post_id=post_id,
                    name=name,
                    entry=update.get("entry"),
                    is_hidden=update.get("is_hidden"),
                )

                result: UpdatePostResult = {
                    "entity_id": update["entity_id"],
                    "post_id": update["post_id"],
                    "success": success,
                    "error": None,
                }
                results.append(result)

            except Exception as e:
                logger.error(
                    f"Failed to update post {update['post_id']} on entity {update['entity_id']}: {e}"
                )
                error_result: UpdatePostResult = {
                    "entity_id": update["entity_id"],
                    "post_id": update["post_id"],
                    "success": False,
                    "error": str(e),
                }
                results.append(error_result)

        return results

    async def delete_posts(
        self, deletions: list[dict[str, Any]]
    ) -> list[DeletePostResult]:
        """Delete posts from entities.

        Args:
            deletions: List of post deletions to perform

        Returns:
            List of results, one per post
        """
        results = []
        for deletion in deletions:
            try:
                # Delete post
                success = self.service.delete_post(
                    entity_id=deletion["entity_id"],
                    post_id=deletion["post_id"],
                )

                result: DeletePostResult = {
                    "entity_id": deletion["entity_id"],
                    "post_id": deletion["post_id"],
                    "success": success,
                    "error": None,
                }
                results.append(result)

            except Exception as e:
                logger.error(
                    f"Failed to delete post {deletion['post_id']} from entity {deletion['entity_id']}: {e}"
                )
                error_result: DeletePostResult = {
                    "entity_id": deletion["entity_id"],
                    "post_id": deletion["post_id"],
                    "success": False,
                    "error": str(e),
                }
                results.append(error_result)

        return results

    async def manage_map_markers(
        self,
        action: str,
        map_id: int,
        marker_id: int | None = None,
        page: int = 1,
        limit: int = 30,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage map markers for a map (list/create/update/delete)."""

        marker_fields = {
            # Conditional identity
            "name",
            "entity_id",
            # Required/geometry
            "latitude",
            "longitude",
            "shape_id",
            "icon",
            # Optional/create/update fields
            "group_id",
            "is_draggable",
            "is_popupless",
            "custom_shape",
            "custom_icon",
            "size_id",
            "opacity",
            "visibility_id",
            "colour",
            "font_colour",
            "circle_radius",
            "polygon_style",
            "css",
        }

        action = action.lower()
        provided_fields = {k: v for k, v in fields.items() if k in marker_fields}

        if action == "list":
            return self.service.list_map_markers(map_id=map_id, page=page, limit=limit)

        if action == "create":
            required_create = {"latitude", "longitude", "shape_id", "icon"}
            missing = [k for k in required_create if k not in provided_fields]
            if missing:
                raise ValueError(
                    f"Missing required create fields: {', '.join(missing)}"
                )

            has_name = "name" in provided_fields
            has_entity = "entity_id" in provided_fields
            if not (has_name or has_entity):
                raise ValueError("Provide either `name` or `entity_id` for create.")

            payload = dict(provided_fields)
            return self.service.create_map_marker(map_id=map_id, payload=payload)

        if action == "update":
            if not marker_id:
                raise ValueError("`marker_id` is required for update.")
            if not provided_fields:
                raise ValueError("No fields to update.")

            # Patch: only include explicitly provided fields (fix: do not overwrite with omitted fields).
            # Clearing entity_id is handled in KankaService.update_map_marker (auto name merge).
            payload = dict(provided_fields)
            return self.service.update_map_marker(
                map_id=map_id, marker_id=marker_id, payload=payload
            )

        if action == "delete":
            if not marker_id:
                raise ValueError("`marker_id` is required for delete.")
            return self.service.delete_map_marker(map_id=map_id, marker_id=marker_id)

        raise ValueError(f"Unknown action: {action}")

    async def manage_relations(
        self,
        action: str,
        entity_id: int,
        relation_id: int | None = None,
        page: int = 1,
        limit: int = 30,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage relations attached to an entity (list/create/update/delete)."""

        relation_fields = {
            "relation",
            "owner_id",
            "target_id",
            "targets",
            "attitude",
            "colour",
            "two_way",
            "is_pinned",
            "visibility_id",
        }

        action = action.lower()
        provided_fields = {k: v for k, v in fields.items() if k in relation_fields}

        if action == "list":
            return self.service.list_relations(
                entity_id=entity_id, page=page, limit=limit
            )

        if action == "create":
            # Required by docs: relation + owner_id and either target_id or targets.
            if "relation" not in provided_fields:
                raise ValueError("Missing required create field: relation")

            payload = dict(provided_fields)
            payload.setdefault("owner_id", entity_id)

            if "owner_id" not in payload:
                raise ValueError("Missing required create field: owner_id")

            if "target_id" not in payload and "targets" not in payload:
                raise ValueError("Provide either `target_id` or `targets` for create.")

            return self.service.create_relation(entity_id=entity_id, payload=payload)

        if action == "update":
            if not relation_id:
                raise ValueError("`relation_id` is required for update.")

            if not provided_fields:
                raise ValueError("No update fields provided.")

            payload = dict(provided_fields)
            payload.setdefault("owner_id", entity_id)
            return self.service.update_relation(
                entity_id=entity_id, relation_id=relation_id, payload=payload
            )

        if action == "delete":
            if not relation_id:
                raise ValueError("`relation_id` is required for delete.")
            return self.service.delete_relation(entity_id=entity_id, relation_id=relation_id)

        raise ValueError(f"Unknown action: {action}")

    async def manage_timeline_elements(
        self,
        action: str,
        timeline_id: int,
        element_id: int | None = None,
        page: int = 1,
        limit: int = 15,
        fetch_all: bool = False,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage timeline elements for a timeline (list/create/update/delete)."""
        timeline_id = self.service.resolve_timeline_subresource_id(timeline_id)

        element_fields = {
            "name",
            "entity_id",
            "era_id",
            "entry",
            "date",
            "colour",
            "position",
            "visibility_id",
        }

        action = action.lower()
        provided_fields = {k: v for k, v in fields.items() if k in element_fields}

        if action == "list":
            if fetch_all:
                return self.service.list_timeline_elements_all(
                    timeline_id=timeline_id, limit=limit
                )
            return self.service.list_timeline_elements(
                timeline_id=timeline_id, page=page, limit=limit
            )

        if action == "create":
            if "era_id" not in provided_fields:
                raise ValueError(
                    "Missing required create field: era_id. Use `action=list` first to inspect timeline eras and select a valid era_id."
                )

            if "name" not in provided_fields and "entity_id" not in provided_fields:
                raise ValueError(
                    "Provide either `name` or `entity_id` for create (name required if entity_id is omitted)."
                )

            payload = dict(provided_fields)
            return self.service.create_timeline_element(
                timeline_id=timeline_id, payload=payload
            )

        if action == "update":
            if not element_id:
                raise ValueError("`element_id` is required for update.")

            if "name" not in provided_fields and "entity_id" not in provided_fields:
                raise ValueError(
                    "For update, provide `name` or `entity_id` (name required if entity_id is omitted)."
                )

            payload = dict(provided_fields)
            return self.service.update_timeline_element(
                timeline_id=timeline_id,
                element_id=element_id,
                payload=payload,
            )

        if action == "delete":
            if not element_id:
                raise ValueError("`element_id` is required for delete.")
            return self.service.delete_timeline_element(
                timeline_id=timeline_id, element_id=element_id
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_timeline_eras(
        self,
        action: str,
        timeline_id: int,
        era_id: int | None = None,
        page: int = 1,
        limit: int = 15,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage timeline eras for a timeline (list/create/update/delete)."""
        timeline_id = self.service.resolve_timeline_subresource_id(timeline_id)
        action = action.lower()
        era_fields = {
            "name",
            "abbreviation",
            "start_year",
            "end_year",
            "position",
            "is_collapsed",
        }
        provided_fields = {
            k: v for k, v in fields.items() if k in era_fields and v is not None
        }

        if action == "list":
            return self.service.list_timeline_eras(
                timeline_id=timeline_id, page=page, limit=limit
            )

        if action == "create":
            if "name" not in provided_fields:
                raise ValueError("Missing required create field: name")
            return self.service.create_timeline_era(
                timeline_id=timeline_id, payload=dict(provided_fields)
            )

        if action == "update":
            if era_id is None:
                raise ValueError("`era_id` is required for update.")
            if not provided_fields:
                raise ValueError("No update fields provided.")
            return self.service.update_timeline_era(
                timeline_id=timeline_id,
                era_id=era_id,
                payload=dict(provided_fields),
            )

        if action == "delete":
            if era_id is None:
                raise ValueError("`era_id` is required for delete.")
            return self.service.delete_timeline_era(
                timeline_id=timeline_id, era_id=era_id
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_attributes(
        self,
        action: str,
        entity_id: int,
        attribute_id: int | None = None,
        page: int = 1,
        limit: int = 30,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage entity properties/attributes (list/create/update/delete)."""
        action = action.lower()

        attr_fields = {
            "name",
            "value",
            "type",
            "type_id",
            "is_private",
            "is_star",
            "position",
            "api_key",
        }

        provided_fields = {
            k: v for k, v in fields.items() if k in attr_fields and v is not None
        }

        # Map our friendly type + fields to the API property payload.
        type_to_type_id = {
            # Kanka entity-attributes docs use numeric type_id values.
            "text": 1,
            "number": 6,
            "checkbox": 3,
            "section": 4,
        }

        if action == "list":
            return self.service.list_attributes(
                entity_id=entity_id, page=page, limit=limit
            )

        if action == "create":
            if "name" not in provided_fields:
                raise ValueError("Missing required create field: name")

            payload: dict[str, Any] = dict(provided_fields)
            if "type" in payload:
                type_str = payload.pop("type")
                type_id = type_to_type_id.get(type_str)
                if type_id is None:
                    raise ValueError(f"Unknown attribute type: {type_str}")
                payload["type_id"] = type_id
            if "position" in payload:
                payload["default_order"] = payload.pop("position")
            if "is_star" in payload:
                payload["is_pinned"] = payload.pop("is_star")
            return self.service.create_attribute(entity_id=entity_id, payload=payload)

        if action == "update":
            if not attribute_id:
                raise ValueError("`attribute_id` is required for update.")
            # Docs: name field is required on update.
            if "name" not in provided_fields:
                raise ValueError("Update requires `name` (API requires it).")

            payload = dict(provided_fields)
            if "type" in payload:
                type_str = payload.pop("type")
                type_id = type_to_type_id.get(type_str)
                if type_id is None:
                    raise ValueError(f"Unknown attribute type: {type_str}")
                payload["type_id"] = type_id
            if "position" in payload:
                payload["default_order"] = payload.pop("position")
            if "is_star" in payload:
                payload["is_pinned"] = payload.pop("is_star")

            return self.service.update_attribute(
                entity_id=entity_id,
                attribute_id=attribute_id,
                payload=payload,
            )

        if action == "delete":
            if not attribute_id:
                raise ValueError("`attribute_id` is required for delete.")
            return self.service.delete_attribute(
                entity_id=entity_id, attribute_id=attribute_id
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_entity_tags(
        self,
        action: str,
        entity_id: int,
        tag_id: int | None = None,
        entity_tag_id: int | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage entity tags (list/add/remove)."""
        action = action.lower()

        if action == "list":
            return self.service.list_entity_tags(entity_id=entity_id)

        if action == "add":
            if tag_id is None:
                raise ValueError("`tag_id` is required for add.")
            return self.service.add_entity_tag(entity_id=entity_id, tag_id=tag_id)

        if action == "remove":
            if entity_tag_id is not None:
                return self.service.remove_entity_tag(
                    entity_id=entity_id, entity_tag_id=entity_tag_id
                )

            if tag_id is None:
                raise ValueError(
                    "Provide either `entity_tag_id` or `tag_id` for remove."
                )

            # Resolve tag_id -> entity_tag_id by listing current entity tags.
            current = self.service.list_entity_tags(entity_id=entity_id)
            items = current.get("data") or []
            matching = None
            for item in items:
                if item.get("tag_id") == tag_id:
                    matching = item
                    break

            if not matching or matching.get("id") is None:
                raise ValueError(f"Entity tag not found for tag_id={tag_id}")

            return self.service.remove_entity_tag(
                entity_id=entity_id, entity_tag_id=matching["id"]
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_inventory(
        self,
        action: str,
        entity_id: int,
        inventory_id: int | None = None,
        page: int = 1,
        limit: int = 30,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage entity inventory (list/create/update/delete)."""
        action = action.lower()

        inv_fields = {
            "item_id",
            "name",
            "amount",
            "position",
            "is_equipped",
            "visibility_id",
            "visibility",
            "currency_id",
        }
        provided_fields = {
            k: v for k, v in fields.items() if k in inv_fields and v is not None
        }

        visibility_id_to_string = {
            1: "all",
            2: "self",
            3: "admin",
            4: "self-admin",
            5: "members",
        }

        if action == "list":
            return self.service.list_inventory(
                entity_id=entity_id, page=page, limit=limit
            )

        if action == "create":
            if "amount" not in provided_fields:
                raise ValueError("Missing required create field: amount")
            if "item_id" not in provided_fields and "name" not in provided_fields:
                raise ValueError("Provide `item_id` or `name` for create.")

            payload = dict(provided_fields)
            payload["entity_id"] = entity_id

            # Map visibility_id -> API's `visiblity` string field.
            if "visibility_id" in payload:
                vid = payload.pop("visibility_id")
                vis = visibility_id_to_string.get(vid)
                if vis is None:
                    raise ValueError(f"Unknown visibility_id: {vid}")
                payload["visiblity"] = vis
            elif "visibility" in payload:
                payload["visiblity"] = payload.pop("visibility")

            # Docs include `amount` + `position` + `is_equipped` etc as-is.
            return self.service.create_inventory(entity_id=entity_id, payload=payload)

        if action == "update":
            if not inventory_id:
                raise ValueError("`inventory_id` is required for update.")
            if not provided_fields:
                raise ValueError("No update fields provided.")

            payload = dict(provided_fields)
            payload["entity_id"] = entity_id

            if "visibility_id" in payload:
                vid = payload.pop("visibility_id")
                vis = visibility_id_to_string.get(vid)
                if vis is None:
                    raise ValueError(f"Unknown visibility_id: {vid}")
                payload["visiblity"] = vis
            elif "visibility" in payload:
                payload["visiblity"] = payload.pop("visibility")

            return self.service.update_inventory(
                entity_id=entity_id,
                inventory_id=inventory_id,
                payload=payload,
            )

        if action == "delete":
            if not inventory_id:
                raise ValueError("`inventory_id` is required for delete.")
            return self.service.delete_inventory(
                entity_id=entity_id, inventory_id=inventory_id
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_permissions(
        self,
        action: str,
        entity_id: int,
        permission_action: int | None = None,
        access: bool | None = None,
        campaign_role_id: int | None = None,
        user_id: int | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage per-entity permissions (list/update)."""
        action = action.lower()

        if action == "list":
            return self.service.list_permissions(entity_id=entity_id)

        if action == "update":
            if permission_action is None:
                raise ValueError("Missing required field: permission_action")
            if access is None:
                raise ValueError("Missing required field: access")
            if campaign_role_id is None and user_id is None:
                raise ValueError(
                    "Provide either `campaign_role_id` or `user_id`."
                )

            payload: dict[str, Any] = {
                "action": permission_action,
                "access": access,
            }
            if campaign_role_id is not None:
                payload["campaign_role_id"] = campaign_role_id
            if user_id is not None:
                payload["user_id"] = user_id

            return self.service.create_permission(
                entity_id=entity_id, payload=payload
            )

        raise ValueError(f"Unknown action: {action}")

    async def get_archives(self) -> dict[str, Any]:
        """Retrieve all archived entities."""
        return self.service.get_archives()

    async def manage_entity_image(
        self,
        action: str,
        entity_id: int,
        file_path: str | None = None,
        is_header: bool = False,
    ) -> dict[str, Any]:
        """Manage an entity's image (list/upload/remove)."""
        action = action.lower()

        if action == "list":
            return self.service.get_entity_image(entity_id=entity_id)

        if action == "upload":
            if file_path is None:
                raise ValueError("Provide `file_path` for upload.")
            return self.service.upload_entity_image_from_file(
                entity_id=entity_id, file_path=file_path, is_header=is_header
            )

        if action == "remove":
            return self.service.remove_entity_image(
                entity_id=entity_id, is_header=is_header
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_calendar_weather(
        self,
        action: str,
        calendar_id: int,
        calendar_weather_id: int | None = None,
        page: int = 1,
        limit: int = 15,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage calendar weather effects (list/create/update/delete)."""
        action = action.lower()

        weather_fields = {
            "year",
            "month",
            "day",
            "weather",
            "temperature",
            "precipitation",
            "wind",
            "effect",
            "visibility_id",
        }
        provided_fields = {k: v for k, v in fields.items() if k in weather_fields and v is not None}

        if action == "list":
            return self.service.list_calendar_weather(
                calendar_id=calendar_id, page=page, limit=limit
            )

        if action == "create":
            required_create = {"year", "month", "day", "weather"}
            missing = [k for k in required_create if k not in provided_fields]
            if missing:
                raise ValueError(f"Missing required create fields: {', '.join(missing)}")
            return self.service.create_calendar_weather(
                calendar_id=calendar_id, payload=dict(provided_fields)
            )

        if action == "update":
            if calendar_weather_id is None:
                raise ValueError("`calendar_weather_id` is required for update.")
            if not provided_fields:
                raise ValueError("No update fields provided.")
            return self.service.update_calendar_weather(
                calendar_id=calendar_id,
                calendar_weather_id=calendar_weather_id,
                payload=dict(provided_fields),
            )

        if action == "delete":
            if calendar_weather_id is None:
                raise ValueError("`calendar_weather_id` is required for delete.")
            return self.service.delete_calendar_weather(
                calendar_id=calendar_id,
                calendar_weather_id=calendar_weather_id,
            )

        raise ValueError(f"Unknown action: {action}")

    async def manage_calendars(
        self,
        action: str,
        calendar_id: int | None = None,
        page: int = 1,
        limit: int = 15,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage calendars (list/create/update/delete)."""
        action = action.lower()

        calendar_fields = {
            "name",
            "month_name",
            "month_length",
            "weekday",
            "suffix",
            "current_year",
            "current_month",
            "current_day",
            "has_leap_year",
            "skip_year_zero",
            "format",
        }
        provided_fields = {
            k: v for k, v in fields.items() if k in calendar_fields and v is not None
        }

        if action == "list":
            return self.service.list_calendars(page=page, limit=limit)

        if action == "create":
            if "name" not in provided_fields:
                raise ValueError("Missing required create field: name")
            return self.service.create_calendar(payload=dict(provided_fields))

        if action == "update":
            if calendar_id is None:
                raise ValueError("`calendar_id` is required for update.")
            if not provided_fields:
                raise ValueError("No update fields provided.")
            return self.service.update_calendar(
                calendar_id=calendar_id,
                payload=dict(provided_fields),
            )

        if action == "delete":
            if calendar_id is None:
                raise ValueError("`calendar_id` is required for delete.")
            return self.service.delete_calendar(calendar_id=calendar_id)

        raise ValueError(f"Unknown action: {action}")

    async def manage_calendar_events(
        self,
        action: str,
        calendar_id: int,
        calendar_event_id: int | None = None,
        entity_id: int | None = None,
        page: int = 1,
        limit: int = 15,
        fetch_all: bool = False,
        **fields: Any,
    ) -> dict[str, Any]:
        """Manage calendar reminders (list/create/update/delete)."""
        action = action.lower()
        reminder_fields = {
            "name",
            "day",
            "month",
            "year",
            "length",
            "calendar_id",
            "colour",
            "comment",
            "is_recurring",
            "recurring_periodicity",
            "recurring_until",
            "type_id",
            "visibility_id",
        }
        provided_fields = {
            k: v for k, v in fields.items() if k in reminder_fields and v is not None
        }

        if action == "list":
            if fetch_all:
                return self.service.list_calendar_events_all(
                    calendar_id=calendar_id, limit=limit
                )
            return self.service.list_calendar_events(
                calendar_id=calendar_id, page=page, limit=limit
            )

        if entity_id is None:
            raise ValueError("`entity_id` is required for create/update/delete.")

        if action == "create":
            # Keep backward compatibility: top-level calendar_id can satisfy required payload field.
            provided_fields.setdefault("calendar_id", calendar_id)
            required_create = {"name", "day", "month", "year", "length", "calendar_id"}
            missing = [k for k in required_create if k not in provided_fields]
            if missing:
                raise ValueError(
                    f"Missing required create fields: {', '.join(missing)}"
                )
            return self.service.create_entity_reminder(
                entity_id=entity_id, payload=dict(provided_fields)
            )

        if action == "update":
            if calendar_event_id is None:
                raise ValueError("`calendar_event_id` is required for update.")
            if not provided_fields:
                raise ValueError("No update fields provided.")
            return self.service.update_entity_reminder(
                entity_id=entity_id,
                reminder_id=calendar_event_id,
                payload=dict(provided_fields),
            )

        if action == "delete":
            if calendar_event_id is None:
                raise ValueError("`calendar_event_id` is required for delete.")
            return self.service.delete_entity_reminder(
                entity_id=entity_id, reminder_id=calendar_event_id
            )

        raise ValueError(f"Unknown action: {action}")

    async def calendar_advance_date(self, calendar_id: int) -> dict[str, Any]:
        """Advance the calendar date by one day."""
        return self.service.calendar_advance_date(calendar_id=calendar_id)

    async def calendar_retreat_date(self, calendar_id: int) -> dict[str, Any]:
        """Retreat the calendar date by one day."""
        return self.service.calendar_retreat_date(calendar_id=calendar_id)

    async def check_entity_updates(
        self, entity_ids: list[int], last_synced: str
    ) -> CheckEntityUpdatesResult:
        """Check which entities have been modified since last sync.

        Args:
            entity_ids: List of entity IDs to check
            last_synced: ISO timestamp of last sync

        Returns:
            Result containing modified and deleted entity IDs
        """
        if not last_synced:
            raise ValueError("last_synced parameter is required")

        modified_entity_ids = []
        deleted_entity_ids = []

        try:
            # Get all entities using the entities endpoint
            # This is more efficient than checking each entity individually
            page = 1
            all_entities = {}

            while page <= 20:  # Reasonable limit to avoid infinite loops
                batch = self.service.client.entities(page=page, limit=100)
                if not batch:
                    break

                for entity_data in batch:
                    entity_id = entity_data.get("id")
                    if entity_id:
                        all_entities[entity_id] = entity_data

                if len(batch) < 100:
                    break
                page += 1

            # Check each requested entity
            for entity_id in entity_ids:
                if entity_id in all_entities:
                    entity_data = all_entities[entity_id]
                    updated_at = entity_data.get("updated_at")

                    if updated_at and updated_at > last_synced:
                        modified_entity_ids.append(entity_id)
                else:
                    # Entity not found - might be deleted
                    deleted_entity_ids.append(entity_id)

            # Get current timestamp
            check_timestamp = datetime.now(timezone.utc).isoformat()

            return {
                "modified_entity_ids": modified_entity_ids,
                "deleted_entity_ids": deleted_entity_ids,
                "check_timestamp": check_timestamp,
            }

        except Exception as e:
            logger.error(f"Check entity updates failed: {e}")
            raise

    _MIGRATION_ALLOWED_OPS = frozenset(
        {
            "update_map_marker",
            "update_calendar_event",
            "create_reminder",
            "delete_entity",
            "update_entity",
            "create_entity",
            "create_post",
            "remove_entity_tags_by_tag_id",
            "sleep_ms",
        }
    )

    async def run_migration_plan(
        self,
        steps: list[dict[str, Any]],
        *,
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        """Run a whitelisted multi-step plan (same sequencing guarantees as a hand script).

        This is not arbitrary code execution: only known operations are allowed.
        Use this for repeatable region/tag migrations, marker repoints, and ordered deletes.

        Step shapes::

            {"op": "update_map_marker", "map_id": int, "marker_id": int, "fields": {...}}
            {"op": "update_calendar_event", "calendar_id": int, "calendar_event_id": int, "fields": {...}}
            {"op": "create_reminder", "entity_id": int, "fields": {...}}
            {"op": "delete_entity", "entity_id": int}
            {"op": "update_entity", "entity_id": int, "fields": {"location_id": ..., "name": ..., ...}}
            {"op": "create_entity", "fields": {"entity_type": str, "name": str, ...}}
            {"op": "create_post", "fields": {"entity_id": int, "name": str, ...}}
            {"op": "remove_entity_tags_by_tag_id", "entity_id": int, "tag_id": int}
            {"op": "sleep_ms", "ms": int}

        ``update_map_marker`` ``fields`` are passed to :meth:`KankaService.update_map_marker`
        (including ``entity_id: null`` to clear links; name is merged automatically).
        """
        results: list[dict[str, Any]] = []

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                err = {
                    "step": i,
                    "op": None,
                    "success": False,
                    "error": "step must be an object",
                }
                results.append(err)
                if stop_on_error:
                    return {
                        "success": False,
                        "stopped_at": i,
                        "results": results,
                    }
                continue

            op = str(step.get("op", "")).strip().lower()
            if op not in self._MIGRATION_ALLOWED_OPS:
                err = {
                    "step": i,
                    "op": op or None,
                    "success": False,
                    "error": (
                        f"unknown or disallowed op (allowed: {sorted(self._MIGRATION_ALLOWED_OPS)}). "
                        "For create workflows, use `create_entity` or `create_post`."
                    ),
                }
                results.append(err)
                if stop_on_error:
                    return {
                        "success": False,
                        "stopped_at": i,
                        "results": results,
                    }
                continue

            try:
                if op == "sleep_ms":
                    ms = int(step.get("ms", step.get("sleep_ms", 0)))
                    if ms > 0:
                        await asyncio.sleep(ms / 1000.0)
                    results.append({"step": i, "op": op, "success": True})
                elif op == "update_map_marker":
                    map_id = int(step["map_id"])
                    marker_id = int(step["marker_id"])
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError("`fields` must be an object for update_map_marker")
                    data = self.service.update_map_marker(map_id, marker_id, fields)
                    results.append(
                        {"step": i, "op": op, "success": True, "data": data}
                    )
                elif op == "update_calendar_event":
                    calendar_id = int(step["calendar_id"])
                    calendar_event_id = int(step["calendar_event_id"])
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError(
                            "`fields` must be an object for update_calendar_event"
                        )
                    data = self.service.update_calendar_event(
                        calendar_id=calendar_id,
                        calendar_event_id=calendar_event_id,
                        payload=fields,
                    )
                    results.append(
                        {"step": i, "op": op, "success": True, "data": data}
                    )
                elif op == "create_reminder":
                    entity_id = int(step["entity_id"])
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError("`fields` must be an object for create_reminder")
                    required = {"name", "day", "month", "year", "length", "calendar_id"}
                    missing = [k for k in required if k not in fields]
                    if missing:
                        raise ValueError(
                            f"create_reminder missing required fields: {', '.join(missing)}"
                        )
                    payload = {
                        k: v
                        for k, v in fields.items()
                        if k
                        in {
                            "name",
                            "day",
                            "month",
                            "year",
                            "length",
                            "calendar_id",
                            "colour",
                            "comment",
                            "is_recurring",
                            "recurring_periodicity",
                            "recurring_until",
                            "type_id",
                            "visibility_id",
                        }
                        and v is not None
                    }
                    data = self.service.create_entity_reminder(
                        entity_id=entity_id, payload=payload
                    )
                    results.append(
                        {"step": i, "op": op, "success": True, "data": data}
                    )
                elif op == "delete_entity":
                    entity_id = int(step["entity_id"])
                    ok = self.service.delete_entity(entity_id)
                    results.append(
                        {"step": i, "op": op, "success": ok, "entity_id": entity_id}
                    )
                elif op == "update_entity":
                    entity_id = int(step["entity_id"])
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError("`fields` must be an object for update_entity")
                    ok = self.service.update_entity(
                        entity_id,
                        name=fields.get("name"),
                        type=fields.get("type"),
                        entry=fields.get("entry"),
                        tags=fields.get("tags"),
                        is_hidden=fields.get("is_hidden"),
                        parent_id=fields.get("parent_id"),
                        parent_id_set=("parent_id" in fields),
                        location_id=fields.get("location_id"),
                        parent_location_id=fields.get("parent_location_id"),
                        status=fields.get("status"),
                        title=fields.get("title"),
                        age=fields.get("age"),
                        sex=fields.get("sex"),
                        pronouns=fields.get("pronouns"),
                        race_id=fields.get("race_id"),
                        family_id=fields.get("family_id"),
                        is_dead=fields.get("is_dead"),
                        is_map_private=fields.get("is_map_private"),
                        creature_id=fields.get("creature_id"),
                        is_extinct=fields.get("is_extinct"),
                        locations=fields.get("locations"),
                        note_id=fields.get("note_id"),
                        is_pinned=fields.get("is_pinned"),
                        journal_id=fields.get("journal_id"),
                        date=fields.get("date"),
                        character_id=fields.get("character_id"),
                        quest_id=fields.get("quest_id"),
                        ability_id=fields.get("ability_id"),
                        charges=fields.get("charges"),
                        organisation_id=fields.get("organisation_id"),
                        is_defunct=fields.get("is_defunct"),
                        map_id=fields.get("map_id"),
                        is_real=fields.get("is_real"),
                        is_completed=fields.get("is_completed"),
                        image_uuid=fields.get("image_uuid"),
                        header_uuid=fields.get("header_uuid"),
                        event_parent_id=fields.get("event_parent_id"),
                        event_parent_id_set=("event_parent_id" in fields),
                        event_locations=fields.get("event_locations"),
                        calendar_id=fields.get("calendar_id"),
                        calendar_id_set=("calendar_id" in fields),
                        calendar_year=fields.get("calendar_year"),
                        calendar_month=fields.get("calendar_month"),
                        calendar_day=fields.get("calendar_day"),
                        icon=fields.get("icon"),
                        colour=fields.get("colour"),
                    )
                    results.append(
                        {
                            "step": i,
                            "op": op,
                            "success": ok,
                            "entity_id": entity_id,
                        }
                    )
                elif op == "create_entity":
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError("`fields` must be an object for create_entity")
                    if not fields.get("entity_type") or not fields.get("name"):
                        raise ValueError(
                            "create_entity requires `fields.entity_type` and `fields.name`"
                        )
                    data = self.service.create_entity(
                        entity_type=fields["entity_type"],
                        name=fields["name"],
                        type=fields.get("type"),
                        entry=fields.get("entry"),
                        tags=fields.get("tags"),
                        is_hidden=fields.get("is_hidden"),
                        parent_id=fields.get("parent_id"),
                        location_id=fields.get("location_id"),
                        parent_location_id=fields.get("parent_location_id"),
                        status=fields.get("status"),
                        title=fields.get("title"),
                        age=fields.get("age"),
                        sex=fields.get("sex"),
                        pronouns=fields.get("pronouns"),
                        race_id=fields.get("race_id"),
                        family_id=fields.get("family_id"),
                        is_dead=fields.get("is_dead"),
                        is_map_private=fields.get("is_map_private"),
                        creature_id=fields.get("creature_id"),
                        is_extinct=fields.get("is_extinct"),
                        locations=fields.get("locations"),
                        note_id=fields.get("note_id"),
                        is_pinned=fields.get("is_pinned"),
                        journal_id=fields.get("journal_id"),
                        date=fields.get("date"),
                        character_id=fields.get("character_id"),
                        quest_id=fields.get("quest_id"),
                        ability_id=fields.get("ability_id"),
                        charges=fields.get("charges"),
                        organisation_id=fields.get("organisation_id"),
                        is_defunct=fields.get("is_defunct"),
                        map_id=fields.get("map_id"),
                        is_real=fields.get("is_real"),
                        is_completed=fields.get("is_completed"),
                        image_uuid=fields.get("image_uuid"),
                        header_uuid=fields.get("header_uuid"),
                        calendar_id=fields.get("calendar_id"),
                        calendar_year=fields.get("calendar_year"),
                        calendar_month=fields.get("calendar_month"),
                        calendar_day=fields.get("calendar_day"),
                        event_parent_id=fields.get("event_parent_id"),
                        event_locations=fields.get("event_locations"),
                        icon=fields.get("icon"),
                        colour=fields.get("colour"),
                    )
                    results.append({"step": i, "op": op, "success": True, "data": data})
                elif op == "create_post":
                    fields = step.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError("`fields` must be an object for create_post")
                    if fields.get("entity_id") is None or not fields.get("name"):
                        raise ValueError(
                            "create_post requires `fields.entity_id` and `fields.name`"
                        )
                    data = self.service.create_post(
                        entity_id=int(fields["entity_id"]),
                        name=fields["name"],
                        entry=fields.get("entry"),
                        is_hidden=fields.get("is_hidden"),
                    )
                    results.append({"step": i, "op": op, "success": True, "data": data})
                elif op == "remove_entity_tags_by_tag_id":
                    entity_id = int(step["entity_id"])
                    tag_id = int(step["tag_id"])
                    resp = self.service.list_entity_tags(entity_id)
                    rows = (
                        resp.get("data")
                        if isinstance(resp.get("data"), list)
                        else []
                    )
                    removed: list[int] = []
                    for row in rows:
                        if row.get("tag_id") == tag_id and row.get("id"):
                            self.service.remove_entity_tag(
                                entity_id, int(row["id"])
                            )
                            removed.append(int(row["id"]))
                    results.append(
                        {
                            "step": i,
                            "op": op,
                            "success": True,
                            "removed_entity_tag_ids": removed,
                        }
                    )
            except Exception as e:
                logger.error("Migration step %s (%s) failed: %s", i, op, e)
                results.append(
                    {"step": i, "op": op, "success": False, "error": str(e)}
                )
                if stop_on_error:
                    return {
                        "success": False,
                        "stopped_at": i,
                        "results": results,
                    }

        return {"success": True, "stopped_at": None, "results": results}


# Global instance management
_operations: KankaOperations | None = None


def get_operations() -> KankaOperations:
    """Get or create the singleton operations instance.

    Returns:
        The global KankaOperations instance
    """
    global _operations
    if _operations is None:
        _operations = KankaOperations(service=get_service())
    return _operations


def create_operations(service: KankaService | None = None) -> KankaOperations:
    """Create a new operations instance for external use.

    This is useful for scripts that want to manage their own instances
    or provide a custom service configuration.

    Args:
        service: Optional KankaService instance

    Returns:
        A new KankaOperations instance
    """
    return KankaOperations(service)
