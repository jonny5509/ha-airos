from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
import re

BASE_SENSORS = {
    "signal": ("Wireless signal", "dBm"),
    "noise": ("Wireless noise", "dBm"),
    "ccq": ("Wireless CCQ", "%"),
    "snr": ("Wireless SNR", "dB"),
    "wlanTxRate": ("Wireless TX rate", "Mbps"),
    "wlanRxRate": ("Wireless RX rate", "Mbps"),
}

OPTIONAL_SENSORS = {
    "essid": ("Wireless SSID", None),
    "frequency": ("Wireless frequency", "MHz"),
    "wlanMac": ("Wireless MAC address", None),
    "ethernet_mac": ("Ethernet MAC address", None),
    "wireless_mac": ("Wireless MAC address", None),
    "mac": ("Device MAC address", None),
    "mode": ("Wireless mode", None),
    "hostname": ("Hostname", None),
    "uptime_seconds": ("Uptime", "s"),
    "ip_address": ("Device IP address", None),
    "cpu_model": ("CPU model", None),
    "load_1m": ("CPU load (1 min)", None),
    "load_5m": ("CPU load (5 min)", None),
    "load_15m": ("CPU load (15 min)", None),
    "mem_total_bytes": ("Memory total", "B"),
    "mem_free_bytes": ("Memory free", "B"),
    "mem_available_bytes": ("Memory available", "B"),
    "ethernet_rx_bytes": ("Ethernet received", "B"),
    "ethernet_tx_bytes": ("Ethernet sent", "B"),
    "wireless_rx_bytes": ("Wireless received", "B"),
    "wireless_tx_bytes": ("Wireless sent", "B"),
}

DEVICE_METADATA = {
    "deviceId": ("Device ID", None),
    "firmwareVersion": ("Firmware version", None),
    "platform": ("Platform", None),
    "deviceIp": ("Device IP address", None),
}


def _parse_device_name(raw_name):
    """Split comma-separated device metadata from the display name."""
    parts = [part.strip() for part in raw_name.split(",")]
    metadata = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in DEVICE_METADATA and value:
            metadata[key] = value

    if metadata:
        return parts[0] or raw_name, metadata
    return raw_name, {}


def _friendly_name(key):
    """Create readable sensor names and use Ethernet instead of LAN."""
    name = key.replace("_", " ").replace("-", " ").strip().title()
    return re.sub(r"\\bLan\\b", "Ethernet", name)


def _device_kind(key):
    """Return the Home Assistant device that should own this sensor."""
    if key in BASE_SENSORS or key.startswith(("wireless_", "wlan")) or key in {
        "essid", "frequency", "wireless_mac", "mode",
    }:
        return "wireless"
    if key.startswith("ethernet_") or key == "ethernet_mac":
        return "ethernet"
    return "main"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    display_name, metadata = _parse_device_name(entry.data["name"])
    sensors = [
        AiRXS2Sensor(
            coordinator, entry, key, unit, label, display_name=display_name,
            device_kind=_device_kind(key),
        )
        for key, (label, unit) in BASE_SENSORS.items()
    ]

    added_keys = set(BASE_SENSORS)
    for key, (label, unit) in OPTIONAL_SENSORS.items():
        if data.get(key) not in (None, ""):
            sensors.append(
                AiRXS2Sensor(
                    coordinator, entry, key, unit, label,
                    display_name=display_name, device_kind=_device_kind(key),
                )
            )
            added_keys.add(key)

    for key, value in data.items():
        if key not in added_keys and value not in (None, ""):
            sensors.append(
                AiRXS2Sensor(
                    coordinator, entry, key, None, _friendly_name(key),
                    display_name=display_name, device_kind=_device_kind(key),
                )
            )

    for key, value in metadata.items():
        label, unit = DEVICE_METADATA[key]
        sensors.append(
            AiRXS2Sensor(
                coordinator, entry, f"device_metadata_{key}", unit, label,
                display_name=display_name, static_value=value, device_kind="main",
            )
        )

    async_add_entities(sensors)


class AiRXS2Sensor(SensorEntity):
    def __init__(
        self, coordinator, entry, key, unit, label=None, display_name=None,
        static_value=None, device_kind="main",
    ):
        self.coordinator = coordinator
        self.key = key
        self._entry = entry
        self._display_name = display_name or entry.data["name"]
        self._static_value = static_value
        self._device_kind = device_kind
        if device_kind == "ethernet":
            self._device_name = f"{self._display_name} Ethernet"
        elif device_kind == "wireless":
            self._device_name = f"{self._display_name} Wireless"
        else:
            self._device_name = self._display_name
        self._attr_name = f"{self._display_name} {label or key}"
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        host = self._entry.data["host"]
        info = {
            "identifiers": {(DOMAIN, host if self._device_kind == "main" else f"{host}_{self._device_kind}")},
            "name": self._device_name,
            "manufacturer": "Ubiquiti",
            "model": "Ubiquiti AirOS" if self._device_kind == "main" else (
                "AirOS Ethernet" if self._device_kind == "ethernet" else "AirOS Wireless"
            ),
        }
        if self._device_kind != "main":
            info["via_device"] = (DOMAIN, host)
        return DeviceInfo(**info)

    @property
    def native_value(self):
        if self._static_value is not None:
            return self._static_value
        return (self.coordinator.data or {}).get(self.key)
