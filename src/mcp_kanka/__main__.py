#!/usr/bin/env python3
"""
Kanka MCP Server

An MCP server that provides tools for interacting with Kanka campaigns.
"""

import asyncio
import json
import logging
import os
from typing import Any

import mcp.server.stdio
import mcp.types as types
from dotenv import load_dotenv
from mcp.server import Server
from pydantic import AnyUrl

from .resources import get_kanka_context
from .tools import (
    handle_check_entity_updates,
    handle_create_entities,
    handle_create_posts,
    handle_delete_entities,
    handle_delete_posts,
    handle_find_entities,
    handle_get_entities,
    handle_manage_attributes,
    handle_manage_entity_tags,
    handle_manage_map_markers,
    handle_run_migration_plan,
    handle_manage_inventory,
    handle_manage_relations,
    handle_manage_timeline_eras,
    handle_manage_timeline_elements,
    handle_search_entities,
    handle_manage_permissions,
    handle_manage_entity_image,
    handle_manage_calendars,
    handle_manage_calendar_weather,
    handle_manage_calendar_events,
    handle_get_archives,
    handle_calendar_advance_date,
    handle_calendar_retreat_date,
    handle_update_entities,
    handle_update_posts,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create the MCP server instance
app: Server[None] = Server("mcp-kanka")


@app.list_resources()  # type: ignore[no-untyped-call, misc]
async def list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri=AnyUrl("kanka://context"),
            name="Kanka Context",
            description="Information about Kanka's structure and this MCP server's capabilities",
            mimeType="application/json",
        )
    ]


@app.read_resource()  # type: ignore[no-untyped-call, misc]
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    if uri == "kanka://context":
        return get_kanka_context()
    raise ValueError(f"Unknown resource: {uri}")


