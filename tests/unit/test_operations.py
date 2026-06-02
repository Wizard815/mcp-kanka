"""Unit tests for the operations module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_kanka.operations import KankaOperations, create_operations, get_operations


class TestOperationsSetup:
    """Test operations instance creation and management."""

    def test_create_operations_with_service(self):
        """Test creating operations with a custom service."""
        mock_service = Mock()
        ops = create_operations(service=mock_service)
        assert isinstance(ops, KankaOperations)
        assert ops.service is mock_service

    def test_create_operations_without_service(self):
        """Test creating operations creates a default service."""
        with patch("mcp_kanka.operations.KankaService") as mock_service_class:
            mock_service_instance = Mock()
            mock_service_class.return_value = mock_service_instance

            ops = create_operations()

            assert isinstance(ops, KankaOperations)
            assert ops.service is mock_service_instance
            mock_service_class.assert_called_once()

    @patch("mcp_kanka.operations.get_service")
    def test_get_operations_singleton(self, mock_get_service):
        """Test get_operations returns singleton."""
        # Reset singleton for this test
        import mcp_kanka.operations

        mcp_kanka.operations._operations = None

        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # First call creates instance
        ops1 = get_operations()
        assert isinstance(ops1, KankaOperations)
        mock_get_service.assert_called_once()

        # Second call returns same instance
        ops2 = get_operations()
        assert ops1 is ops2
        mock_get_service.assert_called_once()  # Still only called once


class TestFindEntities:
    """Test find_entities operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_find_entities_with_query(self, mock_service_class):
        """Test finding entities with search query."""
        # Setup
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock entity objects
        mock_entity = Mock(id=1, entity_id=1, name="Test Entity", type="NPC")
        mock_service.list_entities.return_value = [mock_entity]
        mock_service._entity_to_dict.return_value = {
            "id": 1,
            "entity_id": 1,
            "name": "Test Entity",
            "entity_type": "character",
            "type": "NPC",
            "entry": "Test content with search term",
            "tags": [],
            "is_hidden": False,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.find_entities(
            query="search term", entity_type="character", include_full=True
        )

        # Verify
        assert isinstance(result, dict)
        assert "entities" in result
        assert "sync_info" in result
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Test Entity"

    @patch("mcp_kanka.operations.KankaService")
    async def test_find_entities_invalid_type(self, mock_service_class):
        """Test find_entities with invalid entity type."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Execute with invalid type
        result = await ops.find_entities(entity_type="invalid_type")

        # Should return empty result
        assert result == {"entities": [], "sync_info": {}}

    @pytest.mark.parametrize("entity_type", ["timeline", "calendar", "event"])
    @patch("mcp_kanka.operations.KankaService")
    async def test_find_entities_accepts_timeline_and_calendar_types(
        self, mock_service_class, entity_type
    ):
        """Test find_entities accepts timeline/calendar/event as valid entity types."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.list_entities.return_value = []

        ops = KankaOperations(service=mock_service)

        result = await ops.find_entities(entity_type=entity_type, include_full=False)

        assert "entities" in result
        assert "sync_info" in result
        assert result["entities"] == []
        mock_service.list_entities.assert_called_once()


class TestCreateEntities:
    """Test create_entities operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_single_entity_success(self, mock_service_class):
        """Test successfully creating a single entity."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock successful creation
        mock_service.create_entity.return_value = {
            "id": 1,
            "entity_id": 101,
            "name": "Test Character",
            "mention": "[entity:101]",
        }

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.create_entities(
            [
                {
                    "entity_type": "character",
                    "name": "Test Character",
                    "type": "NPC",
                    "entry": "A test character",
                }
            ]
        )

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["name"] == "Test Character"
        assert result[0]["error"] is None

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_entity_passes_extended_fields(self, mock_service_class):
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_entity.return_value = {
            "id": 2,
            "entity_id": 202,
            "name": "Aria",
            "mention": "[entity:202]",
        }
        ops = KankaOperations(service=mock_service)

        await ops.create_entities(
            [
                {
                    "entity_type": "character",
                    "name": "Aria",
                    "status": 2,
                    "title": "Captain",
                    "race_id": 4,
                    "family_id": 7,
                }
            ]
        )

        kwargs = mock_service.create_entity.call_args.kwargs
        assert kwargs["status"] == 2
        assert kwargs["title"] == "Captain"
        assert kwargs["race_id"] == 4
        assert kwargs["family_id"] == 7


class TestSearchEntities:
    """Test global search operation delegation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_search_entities_returns_service_results(self, mock_service_class):
        """Test search_entities returns list even with mixed result types."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.global_search_entities.return_value = [
            {"entity_id": 1, "name": "Ok"},
            {"entity_id": 2, "name": "Map"},
        ]
        ops = KankaOperations(service=mock_service)

        result = await ops.search_entities("term", page=3)

        assert len(result) == 2
        mock_service.global_search_entities.assert_called_once_with("term", page=3)

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_entity_invalid_type(self, mock_service_class):
        """Test creating entity with invalid type."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Execute with invalid type
        result = await ops.create_entities(
            [
                {
                    "entity_type": "invalid_type",
                    "name": "Test",
                }
            ]
        )

        # Verify error result
        assert len(result) == 1
        assert result[0]["success"] is False
        assert "Invalid entity_type" in result[0]["error"]
        assert result[0]["entity_id"] is None

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_entity_missing_name(self, mock_service_class):
        """Test creating entity without name."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Execute without name
        result = await ops.create_entities(
            [
                {
                    "entity_type": "character",
                    # Missing name
                }
            ]
        )

        # Verify error result
        assert len(result) == 1
        assert result[0]["success"] is False
        assert "Name is required" in result[0]["error"]

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_entities_partial_success(self, mock_service_class):
        """Test creating multiple entities with partial failure."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock mixed results
        mock_service.create_entity.side_effect = [
            {"id": 1, "entity_id": 101, "name": "Success", "mention": "[entity:101]"},
            Exception("API Error"),
        ]

        ops = KankaOperations(service=mock_service)

        # Execute multiple
        result = await ops.create_entities(
            [
                {"entity_type": "character", "name": "Success"},
                {"entity_type": "character", "name": "Failure"},
            ]
        )

        # Verify partial success
        assert len(result) == 2
        assert result[0]["success"] is True
        assert result[1]["success"] is False
        assert "API Error" in result[1]["error"]

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_character_ignores_legacy_reminder_payload(
        self, mock_service_class
    ):
        """Legacy inline reminder payload is ignored by create_entities."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.create_entity.return_value = {
            "id": 1,
            "entity_id": 101,
            "name": "Elder NPC",
            "mention": "[entity:101]",
        }

        ops = KankaOperations(service=mock_service)

        result = await ops.create_entities(
            entities=[
                {
                    "entity_type": "character",
                    "name": "Elder NPC",
                    "type": "NPC",
                    "reminder": {
                        "calendar_id": 8893860,
                        "year": 600,
                        "month": 1,
                        "day": 15,
                        "type": "birth",
                    },
                }
            ]
        )

        assert len(result) == 1
        assert result[0]["success"] is True
        assert "reminder_added" not in result[0]
        mock_service.create_calendar_reminder.assert_not_called()


