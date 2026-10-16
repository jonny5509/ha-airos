from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

BASE_SENSORS = {
    "signal": ("Signal", "dBm"),
    "noise": ("Noise", "dBm"),
    "ccq": ("CCQ", "%"),
    "snr": ("SNR", "dB"),
    "wlanTxRate": ("Wireless TX rate", "Mbps"),
    "wlanRxRate": ("Wireless RX rate", "Mbps"),
}

OPTIONAL_SENSORS = {
    "essid": ("SSID", None),
    "frequency": ("Frequency", "MHz"),
    "wlanMac": ("Wireless MAC", None),
    "mac": ("MAC address", None),
    "mode": ("Wireless mode", None),
    "hostname": ("Hostname", None),
    "uptime_seconds": ("Uptime", "s"),
    "ip_address": ("IP address", None),
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

WLAN_KEYS = {
    "signal", "noise", "ccq", "snr", "wlanTxRate", "wlanRxRate",
    "essid", "frequency", "wlanMac", "mode", "wireless_mac",
    "wireless_rx_bytes", "wireless_tx_bytes",
}
LAN_KEYS = {
    "mac", "ethernet_mac", "ip_address",
    "ethernet_rx_bytes", "ethernet_tx_bytes",
}


def _friendly_name(key):
    return key.replace("_", " ").replace("-", " ").strip().title()


def _device_model(entry, data):
    """Return the hardware model reported by airOS, if available."""
    candidates = [entry.data.get("platform")]
    candidates.extend(data.get(key) for key in (
        "platform", "model", "board.name", "boardName", "deviceModel"
    ))
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        model = candidate.strip()
        if model.casefold() == "nanostation5":
            return "NanoStation 5"
        return model
    return None


def _network_for_key(key):
    """Place wireless telemetry on WLAN and other/system telemetry on LAN."""
    if key in WLAN_KEYS:
        return "wlan"
    if key in LAN_KEYS:
        return "lan"
    normalized = key.casefold()
    if any(token in normalized for token in ("wlan", "wireless", "signal", "noise", "ccq", "snr", "essid", "frequency")):
        return "wlan"
    # Device-wide/system values and unclassified firmware fields go on LAN
    # so every sensor is assigned to exactly one of the two device entries.
    return "lan"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    sensors = [
        AiRXS2Sensor(coordinator, entry, key, unit, label, _network_for_key(key))
        for key, (label, unit) in BASE_SENSORS.items()
    ]

    # Include optional telemetry only when the device reports it.
    added_keys = set(BASE_SENSORS)
    for key, (label, unit) in OPTIONAL_SENSORS.items():
        if data.get(key) not in (None, ""):
            sensors.append(
                AiRXS2Sensor(coordinator, entry, key, unit, label, _network_for_key(key))
            )
            added_keys.add(key)

    # Preserve firmware-specific values, assigning each to one network device.
    for key, value in data.items():
        if key not in added_keys and value not in (None, ""):
            sensors.append(
                AiRXS2Sensor(
                    coordinator, entry, key, None, _friendly_name(key),
                    _network_for_key(key),
                )
            )

    async_add_entities(sensors)


class AiRXS2Sensor(SensorEntity):
    def __init__(self, coordinator, entry, key, unit, label=None, network="lan"):
        self.coordinator = coordinator
        self.key = key
        self._entry = entry
        self._network = network
        self._attr_name = f"{network.upper()} {label or key}"
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        data = self.coordinator.data or {}
        model = _device_model(self._entry, data)
        base_name = model or self._entry.data["name"]
        network_name = self._network.upper()

        if self._network == "wlan":
            mac_address = next(
                (str(data[key]).strip() for key in ("wlanMac", "wireless_mac")
                 if data.get(key) not in (None, "")),
                None,
            )
        else:
            mac_address = next(
                (str(data[key]).strip() for key in ("mac", "ethernet_mac")
                 if data.get(key) not in (None, "")),
                self._entry.data.get("device_id"),
            )

        firmware_version = (
            self._entry.data.get("firmware_version")
            or data.get("firmwareVersion")
            or data.get("firmware_version")
        )

        info = {
            "identifiers": {(DOMAIN, f"{self._entry.data['host']}_{self._network}")},
            "name": f"{base_name} {network_name}",
            "manufacturer": "Ubiquiti",
        }
        if model:
            info["model"] = model
        if firmware_version:
            info["sw_version"] = str(firmware_version)
        if mac_address:
            info["connections"] = {("mac", str(mac_address).strip())}
        return DeviceInfo(**info)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
