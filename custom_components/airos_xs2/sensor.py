from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

WLAN_KEYS = {
    "signal", "noise", "ccq", "snr", "wlanTxRate", "wlanRxRate",
    "essid", "frequency", "wlanMac", "mode", "wireless_mac",
    "wireless_rx_bytes", "wireless_tx_bytes",
}
LAN_KEYS = {
    "mac", "ethernet_mac", "ip_address",
    "ethernet_rx_bytes", "ethernet_tx_bytes",
}

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

_MODEL_KEYS = ("platform", "model", "board.name", "boardName", "deviceModel")


def _friendly_name(key):
    return key.replace("_", " ").replace("-", " ").strip().title()


def _device_model(entry, data):
    """Return the hardware model reported by airOS, if available."""
    candidates = [entry.data.get("platform")]
    candidates.extend(data.get(key) for key in _MODEL_KEYS)
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
    if any(token in normalized for token in (
        "wlan", "wireless", "signal", "noise", "ccq", "snr", "essid", "frequency"
    )):
        return "wlan"
    return "lan"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    host = entry.data["host"]
    model = _device_model(entry, data)
    firmware_version = (
        entry.data.get("firmware_version")
        or data.get("firmwareVersion")
        or data.get("firmware_version")
    )

    # Register the main hardware device first, matching EdgeOS's parent-first
    # device setup pattern so LAN/WLAN children can link to a real registry ID.
    device_registry = dr.async_get(hass)
    parent_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, host)},
        name=model or entry.data["name"],
        manufacturer="Ubiquiti",
        model=model,
        sw_version=str(firmware_version) if firmware_version else None,
    )

    sensors = [
        AiRXS2Sensor(coordinator, entry, "device_model", None, "Hardware model", "device"),
    ]
    firmware_version = (
        entry.data.get("firmware_version")
        or data.get("firmwareVersion")
        or data.get("firmware_version")
    )
    if firmware_version:
        sensors.append(
            AiRXS2Sensor(
                coordinator, entry, "firmware_version", None,
                "Firmware version", "device",
            )
        )

    sensors.extend(
        AiRXS2Sensor(coordinator, entry, key, unit, label, _network_for_key(key))
        for key, (label, unit) in BASE_SENSORS.items()
    )

    added_keys = set(BASE_SENSORS)
    for key, (label, unit) in OPTIONAL_SENSORS.items():
        if data.get(key) not in (None, ""):
            sensors.append(
                AiRXS2Sensor(coordinator, entry, key, unit, label, _network_for_key(key))
            )
            added_keys.add(key)

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
        self.hass = coordinator.hass
        self.key = key
        self._entry = entry
        self._network = network
        self._attr_name = label if network == "device" else f"{network.upper()} {label or key}"
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        data = self.coordinator.data or {}
        model = _device_model(self._entry, data)
        base_name = model or self._entry.data["name"]
        firmware_version = (
            self._entry.data.get("firmware_version")
            or data.get("firmwareVersion")
            or data.get("firmware_version")
        )
        host = self._entry.data["host"]

        if self._network == "device":
            info = {
                "identifiers": {(DOMAIN, host)},
                "name": base_name,
                "manufacturer": "Ubiquiti",
            }
            if model:
                info["model"] = model
            if firmware_version:
                info["sw_version"] = str(firmware_version)
            mac_address = self._entry.data.get("device_id")
            if mac_address:
                info["connections"] = {("mac", str(mac_address).strip())}
            return DeviceInfo(**info)

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
                None,
            )

        info = {
            "identifiers": {(DOMAIN, f"{host}_{self._network}")},
            "name": f"{base_name} {self._network.upper()}",
            "manufacturer": "Ubiquiti",
            "via_device_id": dr.async_get(self.hass).async_get_device(
                identifiers={(DOMAIN, host)}
            ).id,
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
        data = self.coordinator.data or {}
        if self.key == "device_model":
            return _device_model(self._entry, data) or self._entry.data["name"]
        if self.key == "firmware_version":
            return (
                self._entry.data.get("firmware_version")
                or data.get("firmwareVersion")
                or data.get("firmware_version")
            )
        return data.get(self.key)