class TestUpdateEntities:
    """Test update_entities operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_entity_success(self, mock_service_class):
        """Test successfully updating an entity."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.update_entity.return_value = True

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.update_entities([{"entity_id": 101, "name": "Updated Name"}])

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["error"] is None

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_entity_missing_id(self, mock_service_class):
        """Test updating entity without ID."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Execute without entity_id
        result = await ops.update_entities([{"name": "Updated Name"}])

        # Verify error
        assert len(result) == 1
        assert result[0]["success"] is False
        assert "entity_id is required" in result[0]["error"]

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_entity_missing_name(self, mock_service_class):
        """Test updating entity without name (name optional for PATCH)."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Mock successful update when name is omitted
        mock_service.update_entity.return_value = True

        # Execute without name
        result = await ops.update_entities([{"entity_id": 101}])

        # Verify error
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["error"] is None
        mock_service.update_entity.assert_called_once()
        assert mock_service.update_entity.call_args.kwargs["name"] is None
        assert mock_service.update_entity.call_args.kwargs["calendar_id_set"] is False

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_entity_passes_extended_fields(self, mock_service_class):
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.update_entity.return_value = True
        mock_service.raw_request.return_value = {"data": {"parent_id": 99}}

        ops = KankaOperations(service=mock_service)
        await ops.update_entities(
            [
                {
                    "entity_id": 101,
                    "parent_id": 99,
                    "parent_location_id": 9,
                    "is_map_private": True,
                    "status": 1,
                    "event_locations": [4, 5],
                    "calendar_year": 1200,
                    "calendar_month": 4,
                    "calendar_day": 22,
                    "icon": "fa-solid fa-crown",
                    "colour": "#123456",
                }
            ]
        )

        kwargs = mock_service.update_entity.call_args.kwargs
        assert kwargs["parent_id"] == 99
        assert kwargs["parent_id_set"] is True
        assert kwargs["parent_location_id"] == 9
        assert kwargs["is_map_private"] is True
        assert kwargs["status"] == 1
        assert kwargs["event_locations"] == [4, 5]
        assert kwargs["calendar_year"] == 1200
        assert kwargs["calendar_month"] == 4
        assert kwargs["calendar_day"] == 22
        assert kwargs["icon"] == "fa-solid fa-crown"
        assert kwargs["colour"] == "#123456"

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_entity_event_parent_verification_failure(self, mock_service_class):
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.update_entity.return_value = True
        mock_service.get_entity_by_id.return_value = {
            "id": 7,
            "entity_id": 101,
            "entity_type": "event",
            "name": "Child",
        }
        mock_service.module_child_id_to_global_entity.return_value = 200
        mock_service.read_entity_parent_global_id.return_value = (True, 303)

        ops = KankaOperations(service=mock_service)
        result = await ops.update_entities(
            [{"entity_id": 101, "event_parent_id": 77}]
        )

        assert len(result) == 1
        assert result[0]["success"] is False
        err = result[0]["error"] or ""
        assert "Parent verification failed" in err
        assert "200" in err and "303" in err
        mock_service.module_child_id_to_global_entity.assert_called_once_with(
            "event", 77
        )
        mock_service.read_entity_parent_global_id.assert_called_once_with(101)

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_event_explicit_null_calendar_id(self, mock_service_class):
        """Event update forwards explicit null calendar_id for detach."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.update_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        result = await ops.update_entities(
            [{"entity_id": 101, "calendar_id": None}]
        )

        assert len(result) == 1
        assert result[0]["success"] is True
        mock_service.update_entity.assert_called_once()
        assert mock_service.update_entity.call_args.kwargs["calendar_id"] is None
        assert mock_service.update_entity.call_args.kwargs["calendar_id_set"] is True


class TestGetEntities:
    """Test get_entities operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_get_entities_success(self, mock_service_class):
        """Test successfully getting entities."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock entity data
        mock_service.get_entity_by_id.return_value = {
            "id": 1,
            "entity_id": 101,
            "name": "Test Entity",
            "entity_type": "character",
            "type": "NPC",
            "entry": "Description",
            "tags": ["test"],
            "is_hidden": False,
            "parent_id": 500,
        }

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.get_entities([101], include_posts=False)

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["name"] == "Test Entity"
        assert result[0]["parent_id"] == 500
        assert "posts" not in result[0]

    @patch("mcp_kanka.operations.KankaService")
    async def test_get_entities_with_posts(self, mock_service_class):
        """Test getting entities with posts."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock entity with posts
        mock_service.get_entity_by_id.return_value = {
            "id": 1,
            "entity_id": 101,
            "name": "Test Entity",
            "entity_type": "character",
            "posts": [
                {"id": 1, "name": "Post 1", "entry": "Content 1"},
                {"id": 2, "name": "Post 2", "entry": "Content 2"},
            ],
        }

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.get_entities([101], include_posts=True)

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert "posts" in result[0]
        assert len(result[0]["posts"]) == 2

    @patch("mcp_kanka.operations.KankaService")
    async def test_get_entity_not_found(self, mock_service_class):
        """Test getting non-existent entity."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_entity_by_id.return_value = None

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.get_entities([999])

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is False
        assert "not found" in result[0]["error"]
        assert "find_entities" in result[0]["error"]

    @patch("mcp_kanka.operations.KankaService")
    async def test_get_entities_uses_bulk_for_multi_id(self, mock_service_class):
        """Test multi-ID fetch uses bulk endpoint and falls back per-id."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_entities_bulk.return_value = {
            101: {
                "id": 1,
                "entity_id": 101,
                "name": "Bulk Entity",
                "entity_type": "character",
                "parent_id": None,
            }
        }
        mock_service.get_entity_by_id.return_value = {
            "id": 2,
            "entity_id": 202,
            "name": "Single Entity",
            "entity_type": "character",
        }
        ops = KankaOperations(service=mock_service)

        result = await ops.get_entities([101, 202], include_posts=False)

        assert len(result) == 2
        assert result[0]["success"] is True
        assert result[1]["success"] is True
        assert result[0]["parent_id"] is None
        mock_service.get_entities_bulk.assert_called_once_with([101, 202], False)
        mock_service.get_entity_by_id.assert_called_once_with(202, False)

    @patch("mcp_kanka.operations.KankaService")
    async def test_get_entities_timeout_returns_partial_error(
        self, mock_service_class
    ):
        """Test timeout returns a per-entity error instead of failing whole response."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_entity_by_id.side_effect = TimeoutError()
        ops = KankaOperations(service=mock_service)

        result = await ops.get_entities([999], include_posts=False)

        assert len(result) == 1
        assert result[0]["success"] is False
        assert "Timed out" in result[0]["error"]


class TestDeleteEntities:
    """Test delete_entities operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entity_success(self, mock_service_class):
        """Test successfully deleting an entity."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.delete_entities([101])

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["error"] is None

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entity_failure(self, mock_service_class):
        """Test failed entity deletion."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.side_effect = Exception("Not found")

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.delete_entities([999])

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is False
        assert "Not found" in result[0]["error"]

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_batches_and_preserves_order(self, mock_service_class):
        """Large deletes use bounded waves; results match input order."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        ids = list(range(1, 26))

        result = await ops.delete_entities(ids, batch_size=10)

        assert len(result) == 25
        assert [r["entity_id"] for r in result] == ids
        assert mock_service.delete_entity.call_count == 25

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_clamps_batch_size(self, mock_service_class):
        """batch_size above 15 is clamped to 15."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        await ops.delete_entities([1, 2], batch_size=99)

        assert mock_service.delete_entity.call_count == 2

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_dry_run_skips_delete(self, mock_service_class):
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_entity_by_id.return_value = {
            "entity_id": 101,
            "entity_type": "character",
        }

        ops = KankaOperations(service=mock_service)
        result = await ops.delete_entities([101], dry_run=True)

        assert result[0]["success"] is True
        assert result[0]["dry_run"] is True
        mock_service.delete_entity.assert_not_called()

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_warns_for_event_with_calendar(self, mock_service_class):
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_entity_by_id.return_value = {
            "entity_id": 101,
            "entity_type": "event",
            "calendar_id": 7,
        }
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        result = await ops.delete_entities([101], dry_run=True)

        assert result[0]["dry_run"] is True
        assert "orphan its calendar reminder" in result[0]["warning"]
        mock_service.delete_entity.assert_not_called()

    @patch("mcp_kanka.operations.asyncio.sleep", new_callable=AsyncMock)
    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_delay_between_waves(self, mock_service_class, mock_sleep):
        """Multiple waves await asyncio.sleep when delay_ms > 0."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        ids = list(range(1, 26))

        await ops.delete_entities(ids, batch_size=10, delay_ms=100)

        assert mock_sleep.await_count == 2
        mock_sleep.assert_awaited_with(0.1)

    @patch("mcp_kanka.operations.asyncio.sleep", new_callable=AsyncMock)
    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_entities_zero_delay_skips_sleep(self, mock_service_class, mock_sleep):
        """delay_ms=0 does not sleep between waves."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_entity.return_value = True

        ops = KankaOperations(service=mock_service)
        await ops.delete_entities([1, 2, 3], batch_size=1, delay_ms=0)

        mock_sleep.assert_not_awaited()


