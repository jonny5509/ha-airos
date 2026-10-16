"""SSH polling and telemetry parsing for legacy Ubiquiti airOS devices."""
import asyncssh
import json
import logging
import re
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode(errors="ignore")
    return str(value)


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AiRXS2Coordinator(DataUpdateCoordinator):
    """Poll an airOS device and normalize all available telemetry."""

    def __init__(self, hass: HomeAssistant, host, username, password, name):
        self.host = host
        self.username = username
        self.password = password
        self.device_name = name
        self._previous_cpu_ticks = None
        self._previous_idle_ticks = None
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"airos_xs2_{name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _run_command(self, conn, command):
        """Run a read-only command and return stdout (or useful stderr)."""
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
                # Legacy airOS devices often only support obsolete SSH algorithms.
                # Host-key verification should be configurable in a future UI option.
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

                platform_match = re.search(
                    r"(?:^|[,;\s])platform\s*=\s*([^,;\s]+)",
                    output, re.IGNORECASE,
                )
                if platform_match:
                    data["platform"] = platform_match.group(1)

                probes = (
                    ("uptime", "cat /proc/uptime"),
                    ("meminfo", "cat /proc/meminfo"),
                    ("loadavg", "cat /proc/loadavg"),
                    ("cpuinfo", "cat /proc/cpuinfo"),
                    ("stat", "cat /proc/stat"),
                    ("version", "cat /proc/version"),
                    ("ifconfig", "ifconfig"),
                    ("netdev", "cat /proc/net/dev"),
                    ("wireless", "cat /proc/net/wireless"),
                    ("free", "free"),
                    ("wstalist", "wstalist"),
                    ("iwconfig", "iwconfig"),
                    ("hostname", "hostname"),
                )
                for probe, command in probes:
                    try:
                        result = await self._run_command(conn, command)
                        self._parse_probe(probe, result, data)
                    except Exception as err:
                        _LOGGER.debug("airOS probe %s unavailable: %s", probe, err)

                total = data.get("cpu_total_ticks")
                idle = data.get("cpu_idle_ticks")
                if total is not None and idle is not None:
                    if self._previous_cpu_ticks is not None and self._previous_idle_ticks is not None:
                        total_delta = total - self._previous_cpu_ticks
                        idle_delta = idle - self._previous_idle_ticks
                        if total_delta > 0 and 0 <= idle_delta <= total_delta:
                            data["cpu_utilization"] = round(
                                100.0 * (total_delta - idle_delta) / total_delta, 1
                            )
                    self._previous_cpu_ticks = total
                    self._previous_idle_ticks = idle
                return data
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"SSH error: {err}") from err

    def _parse_output(self, output: str):
        """Parse line-oriented and legacy concatenated key=value output."""
        data = {}
        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)"
            r"(?=(?:[A-Za-z][A-Za-z0-9_]*)\s*=|$)", re.DOTALL
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
            "Freq": "frequency", "freq": "frequency",
            "apMac": "ap_mac", "apmac": "ap_mac",
            "deviceId": "device_id", "deviceName": "device_name",
            "deviceIp": "ip_address", "deviceIP": "ip_address",
            "firmwareVersion": "firmware_version",
            "cfgCrc": "config_checksum", "cfgCRC": "config_checksum",
        }
        numeric = {
            "signal", "noise", "ccq", "snr", "frequency", "wlanTxRate",
            "wlanRxRate", "wlanConnections", "uptime_seconds",
            "mem_total_bytes", "mem_free_bytes", "ethernet_rx_bytes",
            "ethernet_tx_bytes", "wireless_rx_bytes", "wireless_tx_bytes", "frequency",
        }
        for source, target in aliases.items():
            if source not in data:
                continue
            raw = data[source]
            if target in numeric:
                match = re.search(r"-?\d+(?:\.\d+)?", str(raw))
                if match:
                    value = float(match.group(0))
                    if target in {
                        "wlanConnections", "uptime_seconds", "mem_total_bytes",
                        "mem_free_bytes", "ethernet_rx_bytes", "ethernet_tx_bytes",
                        "wireless_rx_bytes", "wireless_tx_bytes",
                    }:
                        value = int(value)
                    if target in {"mem_total_bytes", "mem_free_bytes"}:
                        value *= 1024
                    if target == "ccq" and value > 100:
                        value /= 10
                    data[target] = value
            else:
                data[target] = raw

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
        """Parse optional BusyBox/procfs output; unsupported sources are harmless."""
        if not output:
            return
        if name == "uptime":
            match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", output)
            if match:
                data["uptime_seconds"] = int(float(match.group(1)))
        elif name == "meminfo":
            values = {}
            for line in output.splitlines():
                match = re.match(r"^(\w+):\s+(\d+)", line)
                if match:
                    values[match.group(1)] = int(match.group(2)) * 1024
            mapping = {
                "MemTotal": "mem_total_bytes", "MemFree": "mem_free_bytes",
                "MemAvailable": "mem_available_bytes", "Buffers": "mem_buffers_bytes",
                "Cached": "mem_cached_bytes", "SwapTotal": "swap_total_bytes",
                "SwapFree": "swap_free_bytes",
            }
            for source, target in mapping.items():
                if source in values:
                    data[target] = values[source]
            if "mem_total_bytes" in data and "mem_available_bytes" in data:
                data["mem_used_bytes"] = max(
                    0, data["mem_total_bytes"] - data["mem_available_bytes"]
                )
            elif "mem_total_bytes" in data and "mem_free_bytes" in data:
                data["mem_used_bytes"] = max(
                    0, data["mem_total_bytes"] - data["mem_free_bytes"]
                )
            if "swap_total_bytes" in data and "swap_free_bytes" in data:
                data["swap_used_bytes"] = max(
                    0, data["swap_total_bytes"] - data["swap_free_bytes"]
                )
        elif name == "loadavg":
            fields = output.split()
            if len(fields) >= 3:
                for index, key in enumerate(("load_1m", "load_5m", "load_15m")):
                    data[key] = _number(fields[index])
            if len(fields) >= 4 and "/" in fields[3]:
                try:
                    running, total = fields[3].split("/", 1)
                    data["processes_running"] = int(running)
                    data["processes_total"] = int(total)
                except ValueError:
                    pass
        elif name == "cpuinfo":
            for line in output.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                if key.strip().lower() in ("system type", "model name", "processor", "hardware"):
                    if value.strip():
                        data.setdefault("cpu_model", value.strip())
                        break
        elif name == "stat":
            for line in output.splitlines():
                if line.startswith("cpu "):
                    fields = line.split()[1:]
                    if len(fields) >= 4:
                        data["cpu_total_ticks"] = sum(int(v) for v in fields if v.isdigit())
                        data["cpu_idle_ticks"] = int(fields[3]) + (
                            int(fields[4]) if len(fields) > 4 and fields[4].isdigit() else 0
                        )
                    break
        elif name == "version":
            data["kernel_version"] = output.strip().splitlines()[0][:128]
        elif name == "hostname":
            host = output.strip().splitlines()[0] if output.strip() else ""
            if host:
                data["hostname"] = host
        elif name == "ifconfig":
            # Legacy and modern ifconfig formats.
            match = re.search(r"inet addr:([0-9.]+)", output)
            if not match:
                match = re.search(r"\binet (?:addr:)?([0-9.]+)", output)
            if match:
                data.setdefault("ip_address", match.group(1))
            macs = re.findall(r"(?:HWaddr|ether)\s+([0-9A-Fa-f:]{17})", output)
            if macs:
                data.setdefault("ethernet_mac", macs[0])
                if len(macs) > 1:
                    data.setdefault("wireless_mac", macs[1])
            # Parse each interface block for address, link state and counters.
            blocks = re.split(r"\n(?=\S)", output)
            for block in blocks:
                first = block.splitlines()[0] if block.splitlines() else ""
                iface_match = re.match(r"([A-Za-z0-9_.:-]+)\s+", first)
                if not iface_match:
                    continue
                iface = iface_match.group(1).rstrip(":")
                prefix = "wireless" if iface.lower().startswith(("wlan", "ath")) else (
                    "ethernet" if iface.lower().startswith(("eth", "br")) else None
                )
                if not prefix:
                    continue
                data[f"{iface}_interface"] = iface
                if re.search(r"\bUP\b", block):
                    data[f"{iface}_link_up"] = True
                elif re.search(r"\bDOWN\b", block):
                    data[f"{iface}_link_up"] = False
                speed = re.search(r"(?:Speed[:=]\s*)(\d+)\s*Mb/s", block, re.I)
                if speed:
                    data[f"{prefix}_link_speed_mbps"] = int(speed.group(1))
        elif name == "wireless":
            for line in output.splitlines():
                match = re.match(
                    r"^\s*([A-Za-z0-9_.-]+):\s+([0-9A-Fa-f]+)\s+([0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)",
                    line,
                )
                if match:
                    interface, _status, quality, signal, noise = match.groups()
                    data.setdefault(f"{interface}_link_quality", _number(quality))
                    data.setdefault(f"{interface}_signal", _number(signal))
                    data.setdefault(f"{interface}_noise", _number(noise))
        elif name == "free":
            for line in output.splitlines():
                match = re.match(r"^Mem:\s+(\d+)\s+(\d+)\s+(\d+)", line)
                if match:
                    data.setdefault("mem_total_bytes", int(match.group(1)) * 1024)
                    data.setdefault("mem_used_bytes", int(match.group(2)) * 1024)
                    data.setdefault("mem_free_bytes", int(match.group(3)) * 1024)
        elif name == "iwconfig":
            # Common wireless-tools output includes ESSID, frequency, bit rate,
            # Tx-Power, link quality, signal level and noise level.
            patterns = (
                (r'ESSID:"([^"]*)"', "essid", str),
                (r"Frequency[:=]([0-9.]+)\s*GHz", "frequency", lambda v: float(v) * 1000),
                (r"Frequency[:=]([0-9.]+)\s*MHz", "frequency", float),
                (r"Bit Rate[:=]([0-9.]+)\s*Mb/s", "wireless_rate_mbps", float),
                (r"Tx-Power[:=]([0-9.]+)\s*dBm", "txpower", float),
                (r"Link Quality[:=]([0-9.]+)/([0-9.]+)", "wireless_link_quality_ratio", None),
                (r"Signal level[:=](-?[0-9.]+)\s*dBm", "signal", float),
                (r"Noise level[:=](-?[0-9.]+)\s*dBm", "noise", float),
            )
            for pattern, key, convert in patterns:
                match = re.search(pattern, output, re.I)
                if match:
                    if key == "wireless_link_quality_ratio":
                        data["wireless_link_quality"] = _number(match.group(1))
                        data["wireless_link_quality_max"] = _number(match.group(2))
                    else:
                        try:
                            data.setdefault(key, convert(match.group(1)))
                        except (TypeError, ValueError):
                            pass
            if "signal" in data and "noise" in data:
                data["snr"] = _number(data["signal"]) - _number(data["noise"])
        elif name == "wstalist":
            try:
                stations = json.loads(output)
            except (ValueError, TypeError):
                stations = None
            if isinstance(stations, list):
                valid = [station for station in stations if isinstance(station, dict)]
                data["connected_station_count"] = len(valid)
                for field in ("rx_bytes", "tx_bytes", "rx_pps", "tx_pps"):
                    values = [
                        _number(station.get("stats", {}).get(field))
                        for station in valid
                        if isinstance(station.get("stats"), dict)
                        and station["stats"].get(field) is not None
                    ]
                    if values:
                        data[f"stations_{field}"] = sum(values)
                signals = [_number(s["signal"]) for s in valid if s.get("signal") is not None]
                ccqs = [_number(s["ccq"]) for s in valid if s.get("ccq") is not None]
                if signals:
                    data["station_signal_min"] = min(signals)
                    data["station_signal_max"] = max(signals)
                    data["station_signal_average"] = sum(signals) / len(signals)
                if ccqs:
                    data["station_ccq_average"] = sum(ccqs) / len(ccqs)
                for field in ("tx", "rx"):
                    rates = [_number(s.get(f"{field}rate")) for s in valid if s.get(f"{field}rate") is not None]
                    if rates:
                        data[f"stations_{field}_rate_mbps"] = sum(rates)
                # Individual station fields are aggregated into stable per-MAC keys.
                for station in valid:
                    mac = str(station.get("mac") or station.get("macaddr") or "").lower()
                    safe_mac = re.sub(r"[^a-z0-9]", "_", mac)
                    if not safe_mac:
                        continue
                    for source, suffix in (
                        ("signal", "signal"), ("ccq", "ccq"), ("txrate", "tx_rate_mbps"),
                        ("rxrate", "rx_rate_mbps"), ("uptime", "uptime_seconds"),
                    ):
                        if station.get(source) is not None:
                            data[f"station_{safe_mac}_{suffix}"] = _number(station[source])
                    data[f"station_{safe_mac}_mac"] = mac
        elif name == "netdev":
            for line in output.splitlines():
                if ":" not in line:
                    continue
                interface, stats = line.split(":", 1)
                interface = interface.strip()
                values = stats.split()
                if len(values) < 16:
                    continue
                prefix = "wireless" if interface.lower().startswith(("wlan", "ath")) else (
                    "ethernet" if interface.lower().startswith(("eth", "br")) else None
                )
                if not prefix:
                    continue
                # Linux /proc/net/dev: RX bytes, packets, errs, drop, fifo,
                # frame, compressed, multicast; then corresponding TX columns.
                labels = (
                    ("rx_bytes", 0, "B"), ("rx_packets", 1, "packets"),
                    ("rx_errors", 2, "errors"), ("rx_dropped", 3, "packets"),
                    ("tx_bytes", 8, "B"), ("tx_packets", 9, "packets"),
                    ("tx_errors", 10, "errors"), ("tx_dropped", 11, "packets"),
                    ("rx_fifo_errors", 4, "errors"), ("rx_frame_errors", 5, "errors"),
                    ("rx_compressed", 6, "packets"), ("multicast", 7, "packets"),
                    ("tx_fifo_errors", 12, "errors"), ("tx_collisions", 13, "collisions"),
                    ("tx_carrier_errors", 14, "errors"), ("tx_compressed", 15, "packets"),
                )
                data[f"{interface}_interface"] = interface
                for suffix, index, _unit in labels:
                    try:
                        value = int(values[index])
                    except (ValueError, IndexError):
                        continue
                    data.setdefault(f"{prefix}_{suffix}", value)
                    data[f"{interface}_{suffix}"] = value
