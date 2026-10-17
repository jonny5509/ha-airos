import asyncssh
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN


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
        async with asyncssh.connect(
            self.coordinator.host,
            username=self.coordinator.username,
            password=self.coordinator.password,
            known_hosts=None,
            kex_algs=["diffie-hellman-group1-sha1"],
            encryption_algs=["aes128-cbc"],
            server_host_key_algs=["ssh-rsa"],
        ) as conn:
            await conn.run("reboot")

    async def async_turn_off(self, **kwargs):
        pass

    @property
    def is_on(self):
        return False
