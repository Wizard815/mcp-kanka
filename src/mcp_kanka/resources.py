"""Resources provided by the Kanka MCP server."""

import json
from pathlib import Path

from .types import KankaContext

# Path to API reference doc (project root / docs)
_API_REF_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "KANKA_API_REFERENCE.md"
)


def get_kanka_api_reference() -> str:
    """Get the Kanka API reference content for agent context."""
    if _API_REF_PATH.exists():
        return _API_REF_PATH.read_text(encoding="utf-8")
    return "API reference not found. See https://app.kanka.io/api-docs/1.0/"


def get_kanka_context() -> str:
    """Get the Kanka context resource."""
    context: KankaContext = {
        "description": "Kanka is a worldbuilding and campaign management tool. This MCP server provides access to manage entity types, their descriptions, relations, attributes, and organisation membership.",
        "supported_entities": {
            "calendar": "In-world calendars with months, weekdays (moons via Kanka UI)",
            "character": "People in your world (PCs, NPCs, etc)",
            "creature": "Monster types and animals (templates, not individuals)",
            "event": "Historical events linked to calendars",
            "family": "Bloodlines, houses, dynasties",
            "item": "Weapons, artifacts, equipment, treasures",
            "location": "Places, regions, buildings, landmarks",
            "map": "Maps with markers, groups, and layers",
            "organization": "Groups, guilds, governments, companies",
            "race": "Species and ancestries",
            "note": "Private GM notes and session digests",
            "journal": "Session summaries and campaign chronicles",
            "quest": "Missions, objectives, and story arcs",
            "tag": "Tags with descriptions and colours for categorisation",
            "timeline": "Timelines with eras and elements",
        },
        "core_fields": {
            "name": "Required. The entity's name",
            "type": "Optional. Subtype like 'NPC', 'City', 'Guild' (user-defined)",
            "entry": "Optional. Main description in Markdown format",
            "tags": "Optional. String array for categorization",
            "is_hidden": "Optional. If true, hidden from players (admin-only)",
        },
        "terminology": {
            "entity_type": "The main category (character, location, family, item, tag, etc.) - fixed list",
            "type": "User-defined subtype within a category (e.g., 'NPC' for characters, 'City' for locations)",
        },
        "posts": "Additional notes/comments can be attached to any entity",
        "mentions": {
            "description": "Cross-reference entities using [entity:ID] or [entity:ID|custom text] in entry fields",
            "examples": ["[entity:1234]", "[entity:1234|the ancient dragon]"],
            "note": "The MCP server preserves these during Markdown/HTML conversion",
        },
        "limitations": "Conversations, dice rolls, gallery uploads, permissions, and family trees are not available through this MCP server.",
    }

    return json.dumps(context, indent=2)


__all__ = ["get_kanka_context", "get_kanka_api_reference"]
