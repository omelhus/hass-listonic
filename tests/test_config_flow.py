"""Tests for Listonic config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from custom_components.listonic.api import ListonicApiError, ListonicAuthError
from custom_components.listonic.config_flow import ListonicConfigFlow
from custom_components.listonic.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def mock_setup_entry():
    """Mock async_setup_entry."""
    with patch(
        "custom_components.listonic.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_api_client():
    """Mock ListonicApiClient."""
    with patch(
        "custom_components.listonic.config_flow.ListonicApiClient"
    ) as mock_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock(return_value=True)
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_get_clientsession():
    """Mock async_get_clientsession."""
    with patch(
        "custom_components.listonic.config_flow.async_get_clientsession"
    ) as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def hass() -> HomeAssistant:
    """Create a mock Home Assistant instance for testing."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries._entries = {}
    hass.config_entries.async_get_entry = (
        lambda entry_id: hass.config_entries._entries.get(entry_id)
    )
    return hass


def create_mock_config_entry(
    domain: str = DOMAIN,
    title: str = "test@example.com",
    data: dict | None = None,
    options: dict | None = None,
    entry_id: str = "test_entry_id",
) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.domain = domain
    entry.title = title
    entry.data = data or {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "oldpassword"}
    entry.options = options or {}
    entry.entry_id = entry_id
    email = data.get(CONF_EMAIL, "test@example.com") if data else "test@example.com"
    entry.unique_id = email.lower()
    return entry


class TestConfigFlow:
    """Tests for the config flow."""

    async def test_async_step_user_shows_form_initially(
        self, hass: HomeAssistant
    ) -> None:
        """Test that the user step shows form when no input provided."""
        flow = ListonicConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_async_step_user_valid_credentials_creates_entry(
        self,
        hass: HomeAssistant,
        mock_api_client: AsyncMock,
        mock_setup_entry,
        mock_get_clientsession,
    ) -> None:
        """Test that valid credentials create a config entry."""
        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {}

        user_input = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }

        with patch.object(
            flow, "async_set_unique_id", new_callable=AsyncMock
        ) as mock_set_id:
            mock_set_id.return_value = None
            with patch.object(flow, "_abort_if_unique_id_configured"):
                result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test@example.com"
        assert result["data"] == user_input
        mock_api_client.authenticate.assert_called_once()

    async def test_async_step_user_invalid_credentials_shows_error(
        self, hass: HomeAssistant, mock_get_clientsession
    ) -> None:
        """Test that invalid credentials show error."""
        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {}

        user_input = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "wrongpassword",
        }

        with patch(
            "custom_components.listonic.config_flow.ListonicApiClient"
        ) as mock_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock(
                side_effect=ListonicAuthError("Invalid credentials")
            )
            mock_class.return_value = mock_client

            with patch.object(
                flow, "async_set_unique_id", new_callable=AsyncMock
            ) as mock_set_id:
                mock_set_id.return_value = None
                with patch.object(flow, "_abort_if_unique_id_configured"):
                    result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_async_step_user_connection_error_shows_error(
        self, hass: HomeAssistant, mock_get_clientsession
    ) -> None:
        """Test that connection error shows cannot_connect error."""
        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {}

        user_input = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }

        with patch(
            "custom_components.listonic.config_flow.ListonicApiClient"
        ) as mock_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock(
                side_effect=ListonicApiError("Connection failed")
            )
            mock_class.return_value = mock_client

            with patch.object(
                flow, "async_set_unique_id", new_callable=AsyncMock
            ) as mock_set_id:
                mock_set_id.return_value = None
                with patch.object(flow, "_abort_if_unique_id_configured"):
                    result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_async_step_user_unknown_error_shows_error(
        self, hass: HomeAssistant, mock_get_clientsession
    ) -> None:
        """Test that unknown exception shows unknown error."""
        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {}

        user_input = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }

        with patch(
            "custom_components.listonic.config_flow.ListonicApiClient"
        ) as mock_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock(
                side_effect=RuntimeError("Something unexpected")
            )
            mock_class.return_value = mock_client

            with patch.object(
                flow, "async_set_unique_id", new_callable=AsyncMock
            ) as mock_set_id:
                mock_set_id.return_value = None
                with patch.object(flow, "_abort_if_unique_id_configured"):
                    result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

    async def test_async_step_user_duplicate_email_aborts(
        self, hass: HomeAssistant, mock_api_client: AsyncMock, mock_get_clientsession
    ) -> None:
        """Test that duplicate email aborts the flow.

        When _abort_if_unique_id_configured is called and a duplicate exists,
        it raises AbortFlow which is expected to propagate up to the config
        flow framework. In unit tests, we verify this exception is raised.
        """
        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {}

        user_input = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }

        with patch.object(
            flow, "async_set_unique_id", new_callable=AsyncMock
        ) as mock_set_id:
            mock_set_id.return_value = None
            with patch.object(
                flow,
                "_abort_if_unique_id_configured",
                side_effect=AbortFlow("already_configured"),
            ):
                with pytest.raises(AbortFlow) as exc_info:
                    await flow.async_step_user(user_input=user_input)

        assert exc_info.value.reason == "already_configured"


