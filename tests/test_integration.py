"""Integration tests for the Listonic API client.

These tests make real API calls to verify the integration works correctly.
They require valid credentials in environment variables:
- LISTONIC_EMAIL
- LISTONIC_PASSWORD
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from custom_components.listonic.api import (
    ListonicApiClient,
    ListonicAuthError,
)

# Load environment variables
load_dotenv()

# Prefix for test lists - used for cleanup
TEST_LIST_PREFIX = "HA Integration Test"

# Skip all tests if no credentials are available
pytestmark = pytest.mark.skipif(
    not os.getenv("LISTONIC_EMAIL") or not os.getenv("LISTONIC_PASSWORD"),
    reason="Listonic credentials not available in environment",
)


@pytest.fixture
async def client():
    """Create a Listonic API client."""
    email = os.getenv("LISTONIC_EMAIL", "")
    password = os.getenv("LISTONIC_PASSWORD", "")
    client = ListonicApiClient(email, password)
    yield client
    await client.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_lists():
    """Clean up any leftover test lists after all tests complete."""
    # Run tests first
    yield

    # Cleanup after all tests
    import asyncio

    async def do_cleanup():
        email = os.getenv("LISTONIC_EMAIL", "")
        password = os.getenv("LISTONIC_PASSWORD", "")
        if not email or not password:
            return

        client = ListonicApiClient(email, password)
        try:
            lists = await client.get_lists()
            for lst in lists:
                if lst.name.startswith(TEST_LIST_PREFIX):
                    print(f"Cleaning up test list: {lst.name}")
                    await client.delete_list(lst.id)
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            await client.close()

    asyncio.get_event_loop().run_until_complete(do_cleanup())


class TestListonicIntegration:
    """Integration tests that make real API calls."""

    @pytest.mark.asyncio
    async def test_authenticate(self, client: ListonicApiClient):
        """Test authentication with real credentials."""
        result = await client.authenticate()
        assert result is True
        assert client._token is not None

    @pytest.mark.asyncio
    async def test_get_lists(self, client: ListonicApiClient):
        """Test getting lists from the API."""
        lists = await client.get_lists()

        # Returns a list (may be empty for fresh accounts)
        assert isinstance(lists, list)

        # Each list should have required properties
        for lst in lists:
            assert lst.id is not None
            assert lst.name is not None
            assert isinstance(lst.items, list)

    @pytest.mark.asyncio
    async def test_create_and_delete_list(self, client: ListonicApiClient):
        """Test creating and deleting a list."""
        # Create a test list
        test_list = await client.create_list("HA Integration Test List")
        assert test_list.id is not None
        assert test_list.name == "HA Integration Test List"

        # Delete the test list
        result = await client.delete_list(test_list.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_add_check_and_delete_item(self, client: ListonicApiClient):
        """Test the full item lifecycle."""
        # Create a test list
        test_list = await client.create_list("HA Integration Test Items")

        try:
            # Add an item
            item = await client.add_item(test_list.id, "Test Item", "1", "pcs")
            assert item.id is not None
            assert item.name == "Test Item"
            assert item.is_checked is False

            # Check the item
            checked_item = await client.check_item(test_list.id, item.id)
            assert checked_item.is_checked is True

            # Uncheck the item
            unchecked_item = await client.uncheck_item(test_list.id, item.id)
            assert unchecked_item.is_checked is False

            # Delete the item
            result = await client.delete_item(test_list.id, item.id)
            assert result is True

        finally:
            # Clean up - delete the test list
            await client.delete_list(test_list.id)

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test that invalid credentials raise an error."""
        client = ListonicApiClient("invalid@example.com", "wrongpassword")

        with pytest.raises(ListonicAuthError):
            await client.authenticate()

        await client.close()
