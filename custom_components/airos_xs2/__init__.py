from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import AiRXS2Coordinator
from .device import normalize_device_metadata

PLATFORMS = ["sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Older installs may have stored the whole UBNT metadata string as the
    # config-entry name. Split it once so Home Assistant displays a readable
    # device name and retains the remaining fields separately.
    normalized = normalize_device_metadata(entry.data.get("name"))
    new_data = {
        **entry.data,
        **{
            key: value
            for key, value in normalized.items()
            if value is not None
        },
    }
    if new_data != dict(entry.data) or entry.title != normalized["name"]:
        hass.config_entries.async_update_entry(
            entry,
            title=normalized["name"],
            data=new_data,
        )

    hass.data.setdefault(DOMAIN, {})

    coordinator = AiRXS2Coordinator(
        hass,
        entry.data["host"],
        entry.data["username"],
        entry.data["password"],
        entry.data["name"],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
