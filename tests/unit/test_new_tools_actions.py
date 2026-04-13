from unittest.mock import Mock

import pytest

from mcp_kanka.operations import KankaOperations


async def _create_ops_with_mock_service():
    service = Mock()
    # Timeline tools resolve URL/global entity ids to timelines/{module_id}; pass-through by default.
    service.resolve_timeline_subresource_id.side_effect = lambda tid: tid
    ops = KankaOperations(service=service)
    return ops, service


class TestManageMapMarkers:
    async def test_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_map_markers.return_value = {"data": []}

        result = await ops.manage_map_markers(
            action="list", map_id=1, page=2, limit=10
        )

        assert result == {"data": []}
        service.list_map_markers.assert_called_once_with(map_id=1, page=2, limit=10)

    async def test_create_requires_fields(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_map_marker.return_value = {"success": True}

        try:
            await ops.manage_map_markers(action="create", map_id=1, icon=2)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Missing required create fields" in str(e)

    async def test_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_map_marker.return_value = {"success": True}

        await ops.manage_map_markers(
            action="create",
            map_id=1,
            latitude=1.5,
            longitude=2.5,
            shape_id=3,
            icon=4,
            entity_id=123,
            colour="#ffffff",
        )

        payload = {
            "latitude": 1.5,
            "longitude": 2.5,
            "shape_id": 3,
            "icon": 4,
            "entity_id": 123,
            "colour": "#ffffff",
        }
        service.create_map_marker.assert_called_once_with(map_id=1, payload=payload)

    async def test_update_sends_only_provided_fields(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_map_marker.return_value = {"success": True}

        await ops.manage_map_markers(
            action="update",
            map_id=1,
            marker_id=9,
            entity_id=123,
            opacity=80,
        )

        service.update_map_marker.assert_called_once_with(
            map_id=1, marker_id=9, payload={"entity_id": 123, "opacity": 80}
        )

    async def test_update_accepts_group_id_only(self):
        """Updates no longer require name or entity_id when changing other fields."""
        ops, service = await _create_ops_with_mock_service()
        service.update_map_marker.return_value = {"success": True}

        await ops.manage_map_markers(
            action="update",
            map_id=1,
            marker_id=9,
            group_id=12594,
        )

        service.update_map_marker.assert_called_once_with(
            map_id=1, marker_id=9, payload={"group_id": 12594}
        )

    async def test_update_requires_at_least_one_field(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_map_markers(
                action="update", map_id=1, marker_id=9
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "No fields to update" in str(e)

    async def test_delete_requires_marker_id(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_map_markers(action="delete", map_id=1)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "`marker_id` is required" in str(e)

    async def test_delete_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.delete_map_marker.return_value = {"success": True}

        result = await ops.manage_map_markers(
            action="delete", map_id=1, marker_id=10
        )

        assert result == {"success": True}
        service.delete_map_marker.assert_called_once_with(map_id=1, marker_id=10)


class TestManageRelations:
    async def test_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_relations.return_value = {"data": []}

        result = await ops.manage_relations(
            action="list", entity_id=1, page=3, limit=20
        )

        assert result == {"data": []}
        service.list_relations.assert_called_once_with(entity_id=1, page=3, limit=20)

    async def test_create_requires_relation(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_relations(action="create", entity_id=1, target_id=2)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Missing required create field: relation" in str(e)

    async def test_create_builds_payload_with_default_owner(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_relation.return_value = {"success": True}

        await ops.manage_relations(
            action="create",
            entity_id=1,
            relation="Brother",
            target_id=2,
        )

        service.create_relation.assert_called_once_with(
            entity_id=1,
            payload={"relation": "Brother", "target_id": 2, "owner_id": 1},
        )

    async def test_update_requires_relation_id(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_relations(action="update", entity_id=1, attitude=1)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "`relation_id` is required for update" in str(e)

    async def test_update_sends_only_provided_fields(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_relation.return_value = {"success": True}

        await ops.manage_relations(
            action="update",
            entity_id=1,
            relation_id=7,
            attitude=42,
        )

        service.update_relation.assert_called_once_with(
            entity_id=1,
            relation_id=7,
            payload={"attitude": 42, "owner_id": 1},
        )

    async def test_delete_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.delete_relation.return_value = {"success": True}

        result = await ops.manage_relations(
            action="delete", entity_id=1, relation_id=7
        )

        assert result == {"success": True}
        service.delete_relation.assert_called_once_with(entity_id=1, relation_id=7)


class TestManageTimelineElements:
    async def test_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_timeline_elements.return_value = {"data": []}

        result = await ops.manage_timeline_elements(
            action="list", timeline_id=10, page=2, limit=15
        )

        assert result == {"data": []}
        service.resolve_timeline_subresource_id.assert_called_once_with(10)
        service.list_timeline_elements.assert_called_once_with(
            timeline_id=10, page=2, limit=15
        )

    async def test_list_fetch_all_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_timeline_elements_all.return_value = {"data": [{"id": 1}]}

        result = await ops.manage_timeline_elements(
            action="list", timeline_id=10, fetch_all=True, limit=20
        )

        assert result == {"data": [{"id": 1}]}
        service.resolve_timeline_subresource_id.assert_called_once_with(10)
        service.list_timeline_elements_all.assert_called_once_with(
            timeline_id=10, limit=20
        )
        service.list_timeline_elements.assert_not_called()

    async def test_create_requires_era_and_name_or_entity(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_timeline_elements(action="create", timeline_id=10, era_id=1)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Provide either `name` or `entity_id`" in str(e)

    async def test_create_requires_era_id_with_list_guidance(self):
        ops, _service = await _create_ops_with_mock_service()

        with pytest.raises(ValueError) as exc:
            await ops.manage_timeline_elements(action="create", timeline_id=10, name="X")

        assert "action=list" in str(exc.value)

    async def test_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_timeline_element.return_value = {"success": True}

        await ops.manage_timeline_elements(
            action="create",
            timeline_id=10,
            era_id=1,
            name="Event A",
            entry="**bold**",
            position=3,
        )

        service.create_timeline_element.assert_called_once_with(
            timeline_id=10,
            payload={"era_id": 1, "name": "Event A", "entry": "**bold**", "position": 3},
        )

    async def test_update_requires_element_id(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_timeline_elements(action="update", timeline_id=10, name="X")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "`element_id` is required for update" in str(e)

    async def test_update_sends_only_provided_fields(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_timeline_element.return_value = {"success": True}

        await ops.manage_timeline_elements(
            action="update",
            timeline_id=10,
            element_id=20,
            entity_id=999,
            colour="#ff0000",
        )

        service.update_timeline_element.assert_called_once_with(
            timeline_id=10,
            element_id=20,
            payload={"entity_id": 999, "colour": "#ff0000"},
        )

    async def test_delete_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.delete_timeline_element.return_value = {"success": True}

        result = await ops.manage_timeline_elements(
            action="delete", timeline_id=10, element_id=20
        )

        assert result == {"success": True}
        service.delete_timeline_element.assert_called_once_with(
            timeline_id=10, element_id=20
        )

    async def test_list_resolves_global_timeline_entity_id(self):
        ops, service = await _create_ops_with_mock_service()
        service.resolve_timeline_subresource_id.return_value = 44488
        service.resolve_timeline_subresource_id.side_effect = None
        service.list_timeline_elements.return_value = {"data": []}

        await ops.manage_timeline_elements(action="list", timeline_id=9072997)

        service.resolve_timeline_subresource_id.assert_called_once_with(9072997)
        service.list_timeline_elements.assert_called_once_with(
            timeline_id=44488, page=1, limit=15
        )


class TestManageTimelineEras:
    async def test_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_timeline_eras.return_value = {"data": []}

        result = await ops.manage_timeline_eras(
            action="list", timeline_id=10, page=2, limit=12
        )

        assert result == {"data": []}
        service.resolve_timeline_subresource_id.assert_called_once_with(10)
        service.list_timeline_eras.assert_called_once_with(
            timeline_id=10, page=2, limit=12
        )

    async def test_create_requires_name(self):
        ops, _service = await _create_ops_with_mock_service()

        with pytest.raises(ValueError) as exc:
            await ops.manage_timeline_eras(action="create", timeline_id=10)

        assert "Missing required create field: name" in str(exc.value)

    async def test_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_timeline_era.return_value = {"success": True}

        result = await ops.manage_timeline_eras(
            action="create",
            timeline_id=10,
            name="Age of Discovery",
            abbreviation="AoD",
            start_year=550,
            end_year=556,
            position=1,
            is_collapsed=False,
        )

        assert result == {"success": True}
        service.create_timeline_era.assert_called_once_with(
            timeline_id=10,
            payload={
                "name": "Age of Discovery",
                "abbreviation": "AoD",
                "start_year": 550,
                "end_year": 556,
                "position": 1,
                "is_collapsed": False,
            },
        )

    async def test_update_requires_era_id(self):
        ops, _service = await _create_ops_with_mock_service()

        with pytest.raises(ValueError) as exc:
            await ops.manage_timeline_eras(action="update", timeline_id=10, name="Renamed")

        assert "`era_id` is required for update." in str(exc.value)

    async def test_update_and_delete_delegate(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_timeline_era.return_value = {"success": True}
        service.delete_timeline_era.return_value = {"success": True}

        update_result = await ops.manage_timeline_eras(
            action="update", timeline_id=10, era_id=2, name="Renamed"
        )
        delete_result = await ops.manage_timeline_eras(
            action="delete", timeline_id=10, era_id=2
        )

        assert update_result == {"success": True}
        assert delete_result == {"success": True}
        service.update_timeline_era.assert_called_once_with(
            timeline_id=10, era_id=2, payload={"name": "Renamed"}
        )
        service.delete_timeline_era.assert_called_once_with(timeline_id=10, era_id=2)

    async def test_list_resolves_global_timeline_entity_id(self):
        ops, service = await _create_ops_with_mock_service()
        service.resolve_timeline_subresource_id.return_value = 44488
        service.resolve_timeline_subresource_id.side_effect = None
        service.list_timeline_eras.return_value = {"data": []}

        await ops.manage_timeline_eras(action="list", timeline_id=9072997)

        service.resolve_timeline_subresource_id.assert_called_once_with(9072997)
        service.list_timeline_eras.assert_called_once_with(
            timeline_id=44488, page=1, limit=15
        )


class TestArchivesMediaCalendarTools:
    async def test_get_archives_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.get_archives.return_value = {"data": [{"id": 1}]}

        result = await ops.get_archives()

        assert result == {"data": [{"id": 1}]}
        service.get_archives.assert_called_once()

    async def test_manage_calendars_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_calendars.return_value = {"data": []}

        result = await ops.manage_calendars(action="list", page=2, limit=20)

        assert result == {"data": []}
        service.list_calendars.assert_called_once_with(page=2, limit=20)

    async def test_manage_calendars_create_requires_name(self):
        ops, _service = await _create_ops_with_mock_service()

        with pytest.raises(ValueError) as exc:
            await ops.manage_calendars(action="create")

        assert "Missing required create field: name" in str(exc.value)

    async def test_manage_calendars_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_calendar.return_value = {"success": True}

        result = await ops.manage_calendars(
            action="create",
            name="Blood Earth Calendar",
            month_name=["Jan", "Feb"],
            month_length=[30, 30],
            weekday=["Mon", "Tue"],
            suffix="AE",
            current_year=656,
            current_month=4,
            current_day=8,
            has_leap_year=False,
            skip_year_zero=True,
            format="D MMM, Y",
        )

        assert result == {"success": True}
        service.create_calendar.assert_called_once_with(
            payload={
                "name": "Blood Earth Calendar",
                "month_name": ["Jan", "Feb"],
                "month_length": [30, 30],
                "weekday": ["Mon", "Tue"],
                "suffix": "AE",
                "current_year": 656,
                "current_month": 4,
                "current_day": 8,
                "has_leap_year": False,
                "skip_year_zero": True,
                "format": "D MMM, Y",
            }
        )

    async def test_manage_calendars_update_and_delete_delegate(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_calendar.return_value = {"success": True}
        service.delete_calendar.return_value = {"success": True}

        update_result = await ops.manage_calendars(
            action="update", calendar_id=1, name="Renamed Calendar"
        )
        delete_result = await ops.manage_calendars(action="delete", calendar_id=1)

        assert update_result == {"success": True}
        assert delete_result == {"success": True}
        service.update_calendar.assert_called_once_with(
            calendar_id=1, payload={"name": "Renamed Calendar"}
        )
        service.delete_calendar.assert_called_once_with(calendar_id=1)

    async def test_manage_calendars_update_delete_require_calendar_id(self):
        ops, _service = await _create_ops_with_mock_service()

        with pytest.raises(ValueError) as update_exc:
            await ops.manage_calendars(action="update", name="X")
        assert "`calendar_id` is required for update." in str(update_exc.value)

        with pytest.raises(ValueError) as delete_exc:
            await ops.manage_calendars(action="delete")
        assert "`calendar_id` is required for delete." in str(delete_exc.value)

    async def test_manage_entity_image_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.get_entity_image.return_value = {"image": {}, "header": {}}

        result = await ops.manage_entity_image(action="list", entity_id=5)

        assert result == {"image": {}, "header": {}}
        service.get_entity_image.assert_called_once_with(entity_id=5)

    async def test_manage_entity_image_upload_requires_file_path(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_entity_image(action="upload", entity_id=5, file_path=None)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Provide `file_path` for upload" in str(e)

    async def test_manage_entity_image_upload_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.upload_entity_image_from_file.return_value = {"success": True}

        result = await ops.manage_entity_image(
            action="upload", entity_id=5, file_path="C:/img.png", is_header=True
        )

        assert result == {"success": True}
        service.upload_entity_image_from_file.assert_called_once_with(
            entity_id=5, file_path="C:/img.png", is_header=True
        )

    async def test_manage_entity_image_remove_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.remove_entity_image.return_value = {"success": True}

        result = await ops.manage_entity_image(
            action="remove", entity_id=5, is_header=False
        )

        assert result == {"success": True}
        service.remove_entity_image.assert_called_once_with(entity_id=5, is_header=False)

    async def test_manage_calendar_weather_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_calendar_weather.return_value = {"data": []}

        result = await ops.manage_calendar_weather(
            action="list", calendar_id=1, page=2, limit=10
        )

        assert result == {"data": []}
        service.list_calendar_weather.assert_called_once_with(
            calendar_id=1, page=2, limit=10
        )

    async def test_manage_calendar_weather_create_requires_fields(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_calendar_weather(action="create", calendar_id=1, weather="bolt")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Missing required create fields" in str(e)

    async def test_manage_calendar_weather_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_calendar_weather.return_value = {"success": True}

        result = await ops.manage_calendar_weather(
            action="create",
            calendar_id=1,
            year=2020,
            month=1,
            day=2,
            weather="bolt",
            visibility_id=1,
        )

        assert result == {"success": True}
        service.create_calendar_weather.assert_called_once_with(
            calendar_id=1,
            payload={
                "year": 2020,
                "month": 1,
                "day": 2,
                "weather": "bolt",
                "visibility_id": 1,
            },
        )

    async def test_manage_calendar_weather_update_requires_id(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_calendar_weather(action="update", calendar_id=1, year=2020)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "`calendar_weather_id` is required for update" in str(e)

    async def test_manage_calendar_weather_update_requires_fields(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_calendar_weather(
                action="update", calendar_id=1, calendar_weather_id=3
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "No update fields provided" in str(e)

    async def test_manage_calendar_weather_update_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_calendar_weather.return_value = {"success": True}

        result = await ops.manage_calendar_weather(
            action="update",
            calendar_id=1,
            calendar_weather_id=3,
            weather="rain",
        )

        assert result == {"success": True}
        service.update_calendar_weather.assert_called_once_with(
            calendar_id=1, calendar_weather_id=3, payload={"weather": "rain"}
        )

    async def test_manage_calendar_weather_delete_requires_id(self):
        ops, service = await _create_ops_with_mock_service()

        try:
            await ops.manage_calendar_weather(action="delete", calendar_id=1)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "`calendar_weather_id` is required for delete" in str(e)

    async def test_manage_calendar_weather_delete_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.delete_calendar_weather.return_value = {"success": True}

        result = await ops.manage_calendar_weather(
            action="delete", calendar_id=1, calendar_weather_id=3
        )

        assert result == {"success": True}
        service.delete_calendar_weather.assert_called_once_with(
            calendar_id=1, calendar_weather_id=3
        )

    async def test_manage_calendar_events_list_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_calendar_events.return_value = {"data": []}

        result = await ops.manage_calendar_events(
            action="list", calendar_id=1, page=2, limit=10
        )

        assert result == {"data": []}
        service.list_calendar_events.assert_called_once_with(
            calendar_id=1, page=2, limit=10
        )

    async def test_manage_calendar_events_fetch_all_delegates(self):
        ops, service = await _create_ops_with_mock_service()
        service.list_calendar_events_all.return_value = {
            "data": [{"id": 1}],
            "meta": {"fetch_all": True, "total": 1, "last_page": 1},
        }

        result = await ops.manage_calendar_events(
            action="list", calendar_id=1, fetch_all=True, limit=20
        )

        assert result["data"] == [{"id": 1}]
        assert result["meta"]["fetch_all"] is True
        service.list_calendar_events_all.assert_called_once_with(
            calendar_id=1, limit=20
        )
        service.list_calendar_events.assert_not_called()

    async def test_manage_calendar_events_create_requires_entity_id(self):
        ops, _service = await _create_ops_with_mock_service()
        with pytest.raises(ValueError) as exc:
            await ops.manage_calendar_events(action="create", calendar_id=1)
        assert "`entity_id` is required" in str(exc.value)

    async def test_manage_calendar_events_create_builds_payload(self):
        ops, service = await _create_ops_with_mock_service()
        service.create_entity_reminder.return_value = {"success": True}

        result = await ops.manage_calendar_events(
            action="create",
            calendar_id=32596,
            entity_id=9085022,
            name="Session 1",
            day=3,
            month=4,
            year=650,
            length=3,
            colour="#ff8000",
            comment="note",
            visibility_id=1,
        )

        assert result == {"success": True}
        service.create_entity_reminder.assert_called_once_with(
            entity_id=9085022,
            payload={
                "name": "Session 1",
                "day": 3,
                "month": 4,
                "year": 650,
                "length": 3,
                "calendar_id": 32596,
                "colour": "#ff8000",
                "comment": "note",
                "visibility_id": 1,
            },
        )

    async def test_manage_calendar_events_update_and_delete_delegate(self):
        ops, service = await _create_ops_with_mock_service()
        service.update_entity_reminder.return_value = {"success": True}
        service.delete_entity_reminder.return_value = {"success": True}

        update_result = await ops.manage_calendar_events(
            action="update",
            calendar_id=32596,
            entity_id=9085022,
            calendar_event_id=3,
            length=5,
        )
        delete_result = await ops.manage_calendar_events(
            action="delete",
            calendar_id=32596,
            entity_id=9085022,
            calendar_event_id=3,
        )

        assert update_result == {"success": True}
        assert delete_result == {"success": True}
        service.update_entity_reminder.assert_called_once_with(
            entity_id=9085022, reminder_id=3, payload={"length": 5}
        )
        service.delete_entity_reminder.assert_called_once_with(
            entity_id=9085022, reminder_id=3
        )

    async def test_calendar_advance_and_retreat_delegate(self):
        ops, service = await _create_ops_with_mock_service()
        service.calendar_advance_date.return_value = {"success": True}
        service.calendar_retreat_date.return_value = {"success": True}

        assert await ops.calendar_advance_date(calendar_id=1) == {"success": True}
        assert await ops.calendar_retreat_date(calendar_id=1) == {"success": True}
        service.calendar_advance_date.assert_called_once_with(calendar_id=1)
        service.calendar_retreat_date.assert_called_once_with(calendar_id=1)

