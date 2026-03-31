"""Type definitions for the Kanka MCP server."""

from typing import Literal, NotRequired, TypedDict

# Supported entity types
EntityType = Literal[
    "ability",
    "attribute",
    "bookmark",
    "calendar",
    "character",
    "conversation",
    "creature",
    "dice_roll",
    "event",
    "family",
    "journal",
    "location",
    "map",
    "organization",
    "race",
    "note",
    "quest",
    "timeline",
]


# Request types
class DateRange(TypedDict):
    """Date range for filtering."""

    start: str
    end: str


class FindEntitiesParams(TypedDict, total=False):
    """Parameters for find_entities tool."""

    query: str | None
    entity_type: EntityType | None
    name: str | None
    name_exact: bool | None
    name_fuzzy: bool | None
    type: str | None
    tags: list[str] | None
    tag_id: list[int] | None
    date_range: DateRange | None
    include_full: bool | None
    page: int | None
    limit: int | None
    last_synced: str | None  # ISO 8601 timestamp


class EntityInput(TypedDict):
    """Input for creating an entity."""

    entity_type: EntityType
    name: str
    type: str | None
    entry: str | None
    tags: list[str] | None
    is_hidden: bool | None
    # Location-specific: parent Location child_id (the Location module `id`, not an entity_id)
    location_id: int | None
    # Event-specific: calendar child id (calendars/{calendar.id}) and in-world date (events create)
    calendar_id: NotRequired[int | None]
    calendar_year: NotRequired[int | None]
    calendar_month: NotRequired[int | None]
    calendar_day: NotRequired[int | None]
    # Event-specific: parent Event module child id (events/{id}); sent to API as `event_id`
    event_parent_id: NotRequired[int | None]
    # Character-specific
    title: NotRequired[str | None]
    age: NotRequired[str | None]
    sex: NotRequired[str | None]
    pronouns: NotRequired[str | None]
    race_id: NotRequired[int | None]
    family_id: NotRequired[int | None]
    is_dead: NotRequired[bool | None]
    # Location-specific
    parent_location_id: NotRequired[int | None]
    is_map_private: NotRequired[bool | None]
    # Creature-specific
    creature_id: NotRequired[int | None]
    is_extinct: NotRequired[bool | None]
    locations: NotRequired[list[int] | None]
    # Race-specific
    # `race_id` is shared with character and used as parent-race id for races.
    # Note-specific
    note_id: NotRequired[int | None]
    is_pinned: NotRequired[bool | None]
    # Journal-specific
    journal_id: NotRequired[int | None]
    date: NotRequired[str | None]
    character_id: NotRequired[int | None]
    # Quest-specific
    quest_id: NotRequired[int | None]
    # Ability-specific
    ability_id: NotRequired[int | None]
    charges: NotRequired[int | None]
    # Organisation-specific
    organisation_id: NotRequired[int | None]
    is_defunct: NotRequired[bool | None]
    # Map-specific
    map_id: NotRequired[int | None]
    is_real: NotRequired[bool | None]


class CreateEntitiesParams(TypedDict):
    """Parameters for create_entities tool."""

    entities: list[EntityInput]


class EntityUpdate(TypedDict):
    """Update for an entity."""

    entity_id: int
    name: str | None
    type: str | None
    entry: str | None
    tags: list[str] | None
    is_hidden: bool | None
    # Location-specific: parent Location child_id (the Location module `id`, not an entity_id)
    location_id: int | None
    # Event-specific: parent Event module child id; sent to API as `event_id`
    event_parent_id: NotRequired[int | None]
    # Event-specific: calendar child id (nullable). Include key with null to detach event from calendar.
    calendar_id: NotRequired[int | None]
    # Character-specific
    title: NotRequired[str | None]
    age: NotRequired[str | None]
    sex: NotRequired[str | None]
    pronouns: NotRequired[str | None]
    race_id: NotRequired[int | None]
    family_id: NotRequired[int | None]
    is_dead: NotRequired[bool | None]
    # Location-specific
    parent_location_id: NotRequired[int | None]
    is_map_private: NotRequired[bool | None]
    # Creature-specific
    creature_id: NotRequired[int | None]
    is_extinct: NotRequired[bool | None]
    locations: NotRequired[list[int] | None]
    # Note-specific
    note_id: NotRequired[int | None]
    is_pinned: NotRequired[bool | None]
    # Journal-specific
    journal_id: NotRequired[int | None]
    date: NotRequired[str | None]
    character_id: NotRequired[int | None]
    # Quest-specific
    quest_id: NotRequired[int | None]
    # Ability-specific
    ability_id: NotRequired[int | None]
    charges: NotRequired[int | None]
    # Organisation-specific
    organisation_id: NotRequired[int | None]
    is_defunct: NotRequired[bool | None]
    # Map-specific
    map_id: NotRequired[int | None]
    is_real: NotRequired[bool | None]


class UpdateEntitiesParams(TypedDict):
    """Parameters for update_entities tool."""

    updates: list[EntityUpdate]


class GetEntitiesParams(TypedDict):
    """Parameters for get_entities tool."""

    entity_ids: list[int]
    include_posts: bool | None


class DeleteEntitiesParams(TypedDict, total=False):
    """Parameters for delete_entities tool."""

    entity_ids: list[int]
    batch_size: int | None  # max concurrent deletes per wave; clamped 1–15, default 12
    delay_ms: int | None  # pause between waves (ms); default 500, clamped 0–60000
    dry_run: bool | None  # if true, show what would be deleted without deleting


