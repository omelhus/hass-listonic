"""Data update coordinator for Listonic."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ListonicApiClient, ListonicApiError, ListonicList
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class ListonicDataUpdateCoordinator(DataUpdateCoordinator[dict[int, ListonicList]]):
    """Class to manage fetching Listonic data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: ListonicApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, ListonicList]:
        """Fetch data from Listonic API."""
        try:
            lists = await self.client.get_lists()
            return {lst.id: lst for lst in lists}
        except ListonicApiError as err:
            raise UpdateFailed(f"Error communicating with Listonic API: {err}") from err

    async def async_add_item(
        self,
        list_id: int,
        name: str,
        quantity: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Add an item to a list."""
        await self.client.add_item(list_id, name, quantity, unit)
        await self.async_request_refresh()

    async def async_update_item(
        self,
        list_id: int,
        item_id: int,
        **kwargs,
    ) -> None:
        """Update an item."""
        await self.client.update_item(list_id, item_id, **kwargs)
        await self.async_request_refresh()

    async def async_check_item(self, list_id: int, item_id: int) -> None:
        """Check an item."""
        await self.client.check_item(list_id, item_id)
        await self.async_request_refresh()

    async def async_uncheck_item(self, list_id: int, item_id: int) -> None:
        """Uncheck an item."""
        await self.client.uncheck_item(list_id, item_id)
        await self.async_request_refresh()

    async def async_delete_item(self, list_id: int, item_id: int) -> None:
        """Delete an item."""
        await self.client.delete_item(list_id, item_id)
        await self.async_request_refresh()
