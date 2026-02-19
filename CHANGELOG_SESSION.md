# Session Log – 2026-02-18 / 2026-02-19

Overview of changes and additions made during this session.

---

## Summary

This session added support for **Maps**, **Calendars**, **Events**, and **Timelines** to the MCP Kanka server, fixed calendar create/update format mismatches with the Kanka API, fixed map timestamp handling, and hardened `.gitignore` for sensitive and build artifacts.

---

## New Entity Types

| Type      | CRUD | Notes                                                |
|-----------|------|------------------------------------------------------|
| **map**   | ✓    | Markers, groups, layers sub-resources                |
| **calendar** | ✓ | Moons, reminders; Gregorian-style structure          |
| **event** | ✓    | Date, location, calendar linkage                     |
| **timeline** | ✓ | Eras and elements sub-resources                     |

---

## New MCP Tools

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

---

## Branch

- **Branch:** `ModuleAddon`
- **Status:** Ready to push
