"""Unit tests for the service module with mocked KankaClient."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from mcp_kanka.service import KankaService


class TestKankaService:
    """Test the KankaService class with mocked dependencies."""

    @patch("mcp_kanka.service.KankaClient")
    @patch.dict("os.environ", {"KANKA_TOKEN": "test-token", "KANKA_CAMPAIGN_ID": "123"})
    def setup_method(self, method, mock_client_class):
        """Set up test fixtures with mocked client."""
        self.mock_client = MagicMock()
        mock_client_class.return_value = self.mock_client

        self.service = KankaService()

        # Set up mock managers
        self.mock_client.characters = MagicMock()
        self.mock_client.creatures = MagicMock()
        self.mock_client.locations = MagicMock()
        self.mock_client.organisations = MagicMock()
        self.mock_client.races = MagicMock()
        self.mock_client.notes = MagicMock()
        self.mock_client.journals = MagicMock()
        self.mock_client.quests = MagicMock()
        self.mock_client.tags = MagicMock()
        self.mock_client.events = MagicMock()

    def test_initialization_missing_token(self):
        """Test initialization fails without token."""
        with (
            patch.dict("os.environ", {"KANKA_CAMPAIGN_ID": "123"}, clear=True),
            pytest.raises(ValueError, match="KANKA_TOKEN.*required"),
        ):
            KankaService()

    def test_initialization_missing_campaign_id(self):
        """Test initialization fails without campaign ID."""
        with (
            patch.dict("os.environ", {"KANKA_TOKEN": "test-token"}, clear=True),
            pytest.raises(ValueError, match="KANKA_CAMPAIGN_ID.*required"),
        ):
            KankaService()

    def test_search_entities(self):
        """Test entity search functionality."""
        # Mock list results for each entity type
        mock_char1 = Mock()
        mock_char1.entity_id = 1
        mock_char1.name = "Alice"

        mock_char2 = Mock()
        mock_char2.entity_id = 2
        mock_char2.name = "Bob"

        mock_loc = Mock()
        mock_loc.entity_id = 3
        mock_loc.name = "Cave"

        # Set up list() to return appropriate results for each entity type
        self.mock_client.characters.list.return_value = [mock_char1, mock_char2]
        self.mock_client.creatures.list.return_value = []
        self.mock_client.locations.list.return_value = [mock_loc]
        self.mock_client.organisations.list.return_value = []
        self.mock_client.races.list.return_value = []
        self.mock_client.notes.list.return_value = []
        self.mock_client.journals.list.return_value = []
        self.mock_client.quests.list.return_value = []

        # Test search without type filter
        results = self.service.search_entities("test query", limit=100)

        assert len(results) == 3
        assert results[0]["entity_id"] == 1
        assert results[0]["name"] == "Alice"
        assert results[0]["entity_type"] == "character"

        # Verify list was called with name filter
        self.mock_client.characters.list.assert_called_with(
            name="test query", limit=100
        )

    def test_search_entities_with_type_filter(self):
        """Test entity search with type filtering."""
        # Mock list results for characters only
        mock_char1 = Mock()
        mock_char1.entity_id = 1
        mock_char1.name = "Alice"

        mock_char2 = Mock()
        mock_char2.entity_id = 2
        mock_char2.name = "Bob"

        # Only characters.list should be called when filtering by type
        self.mock_client.characters.list.return_value = [mock_char1, mock_char2]

        # Test search with type filter
        results = self.service.search_entities(
            "test", entity_type="character", limit=50
        )

        assert len(results) == 2  # Only characters
        assert all(r["entity_type"] == "character" for r in results)

        # Verify only characters endpoint was called
        self.mock_client.characters.list.assert_called_once_with(name="test", limit=50)

    def test_global_search_entities_skips_malformed_rows(self):
        """Test global_search_entities skips rows missing entity_id."""
        valid = Mock()
        valid.id = 10
        valid.entity_id = 101
        valid.name = "Valid"
        valid.image = None
        valid.type = "character"
        valid.tooltip = "ok"
        valid.url = "/entities/101"
        valid.is_private = False
        valid.created_at = datetime.now(timezone.utc)
        valid.updated_at = datetime.now(timezone.utc)

        malformed = Mock()
        malformed.id = 11
        malformed.name = "Broken"
        malformed.entity_id = None

        self.mock_client.search.return_value = [valid, malformed]

        results = self.service.global_search_entities("term", page=2)

        assert len(results) == 1
        assert results[0]["entity_id"] == 101
        self.mock_client.search.assert_called_once_with("term", page=2)

    def test_global_search_entities_supports_dict_rows(self):
        """Test global_search_entities handles dict-shaped rows defensively."""
        self.mock_client.search.return_value = [
            {
                "id": 12,
                "entity_id": 202,
                "name": "Map Entry",
                "type": "map",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }
        ]

        results = self.service.global_search_entities("map")

        assert len(results) == 1
        assert results[0]["entity_id"] == 202
        assert results[0]["type"] == "map"

    def test_global_search_entities_falls_back_to_raw_on_sdk_error(self):
        """Test SDK search errors fallback to raw endpoint parsing."""
        self.mock_client.search.side_effect = Exception("pydantic validation error")
        self.mock_client._request.return_value = {
            "data": [
                {
                    "id": 303,
                    "name": "Calendar Row",
                    "type": "calendar",
                    "url": "/calendars/1",
                }
            ]
        }

        results = self.service.global_search_entities("calendar")

        assert len(results) == 1
        assert results[0]["entity_id"] == 303
        self.mock_client._request.assert_called_once()

    def test_list_entities(self):
        """Test listing entities of a specific type."""
        # Mock entity objects - set attributes properly
        mock_entity1 = Mock()
        mock_entity1.id = 1
        mock_entity1.entity_id = 101
        mock_entity1.name = "Alice"
        mock_entity1.type = "NPC"
        mock_entity1.visibility_id = 1  # Visible

        mock_entity2 = Mock()
        mock_entity2.id = 2
        mock_entity2.entity_id = 102
        mock_entity2.name = "Bob"
        mock_entity2.type = "Player"
        mock_entity2.visibility_id = 2  # Hidden

        mock_entities = [mock_entity1, mock_entity2]
        self.mock_client.characters.list.return_value = mock_entities
        # Mock pagination properties
        type(self.mock_client.characters).has_next_page = PropertyMock(
            return_value=False
        )

        # Test list with pagination
        results = self.service.list_entities("character", page=1, limit=10)

        assert len(results) == 2
        assert results[0].name == "Alice"
        self.mock_client.characters.list.assert_called_once_with(page=1, related=False)

    def test_list_entities_all(self):
        """Test listing all entities (limit=0)."""
        # Mock entity objects - set attributes properly
        mock_entities = []
        for i in range(1, 6):
            mock = Mock()
            mock.id = i
            mock.name = f"Entity{i}"
            mock_entities.append(mock)

        # Mock pagination - return all on first page
        self.mock_client.locations.list.return_value = mock_entities
        # Mock pagination properties
        type(self.mock_client.locations).has_next_page = PropertyMock(
            return_value=False
        )

        # Test list all
        results = self.service.list_entities("location", page=1, limit=0)

        assert len(results) == 5
        # Should have called list without limit (pagination uses has_next_page)
        self.mock_client.locations.list.assert_called_with(page=1, related=False)

    def test_create_entity_basic(self):
        """Test creating a basic entity."""
        # Mock created entity - set attributes properly
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Character"
        mock_entity.type = "NPC"
        mock_entity.is_private = False  # Public
        mock_entity.tags = []
        mock_entity.entry = "<p>Test description</p>"
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None  # No posts by default
        self.mock_client.characters.create.return_value = mock_entity

        # Initialize tag cache to empty
        self.service._tag_cache = {}

        # Test create
        result = self.service.create_entity(
            entity_type="character",
            name="Test Character",
            type="NPC",
            entry="Test description",
        )

        assert result["id"] == 1
        assert result["entity_id"] == 101
        assert result["name"] == "Test Character"
        assert result["mention"] == "[entity:101]"

        # Check the call was made correctly
        self.mock_client.characters.create.assert_called_once()
        call_args = self.mock_client.characters.create.call_args[1]
        assert call_args["name"] == "Test Character"
        assert call_args["type"] == "NPC"
        assert "<p>Test description</p>" in call_args["entry"]

    def test_create_character_with_extended_fields(self):
        mock_entity = Mock()
        mock_entity.id = 7
        mock_entity.entity_id = 70
        mock_entity.name = "Aria"
        mock_entity.type = "PC"
        mock_entity.is_private = False
        mock_entity.tags = []
        mock_entity.entry = None
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None
        self.mock_client.characters.create.return_value = mock_entity
        self.service._tag_cache = {}

        self.service.create_entity(
            entity_type="character",
            name="Aria",
            title="Captain",
            age="32",
            sex="F",
            pronouns="she/her",
            location_id=12,
            is_dead=False,
            race_id=3,
            family_id=4,
        )

        kwargs = self.mock_client.characters.create.call_args.kwargs
        assert kwargs["title"] == "Captain"
        assert kwargs["age"] == "32"
        assert kwargs["sex"] == "F"
        assert kwargs["pronouns"] == "she/her"
        assert kwargs["location_id"] == 12
        assert kwargs["is_dead"] is False
        assert kwargs["race_id"] == 3
        assert kwargs["family_id"] == 4

    def test_update_location_parent_location_id_maps_to_api_location_id(self):
        with patch.object(
            self.service,
            "get_entity_by_id",
            return_value={
                "id": 18,
                "entity_id": 180,
                "entity_type": "location",
                "name": "District",
            },
        ):
            self.service.update_entity(180, parent_location_id=9, is_map_private=True)

        self.mock_client.locations.update.assert_called_once()
        kwargs = self.mock_client.locations.update.call_args.kwargs
        assert kwargs["location_id"] == 9
        assert kwargs["is_map_private"] is True

    def test_create_event_with_calendar_fields(self):
        """Event create passes calendar placement to the API."""
        mock_entity = Mock()
        mock_entity.id = 5
        mock_entity.entity_id = 55
        mock_entity.name = "Festival"
        mock_entity.type = "holiday"
        mock_entity.is_private = False
        mock_entity.tags = []
        mock_entity.entry = None
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None
        self.mock_client.events.create.return_value = mock_entity
        self.service._tag_cache = {}

        self.service.create_entity(
            entity_type="event",
            name="Festival",
            type="holiday",
            calendar_id=1,
            calendar_year=2026,
            calendar_month=3,
            calendar_day=30,
        )

        self.mock_client.events.create.assert_called_once()
        kwargs = self.mock_client.events.create.call_args.kwargs
        assert kwargs["name"] == "Festival"
        assert kwargs["type"] == "holiday"
        assert kwargs["calendar_id"] == 1
        assert kwargs["calendar_year"] == 2026
        assert kwargs["calendar_month"] == 3
        assert kwargs["calendar_day"] == 30

    def test_create_event_event_parent_id_maps_to_api_event_id(self):
        """MCP event_parent_id is sent as Kanka's event_id (parent module child id)."""
        mock_entity = Mock()
        mock_entity.id = 6
        mock_entity.entity_id = 66
        mock_entity.name = "Child"
        mock_entity.type = "session"
        mock_entity.is_private = False
        mock_entity.tags = []
        mock_entity.entry = None
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None
        self.mock_client.events.create.return_value = mock_entity
        self.service._tag_cache = {}

        self.service.create_entity(
            entity_type="event",
            name="Child",
            type="session",
            event_parent_id=99,
        )

        kwargs = self.mock_client.events.create.call_args.kwargs
        assert kwargs["event_id"] == 99
        assert "calendar_id" not in kwargs

    def test_update_event_event_parent_id_maps_to_api_event_id(self):
        with patch.object(
            self.service,
            "get_entity_by_id",
            return_value={
                "id": 42,
                "entity_id": 500,
                "entity_type": "event",
                "name": "Child",
            },
        ):
            self.service.update_entity(500, event_parent_id=11)

        self.mock_client.events.update.assert_called_once()
        assert self.mock_client.events.update.call_args[0][0] == 42
        assert self.mock_client.events.update.call_args[1]["event_id"] == 11

    def test_update_event_calendar_id_null_is_sent(self):
        with patch.object(
            self.service,
            "get_entity_by_id",
            return_value={
                "id": 42,
                "entity_id": 500,
                "entity_type": "event",
                "name": "Child",
            },
        ):
            self.service.update_entity(500, calendar_id=None, calendar_id_set=True)

        self.mock_client.events.update.assert_called_once()
        assert self.mock_client.events.update.call_args[0][0] == 42
        assert "calendar_id" in self.mock_client.events.update.call_args[1]
        assert self.mock_client.events.update.call_args[1]["calendar_id"] is None

    def test_list_calendar_events_all_merges_pages(self):
        def fake_list(calendar_id: int, page: int = 1, limit: int = 15):
            if page == 1:
                return {
                    "data": [{"id": "a"}],
                    "meta": {"last_page": 2},
                }
            return {
                "data": [{"id": "b"}],
                "meta": {"last_page": 2},
            }

        with patch.object(self.service, "list_calendar_events", side_effect=fake_list):
            out = self.service.list_calendar_events_all(99, limit=15)

        assert [x["id"] for x in out["data"]] == ["a", "b"]
        assert out["meta"]["fetch_all"] is True
        assert out["meta"]["total"] == 2

    def test_create_entity_with_tags(self):
        """Test creating an entity with tags."""
        # Mock tag lookup/creation - set attributes properly
        mock_tag1 = Mock()
        mock_tag1.id = 1
        mock_tag1.name = "hero"

        mock_tag2 = Mock()
        mock_tag2.id = 2
        mock_tag2.name = "warrior"

        # Mock tag list pagination
        self.mock_client.tags.list.return_value = [mock_tag1]
        self.mock_client.tags.create.return_value = mock_tag2

        # Mock created entity
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Character"
        mock_entity.tags = [1, 2]
        mock_entity.entry = "<p>Test description</p>"  # Need entry for conversion
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None  # No posts by default
        self.mock_client.characters.create.return_value = mock_entity

        # Initialize tag cache
        self.service._tag_cache = {}

        # Test create with tags
        self.service.create_entity(
            entity_type="character", name="Test Character", tags=["hero", "warrior"]
        )

        # Check tags were handled
        self.mock_client.tags.list.assert_called()
        self.mock_client.tags.create.assert_called_once_with(name="warrior")

        # Check entity was created with tag IDs
        call_args = self.mock_client.characters.create.call_args[1]
        assert call_args["tags"] == [1, 2]

    def test_get_entity_by_id_falls_back_from_child_id(self):
        """Test resolving module child id to entity_id when direct lookup misses."""
        self.mock_client.entity.side_effect = [
            None,
            {"id": 123, "entity_id": 555, "type": "location", "name": "Hokkaido"},
        ]
        candidate = Mock()
        candidate.entity_id = 555
        self.mock_client.locations.get.side_effect = [candidate, Exception("no sdk row")]

        result = self.service.get_entity_by_id(123)

        assert result is not None
        assert result["entity_id"] == 555
        assert self.mock_client.entity.call_count == 2

    def test_get_entities_bulk_maps_rows(self):
        """Test bulk entity retrieval maps entities by entity_id."""
        self.mock_client._request.return_value = {
            "data": [
                {
                    "id": 1,
                    "entity_id": 101,
                    "name": "A",
                    "type": "character",
                    "is_private": False,
                },
                {
                    "id": 2,
                    "entity_id": 202,
                    "name": "B",
                    "type": "organisation",
                    "is_private": True,
                },
            ]
        }

        result = self.service.get_entities_bulk([101, 202], include_posts=False)

        assert set(result.keys()) == {101, 202}
        assert result[101]["entity_type"] == "character"
        assert result[202]["entity_type"] == "organization"
        self.mock_client._request.assert_called_once()

    def test_update_entity(self):
        """Test updating an entity."""
        # Mock getting entity to find its type
        self.service.get_entity_by_id = Mock(
            return_value={
                "id": 1,
                "entity_id": 101,
                "entity_type": "character",
                "name": "Old Name",
            }
        )

        # Mock update
        self.mock_client.characters.update.return_value = None

        # Test update
        result = self.service.update_entity(
            entity_id=101, name="New Name", type="Updated NPC"
        )

        assert result is True
        self.mock_client.characters.update.assert_called_once_with(
            1, name="New Name", type="Updated NPC"  # The type-specific ID
        )

    def test_update_entity_not_found(self):
        """Test updating non-existent entity."""
        self.service.get_entity_by_id = Mock(return_value=None)

        with pytest.raises(ValueError, match="Entity 999 not found"):
            self.service.update_entity(entity_id=999, name="Test")

    def test_delete_entity(self):
        """Test deleting an entity."""
        # Mock getting entity to find its type
        self.service.get_entity_by_id = Mock(
            return_value={"id": 1, "entity_id": 101, "entity_type": "character"}
        )

        # Mock delete
        self.mock_client.characters.delete.return_value = None

        # Test delete
        result = self.service.delete_entity(entity_id=101)

        assert result is True
        self.mock_client.characters.delete.assert_called_once_with(1)

    def test_create_post(self):
        """Test creating a post on an entity."""
        # Mock getting entity
        self.service.get_entity_by_id = Mock(
            return_value={"id": 1, "entity_id": 101, "entity_type": "character"}
        )

        # Mock post creation - set attributes properly
        mock_post = Mock()
        mock_post.id = 50
        self.mock_client.characters.create_post.return_value = mock_post

        # Test create post
        result = self.service.create_post(
            entity_id=101, name="Test Post", entry="Post content", is_hidden=True
        )

        assert result["post_id"] == 50
        assert result["entity_id"] == 101

        # Check the call
        self.mock_client.characters.create_post.assert_called_once()
        call_args = self.mock_client.characters.create_post.call_args
        assert call_args[0] == (101,)  # Entity ID
        assert call_args[1]["name"] == "Test Post"
        assert call_args[1]["visibility_id"] == 2  # Admin visibility

    def test_update_post(self):
        """Test updating a post."""
        # Mock getting entity
        self.service.get_entity_by_id = Mock(
            return_value={"id": 1, "entity_id": 101, "entity_type": "character"}
        )

        # Test update post
        result = self.service.update_post(
            entity_id=101, post_id=50, name="Updated Post", entry="Updated content"
        )

        assert result is True
        self.mock_client.characters.update_post.assert_called_once()

    def test_delete_post(self):
        """Test deleting a post."""
        # Mock getting entity
        self.service.get_entity_by_id = Mock(
            return_value={"id": 1, "entity_id": 101, "entity_type": "character"}
        )

        # Test delete post
        result = self.service.delete_post(entity_id=101, post_id=50)

        assert result is True
        self.mock_client.characters.delete_post.assert_called_once_with(101, 50)

    def test_entity_to_dict_conversion(self):
        """Test converting entity object to dictionary."""
        # Mock entity - set attributes properly
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Entity"
        mock_entity.type = "NPC"
        mock_entity.is_private = True  # Private entity (hidden)

        # Mock tags
        tag1 = Mock()
        tag1.name = "hero"
        tag2 = Mock()
        tag2.name = "warrior"
        mock_entity.tags = [tag1, tag2]

        mock_entity.entry = "<p>HTML content</p>"
        mock_entity.created_at = datetime.now()
        mock_entity.updated_at = datetime.now()
        mock_entity.posts = None  # No posts by default

        # Initialize tag cache
        self.service._tag_cache = {}

        # Test conversion
        result = self.service._entity_to_dict(mock_entity, "character")

        assert result["id"] == 1
        assert result["entity_id"] == 101
        assert result["name"] == "Test Entity"
        assert result["entity_type"] == "character"
        assert result["type"] == "NPC"
        assert result["is_hidden"] is True
        assert "HTML content" in result["entry"]  # Should be converted to markdown

    def test_get_or_create_tags(self):
        """Test tag creation and caching."""
        # Mock existing tags
        existing_tag = Mock()
        existing_tag.id = 1
        existing_tag.name = "existing"
        # Mock tag list pagination
        self.mock_client.tags.list.return_value = [existing_tag]

        # Mock tag creation
        new_tag = Mock()
        new_tag.id = 2
        new_tag.name = "new"
        self.mock_client.tags.create.return_value = new_tag

        # Test get/create tags
        tag_ids = self.service._get_or_create_tag_ids(["existing", "new", "EXISTING"])

        assert len(tag_ids) == 3
        assert 1 in tag_ids  # existing tag
        assert 2 in tag_ids  # new tag
        assert tag_ids.count(1) == 2  # "existing" and "EXISTING" map to same tag

        # Check new tag was created
        self.mock_client.tags.create.assert_called_once_with(name="new")

    def test_entity_to_dict_with_timestamps(self):
        """Test entity conversion includes timestamps."""
        # Mock entity with timestamps
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Entity"
        mock_entity.type = "NPC"
        mock_entity.is_private = False  # Public
        mock_entity.tags = []
        mock_entity.entry = None
        mock_entity.created_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_entity.updated_at = datetime(2023, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_entity.posts = None  # No posts by default

        # Initialize tag cache
        self.service._tag_cache = {}

        # Test conversion
        result = self.service._entity_to_dict(mock_entity, "character")

        assert result["created_at"] == "2023-01-01T10:00:00+00:00"
        assert result["updated_at"] == "2023-06-15T14:30:00+00:00"

    def test_entity_to_dict_missing_timestamps(self):
        """Test entity conversion handles missing timestamps gracefully."""
        # Mock entity without timestamps
        mock_entity = Mock(
            spec=["id", "entity_id", "name", "type", "is_private", "tags", "entry"]
        )
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Entity"
        mock_entity.type = "NPC"
        mock_entity.is_private = False  # Public
        mock_entity.tags = []
        mock_entity.entry = None
        # No created_at or updated_at attributes

        # Test conversion
        result = self.service._entity_to_dict(mock_entity, "character")

        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_list_entities_with_last_sync(self):
        """Test list_entities passes lastSync parameter correctly."""
        # Mock response
        mock_entity = Mock()
        mock_entity.id = 1
        mock_entity.entity_id = 101
        mock_entity.name = "Test Character"
        mock_entity.updated_at = datetime(2023, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

        self.mock_client.characters.list.return_value = [mock_entity]
        # Mock pagination properties
        type(self.mock_client.characters).has_next_page = PropertyMock(
            return_value=False
        )

        # Test with last_sync
        last_sync_time = "2023-06-01T00:00:00Z"
        entities = self.service.list_entities(
            "character", page=1, limit=30, last_sync=last_sync_time
        )

        # Verify lastSync was passed (note: no limit passed to SDK since we use client-side limiting)
        self.mock_client.characters.list.assert_called_with(
            page=1, related=False, lastSync=last_sync_time
        )

        assert len(entities) == 1
        assert entities[0].id == 1

    def test_list_entities_with_last_sync_pagination(self):
        """Test list_entities with lastSync and pagination."""
        # Mock paginated responses
        mock_entities_page1 = [Mock(id=i, entity_id=100 + i) for i in range(1, 101)]
        mock_entities_page2 = [Mock(id=i, entity_id=200 + i) for i in range(101, 151)]

        self.mock_client.characters.list.side_effect = [
            mock_entities_page1,
            mock_entities_page2[:50],  # Only 50 items in page 2, so we know we're done
        ]

        # Mock pagination properties - first call has next page, second doesn't
        type(self.mock_client.characters).has_next_page = PropertyMock(
            side_effect=[True, False]
        )

        # Test with limit=0 (get all) and last_sync
        last_sync_time = "2023-06-01T00:00:00Z"
        entities = self.service.list_entities(
            "character", page=1, limit=0, last_sync=last_sync_time
        )

        # Verify pages were fetched with lastSync
        assert self.mock_client.characters.list.call_count == 2
        for call in self.mock_client.characters.list.call_args_list:
            assert call[1].get("lastSync") == last_sync_time

        assert len(entities) == 150

    def test_get_map_marker_returns_data(self):
        """GET single map marker returns inner data dict."""
        self.mock_client._request.return_value = {
            "data": {"id": 9, "name": "X", "map_id": 3},
        }
        d = self.service.get_map_marker(3, 9)
        assert d["name"] == "X"
        self.mock_client._request.assert_called_once_with(
            "GET", "maps/3/map_markers/9"
        )

    def test_update_map_marker_clear_entity_merges_name_from_get(self):
        """Clearing entity_id without name triggers GET and PATCH includes current name."""
        self.mock_client._request.side_effect = [
            {"data": {"id": 1, "name": "Shikoku", "map_id": 2}},
            {"data": {"id": 1, "name": "Shikoku", "entity_id": None}},
        ]
        self.service.update_map_marker(2, 1, {"entity_id": None})
        assert self.mock_client._request.call_count == 2
        get_call = self.mock_client._request.call_args_list[0]
        assert get_call[0] == ("GET", "maps/2/map_markers/1")
        patch_call = self.mock_client._request.call_args_list[1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["name"] == "Shikoku"
        assert patch_call[1]["json"]["entity_id"] is None
        assert patch_call[1]["json"]["map_id"] == 2

    def test_update_map_marker_clear_entity_with_explicit_name_skips_get(self):
        """When name is provided, no GET is needed to clear entity_id."""
        self.mock_client._request.return_value = {"data": {}}
        self.service.update_map_marker(
            2, 1, {"entity_id": None, "name": "Shikoku"}
        )
        self.mock_client._request.assert_called_once()
        assert self.mock_client._request.call_args[0][0] == "PATCH"
