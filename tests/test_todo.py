"""Tests for the Listonic todo entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.helpers.device_registry import DeviceEntryType

from custom_components.listonic.api import ListonicItem, ListonicList
from custom_components.listonic.const import DOMAIN
from custom_components.listonic.todo import (
    ListonicTodoListEntity,
    _parse_item_summary,
)


class TestParseItemSummary:
    """Tests for _parse_item_summary function."""

    def test_milk_with_quantity_and_unit(self):
        """Test parsing 'Milk (2 L)' returns name, quantity, and unit."""
        name, quantity, unit = _parse_item_summary("Milk (2 L)")
        assert name == "Milk"
        assert quantity == "2"
        assert unit == "L"

    def test_eggs_with_quantity_only(self):
        """Test parsing 'Eggs (12)' returns name, quantity, and None unit."""
        name, quantity, unit = _parse_item_summary("Eggs (12)")
        assert name == "Eggs"
        assert quantity == "12"
        assert unit is None

    def test_bread_without_quantity(self):
        """Test parsing 'Bread' returns name only."""
        name, quantity, unit = _parse_item_summary("Bread")
        assert name == "Bread"
        assert quantity is None
        assert unit is None

    def test_butter_with_decimal_quantity(self):
        """Test parsing 'Butter (0.5 kg)' handles decimal quantities."""
        name, quantity, unit = _parse_item_summary("Butter (0.5 kg)")
        assert name == "Butter"
        assert quantity == "0.5"
        assert unit == "kg"

    def test_comma_decimal_quantity(self):
        """Test parsing handles comma as decimal separator."""
        name, quantity, unit = _parse_item_summary("Cheese (1,5 kg)")
        assert name == "Cheese"
        assert quantity == "1,5"
        assert unit == "kg"

    def test_item_with_spaces_in_name(self):
        """Test parsing item with spaces in name."""
        name, quantity, unit = _parse_item_summary("Orange Juice (1 L)")
        assert name == "Orange Juice"
        assert quantity == "1"
        assert unit == "L"

    def test_item_with_leading_trailing_whitespace(self):
        """Test parsing handles leading/trailing whitespace around name."""
        name, quantity, unit = _parse_item_summary("  Milk (2 L)  ")
        assert name == "Milk"
        assert quantity == "2"
        assert unit == "L"

    def test_item_with_parentheses_in_name(self):
        """Test item without valid quantity pattern keeps parentheses."""
        name, quantity, unit = _parse_item_summary("Item (note)")
        assert name == "Item (note)"
        assert quantity is None
        assert unit is None


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.async_add_item = AsyncMock()
    coordinator.async_check_item = AsyncMock()
    coordinator.async_uncheck_item = AsyncMock()
    coordinator.async_update_item = AsyncMock()
    coordinator.async_delete_items = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def sample_listonic_item():
    """Create a sample ListonicItem."""
    return ListonicItem(
        id=1001,
        name="Milk",
        is_checked=False,
        quantity="2",
        unit="L",
        description="Fresh milk",
    )


@pytest.fixture
def sample_listonic_item_no_unit():
    """Create a sample ListonicItem without unit."""
    return ListonicItem(
        id=1002,
        name="Eggs",
        is_checked=True,
        quantity="12",
        unit=None,
        description=None,
    )


@pytest.fixture
def sample_listonic_item_no_quantity():
    """Create a sample ListonicItem without quantity."""
    return ListonicItem(
        id=1003,
        name="Bread",
        is_checked=False,
        quantity=None,
        unit=None,
        description=None,
    )


@pytest.fixture
def sample_listonic_list(
    sample_listonic_item, sample_listonic_item_no_unit, sample_listonic_item_no_quantity
):
    """Create a sample ListonicList."""
    return ListonicList(
        id=123,
        name="Groceries",
        items=[
            sample_listonic_item,
            sample_listonic_item_no_unit,
            sample_listonic_item_no_quantity,
        ],
        is_archived=False,
    )


class TestItemToTodoItem:
    """Tests for _item_to_todo_item static method."""

    def test_item_with_quantity_and_unit(self, sample_listonic_item):
        """Test conversion with quantity and unit."""
        todo_item = ListonicTodoListEntity._item_to_todo_item(sample_listonic_item)

        assert todo_item.uid == "1001"
        assert todo_item.summary == "Milk (2 L)"
        assert todo_item.status == TodoItemStatus.NEEDS_ACTION
        assert todo_item.description == "Fresh milk"

    def test_item_with_quantity_no_unit(self, sample_listonic_item_no_unit):
        """Test conversion with quantity but no unit."""
        item = sample_listonic_item_no_unit
        todo_item = ListonicTodoListEntity._item_to_todo_item(item)

        assert todo_item.uid == "1002"
        assert todo_item.summary == "Eggs (12)"
        assert todo_item.status == TodoItemStatus.COMPLETED
        assert todo_item.description is None

    def test_item_without_quantity(self, sample_listonic_item_no_quantity):
        """Test conversion without quantity."""
        item = sample_listonic_item_no_quantity
        todo_item = ListonicTodoListEntity._item_to_todo_item(item)

        assert todo_item.uid == "1003"
        assert todo_item.summary == "Bread"
        assert todo_item.status == TodoItemStatus.NEEDS_ACTION
        assert todo_item.description is None

    def test_checked_item_has_completed_status(self):
        """Test that checked item has COMPLETED status."""
        item = ListonicItem(id=100, name="Test", is_checked=True)
        todo_item = ListonicTodoListEntity._item_to_todo_item(item)
        assert todo_item.status == TodoItemStatus.COMPLETED

    def test_unchecked_item_has_needs_action_status(self):
        """Test that unchecked item has NEEDS_ACTION status."""
        item = ListonicItem(id=100, name="Test", is_checked=False)
        todo_item = ListonicTodoListEntity._item_to_todo_item(item)
        assert todo_item.status == TodoItemStatus.NEEDS_ACTION


class TestTodoItemsProperty:
    """Tests for todo_items property."""

    def test_returns_todo_items_list(self, mock_coordinator, sample_listonic_list):
        """Test that todo_items returns correct TodoItem list."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        todo_items = entity.todo_items

        assert todo_items is not None
        assert len(todo_items) == 3
        assert todo_items[0].uid == "1001"
        assert todo_items[0].summary == "Milk (2 L)"
        assert todo_items[1].uid == "1002"
        assert todo_items[1].summary == "Eggs (12)"
        assert todo_items[2].uid == "1003"
        assert todo_items[2].summary == "Bread"

    def test_returns_none_when_list_not_found(self, mock_coordinator):
        """Test that todo_items returns None when list not in data."""
        mock_coordinator.data = {}
        entity = ListonicTodoListEntity(mock_coordinator, 999)

        assert entity.todo_items is None

    def test_returns_empty_list_for_empty_items(self, mock_coordinator):
        """Test that todo_items returns empty list for list with no items."""
        empty_list = ListonicList(id=456, name="Empty", items=[], is_archived=False)
        mock_coordinator.data = {456: empty_list}
        entity = ListonicTodoListEntity(mock_coordinator, 456)

        todo_items = entity.todo_items

        assert todo_items is not None
        assert len(todo_items) == 0


