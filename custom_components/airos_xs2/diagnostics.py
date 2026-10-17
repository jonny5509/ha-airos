"""Diagnostics support for the AirOS integration."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

FIRMWARE_CATALOG_URL = "https://ui.com/download/airmax-legacy"

TO_REDACT = {
    "host",
    "username",
    "password",
    "deviceIp",
    "ip_address",
    "ethernet_ip_address",
    "wireless_ip_address",
    "hostname",
    "side_devicename",
    "deviceName",
    "devicename",
    "essid",
    "wlanMac",
    "wireless_mac",
    "ethernet_mac",
    "mac",
    "deviceId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return redacted diagnostic information for an AirOS config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "coordinator_data": async_redact_data(data, TO_REDACT),
        "firmware_catalog": {
            "url": FIRMWARE_CATALOG_URL,
            "installed_version": data.get("firmware_upgrade_installed_version"),
            "latest_version": data.get("firmware_upgrade_latest_version"),
            "status": data.get("firmware_upgrade"),
            "reason": data.get("firmware_upgrade_reason"),
        },
    }
