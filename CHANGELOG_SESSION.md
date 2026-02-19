# Session Log – 2026-02-18 / 2026-02-19

Overview of changes and additions to the MCP Kanka server across two implementation phases.

**Reference:** Full Cursor session transcript: `cursor_kanka_mcp_integration_from_mcpad.md` (exported 2/18/2026). That document captures the MCPaddition plan (from 00_Inbox/MCPDUMP) and its implementation.

---

## Summary

**Phase 1 – MCPaddition:** Implemented the MCPaddition feature plan. Added **family**, **item**, **tag** entity types; **parent_id / nesting** so entities can be nested under parents (items under items, locations under locations, maps under maps, etc.); **Item direct API** (items use `client._request()` since python-kanka has no item manager); sub-resource tools **manage_relations**, **manage_attributes**, **manage_organisation_members**.

**Phase 2 – Module expansion:** Added **map**, **calendar**, **event**, **timeline** entity types; map sub-resources (**manage_map_markers**, **manage_map_groups**, **manage_map_layers**); **manage_calendar_reminders**; timeline sub-resources (**manage_timeline_eras**, **manage_timeline_elements**). Fixed Kanka API mismatches: calendar create (flat arrays) vs update (object arrays); map timestamps (API returns strings, not datetimes). Hardened `.gitignore` for `.cursor/`, caches, and logs.

---

## Nesting / Parent Support

- **Items** – Items can be nested under a parent item via `parent_id` (maps to Kanka’s `item_id`).
- **Locations, maps, organisations, notes, journals, quests, races, creatures, families, tags** – All support `parent_id` for nesting. The service maps `parent_id` to the correct API field (`item_id`, `map_id`, `location_id`, `organisation_id`, etc.) per type.
- Create and update both accept `parent_id` for nested entities.

---

## Entity Types (Expanded)

| Type        | CRUD | Notes                                                |
|-------------|------|------------------------------------------------------|
| **family**  | ✓    | Bloodlines, houses (from MCPaddition)                |
| **item**    | ✓    | Items via direct API; nested under parent items      |
| **tag**     | ✓    | Tags with colour (from MCPaddition)                  |
| **map**     | ✓    | Markers, groups, layers sub-resources                |
| **calendar**| ✓    | Moons, reminders; Gregorian-style structure          |
| **event**   | ✓    | Date, location, calendar linkage                     |
| **timeline**| ✓    | Eras and elements sub-resources                      |

---

## New MCP Tools

**From MCPaddition:**
- **manage_relations** – Create / update / delete / list relations between entities
- **manage_attributes** – Create / update / delete / list / bulk-patch custom attributes
- **manage_organisation_members** – Add / update / remove / list org members

**From Module expansion:**
- **manage_map_markers** – Create / update / delete / list map markers
- **manage_map_groups** – Create / update / delete / list map groups
- **manage_map_layers** – Create / update / delete / list map layers
- **manage_calendar_reminders** – Add entities to calendar dates (events, holidays)
- **manage_timeline_eras** – Create / update / delete / list timeline eras
- **manage_timeline_elements** – Create / update / delete / list elements within eras

---

## Fixes

### 1. Calendar create vs update format (Kanka API)

- **Create** expects flat arrays: `month_name`, `month_length`, `month_type`, `weekday`, `moon_name`, `moon_fullmoon`
- **Update** expects object arrays: `months` (objects), `moons` (objects), `weekdays`

Added `_prepare_calendar_structural_fields()` to convert between these formats automatically for both create and update.

### 2. Map timestamp handling

- Maps (direct API) return `created_at` and `updated_at` as strings; other types use datetime objects.
- `_entity_to_dict` called `.isoformat()` on strings, causing `'str' object has no attribute 'isoformat'`.

Added `_normalize_timestamp()` to handle both strings and datetime objects.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/mcp_kanka/service.py` | Calendar structural conversion, map timestamp normalization |
| `src/mcp_kanka/operations.py` | New entity types, manage tools, extra field keys |
| `src/mcp_kanka/tools.py` | Handlers for new manage tools |
| `src/mcp_kanka/__main__.py` | Tool registration and dispatch |
| `src/mcp_kanka/types.py` | New entity types, map/event/timeline fields |
| `src/mcp_kanka/resources.py` | Supported entities list updated |
| `tests/unit/test_service.py` | Calendar create/update format tests |
| `tests/unit/test_resources.py` | Entity type expectations |
| `.gitignore` | `.cursor/`, `.ruff_cache/`, `*.log`, `*.tmp` |

---

## `.gitignore` Additions

- `.cursor/` – MCP config and API tokens
- `.ruff_cache/` – Ruff cache
- `*.log`, `*.tmp` – Logs and temp files

---

## Gregorian Calendar Example

Create a standard Gregorian calendar with Moon cycle:

```json
{
  "entity_type": "calendar",
  "name": "Gregorian Calendar",
  "weekday": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
  "month_name": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  "month_length": [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
  "month_type": ["standard", "standard", ...],
  "moon_name": ["Moon"],
  "moon_fullmoon": ["30"],
  "season_name": ["Spring", "Summer", "Autumn", "Winter"],
  "season_month": [3, 6, 9, 12],
  "season_day": [1, 1, 1, 1],
  "format": "d M, y s",
  "suffix": "CE",
  "has_leap_year": true,
  "leap_year_amount": 1,
  "leap_year_month": 2,
  "leap_year_offset": 4,
  "leap_year_start": 1,
  "skip_year_zero": true
}
```

### Nested item example

Create an item under a parent item:

```json
{
  "entity_type": "item",
  "name": "Magic Sword",
  "parent_id": 12345,
  "entry": "A blade forged in dragon fire."
}
```

---

## Branch

- **Branch:** `ModuleAddon`
- **Remote:** https://github.com/Wizard815/mcp-kanka
