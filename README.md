# airOS XS2 (SSH)

Home Assistant custom integration for legacy Ubiquiti airOS XS2 devices (NanoStation2, PowerStation2, etc).

## Features

- SSH polling of `mca-status`
- Signal, Noise, CCQ, SNR
- TX/RX rate monitoring
- Exposes all additional `mca-status` key/value fields as sensors
- Best-effort uptime, CPU utilization/load, memory and swap, kernel/CPU identity, IP/MAC, wireless-tools telemetry, and interface byte/packet/error/drop counters from BusyBox/procfs (unsupported probes are skipped)
- Dynamically discovers sensor entities when new firmware fields or wireless clients appear after startup
- Aggregated wireless-client signal, CCQ, rate and traffic metrics when `wstalist` exposes them
- Exposes all additional `mca-status` key/value fields as sensors
- Reboot switch
- Config Flow (UI install)
- HACS compatible

## Home Assistant device layout

The integration organizes entities into a parent device and interface child devices, following the system/device/interface layout used by [ha-edgeos](https://github.com/jonny550993/ha-edgeos):

- **System device** — general system telemetry, uptime, memory, CPU/load, host/network identity, and the reboot switch.
- **Wireless child device** — signal, noise, CCQ, SNR, SSID, frequency, wireless rates, and wireless traffic counters.
- **Ethernet child device** — Ethernet traffic counters and Ethernet MAC when the device exposes them.

The wireless and Ethernet devices are linked to the system device in Home Assistant. Unsupported telemetry remains omitted. Extra `mca-status` fields are exposed dynamically, and newly appearing fields/station metrics are registered after startup. Additional interface statistics are best-effort and depend on the firmware's BusyBox tools. Existing sensor and switch unique IDs are preserved to help retain entity registry customizations during the layout change.

---

## Installation (Manual)

1. Download this repository.
2. Copy `custom_components/airos_xs2` into your Home Assistant `/config/custom_components/` directory.
3. Restart Home Assistant.
4. Add integration via **Settings → Devices & Services → Add Integration**.

---

## Installation (HACS)

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/jonny5509/ha-airos`.
3. Select **Integration** as the category.
4. If HACS asks for a branch, select `main`. Do not enter a short commit hash (for example, `5544ed9`) as a branch name.
5. Install the integration and restart Home Assistant.

### Troubleshooting HACS download errors

If the Home Assistant log says HACS is trying to download a URL like
`.../archive/refs/heads/5544ed9.zip` and receives a 404, HACS is treating
`5544ed9` as a branch name, but that branch may not exist. In HACS, remove
the incorrect custom-repository entry and add this repository again, making
sure the selected branch is `main`. Then retry the download.

This HACS configuration issue is separate from SSH connection or `mca-status`
errors reported after the integration loads.

---

## Screenshots

![Overview](docs/screenshots/Screenshot1.png)
![Coop Radio](docs/screenshots/Screenshot2.png)
![Shed Radio](docs/screenshots/Screenshot3.png)

---

## Compatibility

- airOS XS2 firmware 4.x
- Uses legacy SSH algorithms required by older firmware

---

## License

MIT License