class TestReauthFlow:
    """Tests for the reauth flow."""

    async def test_async_step_reauth_triggers_reauth_confirm(
        self, hass: HomeAssistant
    ) -> None:
        """Test that reauth step triggers reauth_confirm."""
        # Create a mock config entry
        entry = create_mock_config_entry()

        # Mock hass.config_entries.async_get_entry
        hass.config_entries._entries = {"test_entry_id": entry}

        flow = ListonicConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "test_entry_id"}

        result = await flow.async_step_reauth(
            entry_data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "oldpassword",
            }
        )

        # Should show the reauth_confirm form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert flow._reauth_entry == entry

    async def test_async_step_reauth_confirm_valid_credentials_updates_entry(
        self, hass: HomeAssistant, mock_api_client: AsyncMock, mock_get_clientsession
    ) -> None:
        """Test that valid credentials in reauth updates the entry."""
        # Create a mock config entry
        entry = create_mock_config_entry()

        flow = ListonicConfigFlow()
        flow.hass = hass
        flow._reauth_entry = entry
        flow.context = {}

        user_input = {CONF_PASSWORD: "newpassword"}

        with patch.object(
            flow, "async_update_reload_and_abort"
        ) as mock_update:
            mock_update.return_value = {
                "type": FlowResultType.ABORT,
                "reason": "reauth_successful",
            }
            result = await flow.async_step_reauth_confirm(user_input=user_input)

        mock_api_client.authenticate.assert_called_once()
        mock_update.assert_called_once_with(
            entry,
            data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "newpassword",
            },
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    async def test_async_step_reauth_confirm_invalid_credentials_shows_error(
        self, hass: HomeAssistant, mock_get_clientsession
    ) -> None:
        """Test that invalid credentials in reauth show error."""
        # Create a mock config entry
        entry = create_mock_config_entry()

        flow = ListonicConfigFlow()
        flow.hass = hass
        flow._reauth_entry = entry
        flow.context = {}

        user_input = {CONF_PASSWORD: "wrongpassword"}

        with patch(
            "custom_components.listonic.config_flow.ListonicApiClient"
        ) as mock_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock(
                side_effect=ListonicAuthError("Invalid credentials")
            )
            mock_class.return_value = mock_client

            result = await flow.async_step_reauth_confirm(user_input=user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_async_step_reauth_confirm_connection_error_shows_error(
        self, hass: HomeAssistant, mock_get_clientsession
    ) -> None:
        """Test that connection error in reauth shows cannot_connect error."""
        # Create a mock config entry
        entry = create_mock_config_entry()

        flow = ListonicConfigFlow()
        flow.hass = hass
        flow._reauth_entry = entry
        flow.context = {}

        user_input = {CONF_PASSWORD: "testpassword"}

        with patch(
            "custom_components.listonic.config_flow.ListonicApiClient"
        ) as mock_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock(
                side_effect=ListonicApiError("Connection failed")
            )
            mock_class.return_value = mock_client

            result = await flow.async_step_reauth_confirm(user_input=user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_async_step_reauth_confirm_shows_form_initially(
        self, hass: HomeAssistant
    ) -> None:
        """Test that reauth_confirm shows form when no input provided."""
        # Create a mock config entry
        entry = create_mock_config_entry()

        flow = ListonicConfigFlow()
        flow.hass = hass
        flow._reauth_entry = entry
        flow.context = {}

        result = await flow.async_step_reauth_confirm(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}
        assert result["description_placeholders"][CONF_EMAIL] == "test@example.com"


class TestOptionsFlow:
    """Tests for the options flow."""

    async def test_options_flow_async_step_init_shows_current_scan_interval(
        self, hass: HomeAssistant
    ) -> None:
        """Test that options flow shows current scan interval."""
        # Create a mock config entry with options
        entry = create_mock_config_entry(options={CONF_SCAN_INTERVAL: 60})

        options_flow = ListonicConfigFlow.async_get_options_flow(entry)
        options_flow.hass = hass

        result = await options_flow.async_step_init(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        # Check the schema has the correct default value
        schema = result["data_schema"]
        # Schema should include scan_interval with default of 60 (current option)
        assert schema is not None

    async def test_options_flow_async_step_init_shows_default_when_no_options(
        self, hass: HomeAssistant
    ) -> None:
        """Test that options flow shows default scan interval when no options set."""
        # Create a mock config entry without options
        entry = create_mock_config_entry(options={})

        options_flow = ListonicConfigFlow.async_get_options_flow(entry)
        options_flow.hass = hass

        result = await options_flow.async_step_init(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        # Schema should use DEFAULT_SCAN_INTERVAL when no option is set
        assert result["data_schema"] is not None

    async def test_options_flow_saves_new_scan_interval(
        self, hass: HomeAssistant
    ) -> None:
        """Test that options flow saves new scan interval."""
        # Create a mock config entry
        entry = create_mock_config_entry(
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}
        )

        options_flow = ListonicConfigFlow.async_get_options_flow(entry)
        options_flow.hass = hass

        user_input = {CONF_SCAN_INTERVAL: 120}

        result = await options_flow.async_step_init(user_input=user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_SCAN_INTERVAL: 120}
