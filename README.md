# Ubiquiti AirOS (SSH)

Home Assistant custom integration for legacy Ubiquiti AirOS devices, including NanoStation2, PowerStation2, and compatible hardware.

## Description

Connects Home Assistant to AirOS devices over SSH and exposes wireless link quality, traffic counters, device information, and other values reported by `mca-status` or supported system probes.

## Requirements

- A compatible Ubiquiti AirOS device (tested against legacy AirOS 4.x).
- SSH access enabled on the device.
- A username and password with permission to run the required status commands.
- Network connectivity from Home Assistant to the device.
- HACS (optional, for HACS installation).

The integration first attempts standard SSH algorithms and retries with legacy algorithms only when negotiation fails. For compatibility with very old AirOS firmware, SSH host-key verification is disabled. This makes the connection vulnerable to man-in-the-middle attacks; use it only on a trusted, isolated management network and never expose device SSH to the internet.

## Installation

### Via HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/jonny5509/ha-airos`.
3. Choose **Integration** as the category.
4. If asked to select a branch, choose `main` (do not use a short commit hash as a branch name).
5. Install the integration and restart Home Assistant.

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/airos_xs2` into your Home Assistant `/config/custom_components/` directory.
3. Restart Home Assistant.

## Setup

1. In Home Assistant, go to **Settings → Devices & services**.
2. Select **Add Integration** and search for **Ubiquiti AirOS (SSH)**.
3. Enter the device name, hostname or IP address, SSH username, and password.
4. Complete setup and allow the integration to begin polling the device.

The integration supports a device configured through the UI; use a separate integration entry for each AirOS device you want to add.

## Entities

The exact entities available depend on the AirOS firmware and which optional system probes the device supports.

### Wireless

| Entity | Description |
| --- | --- |
| Wireless Signal | Received wireless signal level (dBm) |
| Wireless Noise | Wireless noise level (dBm) |
| Wireless CCQ | Client Connection Quality (%) |
| Wireless SNR | Signal-to-noise ratio (dB) |
| Wireless Transmit Rate | Wireless transmit rate (Mbit/s) |
| Wireless Receive Rate | Wireless receive rate (Mbit/s) |
| Wireless Network Name (SSID) | Wireless network name, when reported |
| Wireless Frequency | Wireless frequency, when reported |
| Wireless interface details | Additional wireless status and metadata when available |

### Device and Ethernet

| Entity | Description |
| --- | --- |
| Uptime | Device uptime, when supported |
| CPU Usage | CPU usage, when supported |
| RAM Usage | Memory usage; available memory counters are provided as attributes when supported |
| Ethernet Bytes Received / Sent | Ethernet byte counters, when supported |
| Wireless Bytes Received / Sent | Wireless byte counters, when supported |
| Device information | Hostname, IP/MAC addresses, hardware/platform details, firmware version, and other reported fields when available |
| Firmware Upgrade | Best-effort firmware upgrade information, when the device supports the probe |
| Reboot | Switch to request a device reboot |

The integration also exposes additional `mca-status` key/value fields as sensors when values are available. Some optional probes are skipped when the device's firmware or BusyBox environment does not support them.

## Troubleshooting

### HACS download returns 404

If HACS attempts to download a URL like `.../archive/refs/heads/5544ed9.zip`, it may be treating a short commit hash as a branch name. Remove the incorrect custom-repository entry and add the repository again, selecting `main` as the branch.

### SSH connection or authentication errors

- Confirm SSH is enabled and that Home Assistant can reach the device.
- Check the host, username, and password in the integration configuration.
- Review Home Assistant logs for connection or authentication details.
- Older firmware may need legacy SSH algorithm compatibility; avoid exposing SSH to untrusted networks.

### Missing sensors or device details

Not all AirOS versions provide the same `mca-status` keys or support the optional BusyBox/procfs probes. Unsupported probes are skipped, so some entities may be absent or remain unavailable.

### Debug logging

To enable debug logging temporarily, add the following to your Home Assistant configuration and restart Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.airos_xs2: debug
```

Remember to remove or reduce debug logging after troubleshooting.

## Screenshots

![Overview](docs/screenshots/Screenshot1.png)
![Coop Radio](docs/screenshots/Screenshot2.png)
![Shed Radio](docs/screenshots/Screenshot3.png)

## Compatibility

- Intended for legacy Ubiquiti AirOS devices, including AirOS 4.x; exact sensors depend on firmware and hardware.
- Prefers standard SSH negotiation, with a legacy-algorithm fallback for older devices.
- Parses both legacy and newer common `ifconfig` formats and recognizes common legacy wireless/wired interface names.
- Optional system probes are best-effort; unsupported commands do not invalidate otherwise successful `mca-status` polling.
- HACS compatible.

Compatibility improvements are based on known AirOS output patterns and have not been validated against every hardware model or firmware release. Please include a redacted diagnostics export when reporting model-specific issues.

## License

MIT License.
