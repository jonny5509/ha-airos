# Ubiquiti AirOS (SSH)

Home Assistant custom integration for legacy Ubiquiti AirOS devices (NanoStation2, PowerStation2, etc).

## Features

- SSH polling of `mca-status`
- Signal, Noise, CCQ, SNR
- TX/RX rate monitoring
- Exposes all additional `mca-status` key/value fields as sensors
- Best-effort uptime, memory, load average, CPU model, IP/MAC, and Ethernet/wireless byte counters from common BusyBox/procfs commands (unsupported probes are skipped)
- Reboot switch
- Config Flow (UI install)
- HACS compatible

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

- Ubiquiti AirOS firmware 4.x
- Uses legacy SSH algorithms required by older firmware

---

## License

MIT License