@app.list_tools()  # type: ignore[no-untyped-call, misc]
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="find_entities",
            description="Find entities by search and/or filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (searches names and content)",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": [
                            "ability",
                            "character",
                            "conversation",
                            "creature",
                            "event",
                            "family",
                            "dice_roll",
                            "location",
                            "map",
                            "organization",
                            "race",
                            "note",
                            "journal",
                            "bookmark",
                            "quest",
                            "attribute",
                            "tag",
                            "timeline",
                            "calendar",
                        ],
                        "description": "Entity type to filter by. For `timeline`, lists all campaign timelines via `GET timelines` (not the generic entities type_id filter).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Filter by name (partial match by default, e.g. 'Test' matches 'Test Character')",
                    },
                    "name_exact": {
                        "type": "boolean",
                        "description": "Use exact matching on name filter (case-insensitive)",
                        "default": False,
                    },
                    "name_fuzzy": {
                        "type": "boolean",
                        "description": "Use fuzzy matching on name filter (typo-tolerant)",
                        "default": False,
                    },
                    "type": {
                        "type": "string",
                        "description": "Filter by Type field (e.g., 'NPC', 'City')",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tag names (strings only; resolved to tag IDs for API-side filtering; requires ALL specified tags).",
                    },
                    "tag_id": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Filter by tag IDs (integers only; requires ALL specified tags).",
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "format": "date"},
                            "end": {"type": "string", "format": "date"},
                        },
                        "description": "For filtering journals by date",
                    },
                    "include_full": {
                        "type": "boolean",
                        "description": "Include full entity details",
                        "default": True,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number for pagination",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default 25, max 100, use 0 for all)",
                        "default": 25,
                    },
                    "last_synced": {
                        "type": "string",
                        "description": "ISO 8601 timestamp to get only entities modified after this time",
                    },
                },
            },
        ),
        types.Tool(
            name="search_entities",
            description="Global search across all entity types",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Search term (global search endpoint)",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Search pagination page number",
                        "default": 1,
                    },
                },
                "required": ["search_term"],
            },
        ),
        types.Tool(
            name="create_entities",
            description="Create one or more entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_type": {
                                    "type": "string",
                                    "enum": [
                                        "ability",
                                        "character",
                                        "conversation",
                                        "creature",
                                        "event",
                                        "family",
                                        "location",
                                        "map",
                                        "dice_roll",
                                        "organization",
                                        "race",
                                        "note",
                                        "journal",
                                        "bookmark",
                                        "quest",
                                        "attribute",
                                        "tag",
                                    ],
                                    "description": "Entity type",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Entity name",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "The Type field (e.g., 'NPC', 'Player Character')",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Description (Markdown accepted; auto-converted to HTML for API)",
                                },
                                "parent_id": {
                                    "type": "integer",
                                    "description": "Parent's global entity_id (/entities/{id}). For events: MCP GETs the entity, then PATCHes `events/{child_id}` with `parent_id` (verified Kanka API). For custom modules: PATCH `entities/{id}`. Prefer when you know the parent's entity id.",
                                },
                                "location_id": {
                                    "type": "integer",
                                    "description": "Location child id (module id, not entity_id). Meaning depends on entity type.",
                                },
                                "parent_location_id": {
                                    "type": "integer",
                                    "description": "Locations only: parent location child id (mapped to API `location_id`).",
                                },
                                "title": {"type": "string"},
                                "status": {"type": "integer"},
                                "age": {"type": "string"},
                                "sex": {"type": "string"},
                                "pronouns": {"type": "string"},
                                "race_id": {
                                    "type": "integer",
                                    "description": "Character race child id, or parent race child id for races.",
                                },
                                "family_id": {
                                    "type": "integer",
                                    "description": "Character/family parent family child id.",
                                },
                                "is_dead": {"type": "boolean"},
                                "is_map_private": {"type": "boolean"},
                                "creature_id": {"type": "integer"},
                                "is_extinct": {"type": "boolean"},
                                "locations": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Creatures only: array of location child ids.",
                                },
                                "note_id": {"type": "integer"},
                                "is_pinned": {"type": "boolean"},
                                "journal_id": {"type": "integer"},
                                "date": {"type": "string"},
                                "character_id": {"type": "integer"},
                                "quest_id": {"type": "integer"},
                                "ability_id": {"type": "integer"},
                                "charges": {"type": "integer"},
                                "organisation_id": {"type": "integer"},
                                "is_defunct": {"type": "boolean"},
                                "map_id": {"type": "integer"},
                                "is_real": {"type": "boolean"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players (admin-only)",
                                },
                                "calendar_id": {
                                    "type": "integer",
                                    "description": "Calendar child id (calendars/{calendar.id}) — events only",
                                },
                                "calendar_year": {
                                    "type": "integer",
                                    "description": "In-world year on that calendar — events only",
                                },
                                "calendar_month": {
                                    "type": "integer",
                                    "description": "In-world month — events only",
                                },
                                "calendar_day": {
                                    "type": "integer",
                                    "description": "In-world day — events only",
                                },
                                "event_parent_id": {
                                    "type": "integer",
                                    "description": "Events only. Parent event's module row id (API `events/{id}`). MCP resolves it to the parent's global entity_id, then PATCHes the child event row with `parent_id` (same as `parent_id`).",
                                },
                                "event_locations": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Events only: linked location child ids (3.10 multi-location support).",
                                },
                                "icon": {"type": "string"},
                                "colour": {"type": "string"},
                            },
                            "required": ["entity_type", "name"],
                        },
                    }
                },
                "required": ["entities"],
            },
        ),
        types.Tool(
            name="update_entities",
            description="Update one or more entities. Timelines: PATCH `timelines/{module_id}`. "
            "Event nesting: `GET entities/{entity_id}` → `PATCH events/{child_id}` with `parent_id` "
            "(parent's global entity_id). Custom modules: `PATCH entities/{id}` for `parent_id`.",
            inputSchema={
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {
                                    "type": "integer",
                                    "description": "Entity ID",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Entity name (optional for PATCH; if omitted and API requires it, MCP will retry with current name)",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "The Type field",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Content (Markdown accepted; auto-converted to HTML for API)",
                                },
                                "parent_id": {
                                    "type": ["integer", "null"],
                                    "description": "Parent's global entity_id. For events: MCP PATCHes `events/{child_id}` with this value; null detaches. For custom modules: PATCH `entities/{id}`. Prefer over `event_parent_id` when you know the parent's entity id.",
                                },
                                "location_id": {
                                    "type": "integer",
                                    "description": "Location child id (module id, not entity_id). Meaning depends on entity type.",
                                },
                                "parent_location_id": {
                                    "type": "integer",
                                    "description": "Locations only: parent location child id (mapped to API `location_id`).",
                                },
                                "title": {"type": "string"},
                                "status": {"type": "integer"},
                                "age": {"type": "string"},
                                "sex": {"type": "string"},
                                "pronouns": {"type": "string"},
                                "race_id": {"type": "integer"},
                                "family_id": {"type": "integer"},
                                "is_dead": {"type": "boolean"},
                                "is_map_private": {"type": "boolean"},
                                "creature_id": {"type": "integer"},
                                "is_extinct": {"type": "boolean"},
                                "locations": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                                "note_id": {"type": "integer"},
                                "is_pinned": {"type": "boolean"},
                                "journal_id": {"type": "integer"},
                                "date": {"type": "string"},
                                "character_id": {"type": "integer"},
                                "quest_id": {"type": "integer"},
                                "ability_id": {"type": "integer"},
                                "charges": {"type": "integer"},
                                "organisation_id": {"type": "integer"},
                                "is_defunct": {"type": "boolean"},
                                "map_id": {"type": "integer"},
                                "is_real": {"type": "boolean"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "is_hidden": {"type": "boolean"},
                                "event_parent_id": {
                                    "type": ["integer", "null"],
                                    "description": "Events only. Parent event module row id (`events/{id}`). Resolved to global entity_id, then same as `parent_id` (PATCH child `events/{child_id}`). Null with key present detaches.",
                                },
                                "calendar_id": {
                                    "type": ["integer", "null"],
                                    "description": "Events only. Calendar child id; set to null to detach event from calendar.",
                                },
                                "calendar_year": {
                                    "type": "integer",
                                    "description": "Events only. In-world year on that calendar (PATCH events/{id}).",
                                },
                                "calendar_month": {
                                    "type": "integer",
                                    "description": "Events only. In-world month.",
                                },
                                "calendar_day": {
                                    "type": "integer",
                                    "description": "Events only. In-world day.",
                                },
                                "event_locations": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Events only: linked location child ids (3.10 multi-location support).",
                                },
                                "icon": {"type": "string"},
                                "colour": {"type": "string"},
                            },
                            "required": ["entity_id"],
                        },
                    }
                },
                "required": ["updates"],
            },
        ),
        types.Tool(
            name="get_entities",
            description="Retrieve specific entities by global entity_id. `parent_id` is the immediate parent's entity id when nested (including events).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of global entity IDs (`/entities/{id}`), not module child IDs like `/timelines/{id}` or `/calendars/{id}`.",
                    },
                    "include_posts": {
                        "type": "boolean",
                        "description": "Include posts for each entity",
                        "default": False,
                    },
                },
                "required": ["entity_ids"],
            },
        ),
        types.Tool(
            name="delete_entities",
            description=(
                "Delete one or more entities (no undo; confirm with get_entities first). "
                "Deletes run in concurrent waves of at most batch_size (default 12, max 15) "
                "to avoid timeouts on large lists. Optional delay_ms between waves reduces rate limits. "
                "Use dry_run=true to preview deletions without deleting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of entity IDs to delete",
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": "Max concurrent deletes per wave (1–15; default 12). Larger lists are auto-chunked.",
                        "default": 12,
                        "minimum": 1,
                        "maximum": 15,
                    },
                    "delay_ms": {
                        "type": "integer",
                        "description": "Milliseconds to wait after each wave except the last (0–60000; default 500).",
                        "default": 500,
                        "minimum": 0,
                        "maximum": 60000,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, return what would be deleted without deleting anything.",
                        "default": False,
                    },
                },
                "required": ["entity_ids"],
            },
        ),
        types.Tool(
            name="create_posts",
            description="Create posts on entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "posts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {
                                    "type": "integer",
                                    "description": "The entity ID to attach post to",
                                },
                                "name": {"type": "string", "description": "Post title"},
                                "entry": {
                                    "type": "string",
                                    "description": "Post content (Markdown accepted; auto-converted to HTML for API)",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players (admin-only)",
                                },
                            },
                            "required": ["entity_id", "name"],
                        },
                    }
                },
                "required": ["posts"],
            },
        ),
        types.Tool(
            name="update_posts",
            description="Update existing posts",
            inputSchema={
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {
                                    "type": "integer",
                                    "description": "The entity ID",
                                },
                                "post_id": {
                                    "type": "integer",
                                    "description": "The post ID to update",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Post title (optional for PATCH; if omitted and API requires it, MCP will retry with current title)",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Post content (Markdown accepted; auto-converted to HTML for API)",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players (admin-only)",
                                },
                            },
                            "required": ["entity_id", "post_id"],
                        },
                    }
                },
                "required": ["updates"],
            },
        ),
        types.Tool(
            name="delete_posts",
            description="Delete posts from entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "deletions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {
                                    "type": "integer",
                                    "description": "The entity ID",
                                },
                                "post_id": {
                                    "type": "integer",
                                    "description": "The post ID to delete",
                                },
                            },
                            "required": ["entity_id", "post_id"],
                        },
                    }
                },
                "required": ["deletions"],
            },
        ),
        types.Tool(
            name="manage_map_markers",
            description=(
                "Manage map markers for a specific map (list/create/update/delete) via action-based payloads. "
                "Updates use KankaService.update_map_marker: clearing entity_id (null) auto-fills name from the "
                "current marker so the API does not return 422."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "map_id": {
                        "type": "integer",
                        "description": "The map's child id (the `id` field from map response, NOT entity_id). Used by list/create/update/delete.",
                    },
                    "marker_id": {
                        "type": "integer",
                        "description": "Map marker child id. Required for update/delete only.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 30,
                    },
                    "name": {
                        "type": "string",
                        "description": "Map marker name (create/update only; required when `entity_id` is omitted).",
                    },
                    "entity_id": {
                        "anyOf": [
                            {"type": "integer"},
                            {"type": "null"},
                        ],
                        "description": "Linked entity id (create/update). Use null to clear the link; the server still requires a marker name — the MCP merges the existing name automatically when you omit it.",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Marker latitude (create/update only; required for create).",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Marker longitude (create/update only; required for create).",
                    },
                    "shape_id": {
                        "type": "integer",
                        "description": "Marker shape id (create/update only; required for create).",
                    },
                    "icon": {
                        "type": "integer",
                        "description": "Marker icon id (create/update only; required for create).",
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "Marker group id (create/update only).",
                    },
                    "is_draggable": {
                        "type": "boolean",
                        "description": "Whether marker is draggable (create/update only).",
                    },
                    "is_popupless": {
                        "type": "boolean",
                        "description": "Disable marker tooltip popping on hover (create/update only).",
                    },
                    "custom_shape": {
                        "type": "string",
                        "description": "Polygon coordinates (create/update only).",
                    },
                    "custom_icon": {
                        "type": "string",
                        "description": "HTML string for custom icon (create/update only).",
                    },
                    "size_id": {
                        "type": "integer",
                        "description": "Circle size id 1-6 (create/update only).",
                    },
                    "opacity": {
                        "type": "integer",
                        "description": "Opacity 0-100 (create/update only).",
                    },
                    "visibility_id": {
                        "type": "integer",
                        "description": "Visibility id (1=all, 2=self, 3=admin, 4=self-admin, 5=members) (create/update only).",
                    },
                    "colour": {
                        "type": "string",
                        "description": "Hex color with leading # (create/update only).",
                    },
                    "font_colour": {
                        "type": "string",
                        "description": "Hex color with leading # (create/update only).",
                    },
                    "circle_radius": {
                        "description": "Custom circle radius when size_id=6 (circle shape) (create/update only).",
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                    },
                    "polygon_style": {
                        "type": "array",
                        "description": "Polygon rendering options (stroke, stroke-width, stroke-opacity) (create/update only).",
                    },
                    "css": {
                        "type": "string",
                        "description": "Custom CSS class (create/update only).",
                    },
                },
                "required": ["action", "map_id"],
            },
        ),
        types.Tool(
            name="manage_relations",
            description="Manage relations attached to an entity (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "The owner entity id (the `entities/{entity.id}` path parameter). Used by list/create/update/delete.",
                    },
                    "relation_id": {
                        "type": "integer",
                        "description": "Relation id (child id). Required for update/delete only.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 30,
                    },
                    "relation": {
                        "type": "string",
                        "description": "Relation description (create/update only; required by API on create).",
                    },
                    "owner_id": {
                        "type": "integer",
                        "description": "Relation owner entity id (create/update only; required by API on create). Defaults to `entity_id` if omitted.",
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "Target entity id (create only). Required if `targets` is not provided.",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Target entity ids (create only). Required if `target_id` is not provided.",
                    },
                    "attitude": {
                        "type": "integer",
                        "description": "Attitude/range from -100 to 100 (create/update only).",
                    },
                    "colour": {
                        "type": "string",
                        "description": "Hex colour of the attitude (create/update only; with or without #).",
                    },
                    "two_way": {
                        "type": "boolean",
                        "description": "If set, duplicate relation in the other direction (create/update only).",
                    },
                    "is_pinned": {
                        "type": "boolean",
                        "description": "If relation is visible on the entity submenu (create/update only).",
                    },
                    "visibility_id": {
                        "type": "integer",
                        "description": "Visibility id (1=all, 2=self, 3=admin, 4=self-admin, 5=members) (create/update only).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="manage_timeline_eras",
            description="Manage timeline eras for a timeline (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "timeline_id": {
                        "type": "integer",
                        "description": "Timeline **campaign entity id** (URL `/entities/{id}`) or **module** id for `timelines/{id}/…`. "
                        "If `GET entities/{id}` returns `type: timeline`, the MCP uses `child.id` automatically; otherwise the value is used as the module id.",
                    },
                    "era_id": {
                        "type": "integer",
                        "description": "Timeline era child id. Required for update/delete only.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 15,
                    },
                    "fetch_all": {
                        "type": "boolean",
                        "description": "List only: if true, fetch all pages and merge into one data array.",
                        "default": False,
                    },
                    "name": {
                        "type": "string",
                        "description": "Era name (create/update only; required for create).",
                    },
                    "abbreviation": {
                        "type": "string",
                        "description": "Era abbreviation label (create/update only).",
                    },
                    "start_year": {
                        "type": "integer",
                        "description": "Era start year (create/update only).",
                    },
                    "end_year": {
                        "type": "integer",
                        "description": "Era end year (create/update only).",
                    },
                    "position": {
                        "type": "integer",
                        "description": "Order position on timeline (create/update only).",
                    },
                    "is_collapsed": {
                        "type": "boolean",
                        "description": "Whether this era is collapsed by default (create/update only).",
                    },
                },
                "required": ["action", "timeline_id"],
            },
        ),
        types.Tool(
            name="manage_timeline_elements",
            description="Manage timeline elements for a timeline (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "timeline_id": {
                        "type": "integer",
                        "description": "Timeline **campaign entity id** (URL `/entities/{id}`) or **module** id for `timelines/{id}/…`. "
                        "If `GET entities/{id}` returns `type: timeline`, the MCP uses `child.id` automatically; otherwise the value is used as the module id.",
                    },
                    "element_id": {
                        "type": "integer",
                        "description": "Timeline element child id. Required for update/delete only.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 15,
                    },
                    "name": {
                        "type": "string",
                        "description": "Timeline element name (create/update only; required when `entity_id` is omitted).",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Linked entity id (create/update only; required when `name` is omitted).",
                    },
                    "era_id": {
                        "type": "integer",
                        "description": "Timeline Era id (create/update only; required for create).",
                    },
                    "entry": {
                        "type": "string",
                        "description": "Timeline element entry (Markdown accepted; auto-converted to HTML for API) (create/update only).",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date string for the element (create/update only).",
                    },
                    "colour": {
                        "type": "string",
                        "description": "Colour string for the element (create/update only).",
                    },
                    "position": {
                        "type": "integer",
                        "description": "Position for ordering within the era (create/update only).",
                    },
                    "visibility_id": {
                        "type": "integer",
                        "description": "Visibility id (create/update only; 1=all, 2=self, 3=admin, 4=self-admin, 5=members).",
                    },
                },
                "required": ["action", "timeline_id"],
            },
        ),
        types.Tool(
            name="manage_attributes",
            description="Manage entity properties/attributes (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Entity id (used for list/create/update/delete).",
                    },
                    "attribute_id": {
                        "type": "integer",
                        "description": "Attribute/property id (update/delete only).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 30,
                    },
                    "name": {
                        "type": "string",
                        "description": "Property name (create/update only; required by API on create and update).",
                    },
                    "value": {
                        "type": "string",
                        "description": "Property value (create/update only).",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["text", "number", "checkbox", "section"],
                        "description": "Property type (create/update only).",
                    },
                    "is_private": {
                        "type": "boolean",
                        "description": "If true, property is only visible to admin members (create/update only).",
                    },
                    "is_star": {
                        "type": "boolean",
                        "description": "If true, property is pinned/starred (create/update only).",
                    },
                    "position": {
                        "type": "integer",
                        "description": "Property ordering position (create/update only).",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Optional API-only key field for the property (create/update only).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="manage_entity_tags",
            description="Manage entity tags (list/add/remove) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "remove"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Entity id (used for list/add/remove).",
                    },
                    "tag_id": {
                        "type": "integer",
                        "description": "Tag id (add only; remove only when `entity_tag_id` is omitted).",
                    },
                    "entity_tag_id": {
                        "type": "integer",
                        "description": "Entity-tag id (remove only).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="manage_inventory",
            description="Manage entity inventory (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Entity id (used for list/create/update/delete).",
                    },
                    "inventory_id": {
                        "type": "integer",
                        "description": "Inventory item id (update/delete only).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 30,
                    },
                    "item_id": {
                        "type": "integer",
                        "description": "Inventory object id (create/update only; required without `name`).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Inventory object name (create/update only; required without `item_id`).",
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount in inventory (create/update only; required).",
                    },
                    "position": {
                        "type": "string",
                        "description": "Where the object is stored (create/update only).",
                    },
                    "is_equipped": {
                        "type": "boolean",
                        "description": "If set, the object is equipped (create/update only).",
                    },
                    "visibility_id": {
                        "type": "integer",
                        "description": "Visibility id (1=all, 2=self, 3=admin, 4=self-admin, 5=members) (create/update only).",
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Visibility string (create/update only; alternative to visibility_id).",
                    },
                    "currency_id": {
                        "type": "integer",
                        "description": "Optional currency id (create/update only).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="manage_permissions",
            description="Manage per-entity permissions (list/update) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "update"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Entity id (used for list/update).",
                    },
                    "permission_action": {
                        "type": "integer",
                        "description": "Permission controller action code (update only).",
                    },
                    "access": {
                        "type": "boolean",
                        "description": "Whether the permission is allowed (update only).",
                    },
                    "campaign_role_id": {
                        "type": "integer",
                        "description": "Campaign role id affected by this permission (update only; required if `user_id` omitted).",
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "User id affected by this permission (update only; required if `campaign_role_id` omitted).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="get_archives",
            description="Retrieve archived entities",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="manage_entity_image",
            description="Manage an entity image (list/upload/remove) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "upload", "remove"],
                        "description": "Which operation to perform",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Entity id (used for list/upload/remove).",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Local file path to upload (upload only; required for upload).",
                    },
                    "is_header": {
                        "type": "boolean",
                        "description": "If true, upload/remove the header image instead of the main image (upload/remove only).",
                    },
                },
                "required": ["action", "entity_id"],
            },
        ),
        types.Tool(
            name="manage_calendars",
            description="Manage calendars (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "calendar_id": {
                        "type": "integer",
                        "description": "Calendar child id (required for update/delete only).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 15,
                    },
                    "name": {"type": "string", "description": "Calendar name (create/update only; required for create)."},
                    "month_name": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of month names (create/update only).",
                    },
                    "month_length": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of month lengths (create/update only).",
                    },
                    "weekday": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of weekday names (create/update only).",
                    },
                    "suffix": {
                        "type": "string",
                        "description": "Year suffix like AE/CE (create/update only).",
                    },
                    "current_year": {"type": "integer", "description": "Current year (create/update only)."},
                    "current_month": {"type": "integer", "description": "Current month (create/update only)."},
                    "current_day": {"type": "integer", "description": "Current day (create/update only)."},
                    "has_leap_year": {"type": "boolean", "description": "Whether leap years are enabled (create/update only)."},
                    "skip_year_zero": {"type": "boolean", "description": "Whether year zero is skipped (create/update only)."},
                    "format": {"type": "string", "description": "Display format string (create/update only)."},
                },
                "required": ["action"],
            },
        ),
        types.Tool(
            name="manage_calendar_weather",
            description="Manage calendar weather effects (list/create/update/delete) via action-based payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "calendar_id": {
                        "type": "integer",
                        "description": "Calendar child id. Used by list (`calendars/{id}/reminders`) and required in create/update payloads for entity reminders.",
                    },
                    "calendar_weather_id": {
                        "type": "integer",
                        "description": "Weather id (update/delete only).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 15,
                    },
                    "year": {
                        "type": "integer",
                        "description": "Weather year (create/update only; required for create).",
                    },
                    "month": {
                        "type": "integer",
                        "description": "Weather month (create/update only; required for create).",
                    },
                    "day": {
                        "type": "integer",
                        "description": "Weather day (create/update only; required for create).",
                    },
                    "weather": {
                        "type": "string",
                        "description": "Weather type (create/update only; required for create).",
                    },
                    "temperature": {
                        "type": "string",
                        "description": "Temperature (create/update only).",
                    },
                    "precipitation": {
                        "type": "string",
                        "description": "Precipitation (create/update only).",
                    },
                    "wind": {
                        "type": "string",
                        "description": "Wind (create/update only).",
                    },
                    "effect": {
                        "type": "string",
                        "description": "Effect (create/update only).",
                    },
                    "visibility_id": {
                        "type": "integer",
                        "description": "Visibility id (create/update only).",
                    },
                },
                "required": ["action", "calendar_id"],
            },
        ),
        types.Tool(
            name="manage_calendar_events",
            description="Manage calendar reminders (list/create/update/delete). List uses calendars/{id}/reminders; writes use entities/{entity_id}/reminders endpoints.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "update", "delete"],
                        "description": "Which operation to perform",
                    },
                    "calendar_id": {
                        "type": "integer",
                        "description": "Calendar child id (list endpoint and required create field).",
                    },
                    "entity_id": {
                        "type": "integer",
                        "description": "Global entity_id owning the reminder. Required for create/update/delete.",
                    },
                    "calendar_event_id": {
                        "type": "integer",
                        "description": "Reminder id (required for update/delete).",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page (list only)",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Pagination limit (list only)",
                        "default": 15,
                    },
                    "fetch_all": {
                        "type": "boolean",
                        "description": "List only: if true, fetch all pages and merge into one data array (uses limit per request).",
                        "default": False,
                    },
                    "name": {"type": "string", "description": "Create/update only."},
                    "day": {"type": "integer", "description": "Create/update only."},
                    "month": {"type": "integer", "description": "Create/update only."},
                    "year": {"type": "integer", "description": "Create/update only."},
                    "length": {"type": "integer", "description": "Create/update only."},
                    "colour": {"type": "string", "description": "Optional hex colour."},
                    "comment": {"type": "string"},
                    "is_recurring": {"type": "boolean"},
                    "recurring_periodicity": {"type": "string"},
                    "recurring_until": {"type": "integer"},
                    "type_id": {"type": "integer"},
                    "visibility_id": {"type": "integer"},
                },
                "required": ["action", "calendar_id"],
            },
        ),
        types.Tool(
            name="calendar_advance_date",
            description="Advance a calendar date by one day (single-step nudge, not bulk date setter)",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "integer",
                        "description": "Calendar child id.",
                    }
                },
                "required": ["calendar_id"],
            },
        ),
        types.Tool(
            name="calendar_retreat_date",
            description="Retreat a calendar date by one day (single-step nudge, not bulk date setter)",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "integer",
                        "description": "Calendar child id.",
                    }
                },
                "required": ["calendar_id"],
            },
        ),
        types.Tool(
            name="run_migration_plan",
            description=(
                "Run a whitelisted multi-step migration (JSON steps, not arbitrary Python). "
                "Same sequencing as a hand-written script: map marker updates (with safe entity_id clears), "
                "entity creates/updates, post creates, tag removals, entity deletes, optional sleeps. "
                "Each step: {\"op\": ...}. Ops: update_map_marker (map_id, marker_id, fields), "
                "update_calendar_event (calendar_id, calendar_event_id, fields), "
                "create_reminder (entity_id, fields), "
                "create_entity (fields; events: parent_id or event_parent_id → PATCH events/{child_id} parent_id), "
                "create_post (fields), "
                "update_entity (entity_id, fields; events: parent_id / event_parent_id same as create), remove_entity_tags_by_tag_id (entity_id, tag_id), "
                "delete_entity (entity_id), sleep_ms (ms)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "Ordered steps; each object must include \"op\".",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "update_map_marker",
                                        "update_calendar_event",
                                        "create_reminder",
                                        "create_entity",
                                        "create_post",
                                        "delete_entity",
                                        "update_entity",
                                        "remove_entity_tags_by_tag_id",
                                        "sleep_ms",
                                    ],
                                },
                                "map_id": {"type": "integer"},
                                "marker_id": {"type": "integer"},
                                "calendar_id": {"type": "integer"},
                                "calendar_event_id": {"type": "integer"},
                                "fields": {"type": "object"},
                                "entity_id": {"type": "integer"},
                                "entity_type": {"type": "string"},
                                "name": {"type": "string"},
                                "entry": {"type": "string"},
                                "is_hidden": {"type": "boolean"},
                                "tag_id": {"type": "integer"},
                                "ms": {"type": "integer"},
                            },
                            "required": ["op"],
                        },
                    },
                    "stop_on_error": {
                        "type": "boolean",
                        "description": "If true (default), stop at the first failed step.",
                        "default": True,
                    },
                },
                "required": ["steps"],
            },
        ),
        types.Tool(
            name="check_entity_updates",
            description="Check which entity_ids have been modified since last sync",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of entity IDs to check",
                    },
                    "last_synced": {
                        "type": "string",
                        "description": "ISO 8601 timestamp to check updates since",
                    },
                },
                "required": ["entity_ids", "last_synced"],
            },
        ),
    ]


