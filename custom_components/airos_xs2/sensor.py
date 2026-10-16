"""Dynamically discovered sensors for Ubiquiti airOS telemetry."""
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

BASE_SENSORS = {
    "signal": ("Signal", "dBm"), "noise": ("Noise", "dBm"),
    "ccq": ("CCQ", "%"), "snr": ("SNR", "dB"),
    "wlanTxRate": ("Wireless TX rate", "Mbps"),
    "wlanRxRate": ("Wireless RX rate", "Mbps"),
}

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
    "load_1m": ("System Load (1 min)", None), "load_5m": ("System Load (5 min)", None),
    "load_15m": ("System Load (15 min)", None),
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
    # Per-interface counters use the actual interface name instead of a vague
    # Ethernet label (for example, br0 — RX Bytes or ath0 — Link Status).
    interface_match = re.fullmatch(
        r"([A-Za-z][A-Za-z0-9.:-]*)_(interface|link_up|rx_bytes|rx_packets|rx_errors|rx_dropped|rx_fifo_errors|rx_frame_errors|rx_compressed|multicast|tx_bytes|tx_packets|tx_errors|tx_dropped|tx_fifo_errors|tx_carrier_errors|tx_collisions|tx_compressed|link_quality|signal|noise)",
        key,
        re.IGNORECASE,
    )
    if interface_match:
        interface, metric = interface_match.groups()
        metric_labels = {
            "interface": "Interface", "link_up": "Link Status",
            "rx_bytes": "RX Bytes", "rx_packets": "RX Packets",
            "rx_errors": "RX Errors", "rx_dropped": "RX Dropped Packets",
            "rx_fifo_errors": "RX FIFO Errors", "rx_frame_errors": "RX Frame Errors",
            "rx_compressed": "RX Compressed Packets", "multicast": "Multicast Packets",
            "tx_bytes": "TX Bytes", "tx_packets": "TX Packets",
            "tx_errors": "TX Errors", "tx_dropped": "TX Dropped Packets",
            "tx_fifo_errors": "TX FIFO Errors", "tx_carrier_errors": "TX Carrier Errors",
            "tx_collisions": "TX Collisions", "tx_compressed": "TX Compressed Packets",
            "link_quality": "Link Quality", "signal": "Signal", "noise": "Noise",
        }
        return f"{interface.lower()} — {metric_labels[metric.lower()]}"
    labels = {
        "wlanMac": "Wireless MAC Address", "wireless_mac": "Wireless MAC Address",
        "ethernet_mac": "Ethernet MAC Address", "lan_mac": "Ethernet MAC Address",
        "mac": "Device MAC Address", "ap_mac": "Access Point MAC Address",
        "apMac": "Access Point MAC Address", "apmac": "Access Point MAC Address",
        "device_id": "Device ID", "deviceId": "Device ID",
        "device_name": "Device Name", "deviceName": "Device Name",
        "device_ip": "Device IP Address", "deviceIp": "Device IP Address",
        "deviceIP": "Device IP Address",
        "firmware_version": "Firmware Version", "firmwareVersion": "Firmware Version",
        "config_checksum": "Configuration Checksum", "cfgCrc": "Configuration Checksum",
        "cfg_crc": "Configuration Checksum", "cfgCRC": "Configuration Checksum",
        "freq": "Radio Frequency", "Freq": "Radio Frequency",
        "frequency": "Radio Frequency",
        "ip_address": "IP Address", "lan_ip": "Ethernet IP Address",
        "lanIpAddress": "LAN IP Address", "wlanIpAddress": "Wireless IP Address",
        "uptime": "Device Uptime (raw)", "essid": "SSID",
        "snr": "SNR", "ccq": "CCQ", "wlanTxRate": "Wireless TX Rate",
        "wlanRxRate": "Wireless RX Rate", "wlanConnections": "Wireless Connections",
        "connected_station_count": "Connected Wireless Stations",
        "txpower": "Transmit Power", "tx_power": "Transmit Power",
    }
    if key in labels:
        return labels[key]
    display_key = key[4:] if key.lower().startswith("wlan") else key
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display_key)
    words = words.replace("_", " ").replace("-", " ").strip().split()
    acronyms = {"cpu": "CPU", "ip": "IP", "mac": "MAC", "snr": "SNR",
                "ccq": "CCQ", "rx": "RX", "tx": "TX", "ssid": "SSID"}
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _metadata(key):
    """Infer safe units for per-interface and per-station dynamically found keys."""
    if key in OPTIONAL_SENSORS:
        return OPTIONAL_SENSORS[key]
    if key.endswith("_bytes") or key.endswith("_bytes_total"):
        return (_friendly_name(key), "B")
    if key.endswith(("_packets", "_dropped", "_multicast", "_compressed")):
        return (_friendly_name(key), "packets")
    if key.endswith(("_errors", "_fifo_errors", "_frame_errors", "_carrier_errors")) or "_err_" in key:
        return (_friendly_name(key), "errors")
    if key.endswith("_collisions"):
        return (_friendly_name(key), "collisions")
    if key.endswith("_signal"):
        return (_friendly_name(key), "dBm")
    if key.endswith("_ccq"):
        return (_friendly_name(key), "%")
    if key.endswith(("_rate_mbps", "_speed_mbps")):
        return (_friendly_name(key), "Mbps")
    if key.endswith("_uptime_seconds") or key == "uptime_seconds":
        return (_friendly_name(key), "s")
    if key.endswith("_link_up"):
        return (_friendly_name(key), None)
    return (_friendly_name(key), None)


