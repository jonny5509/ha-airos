import asyncssh
import json
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


def _number(value, default=0.0):
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

                # Older airOS firmware may put identity metadata in a single
                # comma-separated banner, e.g. UBNT,deviceId=...,platform=NanoStation5.
                # Parse the raw response so platform is available for Device Info
                # even when the banner is not formatted as one key/value per line.
                platform_match = re.search(
                    r"(?:^|[,;\\s])platform\\s*=\\s*([^,;\\s]+)",
                    output,
                    re.IGNORECASE,
                )
                if platform_match:
                    data["platform"] = platform_match.group(1)

                # Legacy airOS builds differ significantly. Probe common BusyBox
                # procfs/network commands independently; missing commands/files are
                # ignored so one unsupported probe cannot break the core sensors.
                probes = (
                    ("uptime", "cat /proc/uptime"),
                    ("meminfo", "cat /proc/meminfo"),
                    ("loadavg", "cat /proc/loadavg"),
                    ("cpuinfo", "cat /proc/cpuinfo"),
                    ("ifconfig", "ifconfig"),
                    ("netdev", "cat /proc/net/dev"),
                    ("wireless", "cat /proc/net/wireless"),
                    ("free", "free"),
                    ("wstalist", "wstalist"),
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
        """Parse line-oriented and legacy concatenated mca-status output."""
        data = {}
        # Old airOS may return all key=value fields concatenated on one line.
        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)"
            r"(?=(?:[A-Za-z][A-Za-z0-9_]*)\s*=|$)",
            re.DOTALL,
        )
        for match in pattern.finditer(output.strip()):
            key = match.group(1)
            value = match.group(2).strip().strip(",; ")
            if value:
                data[key] = value

        aliases = {
            "wlanSignal": "signal", "wlanNoise": "noise",
            "wlanCCQ": "ccq", "wlanSNR": "snr",
            "wlanFrequency": "frequency", "wlanESSID": "essid",
            "uptime": "uptime_seconds", "lanIpAddress": "lan_ip",
            "wlanIpAddress": "wlan_ip", "lanRxBytes": "ethernet_rx_bytes",
            "lanTxBytes": "ethernet_tx_bytes", "wlanRxBytes": "wireless_rx_bytes",
            "wlanTxBytes": "wireless_tx_bytes",
        }
        numeric = {
            "signal", "noise", "ccq", "snr", "frequency", "wlanTxRate",
            "wlanRxRate", "wlanConnections", "uptime_seconds", "mem_total_bytes",
            "mem_free_bytes", "ethernet_rx_bytes", "ethernet_tx_bytes",
            "wireless_rx_bytes", "wireless_tx_bytes",
        }
        for source, target in aliases.items():
            if source not in data:
                continue
            raw = data[source]
            if target in numeric:
                number = re.search(r"-?\d+(?:\.\d+)?", str(raw))
                if number:
                    value = float(number.group(0))
                    if target in {"wlanConnections", "uptime_seconds", "mem_total_bytes",
                                  "mem_free_bytes", "ethernet_rx_bytes", "ethernet_tx_bytes",
                                  "wireless_rx_bytes", "wireless_tx_bytes"}:
                        value = int(value)
                    if target in {"mem_total_bytes", "mem_free_bytes"}:
                        value *= 1024
                    if target == "ccq" and value > 100:
                        value /= 10
                    data[target] = value
            else:
                data[target] = raw

        # Older firmware reports CCQ in tenths of a percent and memory in kB.
        for source, target in (("memTotal", "mem_total_bytes"), ("memFree", "mem_free_bytes")):
            if source in data and target not in data:
                match = re.search(r"\d+", str(data[source]))
                if match:
                    data[target] = int(match.group(0)) * 1024
        if "ccq" in data:
            data["ccq"] = _number(data["ccq"])
            if data["ccq"] > 100:
                data["ccq"] /= 10
        if "signal" in data and "noise" in data:
            data["snr"] = _number(data["signal"]) - _number(data["noise"])
        elif "snr" in data:
            data["snr"] = _number(data["snr"])
        for key in numeric:
            if key in data:
                data[key] = _number(data[key], data[key])
        return data

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
        elif name == "cpuinfo":
            for line in output.splitlines():
                if ":" in line and line.split(":", 1)[0].strip().lower() in (
                    "system type", "model name", "processor"
                ):
                    value = line.split(":", 1)[1].strip()
                    if value:
                        data["cpu_model"] = value
                        break
        elif name == "ifconfig":
            # Support both BusyBox legacy "inet addr:" and newer "inet " output.
            match = re.search(r"inet addr:([0-9.]+)", output)
            if not match:
                match = re.search(r"\binet ([0-9.]+)", output)
            if match:
                data["ip_address"] = match.group(1)
            macs = re.findall(r"(?:HWaddr|ether)\s+([0-9A-Fa-f:]{17})", output)
            if macs:
                data.setdefault("ethernet_mac", macs[0])
                if len(macs) > 1:
                    data.setdefault("wireless_mac", macs[1])
        elif name == "free":
            for line in output.splitlines():
                match = re.match(r"^Mem:\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)", line)
                if match:
                    data.setdefault("mem_total_bytes", int(match.group(1)) * 1024)
                    data.setdefault("mem_used_bytes", int(match.group(2)) * 1024)
                    data.setdefault("mem_free_bytes", int(match.group(3)) * 1024)
        elif name == "wstalist":
            try:
                stations = json.loads(output)
            except (ValueError, TypeError):
                stations = None
            if isinstance(stations, list):
                data["connected_station_count"] = len(stations)
                for field in ("rx_bytes", "tx_bytes", "rx_pps", "tx_pps"):
                    values = [
                        _number(station.get("stats", {}).get(field))
                        for station in stations
                        if isinstance(station, dict)
                        and isinstance(station.get("stats"), dict)
                        and station.get("stats", {}).get(field) is not None
                    ]
                    if values:
                        data[f"stations_{field}"] = sum(values)
                signals = [_number(station["signal"]) for station in stations
                           if isinstance(station, dict) and station.get("signal") is not None]
                ccqs = [_number(station["ccq"]) for station in stations
                        if isinstance(station, dict) and station.get("ccq") is not None]
                if signals:
                    data["station_signal_min"] = min(signals)
                    data["station_signal_max"] = max(signals)
                if ccqs:
                    data["station_ccq_average"] = sum(ccqs) / len(ccqs)
        elif name == "netdev":
            for line in output.splitlines():
                if ":" not in line:
                    continue
                interface, stats = line.split(":", 1)
                interface = interface.strip()
                values = stats.split()
                if len(values) < 9:
                    continue
                prefix = "wireless" if interface.lower().startswith(("wlan", "ath")) else (
                    "ethernet" if interface.lower().startswith(("eth", "br")) else None
                )
                if not prefix:
                    continue
                data.setdefault(f"{prefix}_rx_bytes", int(values[0]))
                data.setdefault(f"{prefix}_tx_bytes", int(values[8]))
