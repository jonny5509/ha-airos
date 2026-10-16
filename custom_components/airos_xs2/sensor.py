"""Dynamically discovered sensors for Ubiquiti airOS telemetry."""
import re

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

# Known fields get meaningful labels and units. Unknown mca-status fields are
# still exposed automatically, so this table is intentionally extensible.
OPTIONAL_SENSORS = {
    "essid": ("SSID", None), "frequency": ("Frequency", "MHz"),
    "wlanMac": ("Wireless MAC", None), "wireless_mac": ("Wireless MAC", None),
    "mac": ("MAC address", None), "mode": ("Wireless mode", None),
    "channel_width": ("Channel width", "MHz"), "txpower": ("Transmit power", "dBm"),
    "tx_power": ("Transmit power", "dBm"), "chain0_signal": ("Chain 0 signal", "dBm"),
    "chain1_signal": ("Chain 1 signal", "dBm"), "lan_ip": ("Ethernet IP address", None),
    "lan_mac": ("Ethernet MAC", None), "wlan_ip": ("Wireless IP address", None),
    "rx_rate": ("Receive rate", "Mbps"), "tx_rate": ("Transmit rate", "Mbps"),
    "hostname": ("Hostname", None), "uptime_seconds": ("Uptime", "s"),
    "ip_address": ("IP address", None), "cpu_model": ("CPU model", None),
    "kernel_version": ("Kernel version", None),
    "load_1m": ("CPU load (1 min)", None), "load_5m": ("CPU load (5 min)", None),
    "load_15m": ("CPU load (15 min)", None),
    "mem_total_bytes": ("Memory total", "B"), "mem_free_bytes": ("Memory free", "B"),
    "mem_available_bytes": ("Memory available", "B"), "mem_used_bytes": ("Memory used", "B"),
    "mem_buffers_bytes": ("Memory buffers", "B"), "mem_cached_bytes": ("Memory cached", "B"),
    "swap_total_bytes": ("Swap total", "B"), "swap_free_bytes": ("Swap free", "B"),
    "swap_used_bytes": ("Swap used", "B"),
    "ethernet_rx_bytes": ("Ethernet received", "B"), "ethernet_tx_bytes": ("Ethernet sent", "B"),
    "wireless_rx_bytes": ("Wireless received", "B"), "wireless_tx_bytes": ("Wireless sent", "B"),
    "ethernet_rx_packets": ("Ethernet RX packets", "packets"),
    "ethernet_tx_packets": ("Ethernet TX packets", "packets"),
    "ethernet_rx_errors": ("Ethernet RX errors", "errors"),
    "ethernet_tx_errors": ("Ethernet TX errors", "errors"),
    "ethernet_rx_dropped": ("Ethernet RX dropped", "packets"),
    "ethernet_tx_dropped": ("Ethernet TX dropped", "packets"),
    "wireless_rx_packets": ("Wireless RX packets", "packets"),
    "wireless_tx_packets": ("Wireless TX packets", "packets"),
    "wireless_rx_errors": ("Wireless RX errors", "errors"),
    "wireless_tx_errors": ("Wireless TX errors", "errors"),
    "wireless_rx_dropped": ("Wireless RX dropped", "packets"),
    "wireless_tx_dropped": ("Wireless TX dropped", "packets"),
    "ethernet_mac": ("Ethernet MAC", None), "wlanConnections": ("Wireless connections", "devices"),
    "connected_station_count": ("Connected wireless stations", "devices"),
    "station_signal_min": ("Weakest station signal", "dBm"),
    "station_signal_max": ("Strongest station signal", "dBm"),
    "station_signal_average": ("Average station signal", "dBm"),
    "station_ccq_average": ("Average station CCQ", "%"),
    "stations_rx_bytes": ("Stations received", "B"), "stations_tx_bytes": ("Stations sent", "B"),
    "stations_rx_pps": ("Stations RX packet rate", "packet/s"),
    "stations_tx_pps": ("Stations TX packet rate", "packet/s"),
    "stations_tx_rate_mbps": ("Stations TX rate total", "Mbps"),
    "stations_rx_rate_mbps": ("Stations RX rate total", "Mbps"),
    "wlanTxLatency": ("Wireless TX latency", "ms"),
    "wlanPollingQuality": ("Wireless polling quality", "%"),
    "wlanPollingCapacity": ("Wireless polling capacity", "%"),
    "ackTimeout": ("ACK timeout", None), "distance": ("Wireless link distance", "m"),
    "lanSpeed": ("Ethernet link speed", None), "lanPlugged": ("Ethernet link connected", None),
    "wlanRxPackets": ("Wireless packets received", "packets"),
    "wlanTxPackets": ("Wireless packets sent", "packets"),
    "wlanRxErrors": ("Wireless receive errors", "errors"),
    "wlanTxErrors": ("Wireless transmit errors", "errors"),
    "wlanRxErrNwid": ("Wireless NWID errors", "errors"),
    "wlanRxErrCrypt": ("Wireless crypto errors", "errors"),
    "wlanRxErrFrag": ("Wireless fragment errors", "errors"),
    "wlanRxErrRetries": ("Wireless retry errors", "errors"),
    "wlanRxErrBmiss": ("Wireless beacon-miss errors", "errors"),
    "wlanRxErrOther": ("Other wireless receive errors", "errors"),
    "processes_running": ("Running processes", "processes"),
    "processes_total": ("Total processes", "processes"),
    "cpu_utilization": ("CPU utilization", "%"),
    "wireless_link_quality": ("Wireless link quality", None),
    "wireless_link_quality_max": ("Wireless link quality maximum", None),
    "wireless_rate_mbps": ("Wireless rate", "Mbps"),
    "ethernet_link_speed_mbps": ("Ethernet link speed", "Mbps"),
}

