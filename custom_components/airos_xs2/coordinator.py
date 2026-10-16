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

        # Missing or malformed readings must stay unavailable, not look like real zeroes.
        for key in ("signal", "noise", "wlanTxRate", "wlanRxRate"):
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
                try:
                    rx_bytes = int(values[0])
                    tx_bytes = int(values[8])
                except (TypeError, ValueError):
                    _LOGGER.debug("Skipping malformed /proc/net/dev row: %s", line)
                    continue
                data.setdefault(f"{prefix}_rx_bytes", rx_bytes)
                data.setdefault(f"{prefix}_tx_bytes", tx_bytes)
