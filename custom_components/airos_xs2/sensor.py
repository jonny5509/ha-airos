from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        AiRXS2Sensor(coordinator, entry, "signal", "dBm"),
        AiRXS2Sensor(coordinator, entry, "noise", "dBm"),
        AiRXS2Sensor(coordinator, entry, "ccq", "%"),
        AiRXS2Sensor(coordinator, entry, "snr", "dB"),
        AiRXS2Sensor(coordinator, entry, "wlanTxRate", "Mbps"),
        AiRXS2Sensor(coordinator, entry, "wlanRxRate", "Mbps"),
    ]

    # airOS firmware variants expose different mca-status keys. Add these
    # informational entities only when the connected device actually reports
    # the corresponding value, rather than creating permanently empty sensors.
    optional_sensors = {
        "essid": ("SSID", None),
        "frequency": ("Frequency", "MHz"),
        "wlanMac": ("Wireless MAC", None),
        "mac": ("MAC address", None),
        "mode": ("Wireless mode", None),
        "hostname": ("Hostname", None),
        "uptime": ("Uptime", None),
    }
    for key, (label, unit) in optional_sensors.items():
        if coordinator.data and coordinator.data.get(key) not in (None, ""):
            sensors.append(AiRXS2Sensor(coordinator, entry, key, unit, label))

    async_add_entities(sensors)

class AiRXS2Sensor(SensorEntity):
    def __init__(self, coordinator, entry, key, unit, label=None):
        self.coordinator = coordinator
        self.key = key
        self._entry = entry
        self._attr_name = f"{entry.data['name']} {label or key}"
        self._attr_unique_id = f"{entry.data['host']}_{key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data["host"])},
            name=self._entry.data["name"],
            manufacturer="Ubiquiti",
            model="airOS XS2",
        )

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)
