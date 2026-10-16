from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import AiRXS2Coordinator

PLATFORMS = ["sensor", "switch"]

WIRELESS_KEYS = {
    "signal", "noise", "ccq", "snr", "wlanTxRate", "wlanRxRate",
    "essid", "frequency", "wlanMac", "mode",
    "wireless_rx_bytes", "wireless_tx_bytes", "ip_address",
}
ETHERNET_KEYS = {"ethernet_rx_bytes", "ethernet_tx_bytes", "ethernet_mac"}


def _device_type_for_key(key: str) -> str:
    """Classify interface entities by key, including future telemetry."""
    normalized = key.lower().replace("-", "_")
    if key in WIRELESS_KEYS or "wlan" in normalized or "wireless" in normalized:
        return "wireless"
    if (
        key in ETHERNET_KEYS
        or "ethernet" in normalized
        or normalized.startswith("lan")
    ):
        return "ethernet"
    return "system"


async def _ensure_device_hierarchy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create parent/interface devices and migrate existing entity registry links."""
    host = entry.data["host"]
    name = entry.data["name"]
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    system = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, host)},
        name=name,
        manufacturer="Ubiquiti",
        model="airOS XS2",
    )
    wireless = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{host}_wireless")},
        name=f"{name} Wireless",
        manufacturer="Ubiquiti",
        model="airOS XS2 Wireless Interface",
        via_device_id=system.id,
    )
    ethernet = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{host}_ethernet")},
        name=f"{name} Ethernet",
        manufacturer="Ubiquiti",
        model="airOS XS2 Ethernet Interface",
        via_device_id=system.id,
    )

    # Preserve entity unique IDs while migrating existing registry assignments.
    prefix = f"{host}_"
    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != entry.entry_id or not entity.unique_id.startswith(prefix):
            continue
        key = entity.unique_id[len(prefix):]
        device_type = _device_type_for_key(key) if key != "reboot" else "system"
        target = wireless if device_type == "wireless" else (
            ethernet if device_type == "ethernet" else system
        )
        if entity.device_id != target.id:
            entity_registry.async_update_entity(entity.entity_id, device_id=target.id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
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

    await _ensure_device_hierarchy(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
