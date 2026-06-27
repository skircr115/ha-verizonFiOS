"""DataUpdateCoordinator for Verizon Router."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ROUTER_URL, DOMAIN, UPDATE_INTERVAL
from .verizon_api import VerizonRouterAPI

_LOGGER = logging.getLogger(__name__)


class VerizonRouterCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Verizon Router data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        # Options (if set) take precedence over the original config data so
        # that URL / credential changes made via the options flow take effect
        # immediately on the next reload.
        effective = {**entry.data, **entry.options}

        self.api = VerizonRouterAPI(
            effective[CONF_ROUTER_URL],
            effective[CONF_USERNAME],
            effective[CONF_PASSWORD],
        )

        # Cache for processed sensor definitions. Populated lazily by the first
        # sensor that reads native_value after an update, then shared by all
        # sensors for the remainder of that cycle. Invalidated here each time
        # fresh raw data arrives so that the next read triggers reprocessing.
        self.processed_data: dict[str, dict] | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            data = await self.api.fetch_router_data()
            # Invalidate processed cache — sensors will repopulate on next access
            self.processed_data = None
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err