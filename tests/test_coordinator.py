"""Tests for the Listonic data update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.listonic.api import (
    ListonicApiClient,
    ListonicApiError,
    ListonicAuthError,
    ListonicItem,
    ListonicList,
)
from custom_components.listonic.coordinator import ListonicDataUpdateCoordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_client():
    """Create a mock Listonic API client."""
    client = AsyncMock(spec=ListonicApiClient)
    return client


@pytest.fixture
def sample_lists():
    """Create sample ListonicList objects."""
    return [
        ListonicList(
            id=123,
            name="Groceries",
            items=[
                ListonicItem(id=1, name="Milk", is_checked=False),
                ListonicItem(id=2, name="Bread", is_checked=True),
            ],
            is_archived=False,
        ),
        ListonicList(
            id=456,
            name="Hardware",
            items=[
                ListonicItem(id=3, name="Screws", is_checked=False),
            ],
            is_archived=False,
        ),
    ]


@pytest.fixture
def coordinator(mock_hass, mock_client, mock_config_entry):
    """Create a coordinator instance for testing."""
    return ListonicDataUpdateCoordinator(
        mock_hass,
        mock_client,
        mock_config_entry,
        scan_interval=30,
    )


class TestAsyncUpdateData:
    """Tests for _async_update_data method."""

    @pytest.mark.asyncio
    async def test_fetches_lists_and_returns_dict_keyed_by_id(
        self, coordinator, mock_client, sample_lists
    ):
        """Test _async_update_data fetches lists and returns dict keyed by ID."""
        mock_client.get_lists.return_value = sample_lists

        result = await coordinator._async_update_data()

        mock_client.get_lists.assert_called_once()
        assert isinstance(result, dict)
        assert 123 in result
        assert 456 in result
        assert result[123].name == "Groceries"
        assert result[456].name == "Hardware"
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_raises_update_failed_on_api_error(self, coordinator, mock_client):
        """Test that _async_update_data raises UpdateFailed on API error."""
        mock_client.get_lists.side_effect = ListonicApiError("Connection failed")

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data()

        assert "Error communicating with Listonic API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_config_entry_auth_failed_on_auth_error(
        self, coordinator, mock_client
    ):
        """Test that _async_update_data raises ConfigEntryAuthFailed on auth error."""
        mock_client.get_lists.side_effect = ListonicAuthError("Invalid credentials")

        with pytest.raises(ConfigEntryAuthFailed) as exc_info:
            await coordinator._async_update_data()

        assert "Invalid credentials" in str(exc_info.value)


class TestAsyncAddItem:
    """Tests for async_add_item method."""

    @pytest.mark.asyncio
    async def test_calls_client_and_requests_refresh(
        self, coordinator, mock_client, sample_lists
    ):
        """Test that async_add_item calls client.add_item and requests refresh."""
        mock_client.add_item.return_value = ListonicItem(
            id=100, name="Eggs", is_checked=False
        )
        mock_client.get_lists.return_value = sample_lists

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_add_item(123, "Eggs", "12", "pcs")

            mock_client.add_item.assert_called_once_with(123, "Eggs", "12", "pcs")
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_item_without_optional_params(self, coordinator, mock_client):
        """Test adding item without quantity and unit."""
        mock_client.add_item.return_value = ListonicItem(
            id=100, name="Butter", is_checked=False
        )

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_add_item(123, "Butter")

            mock_client.add_item.assert_called_once_with(123, "Butter", None, None)
            mock_refresh.assert_called_once()


class TestAsyncUpdateItem:
    """Tests for async_update_item method."""

    @pytest.mark.asyncio
    async def test_calls_client_and_requests_refresh(self, coordinator, mock_client):
        """Test that async_update_item calls client.update_item and requests refresh."""
        mock_client.update_item.return_value = ListonicItem(
            id=1, name="Whole Milk", is_checked=False
        )

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_update_item(123, 1, name="Whole Milk")

            # Coordinator passes all params explicitly (including None defaults)
            mock_client.update_item.assert_called_once_with(
                123,
                1,
                is_checked=None,
                name="Whole Milk",
                quantity=None,
                unit=None,
                description=None,
                current_item=None,
            )
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_with_multiple_kwargs(self, coordinator, mock_client):
        """Test updating item with multiple keyword arguments."""
        mock_client.update_item.return_value = ListonicItem(
            id=1, name="2% Milk", is_checked=True, quantity="2", unit="L"
        )

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_update_item(
                123, 1, name="2% Milk", quantity="2", unit="L", is_checked=True
            )

            # Coordinator passes all params explicitly (including None defaults)
            mock_client.update_item.assert_called_once_with(
                123,
                1,
                is_checked=True,
                name="2% Milk",
                quantity="2",
                unit="L",
                description=None,
                current_item=None,
            )
            mock_refresh.assert_called_once()


class TestAsyncCheckItem:
    """Tests for async_check_item method."""

    @pytest.mark.asyncio
    async def test_check_item_calls_client_and_refreshes(
        self, coordinator, mock_client
    ):
        """Test that async_check_item calls client.check_item and requests refresh."""
        mock_client.check_item.return_value = ListonicItem(
            id=1, name="Milk", is_checked=True
        )

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_check_item(123, 1)

            mock_client.check_item.assert_called_once_with(123, 1)
            mock_refresh.assert_called_once()


class TestAsyncUncheckItem:
    """Tests for async_uncheck_item method."""

    @pytest.mark.asyncio
    async def test_uncheck_item_calls_client_and_refreshes(
        self, coordinator, mock_client
    ):
        """Test async_uncheck_item calls client.uncheck_item and refreshes."""
        mock_client.uncheck_item.return_value = ListonicItem(
            id=1, name="Milk", is_checked=False
        )

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_uncheck_item(123, 1)

            mock_client.uncheck_item.assert_called_once_with(123, 1)
            mock_refresh.assert_called_once()


class TestAsyncDeleteItem:
    """Tests for async_delete_item method."""

    @pytest.mark.asyncio
    async def test_delete_item_calls_client_and_refreshes(
        self, coordinator, mock_client
    ):
        """Test that async_delete_item calls client.delete_item and requests refresh."""
        mock_client.delete_item.return_value = True

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_delete_item(123, 1)

            mock_client.delete_item.assert_called_once_with(123, 1)
            mock_refresh.assert_called_once()


class TestAsyncDeleteItems:
    """Tests for async_delete_items (batch) method."""

    @pytest.mark.asyncio
    async def test_batch_delete_only_refreshes_once(self, coordinator, mock_client):
        """Test async_delete_items deletes multiple items but only refreshes once."""
        mock_client.delete_item.return_value = True

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_delete_items(123, [1, 2, 3])

            # Should call delete_item for each item
            assert mock_client.delete_item.call_count == 3
            mock_client.delete_item.assert_any_call(123, 1)
            mock_client.delete_item.assert_any_call(123, 2)
            mock_client.delete_item.assert_any_call(123, 3)

            # But only refresh once at the end
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_delete_empty_list(self, coordinator, mock_client):
        """Test that async_delete_items handles empty list."""
        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_delete_items(123, [])

            mock_client.delete_item.assert_not_called()
            # Still calls refresh even for empty list (per current implementation)
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_delete_single_item(self, coordinator, mock_client):
        """Test that async_delete_items works with a single item."""
        mock_client.delete_item.return_value = True

        with patch.object(
            coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            await coordinator.async_delete_items(123, [5])

            mock_client.delete_item.assert_called_once_with(123, 5)
            mock_refresh.assert_called_once()


class TestCoordinatorInit:
    """Tests for coordinator initialization."""

    def test_coordinator_stores_client(self, mock_hass, mock_client, mock_config_entry):
        """Test that coordinator stores the client reference."""
        coordinator = ListonicDataUpdateCoordinator(
            mock_hass, mock_client, mock_config_entry
        )

        assert coordinator.client is mock_client

    def test_coordinator_stores_config_entry(
        self, mock_hass, mock_client, mock_config_entry
    ):
        """Test that coordinator stores the config entry reference."""
        coordinator = ListonicDataUpdateCoordinator(
            mock_hass, mock_client, mock_config_entry
        )

        assert coordinator.config_entry is mock_config_entry

    def test_coordinator_default_scan_interval(
        self, mock_hass, mock_client, mock_config_entry
    ):
        """Test that coordinator uses default scan interval."""
        from datetime import timedelta

        from custom_components.listonic.const import DEFAULT_SCAN_INTERVAL

        coordinator = ListonicDataUpdateCoordinator(
            mock_hass, mock_client, mock_config_entry
        )

        assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    def test_coordinator_custom_scan_interval(
        self, mock_hass, mock_client, mock_config_entry
    ):
        """Test that coordinator accepts custom scan interval."""
        from datetime import timedelta

        coordinator = ListonicDataUpdateCoordinator(
            mock_hass, mock_client, mock_config_entry, scan_interval=60
        )

        assert coordinator.update_interval == timedelta(seconds=60)
