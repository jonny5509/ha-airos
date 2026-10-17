import asyncio
import asyncssh
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _display_name(raw_name):
    """Hide recognized discovery metadata from the device's display name."""
    if any(field in raw_name for field in ("deviceId=", "firmwareVersion=", "platform=", "deviceIp=")):
        return raw_name.split(",", 1)[0].strip() or raw_name
    return raw_name


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AiRXS2RebootSwitch(coordinator, entry)])


class AiRXS2RebootSwitch(SwitchEntity):
    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self._entry = entry
        detected_model = (coordinator.data or {}).get("device_model")
        self._name = detected_model or _display_name(entry.data["name"])
        self._attr_name = f"{self._name} Reboot"
        self._attr_unique_id = f"{entry.data['host']}_reboot"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data["host"])},
            name=self._name,
            manufacturer="Ubiquiti",
            model=(self.coordinator.data or {}).get("device_model") or "Ubiquiti AirOS",
        )

    async def async_turn_on(self, **kwargs):
        # Reuse the coordinator's modern-first / legacy-fallback SSH connection.
        async with self.coordinator._connect() as conn:
            try:
                result = await conn.run("reboot", check=False, timeout=5)
            except (asyncssh.Error, OSError, asyncio.TimeoutError) as err:
                # A successful reboot commonly drops SSH before it can return an
                # exit status. Authentication and connection setup errors happen
                # outside this block and still surface to Home Assistant.
                _LOGGER.debug(
                    "SSH closed while reboot was running; device may be rebooting: %s",
                    err,
                )
                return

            if result.exit_status not in (None, 0):
                detail = (result.stderr or "").strip()
                raise HomeAssistantError(
                    f"AirOS reboot command failed (exit {result.exit_status}): {detail}"
                )

    async def async_turn_off(self, **kwargs):
        pass

    @property
    def is_on(self):
        return False