class TestPostOperations:
    """Test post-related operations."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_create_post_success(self, mock_service_class):
        """Test successfully creating a post."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Mock successful creation
        mock_service.create_post.return_value = {
            "post_id": 50,
            "entity_id": 101,
        }

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.create_posts(
            [
                {
                    "entity_id": 101,
                    "name": "Test Post",
                    "entry": "Post content",
                }
            ]
        )

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["post_id"] == 50
        assert result[0]["entity_id"] == 101

    @patch("mcp_kanka.operations.KankaService")
    async def test_update_post_success(self, mock_service_class):
        """Test successfully updating a post."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.update_post.return_value = True

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.update_posts(
            [
                {
                    "entity_id": 101,
                    "post_id": 50,
                    "name": "Updated Post",
                    "entry": "Updated content",
                }
            ]
        )

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["post_id"] == 50

    @patch("mcp_kanka.operations.KankaService")
    async def test_delete_post_success(self, mock_service_class):
        """Test successfully deleting a post."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.delete_post.return_value = True

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.delete_posts([{"entity_id": 101, "post_id": 50}])

        # Verify
        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["entity_id"] == 101
        assert result[0]["post_id"] == 50


class TestCheckEntityUpdates:
    """Test check_entity_updates operation."""

    @patch("mcp_kanka.operations.KankaService")
    async def test_check_updates_basic(self, mock_service_class):
        """Test basic check_entity_updates functionality."""
        mock_service = Mock()
        mock_client = Mock()
        mock_service.client = mock_client
        mock_service_class.return_value = mock_service

        # Mock entities response
        mock_client.entities.return_value = [
            {"id": 101, "updated_at": "2023-06-15T00:00:00Z"},
            {"id": 102, "updated_at": "2023-08-20T00:00:00Z"},
            {"id": 103, "updated_at": "2023-05-01T00:00:00Z"},
        ]

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.check_entity_updates(
            entity_ids=[101, 102, 103, 104], last_synced="2023-06-01T00:00:00Z"
        )

        # Verify
        assert set(result["modified_entity_ids"]) == {101, 102}
        assert result["deleted_entity_ids"] == [104]
        assert "check_timestamp" in result

    @patch("mcp_kanka.operations.KankaService")
    async def test_check_updates_missing_last_synced(self, mock_service_class):
        """Test check_entity_updates requires last_synced."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        ops = KankaOperations(service=mock_service)

        # Execute without last_synced
        with pytest.raises(ValueError, match="last_synced parameter is required"):
            await ops.check_entity_updates(entity_ids=[101, 102], last_synced="")

    @patch("mcp_kanka.operations.KankaService")
    async def test_check_updates_empty_list(self, mock_service_class):
        """Test check_entity_updates with empty entity list."""
        mock_service = Mock()
        mock_client = Mock()
        mock_service.client = mock_client
        mock_service_class.return_value = mock_service

        mock_client.entities.return_value = []

        ops = KankaOperations(service=mock_service)

        # Execute
        result = await ops.check_entity_updates(
            entity_ids=[], last_synced="2023-06-01T00:00:00Z"
        )

        # Verify
        assert result["modified_entity_ids"] == []
        assert result["deleted_entity_ids"] == []
        assert "check_timestamp" in result


class TestRunMigrationPlan:
    """Whitelisted migration steps."""

    async def test_runs_update_map_marker_step(self):
        mock_service = Mock()
        mock_service.update_map_marker.return_value = {"data": {"id": 1}}
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [
                {
                    "op": "update_map_marker",
                    "map_id": 10,
                    "marker_id": 20,
                    "fields": {"entity_id": 99},
                }
            ]
        )

        assert result["success"] is True
        assert result["stopped_at"] is None
        mock_service.update_map_marker.assert_called_once_with(
            10, 20, {"entity_id": 99}
        )

    async def test_unknown_op_stops_when_configured(self):
        mock_service = Mock()
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [{"op": "not_a_real_op"}], stop_on_error=True
        )
        assert result["success"] is False
        assert result["stopped_at"] == 0
        assert "create_entity" in result["results"][0]["error"]

    async def test_runs_create_entity_step(self):
        mock_service = Mock()
        mock_service.create_entity.return_value = {"entity_id": 999, "name": "New Place"}
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [
                {
                    "op": "create_entity",
                    "fields": {"entity_type": "location", "name": "New Place"},
                }
            ]
        )

        assert result["success"] is True
        mock_service.create_entity.assert_called_once()
        kwargs = mock_service.create_entity.call_args.kwargs
        assert kwargs["entity_type"] == "location"
        assert kwargs["name"] == "New Place"
        assert kwargs["calendar_id"] is None
        assert kwargs["event_parent_id"] is None

    async def test_runs_create_post_step(self):
        mock_service = Mock()
        mock_service.create_post.return_value = {"post_id": 11, "entity_id": 999}
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [
                {
                    "op": "create_post",
                    "fields": {"entity_id": 999, "name": "Lore", "entry": "Body"},
                }
            ]
        )

        assert result["success"] is True
        mock_service.create_post.assert_called_once_with(
            entity_id=999, name="Lore", entry="Body", is_hidden=None
        )

    async def test_runs_update_calendar_event_step(self):
        mock_service = Mock()
        mock_service.update_calendar_event.return_value = {"success": True}
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [
                {
                    "op": "update_calendar_event",
                    "calendar_id": 32596,
                    "calendar_event_id": 44,
                    "fields": {"name": "Repointed"},
                }
            ]
        )

        assert result["success"] is True
        mock_service.update_calendar_event.assert_called_once_with(
            calendar_id=32596, calendar_event_id=44, payload={"name": "Repointed"}
        )

    async def test_runs_create_reminder_step(self):
        mock_service = Mock()
        mock_service.create_entity_reminder.return_value = {"id": 555}
        ops = KankaOperations(service=mock_service)

        result = await ops.run_migration_plan(
            [
                {
                    "op": "create_reminder",
                    "entity_id": 9085022,
                    "fields": {
                        "name": "Session 1",
                        "day": 3,
                        "month": 4,
                        "year": 650,
                        "length": 3,
                        "calendar_id": 32596,
                    },
                }
            ]
        )

        assert result["success"] is True
        mock_service.create_entity_reminder.assert_called_once_with(
            entity_id=9085022,
            payload={
                "name": "Session 1",
                "day": 3,
                "month": 4,
                "year": 650,
                "length": 3,
                "calendar_id": 32596,
            },
        )
