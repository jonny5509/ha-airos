from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
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
    "ethernet_mac": ("Ethernet MAC", None),
}


WIRELESS_KEYS = {
    *BASE_SENSORS,
    "essid",
    "frequency",
    "wlanMac",
    "mode",
    "wireless_rx_bytes",
    "wireless_tx_bytes",
}
ETHERNET_KEYS = {
    "ethernet_rx_bytes",
    "ethernet_tx_bytes",
    "ethernet_mac",
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
    return key.replace("_", " ").replace("-", " ").strip().title()


def _device_type(key):
    if key in WIRELESS_KEYS:
        return "wireless"
    if key in ETHERNET_KEYS:
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
            if key in {"cpu_model", "hostname", "mac", "ethernet_mac", "wlanMac"}
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
        elif key in {"signal", "noise"}:
            self._attr_icon = "mdi:signal"
        elif key == "snr":
            self._attr_icon = "mdi:signal-distance-variant"
        elif key == "ccq":
            self._attr_icon = "mdi:chart-donut"
        elif key in {"wlanTxRate", "wlanRxRate"}:
            self._attr_icon = "mdi:speedometer"
        elif key == "frequency":
            self._attr_icon = "mdi:access-point"
        elif key == "uptime_seconds":
            self._attr_icon = "mdi:timer-outline"

    @property
    def device_info(self):
        host = self._entry.data["host"]
        name = self._entry.data["name"]

        if self._device_type == "wireless":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_wireless")},
                name=f"{name} Wireless",
                manufacturer="Ubiquiti",
                model="airOS XS2 Wireless Interface",
                via_device=(DOMAIN, host),
            )
        if self._device_type == "ethernet":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{host}_ethernet")},
                name=f"{name} Ethernet",
                manufacturer="Ubiquiti",
                model="airOS XS2 Ethernet Interface",
                via_device=(DOMAIN, host),
            )

        return DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=name,
            manufacturer="Ubiquiti",
            model="airOS XS2",
        )

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
