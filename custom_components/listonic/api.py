"""Listonic API client."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_LISTS_ENDPOINT,
    API_LOGIN_ENDPOINT,
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
)

_LOGGER = logging.getLogger(__name__)

# Base64 encoded client credentials for clientauthorization header
_CLIENT_AUTH = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()


class ListonicAuthError(Exception):
    """Exception for authentication errors."""


class ListonicApiError(Exception):
    """Exception for API errors."""


@dataclass
class ListonicItem:
    """Represents a shopping list item."""

    id: int
    name: str
    is_checked: bool
    quantity: str | None = None
    unit: str | None = None
    price: float | None = None
    description: str | None = None
    category_id: int | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ListonicItem:
        """Create from API response.

        API uses PascalCase field names:
        - Id (string) or IdAsNumber (int)
        - Name, Checked (1/0), Amount, Unit, Price, Description, CategoryId
        """
        # Handle both string Id and numeric IdAsNumber
        item_id = data.get("IdAsNumber") or int(data.get("Id", data.get("id", 0)))
        # Checked is 1/0 in API, convert to bool
        checked = data.get("Checked", data.get("isChecked", 0))
        is_checked = bool(checked) if isinstance(checked, int) else checked

        return cls(
            id=item_id,
            name=data.get("Name", data.get("name", "")),
            is_checked=is_checked,
            quantity=data.get("Amount", data.get("quantity")),
            unit=data.get("Unit", data.get("unit")),
            price=data.get("Price", data.get("price")),
            description=data.get("Description", data.get("description")),
            category_id=data.get("CategoryId", data.get("categoryId")),
        )


@dataclass
class ListonicList:
    """Represents a shopping list."""

    id: int
    name: str
    items: list[ListonicItem]
    is_archived: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ListonicList:
        """Create from API response.

        API uses PascalCase field names:
        - Id (string), Name, Items, Active (1/0), Deleted (1/0)
        """
        # Items array uses capital I
        items = [
            ListonicItem.from_api(item)
            for item in data.get("Items", data.get("items", []))
        ]
        # Id is a string in the API
        list_id = int(data.get("Id", data.get("id", 0)))
        # is_archived is based on Active=0 or Deleted=1
        is_archived = (
            data.get("Active", data.get("active", 1)) == 0
            or data.get("Deleted", data.get("deleted", 0)) == 1
        )
        return cls(
            id=list_id,
            name=data.get("Name", data.get("name", "")),
            items=items,
            is_archived=is_archived,
        )

    @property
    def unchecked_count(self) -> int:
        """Return count of unchecked items."""
        return sum(1 for item in self.items if not item.is_checked)

    @property
    def checked_count(self) -> int:
        """Return count of checked items."""
        return sum(1 for item in self.items if item.is_checked)


class ListonicApiClient:
    """Client for the Listonic API."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._email = email
        self._password = password
        self._session = session
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def authenticate(self) -> bool:
        """Authenticate with the Listonic API."""
        session = await self._get_session()
        url = f"{API_BASE_URL}{API_LOGIN_ENDPOINT}"
        params = {
            "provider": "password",
            "autoMerge": "1",
            "autoDestruct": "1",
        }
        # Form data for OAuth2-style authentication
        form_data = {
            "username": self._email,
            "password": self._password,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "clientauthorization": f"Bearer {_CLIENT_AUTH}",
        }

        try:
            async with session.post(
                url, params=params, data=form_data, headers=headers
            ) as response:
                if response.status == 401:
                    raise ListonicAuthError("Invalid credentials")
                if response.status == 400:
                    text = await response.text()
                    # 400 with auth-related message is an auth error
                    if "Unauthorized" in text or "Invalid" in text:
                        raise ListonicAuthError(f"Invalid credentials: {text}")
                    raise ListonicApiError(f"Bad request: {text}")
                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Authentication failed: {response.status} - {text}"
                    )

                data = await response.json()
                self._token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")

                if not self._token:
                    raise ListonicAuthError("No token in response")

                _LOGGER.debug("Successfully authenticated with Listonic")
                return True

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token."""
        if not self._token:
            await self.authenticate()

    async def get_lists(self) -> list[ListonicList]:
        """Get all shopping lists."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}"
        params = {
            "includeShares": "true",
            "archive": "false",
            "includeItems": "true",
        }

        try:
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    # Token expired, re-authenticate
                    self._token = None
                    await self.authenticate()
                    return await self.get_lists()

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to get lists: {response.status} - {text}"
                    )

                data = await response.json()
                return [ListonicList.from_api(lst) for lst in data]

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def get_list(self, list_id: int) -> ListonicList:
        """Get a specific shopping list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}"
        params = {"includeShares": "true"}

        try:
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.get_list(list_id)

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to get list: {response.status} - {text}"
                    )

                data = await response.json()
                return ListonicList.from_api(data)

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def get_list_items(self, list_id: int) -> list[ListonicItem]:
        """Get items for a specific list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}/items"

        try:
            async with session.get(
                url, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.get_list_items(list_id)

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to get items: {response.status} - {text}"
                    )

                data = await response.json()
                return [ListonicItem.from_api(item) for item in data]

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def add_item(
        self,
        list_id: int,
        name: str,
        quantity: str | None = None,
        unit: str | None = None,
    ) -> ListonicItem:
        """Add an item to a list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}/items"
        # API uses PascalCase field names
        payload: dict[str, Any] = {"Name": name}
        if quantity:
            payload["Amount"] = quantity
        if unit:
            payload["Unit"] = unit

        try:
            async with session.post(
                url, json=payload, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.add_item(list_id, name, quantity, unit)

                if response.status not in (200, 201):
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to add item: {response.status} - {text}"
                    )

                data = await response.json()
                return ListonicItem.from_api(data)

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def update_item(
        self,
        list_id: int,
        item_id: int,
        **kwargs: Any,
    ) -> ListonicItem:
        """Update an item."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}/items/{item_id}"

        # Map Python names to API names (PascalCase)
        payload = {}
        if "is_checked" in kwargs:
            payload["Checked"] = 1 if kwargs["is_checked"] else 0
        if "name" in kwargs:
            payload["Name"] = kwargs["name"]
        if "quantity" in kwargs:
            payload["Amount"] = kwargs["quantity"]
        if "unit" in kwargs:
            payload["Unit"] = kwargs["unit"]
        if "description" in kwargs:
            payload["Description"] = kwargs["description"]

        try:
            async with session.patch(
                url, json=payload, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.update_item(list_id, item_id, **kwargs)

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to update item: {response.status} - {text}"
                    )

                # API returns empty body on success, fetch updated item
                items = await self.get_list_items(list_id)
                for item in items:
                    if item.id == item_id:
                        return item

                # Item not found after update - create minimal response
                return ListonicItem(
                    id=item_id,
                    name=kwargs.get("name", ""),
                    is_checked=kwargs.get("is_checked", False),
                )

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def check_item(self, list_id: int, item_id: int) -> ListonicItem:
        """Mark an item as checked."""
        return await self.update_item(list_id, item_id, is_checked=True)

    async def uncheck_item(self, list_id: int, item_id: int) -> ListonicItem:
        """Mark an item as unchecked."""
        return await self.update_item(list_id, item_id, is_checked=False)

    async def delete_item(self, list_id: int, item_id: int) -> bool:
        """Delete an item from a list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}/items/{item_id}"

        try:
            async with session.delete(
                url, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.delete_item(list_id, item_id)

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to delete item: {response.status} - {text}"
                    )

                return True

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def create_list(self, name: str) -> ListonicList:
        """Create a new shopping list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}"
        # API uses PascalCase field names
        payload = {"Name": name}

        try:
            async with session.post(
                url, json=payload, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.create_list(name)

                if response.status not in (200, 201):
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to create list: {response.status} - {text}"
                    )

                data = await response.json()
                return ListonicList.from_api(data)

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err

    async def delete_list(self, list_id: int) -> bool:
        """Delete a shopping list."""
        await self._ensure_authenticated()
        session = await self._get_session()

        url = f"{API_BASE_URL}{API_LISTS_ENDPOINT}/{list_id}"

        try:
            async with session.delete(
                url, headers=self._get_headers()
            ) as response:
                if response.status == 401:
                    self._token = None
                    await self.authenticate()
                    return await self.delete_list(list_id)

                if response.status != 200:
                    text = await response.text()
                    raise ListonicApiError(
                        f"Failed to delete list: {response.status} - {text}"
                    )

                return True

        except aiohttp.ClientError as err:
            raise ListonicApiError(f"Connection error: {err}") from err
