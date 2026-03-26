"""MCP tool implementations for Kanka operations."""

import logging
from typing import Any

from .operations import get_operations
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

logger = logging.getLogger(__name__)


async def handle_find_entities(**params: Any) -> dict[str, Any]:
    """
    Find entities by search and/or filtering.

    Args:
        **params: Parameters from FindEntitiesParams

    Returns:
        Dictionary with entities and sync_info
    """
    operations = get_operations()

    # Delegate to operations layer
    return await operations.find_entities(
        query=params.get("query"),
        entity_type=params.get("entity_type"),
        name=params.get("name"),
        name_exact=params.get("name_exact", False),
        name_fuzzy=params.get("name_fuzzy", False),
        type=params.get("type"),
        tags=params.get("tags", []),
        tag_id=params.get("tag_id"),
        date_range=params.get("date_range"),
        include_full=params.get("include_full", True),
        page=params.get("page", 1),
        limit=params.get("limit", 25),
        last_synced=params.get("last_synced"),
    )


async def handle_search_entities(**params: Any) -> list[dict[str, Any]]:
    """Global search across all entity types."""
    operations = get_operations()
    return await operations.search_entities(
        search_term=params.get("search_term"),
        page=params.get("page", 1),
    )


async def handle_create_entities(**params: Any) -> list[CreateEntityResult]:
    """
    Create one or more entities.

    Args:
        **params: Parameters from CreateEntitiesParams

    Returns:
        List of creation results
    """
    entities = params.get("entities", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.create_entities(entities)


async def handle_update_entities(**params: Any) -> list[UpdateEntityResult]:
    """
    Update one or more entities.

    Args:
        **params: Parameters from UpdateEntitiesParams

    Returns:
        List of update results
    """
    updates = params.get("updates", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.update_entities(updates)


async def handle_get_entities(**params: Any) -> list[GetEntityResult]:
    """
    Retrieve specific entities by ID.

    Args:
        **params: Parameters from GetEntitiesParams

    Returns:
        List of entity results
    """
    entity_ids = params.get("entity_ids", [])
    include_posts = params.get("include_posts", False)
    operations = get_operations()

    # Delegate to operations layer
    return await operations.get_entities(entity_ids, include_posts)


async def handle_delete_entities(**params: Any) -> list[DeleteEntityResult]:
    """
    Delete one or more entities.

    Args:
        **params: Parameters from DeleteEntitiesParams

    Returns:
        List of deletion results
    """
    entity_ids = params.get("entity_ids", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.delete_entities(entity_ids)


async def handle_create_posts(**params: Any) -> list[CreatePostResult]:
    """
    Create posts on entities.

    Args:
        **params: Parameters from CreatePostsParams

    Returns:
        List of creation results
    """
    posts = params.get("posts", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.create_posts(posts)


async def handle_update_posts(**params: Any) -> list[UpdatePostResult]:
    """
    Update existing posts.

    Args:
        **params: Parameters from UpdatePostsParams

    Returns:
        List of update results
    """
    updates = params.get("updates", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.update_posts(updates)


async def handle_delete_posts(**params: Any) -> list[DeletePostResult]:
    """
    Delete posts from entities.

    Args:
        **params: Parameters from DeletePostsParams

    Returns:
        List of deletion results
    """
    deletions = params.get("deletions", [])
    operations = get_operations()

    # Delegate to operations layer
    return await operations.delete_posts(deletions)


async def handle_check_entity_updates(**params: Any) -> CheckEntityUpdatesResult:
    """
    Check which entity_ids have been modified since last sync.

    Args:
        **params: Parameters from CheckEntityUpdatesParams

    Returns:
        Check result with modified and deleted entity IDs
    """
    entity_ids = params.get("entity_ids", [])
    last_synced = params.get("last_synced")

    # Validate last_synced is provided
    if not last_synced:
        raise ValueError("last_synced parameter is required")

    operations = get_operations()

    # Delegate to operations layer
    return await operations.check_entity_updates(entity_ids, last_synced)


async def handle_manage_map_markers(**params: Any) -> dict[str, Any]:
    """Manage map markers (list/create/update/delete) for a map."""
    operations = get_operations()
    return await operations.manage_map_markers(**params)


async def handle_run_migration_plan(**params: Any) -> dict[str, Any]:
    """Run a whitelisted multi-step migration plan."""
    operations = get_operations()
    steps = params.get("steps") or []
    stop_on_error = params.get("stop_on_error", True)
    return await operations.run_migration_plan(steps, stop_on_error=stop_on_error)


async def handle_manage_relations(**params: Any) -> dict[str, Any]:
    """Manage relations (list/create/update/delete) for an entity."""
    operations = get_operations()
    return await operations.manage_relations(**params)


async def handle_manage_timeline_elements(**params: Any) -> dict[str, Any]:
    """Manage timeline elements for a timeline (list/create/update/delete)."""
    operations = get_operations()
    return await operations.manage_timeline_elements(**params)


async def handle_manage_attributes(**params: Any) -> dict[str, Any]:
    """Manage entity attributes (properties) (list/create/update/delete)."""
    operations = get_operations()
    return await operations.manage_attributes(**params)


async def handle_manage_entity_tags(**params: Any) -> dict[str, Any]:
    """Manage entity tags (list/add/remove)."""
    operations = get_operations()
    return await operations.manage_entity_tags(**params)


async def handle_manage_inventory(**params: Any) -> dict[str, Any]:
    """Manage entity inventory (list/create/update/delete)."""
    operations = get_operations()
    return await operations.manage_inventory(**params)


async def handle_manage_permissions(**params: Any) -> dict[str, Any]:
    """Manage entity permissions (list/update)."""
    operations = get_operations()
    return await operations.manage_permissions(**params)


async def handle_get_archives(**params: Any) -> dict[str, Any]:
    """Retrieve archived entities."""
    operations = get_operations()
    return await operations.get_archives()


async def handle_manage_entity_image(**params: Any) -> dict[str, Any]:
    """Manage an entity image (list/upload/remove)."""
    operations = get_operations()
    return await operations.manage_entity_image(**params)


async def handle_manage_calendar_weather(**params: Any) -> dict[str, Any]:
    """Manage calendar weather effects (list/create/update/delete)."""
    operations = get_operations()
    return await operations.manage_calendar_weather(**params)


async def handle_calendar_advance_date(**params: Any) -> dict[str, Any]:
    """Advance a calendar date by one day."""
    operations = get_operations()
    return await operations.calendar_advance_date(
        calendar_id=params.get("calendar_id")
    )


async def handle_calendar_retreat_date(**params: Any) -> dict[str, Any]:
    """Retreat a calendar date by one day."""
    operations = get_operations()
    return await operations.calendar_retreat_date(
        calendar_id=params.get("calendar_id")
    )
