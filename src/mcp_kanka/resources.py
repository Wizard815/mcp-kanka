"""Resources provided by the Kanka MCP server."""

import json

from .types import KankaContext


def get_kanka_context() -> str:
    """
    Get the Kanka context resource.

    Returns:
        JSON string with Kanka context information
    """
    context: KankaContext = {
        "description": "Kanka is a worldbuilding and campaign management tool. This MCP server provides doc-verified MCP tools for managing core entities and common sub-resources (attributes, inventory, permissions), plus supporting map/timeline/calendar and entity image tools.",
        "supported_entities": {
            "character": "People in your world (PCs, NPCs, etc)",
            "creature": "Monster types and animals (templates, not individuals)",
            "ability": "Abilities and special actions",
            "conversation": "In-game dialog content",
            "location": "Places, regions, buildings, landmarks",
            "organization": "Groups, guilds, governments, companies",
            "dice_roll": "Dice roll definitions",
            "bookmark": "Bookmarks for sharing links",
            "race": "Species and ancestries",
            "note": "Private GM notes and session digests",
            "journal": "Session summaries and campaign chronicles",
            "quest": "Missions, objectives, and story arcs",
            "attribute": "Entity properties/stat blocks",
        },
        "core_fields": {
            "name": "Required. The entity's name",
            "type": "Optional. Subtype like 'NPC', 'City', 'Guild' (user-defined)",
            "entry": "Optional. Description (Markdown accepted; auto-converted to HTML for API)",
            "tags": "Optional. String array for categorization",
            "is_hidden": "Optional. If true, hidden from players (admin-only)",
        },
        "terminology": {
            "entity_type": "The main category (character, location, etc.) - fixed list",
            "type": "User-defined subtype within a category (e.g., 'NPC' for characters, 'City' for locations)",
        },
        "posts": "Additional notes/comments can be attached to any entity",
        "mentions": {
            "description": "Cross-reference entities using [entity:ID] or [entity:ID|custom text] in entry fields",
            "examples": ["[entity:1234]", "[entity:1234|the ancient dragon]"],
            "note": "The MCP server preserves these during Markdown/HTML conversion",
        },
        "entity_parent_nesting": (
            "Nesting uses the parent's global entity_id. For **standard events** (GET entities/{id} returns "
            "type \"event\"), Kanka does **not** reliably persist parent via PATCH entities/{id}; the MCP "
            "uses PATCH events/{child_id} with parent_id, where child_id comes from that same GET. For "
            "custom nested modules, PATCH entities/{id} with parent_id is used. Tools accept parent_id as "
            "the parent's global entity_id; event_parent_id is an event module row id and is resolved to "
            "global before the same logic. Regression-tested in unit tests and scripts/api_test_event_parent.py."
        ),
        "limitations": "Some entity-specific fields/endpoints are not exposed. The server focuses on doc-verified core CRUD plus common sub-resources via `manage_*` tools (attributes, entity tags, inventory, permissions), and selected map/timeline/calendar/entity-image operations. Timeline **entities** support `update_entities` / `delete_entity` via the timelines API (module id resolved from the entity).",
    }

    return json.dumps(context, indent=2)
