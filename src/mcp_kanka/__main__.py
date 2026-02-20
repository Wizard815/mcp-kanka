#!/usr/bin/env python3
"""
Kanka MCP Server

An MCP server that provides tools for interacting with Kanka campaigns.
"""

import asyncio
import logging
import os
from typing import Any

import mcp.server.stdio
import mcp.types as types
from dotenv import load_dotenv
from mcp.server import Server
from pydantic import AnyUrl

from .resources import get_kanka_api_reference, get_kanka_context
from .tools import (
    handle_check_entity_updates,
    handle_create_entities,
    handle_create_posts,
    handle_delete_entities,
    handle_delete_posts,
    handle_find_entities,
    handle_get_entities,
    handle_manage_attributes,
    handle_manage_calendar_reminders,
    handle_manage_map_groups,
    handle_manage_map_layers,
    handle_manage_map_markers,
    handle_manage_organisation_members,
    handle_manage_relations,
    handle_manage_timeline_elements,
    handle_manage_timeline_eras,
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

# All supported entity types for schema reuse
_ENTITY_TYPE_ENUM = [
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


@app.list_resources()  # type: ignore[no-untyped-call, misc]
async def list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri=AnyUrl("kanka://context"),
            name="Kanka Context",
            description="Information about Kanka's structure and this MCP server's capabilities",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("kanka://api-reference"),
            name="Kanka API Reference",
            description="Kanka REST API endpoints, parameters, and formats (from app.kanka.io/api-docs/1.0)",
            mimeType="text/markdown",
        ),
    ]