class TestAsyncCreateTodoItem:
    """Tests for async_create_todo_item method."""

    @pytest.mark.asyncio
    async def test_creates_item_with_name_only(self, mock_coordinator):
        """Test creating item with name only."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(summary="Bread")

        await entity.async_create_todo_item(todo_item)

        mock_coordinator.async_add_item.assert_called_once_with(
            123, "Bread", quantity=None, unit=None
        )

    @pytest.mark.asyncio
    async def test_creates_item_with_quantity_and_unit(self, mock_coordinator):
        """Test creating item with quantity and unit parsed from summary."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(summary="Milk (2 L)")

        await entity.async_create_todo_item(todo_item)

        mock_coordinator.async_add_item.assert_called_once_with(
            123, "Milk", quantity="2", unit="L"
        )

    @pytest.mark.asyncio
    async def test_creates_item_with_quantity_only(self, mock_coordinator):
        """Test creating item with quantity but no unit."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(summary="Eggs (12)")

        await entity.async_create_todo_item(todo_item)

        mock_coordinator.async_add_item.assert_called_once_with(
            123, "Eggs", quantity="12", unit=None
        )

    @pytest.mark.asyncio
    async def test_does_nothing_for_empty_summary(self, mock_coordinator):
        """Test that empty summary does not create item."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(summary="")

        await entity.async_create_todo_item(todo_item)

        mock_coordinator.async_add_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_for_none_summary(self, mock_coordinator):
        """Test that None summary does not create item."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(summary=None)

        await entity.async_create_todo_item(todo_item)

        mock_coordinator.async_add_item.assert_not_called()


class TestAsyncUpdateTodoItem:
    """Tests for async_update_todo_item method."""

    @pytest.mark.asyncio
    async def test_checks_item_when_status_changes_to_completed(
        self, mock_coordinator, sample_listonic_list
    ):
        """Test that changing status to COMPLETED calls async_check_item."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(uid="1001", status=TodoItemStatus.COMPLETED)

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_check_item.assert_called_once_with(123, 1001)
        mock_coordinator.async_uncheck_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_unchecks_item_when_status_changes_to_needs_action(
        self, mock_coordinator, sample_listonic_list
    ):
        """Test that changing status to NEEDS_ACTION calls async_uncheck_item."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        # Item 1002 is already checked, so changing to NEEDS_ACTION should uncheck
        todo_item = TodoItem(uid="1002", status=TodoItemStatus.NEEDS_ACTION)

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_uncheck_item.assert_called_once_with(123, 1002)
        mock_coordinator.async_check_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_description_when_status_unchanged(
        self, mock_coordinator, sample_listonic_list
    ):
        """Test that description update works when status unchanged."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        # Item 1001 is unchecked, keeping it unchecked but updating description
        todo_item = TodoItem(
            uid="1001",
            status=TodoItemStatus.NEEDS_ACTION,
            description="Updated description",
        )

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_update_item.assert_called_once_with(
            123, 1001, description="Updated description"
        )
        mock_coordinator.async_check_item.assert_not_called()
        mock_coordinator.async_uncheck_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_for_none_uid(self, mock_coordinator):
        """Test that None uid does not update anything."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(uid=None, status=TodoItemStatus.COMPLETED)

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_check_item.assert_not_called()
        mock_coordinator.async_uncheck_item.assert_not_called()
        mock_coordinator.async_update_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_for_nonexistent_item(
        self, mock_coordinator, sample_listonic_list
    ):
        """Test that nonexistent item uid does not update anything."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        todo_item = TodoItem(uid="9999", status=TodoItemStatus.COMPLETED)

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_check_item.assert_not_called()
        mock_coordinator.async_uncheck_item.assert_not_called()
        mock_coordinator.async_update_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_update_when_status_same_and_no_description(
        self, mock_coordinator, sample_listonic_list
    ):
        """Test no update called when status same and no description change."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)
        # Item 1001 is already unchecked, so NEEDS_ACTION is same status
        todo_item = TodoItem(uid="1001", status=TodoItemStatus.NEEDS_ACTION)

        await entity.async_update_todo_item(todo_item)

        mock_coordinator.async_check_item.assert_not_called()
        mock_coordinator.async_uncheck_item.assert_not_called()
        mock_coordinator.async_update_item.assert_not_called()


class TestAsyncDeleteTodoItems:
    """Tests for async_delete_todo_items method."""

    @pytest.mark.asyncio
    async def test_deletes_single_item(self, mock_coordinator):
        """Test deleting a single item."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        await entity.async_delete_todo_items(["1001"])

        mock_coordinator.async_delete_items.assert_called_once_with(123, [1001])

    @pytest.mark.asyncio
    async def test_deletes_multiple_items(self, mock_coordinator):
        """Test deleting multiple items."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        await entity.async_delete_todo_items(["1001", "1002", "1003"])

        mock_coordinator.async_delete_items.assert_called_once_with(
            123, [1001, 1002, 1003]
        )

    @pytest.mark.asyncio
    async def test_deletes_empty_list(self, mock_coordinator):
        """Test deleting empty list of items."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        await entity.async_delete_todo_items([])

        mock_coordinator.async_delete_items.assert_called_once_with(123, [])


