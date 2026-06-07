"""Config flow for Verizon FiOS Router integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ROUTER_URL, DEFAULT_ROUTER_URL, DOMAIN
from .verizon_api import VerizonRouterAPI

_LOGGER = logging.getLogger(__name__)


class VerizonFiOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Verizon FiOS Router."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return VerizonFiOSOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the connection
            api = VerizonRouterAPI(
                user_input[CONF_ROUTER_URL],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                _LOGGER.debug(
                    "Testing connection to %s with username %s",
                    user_input[CONF_ROUTER_URL],
                    user_input[CONF_USERNAME],
                )
                if await api.test_connection():
                    # Create the entry
                    await self.async_set_unique_id(user_input[CONF_ROUTER_URL])
                    self._abort_if_unique_id_configured()

                    _LOGGER.info("Successfully connected to router")
                    return self.async_create_entry(
                        title="Verizon FiOS Router",
                        data=user_input,
                    )
                else:
                    _LOGGER.warning("Connection test failed - check credentials")
                    errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception during connection test: %s", err)
                errors["base"] = "unknown"

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ROUTER_URL, default=DEFAULT_ROUTER_URL): str,
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class VerizonFiOSOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Verizon FiOS Router (post-install credential/URL changes)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        # Current effective values: options override data
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            api = VerizonRouterAPI(
                user_input[CONF_ROUTER_URL],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                _LOGGER.debug(
                    "Options flow: testing connection to %s",
                    user_input[CONF_ROUTER_URL],
                )
                if await api.test_connection():
                    _LOGGER.info("Options flow: connection verified, saving options")
                    return self.async_create_entry(title="", data=user_input)
                else:
                    _LOGGER.warning("Options flow: connection test failed")
                    errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Options flow: unexpected error: %s", err)
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ROUTER_URL,
                    default=current.get(CONF_ROUTER_URL, DEFAULT_ROUTER_URL),
                ): str,
                vol.Required(
                    CONF_USERNAME,
                    default=current.get(CONF_USERNAME, "admin"),
                ): str,
                vol.Required(
                    CONF_PASSWORD,
                    default=current.get(CONF_PASSWORD, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "router_url": current.get(CONF_ROUTER_URL, DEFAULT_ROUTER_URL),
            },
        )