class PostInput(TypedDict):
    """Input for creating a post."""

    entity_id: int
    name: str
    entry: str | None
    is_hidden: bool | None


class CreatePostsParams(TypedDict):
    """Parameters for create_posts tool."""

    posts: list[PostInput]


class PostUpdate(TypedDict):
    """Update for a post."""

    entity_id: int
    post_id: int
    name: str | None
    entry: str | None
    is_hidden: bool | None


class UpdatePostsParams(TypedDict):
    """Parameters for update_posts tool."""

    updates: list[PostUpdate]


class PostDeletion(TypedDict):
    """Deletion for a post."""

    entity_id: int
    post_id: int


class DeletePostsParams(TypedDict):
    """Parameters for delete_posts tool."""

    deletions: list[PostDeletion]


# Response types
class EntityMinimal(TypedDict):
    """Minimal entity data returned when include_full=false."""

    entity_id: int
    name: str
    entity_type: EntityType


class EntityFull(TypedDict, total=False):
    """Full entity data returned when include_full=true."""

    id: int
    entity_id: int
    name: str
    entity_type: EntityType
    type: str | None
    entry: str | None
    tags: list[str]
    is_hidden: bool
    created_at: str  # ISO 8601 timestamp
    updated_at: str  # ISO 8601 timestamp
    match_score: float | None  # Only when name_fuzzy=true
    is_completed: bool | None  # For quests only
    image: str | None  # Local path to the picture
    image_full: str | None  # URL to the full picture
    image_thumb: str | None  # URL to the thumbnail
    image_uuid: str | None  # Image gallery UUID
    header_uuid: str | None  # Header image gallery UUID


class PostData(TypedDict):
    """Post data structure."""

    id: int
    name: str
    entry: str | None
    is_hidden: bool


class EntityWithPosts(EntityFull):
    """Entity with posts included."""

    posts: list[PostData] | None


# Sync metadata structure
class SyncInfo(TypedDict):
    """Metadata about synchronization results."""

    request_timestamp: str  # When this request was made
    newest_updated_at: str | None  # Latest updated_at from returned entities
    total_count: int  # Total matching entities (for pagination)
    last_page: int  # Last page number for pagination
    returned_count: int  # Number returned in this response


class FindEntitiesResponse(TypedDict):
    """Response structure for find_entities with sync metadata."""

    entities: list[EntityMinimal | EntityFull]
    sync_info: SyncInfo


class CreateEntityResult(TypedDict):
    """Result of creating an entity."""

    id: int | None
    entity_id: int | None
    name: str
    mention: str | None
    success: bool
    error: str | None


class UpdateEntityResult(TypedDict):
    """Result of updating an entity."""

    entity_id: int
    success: bool
    error: str | None


class GetEntityResult(TypedDict, total=False):
    """Result of getting an entity."""

    id: int | None
    entity_id: int
    name: str | None
    entity_type: EntityType | None
    type: str | None
    entry: str | None
    tags: list[str] | None
    is_hidden: bool | None
    created_at: str | None  # ISO 8601 timestamp
    updated_at: str | None  # ISO 8601 timestamp
    posts: list[PostData] | None
    success: bool
    error: str | None
    is_completed: bool | None  # For quests only
    image: str | None  # Local path to the picture
    image_full: str | None  # URL to the full picture
    image_thumb: str | None  # URL to the thumbnail
    image_uuid: str | None  # Image gallery UUID
    header_uuid: str | None  # Header image gallery UUID


class DeleteEntityResult(TypedDict):
    """Result of deleting an entity."""

    entity_id: int
    success: bool
    error: str | None
    warning: NotRequired[str]
    dry_run: NotRequired[bool]


class CreatePostResult(TypedDict):
    """Result of creating a post."""

    post_id: int | None
    entity_id: int
    success: bool
    error: str | None


class UpdatePostResult(TypedDict):
    """Result of updating a post."""

    entity_id: int
    post_id: int
    success: bool
    error: str | None


class DeletePostResult(TypedDict):
    """Result of deleting a post."""

    entity_id: int
    post_id: int
    success: bool
    error: str | None


# Kanka context resource structure
class KankaContextFields(TypedDict):
    """Core fields description."""

    name: str
    type: str
    entry: str
    tags: str
    is_hidden: str  # This stores the description of the is_hidden field


class KankaContextTerminology(TypedDict):
    """Terminology description."""

    entity_type: str
    type: str


class KankaContextMentions(TypedDict):
    """Mentions description."""

    description: str
    examples: list[str]
    note: str


class KankaContext(TypedDict):
    """Kanka context resource structure."""

    description: str
    supported_entities: dict[str, str]
    core_fields: KankaContextFields
    terminology: KankaContextTerminology
    posts: str
    mentions: KankaContextMentions
    limitations: str


# Check updates request/response
class CheckEntityUpdatesParams(TypedDict):
    """Parameters for check_entity_updates tool."""

    entity_ids: list[int]
    last_synced: str  # ISO 8601 timestamp


class CheckEntityUpdatesResult(TypedDict):
    """Result of checking entity updates."""

    modified_entity_ids: list[int]
    deleted_entity_ids: list[int]  # If API provides this
    check_timestamp: str  # ISO 8601 timestamp