class TestDeviceInfo:
    """Tests for device_info property."""

    def test_returns_correct_device_info(self, mock_coordinator):
        """Test that device_info returns correct DeviceInfo."""
        mock_coordinator.config_entry.entry_id = "my_entry_id"
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        device_info = entity.device_info

        assert device_info["identifiers"] == {(DOMAIN, "my_entry_id")}
        assert device_info["name"] == "Listonic"
        assert device_info["manufacturer"] == "Listonic"
        assert device_info["model"] == "Shopping Lists"
        assert device_info["entry_type"] == DeviceEntryType.SERVICE


class TestEntityProperties:
    """Tests for other entity properties."""

    def test_name_from_list(self, mock_coordinator, sample_listonic_list):
        """Test that name returns list name."""
        mock_coordinator.data = {123: sample_listonic_list}
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        assert entity.name == "Groceries"

    def test_name_fallback_when_list_not_found(self, mock_coordinator):
        """Test that name returns fallback when list not found."""
        mock_coordinator.data = {}
        entity = ListonicTodoListEntity(mock_coordinator, 999)

        assert entity.name == "Listonic List 999"

    def test_unique_id(self, mock_coordinator):
        """Test that unique_id is set correctly."""
        entity = ListonicTodoListEntity(mock_coordinator, 123)

        assert entity.unique_id == "listonic_123"
