"""Tests for readable, stable airOS sensor metadata and grouping."""

from custom_components.airos_xs2 import _device_type_for_key
from custom_components.airos_xs2.sensor import _device_type, _friendly_name, _metadata


def test_normalized_identity_fields_have_readable_names():
    assert _friendly_name("ap_mac") == "Access Point MAC Address"
    assert _friendly_name("device_id") == "Device ID"
    assert _friendly_name("device_name") == "Device Name"
    assert _friendly_name("firmware_version") == "Firmware Version"
    assert _friendly_name("config_checksum") == "Configuration Checksum"
    assert _friendly_name("frequency") == "Radio Frequency"


def test_legacy_aliases_have_consistent_readable_names():
    assert _friendly_name("deviceIP") == "Device IP Address"
    assert _friendly_name("Freq") == "Radio Frequency"
    assert _friendly_name("cfgCRC") == "Configuration Checksum"


def test_interface_sensor_names_keep_interface_identity():
    assert _friendly_name("br0_rx_bytes") == "br0 — RX Bytes"
    assert _friendly_name("ath0_link_up") == "ath0 — Link Status"
    assert _friendly_name("eth0_tx_collisions") == "eth0 — TX Collisions"


def test_dynamic_counter_metadata_has_units():
    assert _metadata("br0_rx_bytes")[1] == "B"
    assert _metadata("ath0_rx_packets")[1] == "packets"
    assert _metadata("eth0_tx_errors")[1] == "errors"


def test_registry_migration_and_entities_use_same_device_groups():
    keys = {
        "frequency": "wireless",
        "chain0_signal": "wireless",
        "rx_rate": "wireless",
        "wlan_ip": "wireless",
        "station_signal_average": "wireless",
        "ath0_rx_bytes": "wireless",
        "ethernet_rx_bytes": "ethernet",
        "lan_ip": "ethernet",
        "br0_rx_bytes": "ethernet",
        "eth0_tx_collisions": "ethernet",
        "cpu_utilization": "system",
        "uptime_seconds": "system",
    }
    for key, expected in keys.items():
        assert _device_type_for_key(key) == expected
        assert _device_type(key) == expected
