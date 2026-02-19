"""Type definitions for the Kanka MCP server."""

from typing import Any, Literal, TypedDict

# Supported entity types
EntityType = Literal[
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
    date_range: DateRange | None
    include_full: bool | None
    page: int | None
    limit: int | None
    last_synced: str | None  # ISO 8601 timestamp


class EntityInput(TypedDict, total=False):
    """Input for creating an entity."""

    entity_type: EntityType  # required
    name: str  # required
    type: str | None
    entry: str | None
    tags: list[str] | None
    is_hidden: bool | None
    # Nesting: parent entity of the same type
    parent_id: int | None
    # Character-specific
    location_id: int | None
    title: str | None
    age: str | None
    sex: str | None
    pronouns: str | None
    is_dead: bool | None
    races: list[int] | None
    families: list[int] | None
    # Organisation-specific
    is_defunct: bool | None
    # Journal-specific
    date: str | None
    character_id: int | None
    # Family-specific
    is_extinct: bool | None
    # Item-specific
    creator_id: int | None
    price: str | None
    size: str | None
    weight: str | None
    # Tag-specific
    colour: str | None
    # Quest-specific
    is_completed: bool | None
    # Map-specific
    center_marker_id: int | None
    center_x: float | None
    center_y: float | None
    is_real: bool | None
    # Event-specific
    calendar_id: int | None
    calendar_year: int | None
    calendar_month: int | None
    calendar_day: int | None
    # Image fields
    image_uuid: str | None
    header_uuid: str | None


class CreateEntitiesParams(TypedDict):
    """Parameters for create_entities tool."""

    entities: list[EntityInput]


class EntityUpdate(TypedDict, total=False):
    """Update for an entity."""

    entity_id: int  # required
    name: str  # required
    type: str | None
    entry: str | None
    tags: list[str] | None
    is_hidden: bool | None
    # Nesting: parent entity of the same type
    parent_id: int | None
    # Character-specific
    location_id: int | None
    title: str | None
    age: str | None
    sex: str | None
    pronouns: str | None
    is_dead: bool | None
    races: list[int] | None
    families: list[int] | None
    # Organisation-specific
    is_defunct: bool | None
    # Journal-specific
    date: str | None
    character_id: int | None
    # Family-specific
    is_extinct: bool | None
    # Item-specific
    creator_id: int | None
    price: str | None
    size: str | None
    weight: str | None
    # Tag-specific
    colour: str | None
    # Quest-specific
    is_completed: bool | None
    # Map-specific
    center_marker_id: int | None
    center_x: float | None
    center_y: float | None
    is_real: bool | None
    # Event-specific
    calendar_id: int | None
    calendar_year: int | None
    calendar_month: int | None
    calendar_day: int | None
    # Image fields
    image_uuid: str | None
    header_uuid: str | None


class UpdateEntitiesParams(TypedDict):
    """Parameters for update_entities tool."""

    updates: list[EntityUpdate]


class GetEntitiesParams(TypedDict):
    """Parameters for get_entities tool."""

    entity_ids: list[int]
    include_posts: bool | None


class DeleteEntitiesParams(TypedDict):
    """Parameters for delete_entities tool."""

    entity_ids: list[int]


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
    name: str
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
    # Nesting
    parent_id: int | None
    # Character-specific
    location_id: int | None
    title: str | None
    age: str | None
    sex: str | None
    pronouns: str | None
    is_dead: bool | None
    races: list[int] | None
    families: list[int] | None
    # Organisation-specific
    is_defunct: bool | None
    # Journal-specific
    date: str | None
    character_id: int | None
    # Family-specific
    is_extinct: bool | None
    # Item-specific
    creator_id: int | None
    price: str | None
    size: str | None
    weight: str | None
    # Tag-specific
    colour: str | None
    # Quest-specific
    is_completed: bool | None
    # Map-specific
    center_marker_id: int | None
    center_x: float | None
    center_y: float | None
    is_real: bool | None
    # Event-specific (date shared with journal)
    calendar_id: int | None
    calendar_year: int | None
    calendar_month: int | None
    calendar_day: int | None
    # Image fields
    image: str | None
    image_full: str | None
    image_thumb: str | None
    image_uuid: str | None
    header_uuid: str | None


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
    # Nesting
    parent_id: int | None
    # Character-specific
    location_id: int | None
    title: str | None
    age: str | None
    sex: str | None
    pronouns: str | None
    is_dead: bool | None
    races: list[int] | None
    families: list[int] | None
    # Organisation-specific
    is_defunct: bool | None
    # Journal-specific
    date: str | None
    character_id: int | None
    # Family-specific
    is_extinct: bool | None
    # Item-specific
    creator_id: int | None
    price: str | None
    size: str | None
    weight: str | None
    # Tag-specific
    colour: str | None
    # Quest-specific
    is_completed: bool | None
    # Map-specific
    center_marker_id: int | None
    center_x: float | None
    center_y: float | None
    is_real: bool | None
    # Event-specific
    calendar_id: int | None
    calendar_year: int | None
    calendar_month: int | None
    calendar_day: int | None
    # Image fields
    image: str | None
    image_full: str | None
    image_thumb: str | None
    image_uuid: str | None
    header_uuid: str | None


class DeleteEntityResult(TypedDict):
    """Result of deleting an entity."""

    entity_id: int
    success: bool
    error: str | None


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


# --- Sub-resource types: Relations ---

ActionType = Literal["create", "update", "delete", "list"]


class RelationAction(TypedDict, total=False):
    """A single relation action."""

    action: ActionType  # required
    entity_id: int  # required
    relation_id: int | None
    target_id: int | None
    relation: str | None
    attitude: int | None
    two_way: bool | None
    colour: str | None
    is_pinned: bool | None
    is_hidden: bool | None


class RelationData(TypedDict, total=False):
    """Relation data returned from API."""

    id: int
    owner_id: int
    target_id: int
    relation: str
    attitude: int | None
    is_pinned: bool
    is_hidden: bool
    colour: str | None


class RelationActionResult(TypedDict, total=False):
    """Result of a single relation action."""

    action: str
    entity_id: int
    relation_id: int | None
    success: bool
    error: str | None
    relation: RelationData | None
    relations: list[RelationData] | None


# --- Sub-resource types: Attributes ---


class AttributeAction(TypedDict, total=False):
    """A single attribute action."""

    action: ActionType  # required (create/update/delete/list) plus "bulk_patch"
    entity_id: int  # required
    attribute_id: int | None
    name: str | None
    value: str | None
    type_id: int | None
    is_pinned: bool | None
    is_hidden: bool | None
    api_key: str | None
    default_order: int | None
    # For bulk_patch: array of attribute dicts
    attributes: list[dict[str, Any]] | None


class AttributeData(TypedDict, total=False):
    """Attribute data returned from API."""

    id: int
    entity_id: int
    name: str
    value: str | None
    type_id: int
    is_pinned: bool
    is_hidden: bool
    api_key: str | None
    default_order: int
    parsed: str | None


class AttributeActionResult(TypedDict, total=False):
    """Result of a single attribute action."""

    action: str
    entity_id: int
    attribute_id: int | None
    success: bool
    error: str | None
    attribute: AttributeData | None
    attributes: list[AttributeData] | None


# --- Sub-resource types: Organisation Members ---


class OrgMemberAction(TypedDict, total=False):
    """A single organisation member action."""

    action: ActionType  # required
    organisation_id: int  # required (entity_id of the org)
    member_id: int | None
    character_id: int | None
    role: str | None
    is_hidden: bool | None
    status_id: int | None
    parent_id: int | None
    pin_id: int | None


class OrgMemberData(TypedDict, total=False):
    """Organisation member data returned from API."""

    id: int
    character_id: int
    organisation_id: int
    role: str | None
    is_hidden: bool
    status_id: int | None
    pin_id: int | None
    parent_id: int | None


class OrgMemberActionResult(TypedDict, total=False):
    """Result of a single org member action."""

    action: str
    organisation_id: int
    member_id: int | None
    success: bool
    error: str | None
    member: OrgMemberData | None
    members: list[OrgMemberData] | None


# --- Sub-resource types: Map Markers ---


class MapMarkerAction(TypedDict, total=False):
    """A single map marker action."""

    action: ActionType  # required
    map_id: int  # required
    marker_id: int | None
    name: str | None
    entity_id: int | None
    latitude: float | None
    longitude: float | None
    shape_id: int | None
    icon: str | None
    size_id: int | None
    custom_icon: str | None
    is_draggable: bool | None
    pin_size: str | None
    entry: str | None
    type_id: int | None
    group_id: int | None
    is_hidden: bool | None


class MapMarkerData(TypedDict, total=False):
    """Map marker data returned from API."""

    id: int
    map_id: int
    name: str | None
    entity_id: int | None
    latitude: float | None
    longitude: float | None
    shape_id: int | None
    icon: str | None
    size_id: int | None
    custom_icon: str | None
    is_draggable: bool
    pin_size: str | None
    entry: str | None
    type_id: int | None
    group_id: int | None
    visibility_id: int | None


class MapMarkerActionResult(TypedDict, total=False):
    """Result of a single map marker action."""

    action: str
    map_id: int
    marker_id: int | None
    success: bool
    error: str | None
    marker: MapMarkerData | None
    markers: list[MapMarkerData] | None


# --- Sub-resource types: Map Groups ---


class MapGroupAction(TypedDict, total=False):
    """A single map group action."""

    action: ActionType  # required
    map_id: int  # required
    group_id: int | None
    name: str | None
    parent_id: int | None
    is_shown: bool | None
    position: str | None
    visibility_id: int | None
    is_hidden: bool | None


class MapGroupData(TypedDict, total=False):
    """Map group data returned from API."""

    id: int
    map_id: int
    name: str
    parent_id: int | None
    is_shown: bool
    position: str | None
    visibility_id: int | None


class MapGroupActionResult(TypedDict, total=False):
    """Result of a single map group action."""

    action: str
    map_id: int
    group_id: int | None
    success: bool
    error: str | None
    group: MapGroupData | None
    groups: list[MapGroupData] | None


# --- Sub-resource types: Map Layers ---


class MapLayerAction(TypedDict, total=False):
    """A single map layer action."""

    action: ActionType  # required
    map_id: int  # required
    layer_id: int | None
    name: str | None
    image_url: str | None
    entry: str | None
    type_id: int | None
    position: str | None
    visibility_id: int | None
    is_hidden: bool | None


class MapLayerData(TypedDict, total=False):
    """Map layer data returned from API."""

    id: int
    map_id: int
    name: str
    image_url: str | None
    entry: str | None
    type_id: int | None
    position: str | None
    visibility_id: int | None


class MapLayerActionResult(TypedDict, total=False):
    """Result of a single map layer action."""

    action: str
    map_id: int
    layer_id: int | None
    success: bool
    error: str | None
    layer: MapLayerData | None
    layers: list[MapLayerData] | None


# --- Sub-resource types: Timeline Eras ---


class TimelineEraAction(TypedDict, total=False):
    """A single timeline era action."""

    action: ActionType  # required
    timeline_id: int  # required
    era_id: int | None
    name: str | None
    abbreviation: str | None
    start_year: int | None
    end_year: int | None
    visibility: str | None


class TimelineEraData(TypedDict, total=False):
    """Timeline era data from API."""

    id: int
    timeline_id: int
    name: str
    abbreviation: str | None
    start_year: int | None
    end_year: int | None
    position: int | None
    elements: list[Any]


class TimelineEraActionResult(TypedDict, total=False):
    """Result of a timeline era action."""

    action: str
    timeline_id: int
    era_id: int | None
    success: bool
    error: str | None
    era: TimelineEraData | None
    eras: list[TimelineEraData] | None


# --- Sub-resource types: Timeline Elements ---


class TimelineElementAction(TypedDict, total=False):
    """A single timeline element action."""

    action: ActionType  # required
    timeline_id: int  # required
    element_id: int | None
    era_id: int  # required for create
    name: str | None
    entity_id: int | None
    entry: str | None
    date: str | None
    colour: str | None
    position: int | None
    is_hidden: bool | None


class TimelineElementData(TypedDict, total=False):
    """Timeline element data from API."""

    id: int
    timeline_id: int
    era_id: int
    name: str
    entity_id: int | None
    entry: str | None
    date: str | None
    colour: str | None
    position: int | None
    visibility_id: int | None


class TimelineElementActionResult(TypedDict, total=False):
    """Result of a timeline element action."""

    action: str
    timeline_id: int
    element_id: int | None
    success: bool
    error: str | None
    element: TimelineElementData | None
    elements: list[TimelineElementData] | None
