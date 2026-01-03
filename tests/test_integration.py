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

    asyncio.run(do_cleanup())


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


class TestTokenRefresh:
    """Integration tests for token refresh functionality."""

    @pytest.mark.asyncio
    async def test_tokens_set_after_auth(self, client: ListonicApiClient):
        """Test that both token and refresh_token are set after authentication."""
        await client.authenticate()
        assert client._token is not None
        assert client._refresh_token is not None

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, client: ListonicApiClient):
        """Test that _refresh_access_token works if the API supports it.

        Note: This test documents the actual API behavior. If the API does not
        support refresh tokens, the test will still pass but record that refresh
        failed and full auth was required.
        """
        # Authenticate first
        await client.authenticate()
        original_token = client._token
        original_refresh_token = client._refresh_token

        assert original_token is not None
        assert original_refresh_token is not None

        # Try to refresh
        result = await client._refresh_access_token()

        if result:
            # Refresh succeeded - verify we got a new token
            assert client._token is not None
            # Token may or may not be different depending on API behavior
            # The important thing is that we have a valid token
            token_changed = client._token != original_token
            print(f"Token refresh succeeded. Token changed: {token_changed}")
        else:
            # Refresh not supported - this is also valid behavior
            # The _refresh_access_token method should have cleared the refresh token
            print("Token refresh not supported by API - will use full authentication")

    @pytest.mark.asyncio
    async def test_handle_auth_failure_recovers(self, client: ListonicApiClient):
        """Test that _handle_auth_failure recovers from token expiry.

        This simulates a scenario where the current token is invalid/expired
        and verifies that the client can recover authentication.
        """
        # First authenticate normally
        await client.authenticate()
        assert client._token is not None

        # Simulate token expiry by invalidating the current token
        client._token = "invalid_expired_token"

        # Now _handle_auth_failure should recover
        result = await client._handle_auth_failure()

        assert result is True, "_handle_auth_failure should recover authentication"
        assert client._token is not None
        assert client._token != "invalid_expired_token"

        # Verify we can make API calls after recovery
        lists = await client.get_lists()
        assert isinstance(lists, list)

    @pytest.mark.asyncio
    async def test_handle_auth_failure_without_refresh_token(
        self, client: ListonicApiClient
    ):
        """Test that _handle_auth_failure works even without a refresh token.

        When no refresh token is available, it should fall back to full
        authentication with username/password.
        """
        # Authenticate first
        await client.authenticate()
        assert client._token is not None

        # Clear both tokens to simulate no refresh token available
        client._token = None
        client._refresh_token = None

        # _handle_auth_failure should still recover via full auth
        result = await client._handle_auth_failure()

        assert result is True
        assert client._token is not None

    @pytest.mark.asyncio
    async def test_api_call_recovers_from_401(self, client: ListonicApiClient):
        """Test that API calls automatically recover from 401 responses.

        This tests the full retry flow where an API call receives a 401,
        triggers _handle_auth_failure, and retries successfully.
        """
        # Authenticate first
        await client.authenticate()

        # Invalidate the token to force a 401 on next request
        client._token = "invalid_token_that_will_cause_401"

        # The get_lists call should:
        # 1. Try with invalid token, get 401
        # 2. Call _handle_auth_failure to recover
        # 3. Retry with new valid token
        # 4. Succeed
        lists = await client.get_lists()

        assert isinstance(lists, list)
        # After recovery, we should have a valid token
        assert client._token is not None
        assert client._token != "invalid_token_that_will_cause_401"
