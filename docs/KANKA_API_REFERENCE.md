# Kanka API Reference

Complete reference from [Kanka API docs](https://app.kanka.io/api-docs/1.0/). Use when implementing MCP tools or when agents forget API details.

**Base URL**: `https://api.kanka.io/1.0/`  
**Headers**: `Authorization: Bearer {token}`, `Content-Type: application/json`  
**Throttling**: 30 requests/min (90 for subscribers)

Unless noted, campaign endpoints need prefix: `1.0/campaigns/{campaign_id}/`

---

## Get Started

### Overview

Kanka revolves around core **entities**: characters, locations, items, etc. The API follows REST principles with variations described per document.

### Setup

- Generate API key at [Profile > API](https://app.kanka.io/settings/api)
- Tokens valid 365 days
- Headers: `Authorization: Bearer {token}`, `Content-Type: application/json`
- Base: `https://api.kanka.io/1.0/`

---

## User

### Profile

| Method | URI |
|--------|-----|
| GET/HEAD | `1.0/profile` |

Returns: `id`, `name`, `avatar`, `locale`, `timezone`, `date_format`, `default_pagination`, `last_campaign_id`, `is_subscriber`, `rate_limit`.

---

## Campaigns

### Campaigns

| Method | URI |
|--------|-----|
| GET | `1.0/campaigns` |
| GET | `1.0/campaigns/{id}` |

User campaigns: list all; single campaign includes `entry_parsed` (mentions converted to links).

### Campaign Roles

| Method | URI |
|--------|-----|
| GET | `1.0/campaigns/{id}/roles` |

Returns roles: `id`, `name`, `is_admin`.

### Campaign Applications

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Campaign Members

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Default Thumbnails / Campaign Styles / Dashboard Widgets / Gallery

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Modules (Entity Types)

| Method | URI |
|--------|-----|
| GET/HEAD | `campaigns/{campaign_id}/entity_types` |
| POST | `entity_types` |
| PUT/PATCH | `entity_types/{entity_type_id}` |
| DELETE | `entity_types/{entity_type_id}` |

Returns modules: `id`, `code`, `singular`, `plural`, `icon`, `is_special`, `is_enabled`, `is_nested`, `has_table`.

Create body: `singular`, `plural`, `icon` (required), `roles` (array).

---

## Core Objects

### Entities

Entities have `id` (type-specific), `entity_id` (global), `child_id` (type id for full data).

| Method | URI |
|--------|-----|
| GET | `entities` |
| GET | `entities/{entity_id}` |
| POST | `entities` (batch, up to 20) |
| PATCH | `entities` (patch entity) |
| POST | `entities/transform` |
| POST | `entities/transfer` |
| GET | `entities/recent` |
| GET | `entities/recovery` |
| POST | `entities/recover` |

Filters: `type_id[]`, `name`, `type`, `is_private`, `tags[]`, etc.

### Characters

| Method | URI |
|--------|-----|
| GET/HEAD | `characters` |
| GET/HEAD | `characters/{id}` |
| POST | `characters` |
| PUT/PATCH | `characters/{id}` |
| DELETE | `characters/{id}` |

Body: `name` (required), `entry`, `title`, `age`, `sex`, `pronouns`, `type`, `families` (array), `location_id`, `races` (array), `tags`, `is_dead`, `is_private`, `personality_name`, `personality_entry`, `appearance_name`, `appearance_entry`.

### Locations

| Method | URI |
|--------|-----|
| GET/HEAD | `locations` |
| GET/HEAD | `locations/{id}` |
| POST | `locations` |
| PUT/PATCH | `locations/{id}` |
| DELETE | `locations/{id}` |

Body: `name` (required), `entry`, `type`, `location_id` (parent), `tags`, `is_destroyed`, `is_private`.

### Families

| Method | URI |
|--------|-----|
| GET/HEAD | `families` |
| GET/HEAD | `families/{id}` |
| POST | `families` |
| PUT/PATCH | `families/{id}` |
| DELETE | `families/{id}` |

Body: `name` (required), `entry`, `type`, `location_id`, `family_id` (parent), `is_extinct`, `tags`, `is_private`.

**Family Tree**:
- GET `families/{id}/tree`
- PUT `families/{id}/tree` (create)
- POST `families/{id}/tree` (update)
- DELETE `families/{id}/tree`

Tree body: `tree` array with nodes (`entity_id`, `uuid`, `role`, `colour`, `relations`, `children`).

### Organisations

| Method | URI |
|--------|-----|
| GET/HEAD | `organisations` |
| GET/HEAD | `organisations/{id}` |
| POST | `organisations` |
| PUT/PATCH | `organisations/{id}` |
| DELETE | `organisations/{id}` |

Body: `name` (required), `entry`, `type`, `organisation_id` (parent), `locations` (array), `tags`, `is_defunct`, `is_private`.

#### Organisation Members

| Method | URI |
|--------|-----|
| GET/HEAD | `organisations/{id}/organisation_members` |
| POST | `organisations/{id}/organisation_members` |
| PUT/PATCH | `organisations/{id}/organisation_members/{member_id}` |
| DELETE | `organisations/{id}/organisation_members/{member_id}` |

### Items

| Method | URI |
|--------|-----|
| GET/HEAD | `items` |
| GET/HEAD | `items/{id}` |
| POST | `items` |
| PUT/PATCH | `items/{id}` |
| DELETE | `items/{id}` |

Body: `name` (required), `entry`, `type`, `location_id`, `creator_id`, `price`, `size`, `weight`, `item_id` (parent), `tags`, `is_private`.

### Notes

| Method | URI |
|--------|-----|
| GET/HEAD | `notes` |
| GET/HEAD | `notes/{id}` |
| POST | `notes` |
| PUT/PATCH | `notes/{id}` |
| DELETE | `notes/{id}` |

Body: `name` (required), `entry`, `type`, `note_id` (parent), `tags`, `is_private`.

### Events

| Method | URI |
|--------|-----|
| GET/HEAD | `events` |
| GET/HEAD | `events/{id}` |
| POST | `events` |
| PUT/PATCH | `events/{id}` |
| DELETE | `events/{id}` |

Body: `name` (required), `entry`, `type`, `date`, `location_id`, `tags`, `is_private`, `event_id` (parent for nesting). Events link to calendars via `calendar_id`, `calendar_year`, `calendar_month`, `calendar_day`.

### Calendars

| Method | URI |
|--------|-----|
| GET/HEAD | `calendars` |
| GET/HEAD | `calendars/{id}` |
| POST | `calendars` |
| PUT/PATCH | `calendars/{id}` |
| DELETE | `calendars/{id}` |

**CRITICAL – Create/Update use same parameters.** Use flat arrays for both:

| Parameter | Type |
|-----------|------|
| `weekday` | array (required, min 2) |
| `month_name` | array |
| `month_length` | array |
| `month_type` | array (`standard`/`intercalary`) |
| `moon_name` | array |
| `moon_fullmoon` | array (string per moon) |
| `current_year`, `current_month`, `current_day` | integer |
| `suffix` | string (e.g. "A.E.") |
| `format` | string |

**GET** returns `moons` as objects `[{name, fullmoon, offset, colour}]`.  
**PUT/PATCH** must use `moon_name` and `moon_fullmoon` – NOT `moons`.

Calendar sub-resources: Reminders, Advance Date, Retreat Date, Weather – see [Calendars](https://app.kanka.io/api-docs/1.0/calendars).

### Timelines

| Method | URI |
|--------|-----|
| GET/HEAD | `timelines` |
| GET/HEAD | `timelines/{id}` |
| POST | `timelines` |
| PUT/PATCH | `timelines/{id}` |
| DELETE | `timelines/{id}` |

Body: `name` (required), `entry`, `type`, `tags`, `is_private`.

Sub-resources: [Timeline Eras](https://app.kanka.io/api-docs/1.0/timeline-eras), [Timeline Elements](https://app.kanka.io/api-docs/1.0/timeline-elements).

### Creatures

| Method | URI |
|--------|-----|
| GET/HEAD | `creatures` |
| GET/HEAD | `creatures/{id}` |
| POST | `creatures` |
| PUT/PATCH | `creatures/{id}` |
| DELETE | `creatures/{id}` |

Body: `name` (required), `entry`, `type`, `creature_id` (parent), `tags`, `locations` (array), `is_extinct`, `is_dead`, `is_private`.

### Races

| Method | URI |
|--------|-----|
| GET/HEAD | `races` |
| GET/HEAD | `races/{id}` |
| POST | `races` |
| PUT/PATCH | `races/{id}` |
| DELETE | `races/{id}` |

Body: `name` (required), `entry`, `type`, `race_id` (parent), `is_extinct`, `tags`, `locations` (array), `is_private`.

### Quests

| Method | URI |
|--------|-----|
| GET/HEAD | `quests` |
| GET/HEAD | `quests/{id}` |
| POST | `quests` |
| PUT/PATCH | `quests/{id}` |
| DELETE | `quests/{id}` |

Body: `name` (required), `entry`, `type`, `quest_id` (parent), `instigator_id`, `location_id`, `tags`, `is_private`.

Sub-resource: `quests/{id}/quest_elements`.

### Maps

| Method | URI |
|--------|-----|
| GET/HEAD | `maps` |
| GET/HEAD | `maps/{id}` |
| POST | `maps` |
| PUT/PATCH | `maps/{id}` |
| DELETE | `maps/{id}` |

Body: `name` (required), `entry`, `type`, `map_id` (parent), `location_id`, `center_marker_id`, `center_x`, `center_y`, `is_real`, `tags`, `is_private`.

#### Map Markers

See [API docs – Map Markers](https://app.kanka.io/api-docs/1.0/). Endpoints under `maps/{map_id}/map_markers`.

#### Map Groups

See [API docs – Map Groups](https://app.kanka.io/api-docs/1.0/). Endpoints under `maps/{map_id}/map_groups`.

#### Map Layers

See [API docs – Map Layers](https://app.kanka.io/api-docs/1.0/). Endpoints under `maps/{map_id}/map_layers`.

### Journals

| Method | URI |
|--------|-----|
| GET/HEAD | `journals` |
| GET/HEAD | `journals/{id}` |
| POST | `journals` |
| PUT/PATCH | `journals/{id}` |
| DELETE | `journals/{id}` |

Body: `name` (required), `entry`, `type`, `date`, `journal_id` (parent), `author_id`, `tags`, `is_private`.

### Abilities

| Method | URI |
|--------|-----|
| GET/HEAD | `abilities` |
| GET/HEAD | `abilities/{id}` |
| POST | `abilities` |
| PUT/PATCH | `abilities/{id}` |
| DELETE | `abilities/{id}` |

Body: `name` (required), `entry`, `type`, `ability_id` (parent), `charges`, `tags`, `is_private`.

### Tags

| Method | URI |
|--------|-----|
| GET/HEAD | `tags` |
| GET/HEAD | `tags/{id}` |
| POST | `tags` |
| PUT/PATCH | `tags/{id}` |
| DELETE | `tags/{id}` |

Body: `name` (required), `entry`, `type`, `colour`, `tag_id` (parent), `tags`, `is_auto_applied`, `is_hidden`, `is_private`.

### Conversations / Dice Rolls

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Attribute Templates

| Method | URI |
|--------|-----|
| GET/HEAD | `attribute_templates` |
| GET/HEAD | `attribute_templates/{id}` |
| POST | `attribute_templates` |
| PUT/PATCH | `attribute_templates/{id}` |
| DELETE | `attribute_templates/{id}` |

Body: `name` (required), `attribute_template_id` (parent), `entity_type_id`, `is_private`, `is_enabled`.

---

## Entities (Sub-resources)

### Abilities (Entity)

See [API docs – Entity Abilities](https://app.kanka.io/api-docs/1.0/entities/entity-abilities).

### Attributes

| Method | URI |
|--------|-----|
| GET | `entities/{entity_id}/attributes` |
| GET | `entities/{entity_id}/attributes/{attr_id}` |
| POST | `entities/{entity_id}/attributes` |
| PUT/PATCH | `entities/{entity_id}/attributes/{attr_id}` |
| DELETE | `entities/{entity_id}/attributes/{attr_id}` |
| PATCH | `entities/{entity_id}/attributes` (bulk) |
| PUT | `entities/{entity_id}/attributes` (replace all) |

Body: `name` (required), `value`, `default_order`, `type_id` (1=standard, 2=multiline, 3=checkbox, 4=section, 5=random, 6=number, 7=list), `is_private`, `is_pinned`, `api_key` (max 20).

### Assets / Image / Inventory

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Mentions

Entity mentions: `[entity:123]` or `[entity:123|text]`. Parsed in `entry_parsed`.

### Permissions

See [API docs](https://app.kanka.io/api-docs/1.0/).

### Posts

| Method | URI |
|--------|-----|
| GET | `entities/{entity_id}/posts` |
| GET | `entities/{entity_id}/posts/{post_id}` |
| POST | `entities/{entity_id}/posts` |
| PUT/PATCH | `entities/{entity_id}/posts/{post_id}` |
| DELETE | `entities/{entity_id}/posts/{post_id}` |

Body: `name` (required), `entry`, `entity_id` (required), `visibility_id` (1=all, 2=self, 3=admin, 4=self-admin, 5=members).

### Connections (Relations)

API uses "Relations"; UI calls them "Connections".

| Method | URI |
|--------|-----|
| GET | `entities/{entity_id}/relations` |
| GET | `entities/{entity_id}/relations/{rel_id}` |
| POST | `entities/{entity_id}/relations` |
| PUT/PATCH | `entities/{entity_id}/relations/{rel_id}` |
| DELETE | `entities/{entity_id}/relations/{rel_id}` |
| GET | `relations` (campaign-wide) |

Body: `relation` (required), `owner_id` (required), `target_id` or `targets`, `attitude` (-100–100), `colour`, `two_way`, `is_pinned`, `visibility_id`.

### Reminders

| Method | URI |
|--------|-----|
| GET | `entities/{entity_id}/reminders` |
| GET | `entities/{entity_id}/reminders/{event_id}` |
| POST | `entities/{entity_id}/reminders` |
| PUT/PATCH | `entities/{entity_id}/reminders/{event_id}` |
| DELETE | `entities/{entity_id}/reminders/{event_id}` |

Note: Official docs show `entity_events` but the live API uses `reminders`.

Body: `name`, `day`, `month`, `year`, `length`, `calendar_id` (required), `recurring_periodicity` (yearly/monthly/moon), `recurring_until`, `colour`, `comment`, `type_id` (2=birth, 3=death).

Calendar reminders: `calendars/{id}/reminders` – see [Calendars](https://app.kanka.io/api-docs/1.0/calendars).

### Tags (Entity Tags)

| Method | URI |
|--------|-----|
| GET | `entities/{entity_id}/entity_tags` |
| GET | `entities/{entity_id}/entity_tags/{tag_id}` |
| POST | `entities/{entity_id}/entity_tags` |
| PUT/PATCH | `entities/{entity_id}/entity_tags/{tag_id}` |
| DELETE | `entities/{entity_id}/entity_tags/{tag_id}` |

Body: `tag_id` (required).

### Templates

See [API docs](https://app.kanka.io/api-docs/1.0/).

---

## Search

### Search

| Method | URI |
|--------|-----|
| GET | `search/{search_term}` |

Returns matching entities with `id`, `entity_id`, `name`, `type`, `image`, `tooltip`, `url`.

### Archives

| Method | URI |
|--------|-----|
| GET | `entities/archived` |
| POST | `entities/{entity_id}/archive` |

---

## Other Concepts

### Filters

| Method | URI |
|--------|-----|
| GET | `1.0/filters` |
| GET | `1.0/filters/{type_code}` |

List endpoints support filters (e.g. `?name=John&tag_id[]=5`). Use `?fields=id,name,...` to limit response fields.

### Pagination

List endpoints return `data`, `links` (`first`, `last`, `prev`, `next`), `meta`. Default ~15–100 per page.

### Visibilities

| ID | Code | Description |
|----|------|-------------|
| 1 | all | Everyone |
| 2 | admin | Admin role only |
| 3 | admin-self | Admin + creator |
| 4 | self | Creator only |
| 5 | members | Campaign members |

Entity-level visibility uses `is_private` (true = admin only).

### Last Sync

Index endpoints return `sync` (UTC timestamp). Use `?lastSync=2020-12-24T19:17:42.207577Z` to get only entities changed since that time.
