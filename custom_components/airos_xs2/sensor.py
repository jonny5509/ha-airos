from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
import re

BASE_SENSORS = {
    "signal": ("Wireless Signal", "dBm"),
    "noise": ("Wireless Noise", "dBm"),
    "ccq": ("Wireless CCQ", "%"),
    "snr": ("Wireless SNR", "dB"),
    "wlanTxRate": ("Wireless Transmit Rate", "Mbit/s"),
    "wlanRxRate": ("Wireless Receive Rate", "Mbit/s"),
}

OPTIONAL_SENSORS = {
    "essid": ("Wireless Network Name (SSID)", None),
    "frequency": ("Wireless Frequency", "MHz"),
    "wlanMac": ("Wireless MAC Address", None),
    "ethernet_mac": ("Ethernet MAC Address", None),
    "wireless_mac": ("Wireless MAC Address", None),
    "mac": ("Device MAC Address", None),
    "mode": ("Wireless Mode", None),
    "hostname": ("Hostname", None),
    "uptime_seconds": ("Uptime", "s"),
    "ip_address": ("Device IP Address", None),
    "cpu_model": ("CPU Model", None),
    "load_1m": ("CPU Load (1 Minute)", None),
    "load_5m": ("CPU Load (5 Minutes)", None),
    "load_15m": ("CPU Load (15 Minutes)", None),
    "mem_total_bytes": ("Total Memory", "B"),
    "mem_free_bytes": ("Free Memory", "B"),
    "mem_available_bytes": ("Available Memory", "B"),
    "ethernet_rx_bytes": ("Ethernet Bytes Received", "B"),
    "ethernet_tx_bytes": ("Ethernet Bytes Sent", "B"),
    "wireless_rx_bytes": ("Wireless Bytes Received", "B"),
    "wireless_tx_bytes": ("Wireless Bytes Sent", "B"),
}

DEVICE_METADATA = {
    "deviceId": ("Device ID", None),
    "firmwareVersion": ("Firmware Version", None),
    "platform": ("Platform", None),
    "deviceIp": ("Configured Device IP Address", None),
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


SENSOR_NAME_OVERRIDES = {
    "signal": "Wireless Signal",
    "noise": "Wireless Noise",
    "ccq": "Wireless CCQ",
    "snr": "Wireless SNR",
    "wlanTxRate": "Wireless Transmit Rate",
    "wlanRxRate": "Wireless Receive Rate",
    "wlanMac": "Wireless MAC Address",
    "wireless_mac": "Wireless MAC Address",
    "ethernet_mac": "Ethernet MAC Address",
    "mac": "Device MAC Address",
    "essid": "Wireless Network Name (SSID)",
    "frequency": "Wireless Frequency",
    "mode": "Wireless Mode",
    "hostname": "Hostname",
    "uptime_seconds": "Uptime",
    "ip_address": "Device IP Address",
    "cpu_model": "CPU Model",
    "load_1m": "CPU Load (1 Minute)",
    "load_5m": "CPU Load (5 Minutes)",
    "load_15m": "CPU Load (15 Minutes)",
    "mem_total_bytes": "Total Memory",
    "mem_free_bytes": "Free Memory",
    "mem_available_bytes": "Available Memory",
    "ethernet_rx_bytes": "Ethernet Bytes Received",
    "ethernet_tx_bytes": "Ethernet Bytes Sent",
    "wireless_rx_bytes": "Wireless Bytes Received",
    "wireless_tx_bytes": "Wireless Bytes Sent",
    "deviceId": "Device ID",
    "firmwareVersion": "Firmware Version",
    "platform": "Platform",
    "deviceIp": "Configured Device IP Address",
}


def _friendly_name(key):
    """Return a readable, consistently capitalized name for a sensor key."""
    if key in SENSOR_NAME_OVERRIDES:
        return SENSOR_NAME_OVERRIDES[key]

    # Convert camelCase and separators into words before applying protocol terms.
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key)
    name = re.sub(r"[_-]+", " ", name).strip()
    words = name.split()
    normalized = []
    for word in words:
        lower = word.lower()
        if lower in {"wlan", "wireless", "wifi"}:
            normalized.append("Wireless")
        elif lower in {"lan", "ethernet", "eth"}:
            normalized.append("Ethernet")
        elif lower in {"mac", "ip", "cpu", "ccq", "snr", "ssid", "tx", "rx", "mhz", "dbm", "id", "url", "ram"}:
            normalized.append(lower.upper())
        else:
            normalized.append(lower.capitalize())
    return " ".join(normalized) or "Unknown"


def _device_kind(key):
    """Return the Home Assistant device that should own this sensor."""
    normalized = key.lower()
    # Check WLAN first because "lan" is also present inside "wlan".
    if normalized.startswith(("wlan", "wireless_")) or key in BASE_SENSORS or key in {
        "essid", "frequency", "wireless_mac", "mode",
    }:
        return "wireless"
    if "lan" in normalized or normalized.startswith("ethernet_") or normalized == "ethernet_mac":
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
        # Prefer the MAC reported directly by AirOS over the interface-probe
        # alias when both describe the same wireless interface.
        if key == "wireless_mac" and data.get("wlanMac") not in (None, ""):
            added_keys.add(key)
            continue
        # IP discovery depends on an optional SSH probe. Register the entity
        # even if the first probe fails, so it can become available on later polls.
        if key == "ip_address" or data.get(key) not in (None, ""):
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

        # Tell Home Assistant how to interpret readings and long-term statistics.
        if key in {"signal", "noise"}:
            self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        elif key == "frequency":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
        elif key == "uptime_seconds":
            self._attr_device_class = SensorDeviceClass.DURATION
        elif key in {"mem_total_bytes", "mem_free_bytes", "mem_available_bytes",
                     "ethernet_rx_bytes", "ethernet_tx_bytes",
                     "wireless_rx_bytes", "wireless_tx_bytes"}:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE

        if key in {"ethernet_rx_bytes", "ethernet_tx_bytes",
                   "wireless_rx_bytes", "wireless_tx_bytes"}:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {"signal", "noise", "ccq", "snr", "wlanTxRate", "wlanRxRate",
                     "frequency", "load_1m", "load_5m", "load_15m",
                     "mem_total_bytes", "mem_free_bytes", "mem_available_bytes"}:
            self._attr_state_class = SensorStateClass.MEASUREMENT

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