WIRELESS_KEYS = {
    *BASE_SENSORS, "essid", "frequency", "wlanMac", "mode",
    "wireless_rx_bytes", "wireless_tx_bytes", "channel_width", "txpower", "tx_power",
    "chain0_signal", "chain1_signal", "rx_rate", "tx_rate", "wlan_ip",
    "wlanConnections", "connected_station_count", "station_signal_min",
    "station_signal_max", "station_signal_average", "station_ccq_average",
    "stations_rx_bytes", "stations_tx_bytes", "stations_rx_pps", "stations_tx_pps",
    "stations_tx_rate_mbps", "stations_rx_rate_mbps", "wlanTxLatency",
    "wlanPollingQuality", "wlanPollingCapacity", "ackTimeout", "distance",
    "wlanRxPackets", "wlanTxPackets", "wlanRxErrors", "wlanTxErrors",
    "wlanRxErrNwid", "wlanRxErrCrypt", "wlanRxErrFrag", "wlanRxErrRetries",
    "wlanRxErrBmiss", "wlanRxErrOther", "wireless_link_quality",
    "wireless_link_quality_max", "wireless_rate_mbps",
}
ETHERNET_KEYS = {
    "ethernet_rx_bytes", "ethernet_tx_bytes", "ethernet_mac", "lan_ip", "lan_mac",
    "lanSpeed", "lanPlugged", "ethernet_rx_packets", "ethernet_tx_packets",
    "ethernet_rx_errors", "ethernet_tx_errors", "ethernet_rx_dropped",
    "ethernet_tx_dropped", "ethernet_link_speed_mbps",
}


