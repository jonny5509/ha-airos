import asyncssh
import logging
import re
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _to_text(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return val.decode(errors="ignore")
    return str(val)


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AiRXS2Coordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host, username, password, name):
        self.host = host
        self.username = username
        self.password = password
        self.device_name = name

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"airos_xs2_{name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _run_command(self, conn, command):
        """Run a read-only command without relying on completed-result attributes."""
        async with conn.create_process(command) as proc:
            stdout = await proc.stdout.read()
            stderr = await proc.stderr.read()
            await proc.wait()
        output = _to_text(stdout)
        return output if output.strip() else _to_text(stderr)

    async def _async_update_data(self):
        try:
            async with asyncssh.connect(
                self.host,
                username=self.username,
                password=self.password,
                known_hosts=None,
                kex_algs=["diffie-hellman-group1-sha1"],
                encryption_algs=["aes128-cbc"],
                server_host_key_algs=["ssh-rsa"],
            ) as conn:
                output = await self._run_command(conn, "mca-status")
                if "=" not in output:
                    raise UpdateFailed(
                        f"mca-status returned no key=value output: {output[:200]}"
                    )
                data = self._parse_output(output)

                # Legacy airOS builds differ significantly. Probe common BusyBox
                # procfs/network commands independently; missing commands/files are
                # ignored so one unsupported probe cannot break the core sensors.
                probes = (
                    ("uptime", "cat /proc/uptime"),
                    ("meminfo", "cat /proc/meminfo"),
                    ("loadavg", "cat /proc/loadavg"),
                    ("cpuinfo", "cat /proc/cpuinfo"),
                    ("version", "cat /etc/version"),
                    ("board", "cat /etc/board.info"),
                    ("ifconfig", "ifconfig"),
                    ("netdev", "cat /proc/net/dev"),
                )
                for name, command in probes:
                    try:
                        result = await self._run_command(conn, command)
                        self._parse_probe(name, result, data)
                    except Exception as err:
                        _LOGGER.debug("airOS probe %s unavailable: %s", name, err)

                return data

        except UpdateFailed:
            raise
        except Exception as e:
            raise UpdateFailed(f"SSH error: {e}") from e

    def _parse_output(self, output: str):
        data = {}
        for line in output.splitlines():
            if "=" in line:
                key, value = line.strip().split("=", 1)
                data[key] = value.strip()

        # Identify hardware from metadata commonly exposed by different airOS builds.
        self._identify_device(data, output)

        # Expose only one canonical uptime sensor, populated by the procfs probe.
        # airOS firmware may also report uptime-like keys in mca-status; discard
        # those aliases so they cannot create duplicate entities.
        for key in list(data):
            if key.lower() in {"uptime", "uptime_seconds", "systemuptime"}:
                data.pop(key, None)

        # Missing or malformed readings must stay unavailable, not look like real zeroes.
        for key in ("signal", "noise", "wlanTxRate", "wlanRxRate", "frequency"):
            value = _number(data.get(key))
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value

        raw_ccq = _number(data.get("ccq"))
        if raw_ccq is None:
            data.pop("ccq", None)
        else:
            # AirOS mca-status reports CCQ in tenths of a percent.
            data["ccq"] = raw_ccq / 10

        if "signal" in data and "noise" in data:
            data["snr"] = data["signal"] - data["noise"]
        else:
            data.pop("snr", None)
        return data

    @staticmethod
    def _identify_device(data, extra_output=""):
        """Infer a readable model from airOS metadata and legacy system files."""
        identity_keys = {
            "platform", "deviceid", "board", "boardname", "board_name",
            "product", "productname", "model", "devicemodel", "hardware",
        }
        parts = [extra_output]
        for key, value in data.items():
            if key.lower() in identity_keys or key.lower() in {"firmwareversion", "cpu_model"}:
                parts.append(str(value))
        identity = " ".join(parts)
        compact = re.sub(r"[^a-z0-9]", "", identity.lower())
        # Match the requested original NanoStation models before generic platform names.
        if re.search(r"nanostation\s*2|\bns2\b", identity, re.IGNORECASE) or "nanostation2" in compact:
            data["device_model"] = "NanoStation2"
        elif re.search(r"nanostation\s*5|\bns5\b", identity, re.IGNORECASE) or "nanostation5" in compact:
            data["device_model"] = "NanoStation5"
        else:
            for key in ("platform", "deviceId", "board", "board_name", "product", "model", "cpu_model"):
                value = data.get(key)
                if value and str(value).strip():
                    data["device_model"] = str(value).strip()
                    break

    def _parse_probe(self, name, output, data):
        if not output:
            return

        if name == "uptime":
            match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", output)
            if match:
                data["uptime_seconds"] = float(match.group(1))
        elif name == "meminfo":
            values = {}
            for line in output.splitlines():
                match = re.match(r"^(MemTotal|MemFree|MemAvailable):\s+(\d+)", line)
                if match:
                    values[match.group(1)] = int(match.group(2)) * 1024
            for source, target in (
                ("MemTotal", "mem_total_bytes"),
                ("MemFree", "mem_free_bytes"),
                ("MemAvailable", "mem_available_bytes"),
            ):
                if source in values:
                    data[target] = values[source]
        elif name == "loadavg":
            fields = output.split()
            if len(fields) >= 3:
                for index, key in enumerate(("load_1m", "load_5m", "load_15m")):
                    data[key] = _number(fields[index])
        elif name in {"version", "board"}:
            # Some firmware exposes model/board identity in these files rather than mca-status.
            data[f"_{name}_identity"] = output.strip()[:500]
            self._identify_device(data, output)
        elif name == "cpuinfo":
            for line in output.splitlines():
                if ":" in line and line.split(":", 1)[0].strip().lower() in (
                    "system type", "model name", "processor"
                ):
                    value = line.split(":", 1)[1].strip()
                    if value:
                        data["cpu_model"] = value
                        self._identify_device(data)
                        break
        elif name == "ifconfig":
            # Parse each interface separately; order varies by firmware.
            # Legacy airOS commonly uses ath0/wlan0, eth0, and br0.
            blocks = re.split(r"(?m)^(?=[A-Za-z0-9_.:-]+\s+Link encap:)", output)
            for block in blocks:
                heading = re.match(r"^([A-Za-z0-9_.:-]+)\s+Link encap:", block)
                if not heading:
                    continue
                interface = heading.group(1).lower()
                is_wireless = interface.startswith(("wlan", "ath"))
                is_ethernet = interface.startswith(("eth", "br"))
                if not (is_wireless or is_ethernet):
                    continue

                prefix = "wireless" if is_wireless else "ethernet"
                mac = re.search(r"(?:HWaddr|ether)\s+([0-9A-Fa-f:]{17})", block)
                if mac:
                    data.setdefault(f"{prefix}_mac", mac.group(1))
                    if is_wireless:
                        data.setdefault("wlanMac", mac.group(1))
                ip = re.search(r"inet addr:([0-9.]+)", block)
                if not ip:
                    ip = re.search(r"\binet ([0-9.]+)", block)
                if ip:
                    data.setdefault("ip_address", ip.group(1))

                flags = re.search(r"<([^>]+)>", block)
                if flags:
                    state = "up" if "UP" in flags.group(1).split(",") else "down"
                    data.setdefault(f"{prefix}_interface_state", state)
                elif re.search(r"(?m)^\s*UP(?:\s|$)", block):
                    data.setdefault(f"{prefix}_interface_state", "up")
                elif re.search(r"(?m)^\s*DOWN(?:\s|$)", block):
                    data.setdefault(f"{prefix}_interface_state", "down")

        elif name == "netdev":
            # Prefer physical interfaces to bridge aliases, avoiding br0 counters
            # being mislabeled as the physical Ethernet port when eth0 is present.
            counters = {}
            for line in output.splitlines():
                if ":" not in line:
                    continue
                interface, stats = line.split(":", 1)
                interface = interface.strip().lower()
                values = stats.split()
                if len(values) < 9:
                    continue
                if interface.startswith(("wlan", "ath")):
                    prefix, priority = "wireless", 2
                elif interface.startswith("eth"):
                    prefix, priority = "ethernet", 2
                elif interface.startswith("br"):
                    prefix, priority = "ethernet", 1
                else:
                    continue
                try:
                    rx_bytes = int(values[0])
                    tx_bytes = int(values[8])
                except (TypeError, ValueError):
                    _LOGGER.debug("Skipping malformed /proc/net/dev row: %s", line)
                    continue
                previous = counters.get(prefix)
                if previous is None or priority > previous[0]:
                    counters[prefix] = (priority, rx_bytes, tx_bytes)
            for prefix, (_, rx_bytes, tx_bytes) in counters.items():
                data[f"{prefix}_rx_bytes"] = rx_bytes
                data[f"{prefix}_tx_bytes"] = tx_bytes