@app.call_tool()  # type: ignore[misc]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        result: Any
        if name == "find_entities":
            result = await handle_find_entities(**arguments)
        elif name == "search_entities":
            result = await handle_search_entities(**arguments)
        elif name == "create_entities":
            result = await handle_create_entities(**arguments)
        elif name == "update_entities":
            result = await handle_update_entities(**arguments)
        elif name == "get_entities":
            result = await handle_get_entities(**arguments)
        elif name == "delete_entities":
            result = await handle_delete_entities(**arguments)
        elif name == "create_posts":
            result = await handle_create_posts(**arguments)
        elif name == "update_posts":
            result = await handle_update_posts(**arguments)
        elif name == "delete_posts":
            result = await handle_delete_posts(**arguments)
        elif name == "manage_map_markers":
            result = await handle_manage_map_markers(**arguments)
        elif name == "run_migration_plan":
            result = await handle_run_migration_plan(**arguments)
        elif name == "manage_relations":
            result = await handle_manage_relations(**arguments)
        elif name == "manage_timeline_elements":
            result = await handle_manage_timeline_elements(**arguments)
        elif name == "manage_timeline_eras":
            result = await handle_manage_timeline_eras(**arguments)
        elif name == "manage_attributes":
            result = await handle_manage_attributes(**arguments)
        elif name == "manage_entity_tags":
            result = await handle_manage_entity_tags(**arguments)
        elif name == "manage_inventory":
            result = await handle_manage_inventory(**arguments)
        elif name == "manage_permissions":
            result = await handle_manage_permissions(**arguments)
        elif name == "get_archives":
            result = await handle_get_archives(**arguments)
        elif name == "manage_entity_image":
            result = await handle_manage_entity_image(**arguments)
        elif name == "manage_calendars":
            result = await handle_manage_calendars(**arguments)
        elif name == "manage_calendar_weather":
            result = await handle_manage_calendar_weather(**arguments)
        elif name == "manage_calendar_events":
            result = await handle_manage_calendar_events(**arguments)
        elif name == "calendar_advance_date":
            result = await handle_calendar_advance_date(**arguments)
        elif name == "calendar_retreat_date":
            result = await handle_calendar_retreat_date(**arguments)
        elif name == "check_entity_updates":
            result = await handle_check_entity_updates(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, default=str),
            )
        ]
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    """Main entry point for the MCP server."""
    # Validate required environment variables
    if not os.getenv("KANKA_TOKEN"):
        logger.error("KANKA_TOKEN environment variable is required")
        raise ValueError("KANKA_TOKEN environment variable is required")

    if not os.getenv("KANKA_CAMPAIGN_ID"):
        logger.error("KANKA_CAMPAIGN_ID environment variable is required")
        raise ValueError("KANKA_CAMPAIGN_ID environment variable is required")

    logger.info("Starting Kanka MCP server...")

    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
