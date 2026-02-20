"""High-level operations layer for Kanka functionality.

This module provides a reusable operations layer that can be used by both
MCP tools and external scripts, ensuring consistent behavior and type safety.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .service import KankaService, get_service
from .types import (
    CheckEntityUpdatesResult,
    CreateEntityResult,
    CreatePostResult,
    DeleteEntityResult,
    DeletePostResult,
    EntityType,
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

VALID_ENTITY_TYPES: list[EntityType] = [
    "calendar",
    "character",
    "creature",
    "event",
    "family",
    "item",
    "location",
    "map",
    "organization",
    "race",
    "note",
    "journal",
    "quest",
    "tag",
    "timeline",
]

# Fields that get forwarded as **extra_fields to service.create_entity / update_entity
_EXTRA_FIELD_KEYS = [
    "location_id",
    "title",
    "age",
    "sex",
    "pronouns",
    "is_dead",
    "races",
    "families",
    "is_defunct",
    "date",
    "character_id",
    "is_extinct",
    "creator_id",
    "price",
    "size",
    "weight",
    "colour",
    "center_marker_id",
    "center_x",
    "center_y",
    "is_real",
    "date",
    "calendar_id",
    "calendar_year",
    "calendar_month",
    "calendar_day",
    # Calendar structural (months, weekdays; moons skipped - add via Kanka UI)
    "weekday",
    "weekdays",
    "months",
    "month_name",
    "month_length",
    "month_type",
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
]


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
        self.service = service or KankaService()

    # ---- Helper to extract extra entity-specific fields ----

    @staticmethod
    def _extract_extra_fields(data: dict[str, Any]) -> dict[str, Any]:
        """Pull entity-specific optional fields out of a flat dict."""
        return {
            k: data[k] for k in _EXTRA_FIELD_KEYS if k in data and data[k] is not None
        }

    # ---- Entity operations ----

    async def find_entities(
        self,
        query: str | None = None,
        entity_type: str | None = None,
        name: str | None = None,
        name_exact: bool = False,
        name_fuzzy: bool = False,
        type: str | None = None,
        tags: list[str] | None = None,
        date_range: dict[str, str] | None = None,
        include_full: bool = True,
        page: int = 1,
        limit: int = 25,
        last_synced: str | None = None,
    ) -> dict[str, Any]:
        """Find entities with search and filtering capabilities."""
        if entity_type and entity_type not in VALID_ENTITY_TYPES:
            logger.error(
                f"Invalid entity_type: {entity_type}. "
                f"Must be one of: {', '.join(VALID_ENTITY_TYPES)}"
            )
            return {"entities": [], "sync_info": {}}

        try:
            if query:
                entities = []
                if entity_type:
                    from typing import cast

                    entity_objects = self.service.list_entities(
                        cast(EntityType, entity_type),
                        page=1,
                        limit=0,
                        last_sync=last_synced,
                        related=include_full,
                    )
                    for obj in entity_objects:
                        entities.append(self.service._entity_to_dict(obj, entity_type))
                else:
                    for et in VALID_ENTITY_TYPES:
                        try:
                            entity_objects = self.service.list_entities(
                                et,
                                page=1,
                                limit=0,
                                last_sync=last_synced,
                                related=include_full,
                            )
                            for obj in entity_objects:
                                entities.append(self.service._entity_to_dict(obj, et))
                        except Exception as e:
                            logger.debug(f"Could not search {et}: {e}")
                            continue

                entities = search_in_content(entities, query)

                if not include_full:
                    entities = [
                        {
                            "entity_id": e["entity_id"],
                            "name": e["name"],
                            "entity_type": e["entity_type"],
                        }
                        for e in entities
                    ]
            else:
                if not entity_type:
                    return {"entities": [], "sync_info": {}}

                from typing import cast

                entity_objects = self.service.list_entities(
                    cast(EntityType, entity_type),
                    page=1,
                    limit=0,
                    last_sync=last_synced,
                    related=include_full,
                )
                entities = [
                    self.service._entity_to_dict(obj, entity_type)
                    for obj in entity_objects
                ]

            # Client-side filters
            if name:
                entities = filter_entities_by_name(
                    entities, name, exact=name_exact, fuzzy=name_fuzzy
                )
            if type:
                entities = filter_entities_by_type(entities, type)
            if tags:
                entities = filter_entities_by_tags(entities, tags)
            if date_range and entity_type == "journal":
                start = date_range.get("start")
                end = date_range.get("end")
                if start and end:
                    entities = filter_journals_by_date_range(entities, start, end)

            paginated, total_pages, total_items = paginate_results(
                entities, page, limit
            )

            newest_updated_at = None
            for entity in paginated:
                if entity.get("updated_at") and (
                    newest_updated_at is None
                    or entity["updated_at"] > newest_updated_at
                ):
                    newest_updated_at = entity["updated_at"]

            sync_info = {
                "request_timestamp": datetime.now(timezone.utc).isoformat(),
                "newest_updated_at": newest_updated_at,
                "total_count": total_items,
                "returned_count": len(paginated),
            }

            if not include_full:
                formatted_entities = [
                    {
                        "entity_id": e["entity_id"],
                        "name": e["name"],
                        "entity_type": e["entity_type"],
                    }
                    for e in paginated
                ]
            else:
                formatted_entities = paginated

            return {
                "entities": formatted_entities,
                "sync_info": sync_info,
            }

        except Exception as e:
            logger.error(f"find_entities failed: {e}")
            raise

    async def create_entities(
        self, entities: list[dict[str, Any]]
    ) -> list[CreateEntityResult]:
        """Create one or more entities."""
        results: list[CreateEntityResult] = []

        for entity_input in entities:
            entity_type = entity_input.get("entity_type")
            entity_name = entity_input.get("name", "")

            if not entity_type or entity_type not in VALID_ENTITY_TYPES:
                results.append(
                    {
                        "id": None,
                        "entity_id": None,
                        "name": entity_name,
                        "mention": None,
                        "success": False,
                        "error": (
                            f"Invalid entity_type '{entity_type}'. "
                            f"Must be one of: {', '.join(VALID_ENTITY_TYPES)}"
                        ),
                    }
                )
                continue

            if not entity_name:
                results.append(
                    {
                        "id": None,
                        "entity_id": None,
                        "name": "",
                        "mention": None,
                        "success": False,
                        "error": "Name is required",
                    }
                )
                continue

            # Extract reminder (birth/death/founded) for age calc - not passed to create_entity
            reminder = entity_input.get("reminder")
            if reminder and entity_type not in (
                "character",
                "location",
                "organization",
                "family",
            ):
                reminder = None  # Only these entity types support age reminders
            extra = self._extract_extra_fields(entity_input)
            if reminder:
                extra = {k: v for k, v in extra.items() if k != "reminder"}

            try:
                created = self.service.create_entity(
                    entity_type=entity_type,
                    name=entity_name,
                    type=entity_input.get("type"),
                    entry=entity_input.get("entry"),
                    tags=entity_input.get("tags"),
                    is_hidden=entity_input.get("is_hidden"),
                    is_completed=entity_input.get("is_completed"),
                    image_uuid=entity_input.get("image_uuid"),
                    header_uuid=entity_input.get("header_uuid"),
                    parent_id=entity_input.get("parent_id"),
                    **extra,
                )
                result_entry = {
                    "id": created["id"],
                    "entity_id": created["entity_id"],
                    "name": created["name"],
                    "mention": created.get("mention"),
                    "success": True,
                    "error": None,
                }

                # Add reminder (birth/death/founded) for age calculation
                if reminder and created.get("entity_id"):
                    event_type = reminder.get("type", "birth")
                    try:
                        self.service.create_calendar_reminder(
                            entity_id=created["entity_id"],
                            calendar_id=reminder["calendar_id"],
                            year=reminder["year"],
                            month=reminder["month"],
                            day=reminder["day"],
                            length=1,
                            event_type=event_type,
                        )
                        result_entry["reminder_added"] = True
                    except Exception as r_err:
                        logger.warning(
                            f"Failed to add reminder for {created['entity_id']}: {r_err}"
                        )
                        result_entry["reminder_added"] = False
                        result_entry["reminder_error"] = str(r_err)

                results.append(result_entry)

            except Exception as e:
                logger.error(f"Failed to create entity '{entity_name}': {e}")
                results.append(
                    {
                        "id": None,
                        "entity_id": None,
                        "name": entity_name,
                        "mention": None,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    async def update_entities(
        self, updates: list[dict[str, Any]]
    ) -> list[UpdateEntityResult]:
        """Update one or more entities."""
        results: list[UpdateEntityResult] = []

        for update in updates:
            entity_id = update.get("entity_id")
            name = update.get("name")

            if not entity_id:
                results.append(
                    {"entity_id": 0, "success": False, "error": "entity_id is required"}
                )
                continue

            if not name:
                results.append(
                    {
                        "entity_id": entity_id,
                        "success": False,
                        "error": "name is required for updates (Kanka API requirement)",
                    }
                )
                continue

            try:
                success = self.service.update_entity(
                    entity_id=entity_id,
                    name=name,
                    type=update.get("type"),
                    entry=update.get("entry"),
                    tags=update.get("tags"),
                    is_hidden=update.get("is_hidden"),
                    is_completed=update.get("is_completed"),
                    image_uuid=update.get("image_uuid"),
                    header_uuid=update.get("header_uuid"),
                    parent_id=update.get("parent_id"),
                    **self._extract_extra_fields(update),
                )
                results.append(
                    {"entity_id": entity_id, "success": success, "error": None}
                )

            except Exception as e:
                logger.error(f"Failed to update entity {entity_id}: {e}")
                results.append(
                    {"entity_id": entity_id, "success": False, "error": str(e)}
                )

        return results

    async def get_entities(
        self, entity_ids: list[int], include_posts: bool = False
    ) -> list[GetEntityResult]:
        """Get specific entities by ID."""
        results: list[GetEntityResult] = []

        for entity_id in entity_ids:
            try:
                entity = self.service.get_entity_by_id(entity_id, include_posts)

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
                        "parent_id": entity.get("parent_id"),
                        "image": entity.get("image"),
                        "image_full": entity.get("image_full"),
                        "image_thumb": entity.get("image_thumb"),
                        "image_uuid": entity.get("image_uuid"),
                        "header_uuid": entity.get("header_uuid"),
                    }

                    # Forward all entity-specific fields present in the dict
                    for key in _EXTRA_FIELD_KEYS:
                        if key in entity:
                            result[key] = entity[key]  # type: ignore[literal-required]

                    # Quest-specific
                    if entity.get("entity_type") == "quest":
                        result["is_completed"] = entity.get("is_completed")

                    if include_posts:
                        result["posts"] = entity.get("posts", [])

                    results.append(result)
                else:
                    results.append(
                        {
                            "entity_id": entity_id,
                            "success": False,
                            "error": f"Entity {entity_id} not found",
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to get entity {entity_id}: {e}")
                results.append(
                    {"entity_id": entity_id, "success": False, "error": str(e)}
                )

        return results

    async def delete_entities(self, entity_ids: list[int]) -> list[DeleteEntityResult]:
        """Delete one or more entities."""
        results: list[DeleteEntityResult] = []

        for entity_id in entity_ids:
            try:
                success = self.service.delete_entity(entity_id)
                results.append(
                    {"entity_id": entity_id, "success": success, "error": None}
                )
            except Exception as e:
                logger.error(f"Failed to delete entity {entity_id}: {e}")
                results.append(
                    {"entity_id": entity_id, "success": False, "error": str(e)}
                )

        return results

    # ---- Post operations ----

    async def create_posts(self, posts: list[dict[str, Any]]) -> list[CreatePostResult]:
        """Create posts on entities."""
        results: list[CreatePostResult] = []

        for post_input in posts:
            try:
                created = self.service.create_post(
                    entity_id=post_input["entity_id"],
                    name=post_input["name"],
                    entry=post_input.get("entry"),
                    is_hidden=post_input.get("is_hidden", False),
                )
                results.append(
                    {
                        "post_id": created["post_id"],
                        "entity_id": created["entity_id"],
                        "success": True,
                        "error": None,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to create post on entity {post_input['entity_id']}: {e}"
                )
                results.append(
                    {
                        "post_id": None,
                        "entity_id": post_input["entity_id"],
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    async def update_posts(
        self, updates: list[dict[str, Any]]
    ) -> list[UpdatePostResult]:
        """Update existing posts."""
        results: list[UpdatePostResult] = []

        for update in updates:
            try:
                success = self.service.update_post(
                    entity_id=update["entity_id"],
                    post_id=update["post_id"],
                    name=update["name"],
                    entry=update.get("entry"),
                    is_hidden=update.get("is_hidden"),
                )
                results.append(
                    {
                        "entity_id": update["entity_id"],
                        "post_id": update["post_id"],
                        "success": success,
                        "error": None,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to update post {update['post_id']} on entity {update['entity_id']}: {e}"
                )
                results.append(
                    {
                        "entity_id": update["entity_id"],
                        "post_id": update["post_id"],
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    async def delete_posts(
        self, deletions: list[dict[str, Any]]
    ) -> list[DeletePostResult]:
        """Delete posts from entities."""
        results: list[DeletePostResult] = []

        for deletion in deletions:
            try:
                success = self.service.delete_post(
                    entity_id=deletion["entity_id"],
                    post_id=deletion["post_id"],
                )
                results.append(
                    {
                        "entity_id": deletion["entity_id"],
                        "post_id": deletion["post_id"],
                        "success": success,
                        "error": None,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to delete post {deletion['post_id']} from entity {deletion['entity_id']}: {e}"
                )
                results.append(
                    {
                        "entity_id": deletion["entity_id"],
                        "post_id": deletion["post_id"],
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Relations ----

    async def manage_relations(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of relation actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            entity_id = action_input.get("entity_id")

            if not entity_id:
                results.append(
                    {
                        "action": action,
                        "entity_id": 0,
                        "success": False,
                        "error": "entity_id is required",
                    }
                )
                continue

            try:
                if action == "list":
                    relations = self.service.list_relations(entity_id)
                    results.append(
                        {
                            "action": "list",
                            "entity_id": entity_id,
                            "success": True,
                            "error": None,
                            "relations": relations,
                        }
                    )

                elif action == "create":
                    target_id = action_input.get("target_id")
                    relation_label = action_input.get("relation")
                    if not target_id or not relation_label:
                        results.append(
                            {
                                "action": "create",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "target_id and relation are required",
                            }
                        )
                        continue

                    rel = self.service.create_relation(
                        entity_id=entity_id,
                        target_id=target_id,
                        relation=relation_label,
                        attitude=action_input.get("attitude"),
                        two_way=action_input.get("two_way"),
                        colour=action_input.get("colour"),
                        is_pinned=action_input.get("is_pinned"),
                        is_hidden=action_input.get("is_hidden"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "entity_id": entity_id,
                            "relation_id": rel.get("id"),
                            "success": True,
                            "error": None,
                            "relation": rel,
                        }
                    )

                elif action == "update":
                    relation_id = action_input.get("relation_id")
                    if not relation_id:
                        results.append(
                            {
                                "action": "update",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "relation_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "relation",
                            "target_id",
                            "attitude",
                            "two_way",
                            "colour",
                            "is_pinned",
                            "is_hidden",
                        )
                        if k in action_input
                    }
                    rel = self.service.update_relation(entity_id, relation_id, **fields)
                    results.append(
                        {
                            "action": "update",
                            "entity_id": entity_id,
                            "relation_id": relation_id,
                            "success": True,
                            "error": None,
                            "relation": rel,
                        }
                    )

                elif action == "delete":
                    relation_id = action_input.get("relation_id")
                    if not relation_id:
                        results.append(
                            {
                                "action": "delete",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "relation_id is required",
                            }
                        )
                        continue
                    self.service.delete_relation(entity_id, relation_id)
                    results.append(
                        {
                            "action": "delete",
                            "entity_id": entity_id,
                            "relation_id": relation_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "entity_id": entity_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Relation action '{action}' failed for entity {entity_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "entity_id": entity_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Attributes ----

    async def manage_attributes(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of attribute actions (create/update/delete/list/bulk_patch)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            entity_id = action_input.get("entity_id")

            if not entity_id:
                results.append(
                    {
                        "action": action,
                        "entity_id": 0,
                        "success": False,
                        "error": "entity_id is required",
                    }
                )
                continue

            try:
                if action == "list":
                    attrs = self.service.list_attributes(entity_id)
                    results.append(
                        {
                            "action": "list",
                            "entity_id": entity_id,
                            "success": True,
                            "error": None,
                            "attributes": attrs,
                        }
                    )

                elif action == "create":
                    attr_name = action_input.get("name")
                    if not attr_name:
                        results.append(
                            {
                                "action": "create",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "name is required",
                            }
                        )
                        continue
                    attr = self.service.create_attribute(
                        entity_id=entity_id,
                        name=attr_name,
                        value=action_input.get("value"),
                        type_id=action_input.get("type_id"),
                        is_pinned=action_input.get("is_pinned"),
                        is_hidden=action_input.get("is_hidden"),
                        api_key=action_input.get("api_key"),
                        default_order=action_input.get("default_order"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "entity_id": entity_id,
                            "attribute_id": attr.get("id"),
                            "success": True,
                            "error": None,
                            "attribute": attr,
                        }
                    )

                elif action == "update":
                    attribute_id = action_input.get("attribute_id")
                    if not attribute_id:
                        results.append(
                            {
                                "action": "update",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "attribute_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "value",
                            "type_id",
                            "is_pinned",
                            "is_hidden",
                            "api_key",
                            "default_order",
                        )
                        if k in action_input
                    }
                    attr = self.service.update_attribute(
                        entity_id, attribute_id, **fields
                    )
                    results.append(
                        {
                            "action": "update",
                            "entity_id": entity_id,
                            "attribute_id": attribute_id,
                            "success": True,
                            "error": None,
                            "attribute": attr,
                        }
                    )

                elif action == "delete":
                    attribute_id = action_input.get("attribute_id")
                    if not attribute_id:
                        results.append(
                            {
                                "action": "delete",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "attribute_id is required",
                            }
                        )
                        continue
                    self.service.delete_attribute(entity_id, attribute_id)
                    results.append(
                        {
                            "action": "delete",
                            "entity_id": entity_id,
                            "attribute_id": attribute_id,
                            "success": True,
                            "error": None,
                        }
                    )

                elif action == "bulk_patch":
                    attributes = action_input.get("attributes", [])
                    if not attributes:
                        results.append(
                            {
                                "action": "bulk_patch",
                                "entity_id": entity_id,
                                "success": False,
                                "error": "attributes array is required",
                            }
                        )
                        continue
                    patched = self.service.bulk_patch_attributes(entity_id, attributes)
                    results.append(
                        {
                            "action": "bulk_patch",
                            "entity_id": entity_id,
                            "success": True,
                            "error": None,
                            "attributes": patched,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "entity_id": entity_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Attribute action '{action}' failed for entity {entity_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "entity_id": entity_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Organisation Members ----

    async def manage_organisation_members(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of organisation member actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            organisation_id = action_input.get("organisation_id")

            if not organisation_id:
                results.append(
                    {
                        "action": action,
                        "organisation_id": 0,
                        "success": False,
                        "error": "organisation_id is required",
                    }
                )
                continue

            try:
                if action == "list":
                    members = self.service.list_org_members(organisation_id)
                    results.append(
                        {
                            "action": "list",
                            "organisation_id": organisation_id,
                            "success": True,
                            "error": None,
                            "members": members,
                        }
                    )

                elif action == "create":
                    character_id = action_input.get("character_id")
                    if not character_id:
                        results.append(
                            {
                                "action": "create",
                                "organisation_id": organisation_id,
                                "success": False,
                                "error": "character_id is required",
                            }
                        )
                        continue
                    member = self.service.create_org_member(
                        organisation_id=organisation_id,
                        character_id=character_id,
                        role=action_input.get("role"),
                        is_hidden=action_input.get("is_hidden"),
                        status_id=action_input.get("status_id"),
                        parent_id=action_input.get("parent_id"),
                        pin_id=action_input.get("pin_id"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "organisation_id": organisation_id,
                            "member_id": member.get("id"),
                            "success": True,
                            "error": None,
                            "member": member,
                        }
                    )

                elif action == "update":
                    member_id = action_input.get("member_id")
                    if not member_id:
                        results.append(
                            {
                                "action": "update",
                                "organisation_id": organisation_id,
                                "success": False,
                                "error": "member_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "character_id",
                            "role",
                            "is_hidden",
                            "status_id",
                            "parent_id",
                            "pin_id",
                        )
                        if k in action_input
                    }
                    member = self.service.update_org_member(
                        organisation_id, member_id, **fields
                    )
                    results.append(
                        {
                            "action": "update",
                            "organisation_id": organisation_id,
                            "member_id": member_id,
                            "success": True,
                            "error": None,
                            "member": member,
                        }
                    )

                elif action == "delete":
                    member_id = action_input.get("member_id")
                    if not member_id:
                        results.append(
                            {
                                "action": "delete",
                                "organisation_id": organisation_id,
                                "success": False,
                                "error": "member_id is required",
                            }
                        )
                        continue
                    self.service.delete_org_member(organisation_id, member_id)
                    results.append(
                        {
                            "action": "delete",
                            "organisation_id": organisation_id,
                            "member_id": member_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "organisation_id": organisation_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Org member action '{action}' failed for org {organisation_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "organisation_id": organisation_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Map Markers ----

    async def manage_map_markers(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of map marker actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            map_id = action_input.get("map_id")

            if not map_id:
                results.append(
                    {
                        "action": action,
                        "map_id": 0,
                        "success": False,
                        "error": "map_id is required (map's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    markers = self.service.list_map_markers(map_id)
                    results.append(
                        {
                            "action": "list",
                            "map_id": map_id,
                            "success": True,
                            "error": None,
                            "markers": markers,
                        }
                    )

                elif action == "create":
                    marker = self.service.create_map_marker(
                        map_id=map_id,
                        name=action_input.get("name"),
                        entity_id=action_input.get("entity_id"),
                        latitude=action_input.get("latitude"),
                        longitude=action_input.get("longitude"),
                        shape_id=action_input.get("shape_id"),
                        icon=action_input.get("icon"),
                        group_id=action_input.get("group_id"),
                        is_draggable=action_input.get("is_draggable"),
                        is_hidden=action_input.get("is_hidden"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "map_id": map_id,
                            "marker_id": marker.get("id"),
                            "success": True,
                            "error": None,
                            "marker": marker,
                        }
                    )

                elif action == "update":
                    marker_id = action_input.get("marker_id")
                    if not marker_id:
                        results.append(
                            {
                                "action": "update",
                                "map_id": map_id,
                                "success": False,
                                "error": "marker_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "entity_id",
                            "latitude",
                            "longitude",
                            "shape_id",
                            "icon",
                            "group_id",
                            "is_draggable",
                            "is_hidden",
                        )
                        if k in action_input
                    }
                    marker = self.service.update_map_marker(map_id, marker_id, **fields)
                    results.append(
                        {
                            "action": "update",
                            "map_id": map_id,
                            "marker_id": marker_id,
                            "success": True,
                            "error": None,
                            "marker": marker,
                        }
                    )

                elif action == "delete":
                    marker_id = action_input.get("marker_id")
                    if not marker_id:
                        results.append(
                            {
                                "action": "delete",
                                "map_id": map_id,
                                "success": False,
                                "error": "marker_id is required",
                            }
                        )
                        continue
                    self.service.delete_map_marker(map_id, marker_id)
                    results.append(
                        {
                            "action": "delete",
                            "map_id": map_id,
                            "marker_id": marker_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "map_id": map_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Map marker action '{action}' failed for map {map_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "map_id": map_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Map Groups ----

    async def manage_map_groups(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of map group actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            map_id = action_input.get("map_id")

            if not map_id:
                results.append(
                    {
                        "action": action,
                        "map_id": 0,
                        "success": False,
                        "error": "map_id is required (map's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    groups = self.service.list_map_groups(map_id)
                    results.append(
                        {
                            "action": "list",
                            "map_id": map_id,
                            "success": True,
                            "error": None,
                            "groups": groups,
                        }
                    )

                elif action == "create":
                    name = action_input.get("name")
                    if not name:
                        results.append(
                            {
                                "action": "create",
                                "map_id": map_id,
                                "success": False,
                                "error": "name is required",
                            }
                        )
                        continue
                    group = self.service.create_map_group(
                        map_id=map_id,
                        name=name,
                        parent_id=action_input.get("parent_id"),
                        is_shown=action_input.get("is_shown"),
                        position=action_input.get("position"),
                        is_hidden=action_input.get("is_hidden"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "map_id": map_id,
                            "group_id": group.get("id"),
                            "success": True,
                            "error": None,
                            "group": group,
                        }
                    )

                elif action == "update":
                    group_id = action_input.get("group_id")
                    if not group_id:
                        results.append(
                            {
                                "action": "update",
                                "map_id": map_id,
                                "success": False,
                                "error": "group_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "parent_id",
                            "is_shown",
                            "position",
                            "is_hidden",
                        )
                        if k in action_input
                    }
                    group = self.service.update_map_group(map_id, group_id, **fields)
                    results.append(
                        {
                            "action": "update",
                            "map_id": map_id,
                            "group_id": group_id,
                            "success": True,
                            "error": None,
                            "group": group,
                        }
                    )

                elif action == "delete":
                    group_id = action_input.get("group_id")
                    if not group_id:
                        results.append(
                            {
                                "action": "delete",
                                "map_id": map_id,
                                "success": False,
                                "error": "group_id is required",
                            }
                        )
                        continue
                    self.service.delete_map_group(map_id, group_id)
                    results.append(
                        {
                            "action": "delete",
                            "map_id": map_id,
                            "group_id": group_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "map_id": map_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Map group action '{action}' failed for map {map_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "map_id": map_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Map Layers ----

    async def manage_map_layers(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute a batch of map layer actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            map_id = action_input.get("map_id")

            if not map_id:
                results.append(
                    {
                        "action": action,
                        "map_id": 0,
                        "success": False,
                        "error": "map_id is required (map's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    layers = self.service.list_map_layers(map_id)
                    results.append(
                        {
                            "action": "list",
                            "map_id": map_id,
                            "success": True,
                            "error": None,
                            "layers": layers,
                        }
                    )

                elif action == "create":
                    name = action_input.get("name")
                    if not name:
                        results.append(
                            {
                                "action": "create",
                                "map_id": map_id,
                                "success": False,
                                "error": "name is required",
                            }
                        )
                        continue
                    layer = self.service.create_map_layer(
                        map_id=map_id,
                        name=name,
                        image_url=action_input.get("image_url"),
                        entry=action_input.get("entry"),
                        type_id=action_input.get("type_id"),
                        position=action_input.get("position"),
                        is_hidden=action_input.get("is_hidden"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "map_id": map_id,
                            "layer_id": layer.get("id"),
                            "success": True,
                            "error": None,
                            "layer": layer,
                        }
                    )

                elif action == "update":
                    layer_id = action_input.get("layer_id")
                    if not layer_id:
                        results.append(
                            {
                                "action": "update",
                                "map_id": map_id,
                                "success": False,
                                "error": "layer_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "image_url",
                            "entry",
                            "type_id",
                            "position",
                            "is_hidden",
                        )
                        if k in action_input
                    }
                    layer = self.service.update_map_layer(map_id, layer_id, **fields)
                    results.append(
                        {
                            "action": "update",
                            "map_id": map_id,
                            "layer_id": layer_id,
                            "success": True,
                            "error": None,
                            "layer": layer,
                        }
                    )

                elif action == "delete":
                    layer_id = action_input.get("layer_id")
                    if not layer_id:
                        results.append(
                            {
                                "action": "delete",
                                "map_id": map_id,
                                "success": False,
                                "error": "layer_id is required",
                            }
                        )
                        continue
                    self.service.delete_map_layer(map_id, layer_id)
                    results.append(
                        {
                            "action": "delete",
                            "map_id": map_id,
                            "layer_id": layer_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "map_id": map_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Map layer action '{action}' failed for map {map_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "map_id": map_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Calendar Reminders ----

    async def manage_calendar_reminders(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute calendar reminder actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            calendar_id = action_input.get("calendar_id")

            if not calendar_id:
                results.append(
                    {
                        "action": action,
                        "calendar_id": 0,
                        "success": False,
                        "error": "calendar_id is required (calendar's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    reminders = self.service.list_calendar_reminders(calendar_id)
                    results.append(
                        {
                            "action": "list",
                            "calendar_id": calendar_id,
                            "success": True,
                            "error": None,
                            "reminders": reminders,
                        }
                    )

                elif action == "create":
                    entity_id = action_input.get("entity_id")
                    year = action_input.get("year")
                    month = action_input.get("month")
                    day = action_input.get("day")
                    if (
                        entity_id is None
                        or year is None
                        or month is None
                        or day is None
                    ):
                        results.append(
                            {
                                "action": "create",
                                "calendar_id": calendar_id,
                                "success": False,
                                "error": "entity_id, year, month, day are required",
                            }
                        )
                        continue
                    reminder = self.service.create_calendar_reminder(
                        entity_id=entity_id,
                        calendar_id=calendar_id,
                        year=year,
                        month=month,
                        day=day,
                        length=action_input.get("length", 1),
                        name=action_input.get("name"),
                        comment=action_input.get("comment"),
                        colour=action_input.get("colour"),
                        is_recurring=action_input.get("is_recurring"),
                        recurring_periodicity=action_input.get("recurring_periodicity"),
                        recurring_until=action_input.get("recurring_until"),
                        is_hidden=action_input.get("is_hidden"),
                        event_type=action_input.get("event_type"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "calendar_id": calendar_id,
                            "reminder_id": reminder.get("id"),
                            "success": True,
                            "error": None,
                            "reminder": reminder,
                        }
                    )

                elif action == "update":
                    entity_id = action_input.get("entity_id")
                    reminder_id = action_input.get("reminder_id")
                    if not entity_id or not reminder_id:
                        results.append(
                            {
                                "action": "update",
                                "calendar_id": calendar_id,
                                "success": False,
                                "error": "entity_id and reminder_id are required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "year",
                            "month",
                            "day",
                            "length",
                            "name",
                            "comment",
                            "colour",
                            "is_recurring",
                            "recurring_periodicity",
                            "recurring_until",
                            "is_hidden",
                            "event_type",
                        )
                        if k in action_input
                    }
                    reminder = self.service.update_calendar_reminder(
                        entity_id, reminder_id, **fields
                    )
                    results.append(
                        {
                            "action": "update",
                            "calendar_id": calendar_id,
                            "reminder_id": reminder_id,
                            "success": True,
                            "error": None,
                            "reminder": reminder,
                        }
                    )

                elif action == "delete":
                    entity_id = action_input.get("entity_id")
                    reminder_id = action_input.get("reminder_id")
                    if not entity_id or not reminder_id:
                        results.append(
                            {
                                "action": "delete",
                                "calendar_id": calendar_id,
                                "success": False,
                                "error": "entity_id and reminder_id are required",
                            }
                        )
                        continue
                    self.service.delete_calendar_reminder(entity_id, reminder_id)
                    results.append(
                        {
                            "action": "delete",
                            "calendar_id": calendar_id,
                            "reminder_id": reminder_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "calendar_id": calendar_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Calendar reminder action '{action}' failed for calendar {calendar_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "calendar_id": calendar_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Timeline Eras ----

    async def manage_timeline_eras(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute timeline era actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            timeline_id = action_input.get("timeline_id")

            if not timeline_id:
                results.append(
                    {
                        "action": action,
                        "timeline_id": 0,
                        "success": False,
                        "error": "timeline_id is required (timeline's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    eras = self.service.list_timeline_eras(timeline_id)
                    results.append(
                        {
                            "action": "list",
                            "timeline_id": timeline_id,
                            "success": True,
                            "error": None,
                            "eras": eras,
                        }
                    )

                elif action == "create":
                    name = action_input.get("name")
                    if not name:
                        results.append(
                            {
                                "action": "create",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "name is required",
                            }
                        )
                        continue
                    era = self.service.create_timeline_era(
                        timeline_id=timeline_id,
                        name=name,
                        abbreviation=action_input.get("abbreviation"),
                        start_year=action_input.get("start_year"),
                        end_year=action_input.get("end_year"),
                        visibility=action_input.get("visibility"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "timeline_id": timeline_id,
                            "era_id": era.get("id"),
                            "success": True,
                            "error": None,
                            "era": era,
                        }
                    )

                elif action == "update":
                    era_id = action_input.get("era_id")
                    if not era_id:
                        results.append(
                            {
                                "action": "update",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "era_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "abbreviation",
                            "start_year",
                            "end_year",
                            "visibility",
                        )
                        if k in action_input
                    }
                    era = self.service.update_timeline_era(
                        timeline_id, era_id, **fields
                    )
                    results.append(
                        {
                            "action": "update",
                            "timeline_id": timeline_id,
                            "era_id": era_id,
                            "success": True,
                            "error": None,
                            "era": era,
                        }
                    )

                elif action == "delete":
                    era_id = action_input.get("era_id")
                    if not era_id:
                        results.append(
                            {
                                "action": "delete",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "era_id is required",
                            }
                        )
                        continue
                    self.service.delete_timeline_era(timeline_id, era_id)
                    results.append(
                        {
                            "action": "delete",
                            "timeline_id": timeline_id,
                            "era_id": era_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "timeline_id": timeline_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Timeline era action '{action}' failed for timeline {timeline_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "timeline_id": timeline_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sub-resource: Timeline Elements ----

    async def manage_timeline_elements(
        self, actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute timeline element actions (create/update/delete/list)."""
        results: list[dict[str, Any]] = []

        for action_input in actions:
            action = action_input.get("action", "")
            timeline_id = action_input.get("timeline_id")

            if not timeline_id:
                results.append(
                    {
                        "action": action,
                        "timeline_id": 0,
                        "success": False,
                        "error": "timeline_id is required (timeline's entity_id)",
                    }
                )
                continue

            try:
                if action == "list":
                    elements = self.service.list_timeline_elements(timeline_id)
                    results.append(
                        {
                            "action": "list",
                            "timeline_id": timeline_id,
                            "success": True,
                            "error": None,
                            "elements": elements,
                        }
                    )

                elif action == "create":
                    era_id = action_input.get("era_id")
                    if not era_id:
                        results.append(
                            {
                                "action": "create",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "era_id is required",
                            }
                        )
                        continue
                    name = action_input.get("name")
                    entity_id = action_input.get("entity_id")
                    if not name and not entity_id:
                        results.append(
                            {
                                "action": "create",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "name or entity_id is required",
                            }
                        )
                        continue
                    element = self.service.create_timeline_element(
                        timeline_id=timeline_id,
                        era_id=era_id,
                        name=name,
                        entity_id=entity_id,
                        entry=action_input.get("entry"),
                        date=action_input.get("date"),
                        colour=action_input.get("colour"),
                        position=action_input.get("position"),
                        is_hidden=action_input.get("is_hidden"),
                    )
                    results.append(
                        {
                            "action": "create",
                            "timeline_id": timeline_id,
                            "element_id": element.get("id"),
                            "success": True,
                            "error": None,
                            "element": element,
                        }
                    )

                elif action == "update":
                    element_id = action_input.get("element_id")
                    if not element_id:
                        results.append(
                            {
                                "action": "update",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "element_id is required",
                            }
                        )
                        continue
                    fields = {
                        k: action_input[k]
                        for k in (
                            "name",
                            "entity_id",
                            "entry",
                            "date",
                            "colour",
                            "position",
                            "is_hidden",
                        )
                        if k in action_input
                    }
                    element = self.service.update_timeline_element(
                        timeline_id, element_id, **fields
                    )
                    results.append(
                        {
                            "action": "update",
                            "timeline_id": timeline_id,
                            "element_id": element_id,
                            "success": True,
                            "error": None,
                            "element": element,
                        }
                    )

                elif action == "delete":
                    element_id = action_input.get("element_id")
                    if not element_id:
                        results.append(
                            {
                                "action": "delete",
                                "timeline_id": timeline_id,
                                "success": False,
                                "error": "element_id is required",
                            }
                        )
                        continue
                    self.service.delete_timeline_element(timeline_id, element_id)
                    results.append(
                        {
                            "action": "delete",
                            "timeline_id": timeline_id,
                            "element_id": element_id,
                            "success": True,
                            "error": None,
                        }
                    )

                else:
                    results.append(
                        {
                            "action": action,
                            "timeline_id": timeline_id,
                            "success": False,
                            "error": f"Unknown action '{action}'",
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Timeline element action '{action}' failed for timeline {timeline_id}: {e}"
                )
                results.append(
                    {
                        "action": action,
                        "timeline_id": timeline_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    # ---- Sync operations ----

    async def check_entity_updates(
        self, entity_ids: list[int], last_synced: str
    ) -> CheckEntityUpdatesResult:
        """Check which entities have been modified since last sync."""
        if not last_synced:
            raise ValueError("last_synced parameter is required")

        modified_entity_ids: list[int] = []
        deleted_entity_ids: list[int] = []

        try:
            page = 1
            all_entities: dict[int, dict[str, Any]] = {}

            while page <= 20:
                batch = self.service.client.entities(page=page, limit=100)
                if not batch:
                    break
                for entity_data in batch:
                    eid = entity_data.get("id")
                    if eid:
                        all_entities[eid] = entity_data
                if len(batch) < 100:
                    break
                page += 1

            for entity_id in entity_ids:
                if entity_id in all_entities:
                    updated_at = all_entities[entity_id].get("updated_at")
                    if updated_at and updated_at > last_synced:
                        modified_entity_ids.append(entity_id)
                else:
                    deleted_entity_ids.append(entity_id)

            return {
                "modified_entity_ids": modified_entity_ids,
                "deleted_entity_ids": deleted_entity_ids,
                "check_timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Check entity updates failed: {e}")
            raise


# Global instance management
_operations: KankaOperations | None = None


def get_operations() -> KankaOperations:
    """Get or create the singleton operations instance."""
    global _operations
    if _operations is None:
        _operations = KankaOperations(service=get_service())
    return _operations


def create_operations(service: KankaService | None = None) -> KankaOperations:
    """Create a new operations instance for external use."""
    return KankaOperations(service)
