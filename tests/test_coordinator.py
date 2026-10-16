"""Unit tests for airOS telemetry parsing."""
from custom_components.airos_xs2.coordinator import AiRXS2Coordinator


def coordinator_for_parsing():
    # Parser methods don't need Home Assistant initialization.
    return object.__new__(AiRXS2Coordinator)


def test_parse_mca_status_aliases_and_ccq():
    coordinator = coordinator_for_parsing()
    data = coordinator._parse_output(
        "wlanSignal=-62\nwlanNoise=-96\nwlanCCQ=975\nwlanFrequency=2437\n"
    )
    assert data["signal"] == -62
    assert data["noise"] == -96
    assert data["snr"] == 34
    assert data["ccq"] == 97.5
    assert data["frequency"] == 2437


def test_parse_meminfo_and_derive_used_memory():
    coordinator = coordinator_for_parsing()
    data = {}
    coordinator._parse_probe(
        "meminfo",
        "MemTotal:       32768 kB\nMemFree:         8192 kB\n"
        "MemAvailable:   12288 kB\nBuffers:          512 kB\n"
        "Cached:          1024 kB\nSwapTotal:       4096 kB\nSwapFree:        2048 kB\n",
        data,
    )
    assert data["mem_total_bytes"] == 32768 * 1024
    assert data["mem_available_bytes"] == 12288 * 1024
    assert data["mem_used_bytes"] == (32768 - 12288) * 1024
    assert data["mem_buffers_bytes"] == 512 * 1024
    assert data["mem_cached_bytes"] == 1024 * 1024
    assert data["swap_used_bytes"] == 2048 * 1024


def test_parse_netdev_all_standard_counters():
    coordinator = coordinator_for_parsing()
    data = {}
    coordinator._parse_probe(
        "netdev",
        "Inter-| Receive | Transmit\n"
        " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
        " eth0: 1000 20 3 4 5 6 7 8 2000 30 9 10 11 12 13 14\n",
        data,
    )
    assert data["ethernet_rx_bytes"] == 1000
    assert data["ethernet_rx_packets"] == 20
    assert data["ethernet_rx_errors"] == 3
    assert data["ethernet_rx_dropped"] == 4
    assert data["ethernet_tx_bytes"] == 2000
    assert data["ethernet_tx_packets"] == 30
    assert data["ethernet_tx_errors"] == 9
    assert data["ethernet_tx_dropped"] == 10
    assert data["eth0_tx_collisions"] == 12


def test_parse_load_average_process_counts():
    coordinator = coordinator_for_parsing()
    data = {}
    coordinator._parse_probe("loadavg", "0.10 0.20 0.30 2/55 1234\n", data)
    assert data["load_1m"] == 0.1
    assert data["load_5m"] == 0.2
    assert data["load_15m"] == 0.3
    assert data["processes_running"] == 2
    assert data["processes_total"] == 55



def test_parse_legacy_nanostation5_identity_aliases():
    coordinator = coordinator_for_parsing()
    data = coordinator._parse_output(
        "apMac=D2:21:F9:96:52:D7\\n"
        "deviceId=00:15:6D:BD:D9:B4\\n"
        "deviceName=UBNT\\n"
        "deviceIp=192.168.4.214\\n"
        "firmwareVersion=XS5.ar2313.v4.0.1.4978.111219.2126\\n"
        "Freq=5745\\n"
        "cfgCrc=40ca6cd2\\n"
    )
    assert data["ap_mac"] == "D2:21:F9:96:52:D7"
    assert data["device_id"] == "00:15:6D:BD:D9:B4"
    assert data["device_name"] == "UBNT"
    assert data["ip_address"] == "192.168.4.214"
    assert data["firmware_version"] == "XS5.ar2313.v4.0.1.4978.111219.2126"
    assert data["frequency"] == 5745
    assert data["config_checksum"] == "40ca6cd2"
