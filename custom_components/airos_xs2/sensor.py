from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
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
    "wireless_mac": ("Wireless MAC", None),
    "mac": ("MAC address", None),
    "mode": ("Wireless mode", None),
    "channel_width": ("Channel width", "MHz"),
    "txpower": ("Transmit power", "dBm"),
    "tx_power": ("Transmit power", "dBm"),
    "chain0_signal": ("Chain 0 signal", "dBm"),
    "chain1_signal": ("Chain 1 signal", "dBm"),
    "lan_ip": ("Ethernet IP address", None),
    "lan_mac": ("Ethernet MAC", None),
    "wlan_ip": ("Wireless IP address", None),
    "rx_rate": ("Receive rate", "Mbps"),
    "tx_rate": ("Transmit rate", "Mbps"),
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
    "mem_used_bytes": ("Memory used", "B"),
    "ethernet_rx_bytes": ("Ethernet received", "B"),
    "ethernet_tx_bytes": ("Ethernet sent", "B"),
    "wireless_rx_bytes": ("Wireless received", "B"),
    "wireless_tx_bytes": ("Wireless sent", "B"),
    "ethernet_mac": ("Ethernet MAC", None),
    "wlanConnections": ("Wireless connections", "devices"),
    "connected_station_count": ("Connected wireless stations", "devices"),
    "station_signal_min": ("Weakest station signal", "dBm"),
    "station_signal_max": ("Strongest station signal", "dBm"),
    "station_ccq_average": ("Average station CCQ", "%"),
    "stations_rx_bytes": ("Stations received", "B"),
    "stations_tx_bytes": ("Stations sent", "B"),
    "stations_rx_pps": ("Stations RX packet rate", "packet/s"),
    "stations_tx_pps": ("Stations TX packet rate", "packet/s"),
    "mem_used_bytes": ("Memory used", "B"),
    "wlanTxLatency": ("Wireless TX latency", "ms"),
    "wlanPollingQuality": ("Wireless polling quality", "%"),
    "wlanPollingCapacity": ("Wireless polling capacity", "%"),
    "ackTimeout": ("ACK timeout", None),
    "distance": ("Wireless link distance", "m"),
    "lanSpeed": ("Ethernet link speed", None),
    "lanPlugged": ("Ethernet link connected", None),
    "wlanRxPackets": ("Wireless packets received", "packets"),
    "wlanTxPackets": ("Wireless packets sent", "packets"),
    "wlanRxErrors": ("Wireless receive errors", "errors"),
    "wlanTxErrors": ("Wireless transmit errors", "errors"),
    "lanRxPackets": ("Ethernet packets received", "packets"),
    "lanTxPackets": ("Ethernet packets sent", "packets"),
    "lanRxErrors": ("Ethernet receive errors", "errors"),
    "lanTxErrors": ("Ethernet transmit errors", "errors"),
    "wlanRxErrNwid": ("Wireless NWID errors", "errors"),
    "wlanRxErrCrypt": ("Wireless crypto errors", "errors"),
    "wlanRxErrFrag": ("Wireless fragment errors", "errors"),
    "wlanRxErrRetries": ("Wireless retry errors", "errors"),
    "wlanRxErrBmiss": ("Wireless beacon-miss errors", "errors"),
    "wlanRxErrOther": ("Other wireless receive errors", "errors"),
}

WIRELESS_KEYS = {
    *BASE_SENSORS,
    "essid",
    "frequency",
    "wlanMac",
    "mode",
    "wireless_rx_bytes",
    "wireless_tx_bytes",
    "channel_width",
    "txpower",
    "tx_power",
    "chain0_signal",
    "chain1_signal",
    "rx_rate",
    "tx_rate",
    "wlan_ip",
    "wlanConnections",
    "connected_station_count",
    "station_signal_min",
    "station_signal_max",
    "station_ccq_average",
    "stations_rx_bytes",
    "stations_tx_bytes",
    "stations_rx_pps",
    "stations_tx_pps",
    "wlanTxLatency",
    "wlanPollingQuality",
    "wlanPollingCapacity",
    "ackTimeout",
    "distance",
    "wlanRxPackets",
    "wlanTxPackets",
    "wlanRxErrors",
    "wlanTxErrors",
    "wlanRxErrNwid",
    "wlanRxErrCrypt",
    "wlanRxErrFrag",
    "wlanRxErrRetries",
    "wlanRxErrBmiss",
    "wlanRxErrOther",
}
ETHERNET_KEYS = {
    "ethernet_rx_bytes",
    "ethernet_tx_bytes",
    "ethernet_mac",
    "lan_ip",
    "lan_mac",
    "lanSpeed",
    "lanPlugged",
    "lanRxPackets",
    "lanTxPackets",
    "lanRxErrors",
    "lanTxErrors",
}
SYSTEM_SENSOR_ICONS = {
    "uptime_seconds": "mdi:timer-outline",
    "load_1m": "mdi:chart-line",
    "load_5m": "mdi:chart-line",
    "load_15m": "mdi:chart-line",
    "mem_total_bytes": "mdi:memory",
    "mem_free_bytes": "mdi:memory",
    "mem_available_bytes": "mdi:memory",
    "cpu_model": "mdi:chip",
    "ip_address": "mdi:ip-network",
    "hostname": "mdi:router-network",
}