def _friendly_name(key):
    """Make firmware-specific keys readable without losing their identity."""
    labels = {
        "wlanMac": "Wireless MAC", "wireless_mac": "Wireless MAC",
        "ethernet_mac": "Ethernet MAC", "lan_mac": "Ethernet MAC",
        "mac": "MAC address", "essid": "SSID", "snr": "SNR", "ccq": "CCQ",
        "ip_address": "IP address", "lan_ip": "Ethernet IP address",
        "wlan_ip": "Wireless IP address", "wlanTxRate": "Wireless TX rate",
        "wlanRxRate": "Wireless RX rate", "wlanConnections": "Wireless connections",
        "connected_station_count": "Connected wireless stations",
        "txpower": "Transmit power", "tx_power": "Transmit power",
    }
    if key in labels:
        return labels[key]
    display_key = key[4:] if key.lower().startswith("wlan") else key
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display_key)
    words = words.replace("_", " ").replace("-", " ").strip().split()
    acronyms = {"cpu": "CPU", "ip": "IP", "mac": "MAC", "snr": "SNR",
                "ccq": "CCQ", "rx": "RX", "tx": "TX", "ssid": "SSID"}
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _device_type(key):
    normalized = key.lower().replace("-", "_")
    if key in WIRELESS_KEYS or "wlan" in normalized or "wireless" in normalized or key.startswith("station_"):
        return "wireless"
    if key in ETHERNET_KEYS or "ethernet" in normalized or normalized.startswith("lan") or normalized.startswith("eth"):
        return "ethernet"
    return "system"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_keys = set()
    entities = {}

    def add_new_sensors():
        """Create an entity the first time a telemetry key is observed."""
        data = coordinator.data or {}
        candidates = set(BASE_SENSORS) | {
            key for key, value in data.items() if value is not None and value != ""
        }
        new_keys = candidates - known_keys
        if not new_keys:
            return
        batch = []
        for key in sorted(new_keys):
            label, unit = OPTIONAL_SENSORS.get(key, (None, None))
            if key in BASE_SENSORS:
                label, unit = BASE_SENSORS[key]
            entity = AiRXS2Sensor(coordinator, entry, key, unit, label or _friendly_name(key))
            entities[key] = entity
            batch.append(entity)
            known_keys.add(key)
        async_add_entities(batch)

    add_new_sensors()
    # A key absent at first boot can appear later (e.g. a station connects).
    # Coordinator listeners run after each successful data refresh.
    coordinator.async_add_listener(add_new_sensors)


class AiRXS2Sensor(SensorEntity):
    """A single normalized or firmware-specific telemetry value."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, unit=None, label=None):
        self.coordinator = coordinator
        self.key = key
        self._entry = entry
        self._device_type = _device_type(key)
        self._attr_name = label or _friendly_name(key)
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        if unit:
            self._attr_native_unit_of_measurement = unit
        if key in {
            "cpu_model", "hostname", "kernel_version", "mac", "ethernet_mac",
            "lan_mac", "wlanMac", "wireless_mac", "platform",
        }:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "uptime_seconds":
            self._attr_icon = "mdi:timer-outline"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {
            "mem_total_bytes", "mem_free_bytes", "mem_available_bytes", "mem_used_bytes",
            "mem_buffers_bytes", "mem_cached_bytes", "swap_total_bytes", "swap_free_bytes",
            "swap_used_bytes",
        }:
            self._attr_icon = "mdi:memory"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key.startswith("load_"):
            self._attr_icon = "mdi:chart-line"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key in {
            "ethernet_rx_bytes", "wireless_rx_bytes", "ethernet_tx_bytes",
            "wireless_tx_bytes",
        }:
            self._attr_icon = "mdi:download-network" if "_rx_" in key else "mdi:upload-network"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {"signal", "noise", "chain0_signal", "chain1_signal"} or key.endswith("_signal"):
            self._attr_icon = "mdi:signal"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key == "snr":
            self._attr_icon = "mdi:signal-distance-variant"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key == "ccq" or key.endswith("_ccq"):
            self._attr_icon = "mdi:chart-donut"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "rate" in key.lower() and ("wlan" in key.lower() or "station" in key.lower()):
            self._attr_icon = "mdi:speedometer"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self):
        return self.coordinator.last_update_success and (self.coordinator.data or {}).get(self.key) is not None

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        # Sensor entities should not publish Python booleans as numeric values.
        return value

    @property
    def device_info(self):
        host = self._entry.data["host"]
        name = self._entry.data["name"]
        model = str((self.coordinator.data or {}).get("platform") or "airOS")
        if self._device_type == "wireless":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_wireless")}, name=f"{name} Wireless",
                manufacturer="Ubiquiti", model=f"{model} Wireless Interface",
                via_device=(DOMAIN, host),
            )
        if self._device_type == "ethernet":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_ethernet")}, name=f"{name} Ethernet",
                manufacturer="Ubiquiti", model=f"{model} Ethernet Interface",
                via_device=(DOMAIN, host),
            )
        return DeviceInfo(
            identifiers={(DOMAIN, host)}, name=name,
            manufacturer="Ubiquiti", model=model,
        )
