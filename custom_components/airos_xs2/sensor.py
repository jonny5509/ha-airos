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


def _friendly_name(key):
    return key.replace("_", " ").replace("-", " ").strip().title()


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    sensors = [
        AiRXS2Sensor(coordinator, entry, key, unit, label)
        for key, (label, unit) in BASE_SENSORS.items()
    ]

    # Include extra system/network telemetry when supported, plus every
    # additional key returned by mca-status so firmware-specific data is not lost.
    added_keys = set(BASE_SENSORS)
    for key, (label, unit) in OPTIONAL_SENSORS.items():
        if data.get(key) not in (None, ""):
            sensors.append(AiRXS2Sensor(coordinator, entry, key, unit, label))
            added_keys.add(key)

    for key, value in data.items():
        if key not in added_keys and value not in (None, ""):
            sensors.append(
                AiRXS2Sensor(coordinator, entry, key, None, _friendly_name(key))
            )

    async_add_entities(sensors)


class AiRXS2Sensor(SensorEntity):
    def __init__(self, coordinator, entry, key, unit, label=None):
        self.coordinator = coordinator
        self.key = key
        self._entry = entry
        self._attr_name = f"{coordinator.get_device_name(entry)} {label or key}"
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        interface = self._interface_for_key(self.key)
        if interface:
            return self.coordinator.get_interface_device_info(self._entry, interface)
        return self.coordinator.get_device_info(self._entry)

    @staticmethod
    def _interface_for_key(key):
        """Group network/radio entities under the matching child device."""
        if key in {
            "signal", "noise", "ccq", "snr", "wlanTxRate", "wlanRxRate",
            "essid", "frequency", "wlanMac", "wireless_mac",
            "wireless_rx_bytes", "wireless_tx_bytes",
        } or key.lower().startswith(("wlan", "wireless", "ath")):
            return "wlan"
        if key in {
            "ip_address", "mac", "ethernet_mac", "ethMac",
            "ethernet_rx_bytes", "ethernet_tx_bytes", "deviceIp",
        } or key.lower().startswith(("ethernet", "eth")):
            return "lan"
        return None

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