def _device_type(key):
    normalized = key.lower().replace("-", "_")
    if (
        key in WIRELESS_KEYS or "wlan" in normalized or "wireless" in normalized
        or normalized.startswith("ath") or key.startswith("station_")
    ):
        return "wireless"
    if (
        key in ETHERNET_KEYS or "ethernet" in normalized
        or normalized.startswith("lan") or normalized.startswith("eth")
        or normalized.startswith("br")
    ):
        return "ethernet"
    return "system"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up baseline sensors and dynamically register newly observed telemetry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_keys = set()

    def add_new_sensors():
        data = coordinator.data or {}
        # Hide internal CPU counters; expose the derived utilization percentage.
        candidates = set(BASE_SENSORS) | {
            key for key, value in data.items()
            if value is not None and value != "" and key not in {"cpu_total_ticks", "cpu_idle_ticks"}
        }
        # The raw mca-status field and its normalized alias often contain the
        # same value. Prefer the normalized entity rather than exposing both.
        aliases = {
            "uptime": "uptime_seconds",
            "lanIpAddress": "lan_ip",
            "lanRxBytes": "ethernet_rx_bytes",
            "lanTxBytes": "ethernet_tx_bytes",
            "wlanRxBytes": "wireless_rx_bytes",
            "wlanTxBytes": "wireless_tx_bytes",
            "deviceIp": "ip_address",
            "device_ip": "ip_address",
            "wlanIpAddress": "wlan_ip",
            "wlanFrequency": "frequency",
            "wlanESSID": "essid",
            "wlanESSID": "essid",
            "wlanSignal": "signal",
            "wlanNoise": "noise",
            "wlanCCQ": "ccq",
            "wlanSNR": "snr",
            "apMac": "ap_mac", "apmac": "ap_mac",
            "deviceId": "device_id", "deviceName": "device_name",
            "deviceIp": "ip_address", "deviceIP": "ip_address",
            "firmwareVersion": "firmware_version",
            "cfgCrc": "config_checksum", "cfgCRC": "config_checksum",
            "Freq": "frequency", "freq": "frequency",
        }
        # Canonical keys always win when both forms are present. The raw
        # firmware value may differ only because the normalized value is
        # parsed (for example, "5745 MHz" becomes the integer 5745).
        redundant = {
            source for source, target in aliases.items()
            if target in data and source in data
        }
        new_keys = candidates - known_keys - redundant
        if not new_keys:
            return
        batch = []
        for key in sorted(new_keys):
            label, unit = _metadata(key)
            entity = AiRXS2Sensor(coordinator, entry, key, unit, label)
            batch.append(entity)
            known_keys.add(key)
        async_add_entities(batch)

    add_new_sensors()
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
            "cpu_model", "hostname", "kernel_version", "mac", "ap_mac",
            "device_id", "device_name", "firmware_version", "config_checksum",
            "ethernet_mac", "lan_mac", "wlanMac", "wireless_mac", "platform",
        }:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "uptime_seconds":
            self._attr_icon = "mdi:timer-outline"
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key.endswith("_bytes") or key in {
            "ethernet_rx_bytes", "wireless_rx_bytes", "ethernet_tx_bytes", "wireless_tx_bytes",
        }:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_icon = "mdi:download-network" if "_rx_" in key else "mdi:upload-network"
        elif key.endswith(("_packets", "_errors", "_dropped", "_collisions")):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key in {
            "mem_total_bytes", "mem_free_bytes", "mem_available_bytes", "mem_used_bytes",
            "mem_buffers_bytes", "mem_cached_bytes", "swap_total_bytes", "swap_free_bytes",
            "swap_used_bytes",
        }:
            self._attr_icon = "mdi:memory"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key.startswith("load_") or key in {"cpu_utilization", "signal", "noise", "snr", "ccq", "frequency"}:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key.endswith("_signal"):
            self._attr_icon = "mdi:signal"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key.endswith("_ccq"):
            self._attr_icon = "mdi:chart-donut"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self):
        return self.coordinator.last_update_success and (self.coordinator.data or {}).get(self.key) is not None

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        if self.key.endswith("_link_up") or self.key in {"lanPlugged"}:
            if value is True or str(value).lower() in {"1", "true", "up", "yes"}:
                return "Up" if self.key.endswith("_link_up") else "Connected"
            if value is False or str(value).lower() in {"0", "false", "down", "no"}:
                return "Down" if self.key.endswith("_link_up") else "Disconnected"
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
