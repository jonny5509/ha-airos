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
        self._previous_cpu_stats = None

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
                    ("cpu_stat", "cat /proc/stat"),
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

        # Some legacy AirOS versions bundle identity metadata into side_devicename,
        # e.g. "UBNT,deviceId=...,firmwareVersion=...,platform=...,deviceIp=...".
        # Split those fields into their own values so Home Assistant can expose
        # them as individual sensors instead of hiding them in the name sensor.
        for key, value in list(data.items()):
            if key.lower() != "side_devicename":
                continue
            parts = [part.strip() for part in value.split(",")]
            data[key] = parts[0] or "AirOS Device"
            metadata_keys = {
                "deviceid": "deviceId",
                "firmwareversion": "firmwareVersion",
                "platform": "platform",
                "deviceip": "deviceIp",
            }
            for part in parts[1:]:
                if "=" not in part:
                    continue
                metadata_key, metadata_value = part.split("=", 1)
                canonical_key = metadata_keys.get(metadata_key.strip().lower())
                metadata_value = metadata_value.strip()
                if canonical_key and metadata_value:
                    data.setdefault(canonical_key, metadata_value)

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
        if re.search(r"nanostation\s*2|\bns2\b|\bxs2\b", identity, re.IGNORECASE) or "nanostation2" in compact or "xs2" in compact:
            data["device_model"] = "NanoStation2"
        elif re.search(r"nanostation\s*5|\bns5\b|\bxs5\b", identity, re.IGNORECASE) or "nanostation5" in compact or "xs5" in compact:
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
        elif name == "cpu_stat":
            # /proc/stat exposes cumulative CPU time counters. Compare consecutive
            # samples to calculate actual utilisation rather than load average.
            lines = output.splitlines()
            fields = lines[0].split() if lines else []
            if fields and fields[0] == "cpu" and len(fields) >= 5:
                try:
                    counters = [int(value) for value in fields[1:9]]
                except ValueError:
                    counters = []

                if len(counters) >= 4:
                    total = sum(counters)
                    idle = counters[3]
                    if len(counters) >= 5:
                        idle += counters[4]  # Treat I/O wait as idle time.

                    previous = self._previous_cpu_stats
                    self._previous_cpu_stats = (total, idle)
                    if previous is not None:
                        total_delta = total - previous[0]
                        idle_delta = idle - previous[1]
                        if total_delta > 0 and 0 <= idle_delta <= total_delta:
                            data["cpu_usage"] = round(
                                100 * (total_delta - idle_delta) / total_delta, 2
                            )
        elif name in {"version", "board"}:
            # Some firmware exposes model/board identity in these files rather than mca-status.
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