@app.read_resource()  # type: ignore[no-untyped-call, misc]
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    if uri == "kanka://context":
        return get_kanka_context()
    if uri == "kanka://api-reference":
        return get_kanka_api_reference()
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
                        "enum": _ENTITY_TYPE_ENUM,
                        "description": "Entity type to filter by",
                    },
                    "name": {
                        "type": "string",
                        "description": "Filter by name (partial match by default)",
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
                        "description": "Filter by tags (matches entities having ALL specified tags)",
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
                                    "enum": _ENTITY_TYPE_ENUM,
                                    "description": "Entity type",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Entity name",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "The Type field (e.g., 'NPC', 'City')",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Description in Markdown format",
                                },
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players (admin-only)",
                                },
                                "parent_id": {
                                    "type": "integer",
                                    "description": "Parent entity ID for nesting (same entity type)",
                                },
                                "location_id": {
                                    "type": "integer",
                                    "description": "Location entity ID (characters, orgs, families, items, creatures)",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Character title (characters only)",
                                },
                                "age": {
                                    "type": "string",
                                    "description": "Character age (characters only)",
                                },
                                "sex": {
                                    "type": "string",
                                    "description": "Character sex/gender (characters only)",
                                },
                                "pronouns": {
                                    "type": "string",
                                    "description": "Character pronouns (characters only)",
                                },
                                "is_dead": {
                                    "type": "boolean",
                                    "description": "Whether character is dead (characters only)",
                                },
                                "races": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Array of race IDs (characters only)",
                                },
                                "families": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Array of family IDs (characters only)",
                                },
                                "is_completed": {
                                    "type": "boolean",
                                    "description": "Whether quest is completed (quests only)",
                                },
                                "date": {
                                    "type": "string",
                                    "description": "Session date (journals only)",
                                },
                                "character_id": {
                                    "type": "integer",
                                    "description": "Author/character entity ID (journals, quests)",
                                },
                                "is_extinct": {
                                    "type": "boolean",
                                    "description": "Whether family is extinct (families only)",
                                },
                                "is_defunct": {
                                    "type": "boolean",
                                    "description": "Whether org is defunct (organisations only)",
                                },
                                "creator_id": {
                                    "type": "integer",
                                    "description": "Creator entity ID (items only)",
                                },
                                "price": {
                                    "type": "string",
                                    "description": "Item price (items only)",
                                },
                                "size": {
                                    "type": "string",
                                    "description": "Item size (items only)",
                                },
                                "weight": {
                                    "type": "string",
                                    "description": "Item weight (items only)",
                                },
                                "colour": {
                                    "type": "string",
                                    "description": "Hex colour (tags only)",
                                },
                                "image_uuid": {
                                    "type": "string",
                                    "description": "Gallery image UUID",
                                },
                                "header_uuid": {
                                    "type": "string",
                                    "description": "Gallery header image UUID",
                                },
                                "reminder": {
                                    "type": "object",
                                    "description": "Create a reminder on entity with type birth/death (characters) or founded (locations/orgs/families) for age calc. See https://docs.kanka.io/en/latest/advanced/age.html",
                                    "properties": {
                                        "calendar_id": {
                                            "type": "integer",
                                            "description": "Calendar entity_id",
                                        },
                                        "year": {"type": "integer"},
                                        "month": {"type": "integer"},
                                        "day": {"type": "integer"},
                                        "type": {
                                            "type": "string",
                                            "enum": ["birth", "death", "founded"],
                                            "description": "birth/death for characters; founded for locations, organisations, families",
                                        },
                                    },
                                    "required": [
                                        "calendar_id",
                                        "year",
                                        "month",
                                        "day",
                                        "type",
                                    ],
                                },
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
            description="Update one or more entities",
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
                                    "description": "Entity name (required by Kanka API even if unchanged)",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "The Type field",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Content in Markdown format",
                                },
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "is_hidden": {"type": "boolean"},
                                "parent_id": {
                                    "type": "integer",
                                    "description": "Parent entity ID for nesting (same entity type)",
                                },
                                "location_id": {
                                    "type": "integer",
                                    "description": "Location entity ID",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Character title",
                                },
                                "age": {
                                    "type": "string",
                                    "description": "Character age",
                                },
                                "sex": {
                                    "type": "string",
                                    "description": "Character sex/gender",
                                },
                                "pronouns": {
                                    "type": "string",
                                    "description": "Character pronouns",
                                },
                                "is_dead": {
                                    "type": "boolean",
                                    "description": "Whether character is dead",
                                },
                                "races": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Array of race IDs",
                                },
                                "families": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Array of family IDs",
                                },
                                "is_completed": {
                                    "type": "boolean",
                                    "description": "Whether quest is completed",
                                },
                                "date": {
                                    "type": "string",
                                    "description": "Session date (journals)",
                                },
                                "character_id": {
                                    "type": "integer",
                                    "description": "Author/character entity ID",
                                },
                                "is_extinct": {
                                    "type": "boolean",
                                    "description": "Whether family is extinct",
                                },
                                "is_defunct": {
                                    "type": "boolean",
                                    "description": "Whether org is defunct",
                                },
                                "creator_id": {
                                    "type": "integer",
                                    "description": "Creator entity ID (items)",
                                },
                                "price": {
                                    "type": "string",
                                    "description": "Item price",
                                },
                                "size": {"type": "string", "description": "Item size"},
                                "weight": {
                                    "type": "string",
                                    "description": "Item weight",
                                },
                                "colour": {
                                    "type": "string",
                                    "description": "Hex colour (tags)",
                                },
                                "image_uuid": {
                                    "type": "string",
                                    "description": "Gallery image UUID",
                                },
                                "header_uuid": {
                                    "type": "string",
                                    "description": "Gallery header image UUID",
                                },
                                "weekdays": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Calendar: weekday names (min 2)",
                                },
                                "months": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "length": {"type": "integer"},
                                            "type": {"type": "string"},
                                        },
                                    },
                                    "description": "Calendar: months as [{name, length, type}]",
                                },
                                "current_year": {
                                    "type": "integer",
                                    "description": "Calendar: current year",
                                },
                                "current_month": {
                                    "type": "integer",
                                    "description": "Calendar: current month",
                                },
                                "current_day": {
                                    "type": "integer",
                                    "description": "Calendar: current day",
                                },
                                "suffix": {
                                    "type": "string",
                                    "description": "Calendar: year suffix (e.g. A.E., BC)",
                                },
                            },
                            "required": ["entity_id", "name"],
                        },
                    }
                },
                "required": ["updates"],
            },
        ),
        types.Tool(
            name="get_entities",
            description="Retrieve specific entities by ID with their posts",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of entity IDs to retrieve",
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
            description="Delete one or more entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of entity IDs to delete",
                    }
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
                                    "description": "Post content in Markdown format",
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
                                    "description": "Post title (required by API even if unchanged)",
                                },
                                "entry": {
                                    "type": "string",
                                    "description": "Post content in Markdown format",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players (admin-only)",
                                },
                            },
                            "required": ["entity_id", "post_id", "name"],
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
        # --- Sub-resource tools ---
        types.Tool(
            name="manage_relations",
            description="Create, update, delete, or list relations (connections) between entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "entity_id": {
                                    "type": "integer",
                                    "description": "The source entity ID",
                                },
                                "relation_id": {
                                    "type": "integer",
                                    "description": "Relation ID (for update/delete)",
                                },
                                "target_id": {
                                    "type": "integer",
                                    "description": "Target entity ID (for create)",
                                },
                                "relation": {
                                    "type": "string",
                                    "description": "Relation label (e.g. 'Brother of', 'Reports to')",
                                },
                                "attitude": {
                                    "type": "integer",
                                    "description": "Attitude score (-100 to 100)",
                                },
                                "two_way": {
                                    "type": "boolean",
                                    "description": "If true, creates a mirrored relation",
                                },
                                "colour": {
                                    "type": "string",
                                    "description": "Hex colour string",
                                },
                                "is_pinned": {
                                    "type": "boolean",
                                    "description": "Pin relation on entity submenu",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players",
                                },
                            },
                            "required": ["action", "entity_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_attributes",
            description="Create, update, delete, list, or bulk-patch custom attributes on entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "create",
                                        "update",
                                        "delete",
                                        "list",
                                        "bulk_patch",
                                    ],
                                    "description": "The action to perform",
                                },
                                "entity_id": {
                                    "type": "integer",
                                    "description": "The entity ID",
                                },
                                "attribute_id": {
                                    "type": "integer",
                                    "description": "Attribute ID (for update/delete)",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Attribute name",
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Attribute value",
                                },
                                "type_id": {
                                    "type": "integer",
                                    "description": "Attribute type: 1=standard, 2=multiline, 3=checkbox, 4=section, 5=random, 6=number, 7=list",
                                },
                                "is_pinned": {
                                    "type": "boolean",
                                    "description": "Pin attribute on entity view",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players",
                                },
                                "api_key": {
                                    "type": "string",
                                    "description": "Custom API key (max 20 chars)",
                                },
                                "default_order": {
                                    "type": "integer",
                                    "description": "Display order",
                                },
                                "attributes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {
                                                "type": "integer",
                                                "description": "Existing attribute ID (for update in bulk)",
                                            },
                                            "name": {"type": "string"},
                                            "value": {"type": "string"},
                                            "type_id": {"type": "integer"},
                                            "is_pinned": {"type": "boolean"},
                                            "is_hidden": {"type": "boolean"},
                                            "api_key": {"type": "string"},
                                        },
                                        "required": ["name"],
                                    },
                                    "description": "Array of attributes for bulk_patch action",
                                },
                            },
                            "required": ["action", "entity_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_organisation_members",
            description="Add, update, remove, or list members of an organisation",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "organisation_id": {
                                    "type": "integer",
                                    "description": "The entity_id of the organisation",
                                },
                                "member_id": {
                                    "type": "integer",
                                    "description": "Member ID (for update/delete)",
                                },
                                "character_id": {
                                    "type": "integer",
                                    "description": "Character entity ID to add as member",
                                },
                                "role": {
                                    "type": "string",
                                    "description": "Member's role in the organisation",
                                },
                                "is_hidden": {
                                    "type": "boolean",
                                    "description": "If true, hidden from players",
                                },
                                "status_id": {
                                    "type": "integer",
                                    "description": "0=active, 1=past, 2=unknown",
                                },
                                "parent_id": {
                                    "type": "integer",
                                    "description": "Parent member ID (boss)",
                                },
                                "pin_id": {
                                    "type": "integer",
                                    "description": "0=none, 1=pin to character, 2=pin to org, 3=both",
                                },
                            },
                            "required": ["action", "organisation_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_map_markers",
            description="Create, update, delete, or list markers on a map",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "map_id": {
                                    "type": "integer",
                                    "description": "The map's entity_id",
                                },
                                "marker_id": {
                                    "type": "integer",
                                    "description": "Marker ID (for update/delete)",
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Marker name (required for create without entity_id)",
                                },
                                "entity_id": {
                                    "type": "integer",
                                    "description": "Entity to link to marker (required for create without name)",
                                },
                                "latitude": {"type": "number"},
                                "longitude": {"type": "number"},
                                "shape_id": {
                                    "type": "integer",
                                    "description": "1=Marker, 2=Label, 3=Circle, 4=Polygon",
                                },
                                "icon": {"type": "string"},
                                "group_id": {"type": "integer"},
                                "is_draggable": {"type": "boolean"},
                                "is_hidden": {"type": "boolean"},
                            },
                            "required": ["action", "map_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_map_groups",
            description="Create, update, delete, or list marker groups on a map",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "map_id": {
                                    "type": "integer",
                                    "description": "The map's entity_id",
                                },
                                "group_id": {
                                    "type": "integer",
                                    "description": "Group ID (for update/delete)",
                                },
                                "name": {"type": "string"},
                                "parent_id": {"type": "integer"},
                                "is_shown": {"type": "boolean"},
                                "position": {"type": "integer"},
                                "is_hidden": {"type": "boolean"},
                            },
                            "required": ["action", "map_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_map_layers",
            description="Create, update, delete, or list layers on a map",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "map_id": {
                                    "type": "integer",
                                    "description": "The map's entity_id",
                                },
                                "layer_id": {
                                    "type": "integer",
                                    "description": "Layer ID (for update/delete)",
                                },
                                "name": {"type": "string"},
                                "image_url": {"type": "string"},
                                "entry": {"type": "string"},
                                "type_id": {"type": "integer"},
                                "position": {"type": "integer"},
                                "is_hidden": {"type": "boolean"},
                            },
                            "required": ["action", "map_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_calendar_reminders",
            description="Add, update, remove, or list events on a calendar. Use event_type 'birth'/'death' for characters (age calc), 'founded' for locations/orgs/families. See https://docs.kanka.io/en/latest/advanced/age.html",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "calendar_id": {
                                    "type": "integer",
                                    "description": "The calendar's entity_id",
                                },
                                "entity_id": {
                                    "type": "integer",
                                    "description": "Entity to place on calendar (Event, Character, etc.)",
                                },
                                "reminder_id": {
                                    "type": "integer",
                                    "description": "Reminder ID (for update/delete)",
                                },
                                "year": {"type": "integer"},
                                "month": {"type": "integer"},
                                "day": {"type": "integer"},
                                "length": {
                                    "type": "integer",
                                    "description": "Duration in days (default 1)",
                                },
                                "name": {"type": "string"},
                                "comment": {"type": "string"},
                                "colour": {"type": "string"},
                                "is_recurring": {"type": "boolean"},
                                "recurring_periodicity": {
                                    "type": "string",
                                    "description": "yearly, monthly, or moon_id_f/n",
                                },
                                "recurring_until": {"type": "integer"},
                                "is_hidden": {"type": "boolean"},
                                "event_type": {
                                    "type": "string",
                                    "description": "For age/foundation: 'birth', 'death', or 'founded'. Characters: birth/death. Locations/Orgs/Families: founded.",
                                },
                            },
                            "required": ["action", "calendar_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_timeline_eras",
            description="Create, update, delete, or list eras on a timeline",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "timeline_id": {
                                    "type": "integer",
                                    "description": "The timeline's entity_id",
                                },
                                "era_id": {
                                    "type": "integer",
                                    "description": "Era ID (for update/delete)",
                                },
                                "name": {"type": "string"},
                                "abbreviation": {"type": "string"},
                                "start_year": {"type": "integer"},
                                "end_year": {"type": "integer"},
                                "visibility": {
                                    "type": "string",
                                    "description": "all, admin, or self",
                                },
                            },
                            "required": ["action", "timeline_id"],
                        },
                    }
                },
                "required": ["actions"],
            },
        ),
        types.Tool(
            name="manage_timeline_elements",
            description="Create, update, delete, or list elements on a timeline",
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "delete", "list"],
                                    "description": "The action to perform",
                                },
                                "timeline_id": {
                                    "type": "integer",
                                    "description": "The timeline's entity_id",
                                },
                                "element_id": {
                                    "type": "integer",
                                    "description": "Element ID (for update/delete)",
                                },
                                "era_id": {
                                    "type": "integer",
                                    "description": "Era ID (required for create)",
                                },
                                "name": {"type": "string"},
                                "entity_id": {"type": "integer"},
                                "entry": {"type": "string"},
                                "date": {"type": "string"},
                                "colour": {"type": "string"},
                                "position": {"type": "integer"},
                                "is_hidden": {"type": "boolean"},
                            },
                            "required": ["action", "timeline_id"],
                        },
                    }
                },
                "required": ["actions"],
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
        elif name == "check_entity_updates":
            result = await handle_check_entity_updates(**arguments)
        elif name == "manage_relations":
            result = await handle_manage_relations(**arguments)
        elif name == "manage_attributes":
            result = await handle_manage_attributes(**arguments)
        elif name == "manage_organisation_members":
            result = await handle_manage_organisation_members(**arguments)
        elif name == "manage_map_markers":
            result = await handle_manage_map_markers(**arguments)
        elif name == "manage_map_groups":
            result = await handle_manage_map_groups(**arguments)
        elif name == "manage_map_layers":
            result = await handle_manage_map_layers(**arguments)
        elif name == "manage_calendar_reminders":
            result = await handle_manage_calendar_reminders(**arguments)
        elif name == "manage_timeline_eras":
            result = await handle_manage_timeline_eras(**arguments)
        elif name == "manage_timeline_elements":
            result = await handle_manage_timeline_elements(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=str(result))]
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    """Main entry point for the MCP server."""
    if not os.getenv("KANKA_TOKEN"):
        logger.error("KANKA_TOKEN environment variable is required")
        raise ValueError("KANKA_TOKEN environment variable is required")

    if not os.getenv("KANKA_CAMPAIGN_ID"):
        logger.error("KANKA_CAMPAIGN_ID environment variable is required")
        raise ValueError("KANKA_CAMPAIGN_ID environment variable is required")

    logger.info("Starting Kanka MCP server...")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