def _friendly_name(key):
    """Turn firmware-specific keys into readable Home Assistant names."""
    labels = {
        "wlanMac": "Wireless MAC",
        "wireless_mac": "Wireless MAC",
        "ethernet_mac": "Ethernet MAC",
        "lan_mac": "Ethernet MAC",
        "mac": "MAC address",
        "essid": "SSID",
        "snr": "SNR",
        "ccq": "CCQ",
        "ip_address": "IP address",
        "lan_ip": "Ethernet IP address",
        "wlan_ip": "Wireless IP address",
        "wlanTxRate": "Wireless TX rate",
        "wlanRxRate": "Wireless RX rate",
        "wlanLinkQuality": "Link quality",
        "wlanLinkQualityPercent": "Link quality",
        "wlanSignal": "Signal",
        "wlanNoise": "Noise",
        "wlanSNR": "SNR",
        "wlanCCQ": "CCQ",
        "wlanFrequency": "Frequency",
        "wlanESSID": "SSID",
        "wlanConnections": "Wireless connections",
        "connected_station_count": "Connected wireless stations",
        "wlanTxLatency": "Wireless TX latency",
        "wlanPollingQuality": "Wireless polling quality",
        "wlanPollingCapacity": "Wireless polling capacity",
        "ackTimeout": "ACK timeout",
        "distance": "Wireless link distance",
        "lanSpeed": "Ethernet link speed",
        "lanPlugged": "Ethernet link connected",
        "txpower": "Transmit power",
        "tx_power": "Transmit power",
    }
    if key in labels:
        return labels[key]

    # Split camelCase as well as underscores, then preserve common acronyms.
    import re

    # WLAN is an interface prefix, not part of the friendly sensor name.
    # Known fields above retain domain-specific labels; unknown WLAN fields
    # also get readable names rather than exposing the raw prefix.
    display_key = key[4:] if key.lower().startswith("wlan") else key
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display_key)
    words = words.replace("_", " ").replace("-", " ").strip().split()
    acronyms = {"cpu": "CPU", "ip": "IP", "mac": "MAC", "snr": "SNR", "ccq": "CCQ", "wlan": "WLAN", "lan": "LAN", "rx": "RX", "tx": "TX", "ssid": "SSID", "essid": "SSID"}
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _device_type(key):
    """Classify WLAN and LAN telemetry consistently, including unknown keys."""
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


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    sensors = [
        AiRXS2Sensor(coordinator, entry, key, unit, label)
        for key, (label, unit) in BASE_SENSORS.items()
    ]

    # Keep optional telemetry and firmware-specific mca-status values. Place
    # each entity on the most appropriate system, wireless, or Ethernet device.
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
        self._device_type = _device_type(key)
        self._attr_name = label or key
        # Preserve the existing unique IDs so Home Assistant can retain entity
        # registry customizations when entities move to their new child devices.
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
            if key in {"cpu_model", "hostname", "mac", "ethernet_mac", "lan_mac", "wlanMac", "wireless_mac"}
            else None
        )
        if unit:
            self._attr_native_unit_of_measurement = unit

        if key == "uptime_seconds":
            self._attr_icon = "mdi:timer-outline"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {"mem_total_bytes", "mem_free_bytes", "mem_available_bytes"}:
            self._attr_icon = "mdi:memory"
        elif key.startswith("load_"):
            self._attr_icon = "mdi:chart-line"
        elif key in {"ethernet_rx_bytes", "wireless_rx_bytes"}:
            self._attr_icon = "mdi:download-network"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {"ethernet_tx_bytes", "wireless_tx_bytes"}:
            self._attr_icon = "mdi:upload-network"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {"signal", "noise", "chain0_signal", "chain1_signal"}:
            self._attr_icon = "mdi:signal"
        elif key == "snr":
            self._attr_icon = "mdi:signal-distance-variant"
        elif key == "ccq":
            self._attr_icon = "mdi:chart-donut"
        elif key in {"wlanTxRate", "wlanRxRate"}:
            self._attr_icon = "mdi:speedometer"
        elif key == "frequency":
            self._attr_icon = "mdi:access-point"

    @property
    def device_info(self):
        host = self._entry.data["host"]
        name = self._entry.data["name"]

        model = str((self.coordinator.data or {}).get("platform") or "airOS")

        if self._device_type == "wireless":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_wireless")},
                name=f"{name} Wireless",
                manufacturer="Ubiquiti",
                model=f"{model} Wireless Interface",
                via_device=(DOMAIN, host),
            )
        if self._device_type == "ethernet":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_ethernet")},
                name=f"{name} Ethernet",
                manufacturer="Ubiquiti",
                model=f"{model} Ethernet Interface",
                via_device=(DOMAIN, host),
            )

        return DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=name,
            manufacturer="Ubiquiti",
            model=model,
        )

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
