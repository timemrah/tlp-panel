"""Read power, battery and TLP state from sysfs and /run/tlp.

Everything in this module works without root privileges.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

POWER_SUPPLY = Path("/sys/class/power_supply")
TLP_RUN_DIR = Path("/run/tlp")
TLP_LAST_PWR = TLP_RUN_DIR / "last_pwr"
TLP_RUN_CONF = TLP_RUN_DIR / "run.conf"
TLP_MANUAL_MODE = TLP_RUN_DIR / "manual_mode"
ABM_SUPPORTED_FILE = Path("/var/lib/tlp-panel/abm-supported")

# TLP writes 0 for AC, 1 for battery.
MODE_AC = "ac"
MODE_BATTERY = "battery"
MODE_UNKNOWN = "unknown"


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None


def _read_int(path: Path) -> int | None:
    raw = _read(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _supplies_of_type(kind: str) -> list[Path]:
    found = []
    try:
        entries = sorted(POWER_SUPPLY.iterdir())
    except OSError:
        return found
    for entry in entries:
        if _read(entry / "type") == kind:
            found.append(entry)
    return found


@dataclass
class Battery:
    """A single battery, with values normalised to watts and watt-hours."""

    name: str
    percent: int | None = None
    status: str | None = None
    power_w: float | None = None
    energy_wh: float | None = None
    energy_full_wh: float | None = None
    energy_design_wh: float | None = None
    cycle_count: int | None = None
    start_threshold: int | None = None
    stop_threshold: int | None = None

    @property
    def health_percent(self) -> float | None:
        if not self.energy_full_wh or not self.energy_design_wh:
            return None
        return self.energy_full_wh / self.energy_design_wh * 100.0

    @property
    def charging(self) -> bool:
        return (self.status or "").lower() == "charging"

    @property
    def discharging(self) -> bool:
        return (self.status or "").lower() == "discharging"

    @property
    def runtime_hours(self) -> float | None:
        """Hours left at the current draw. Only meaningful while discharging."""
        if not self.discharging or not self.power_w or not self.energy_wh:
            return None
        if self.power_w <= 0:
            return None
        return self.energy_wh / self.power_w

    def charge_hours_to(self, target_wh: float) -> float | None:
        """Hours until the pack reaches a given energy, at the current rate."""
        if not self.charging or not self.power_w or self.power_w <= 0:
            return None
        if self.energy_wh is None:
            return None
        remaining = target_wh - self.energy_wh
        if remaining <= 0:
            return None
        return remaining / self.power_w

    @property
    def limit_energy_wh(self) -> float | None:
        """Energy the pack holds when charging stops."""
        if not self.energy_full_wh:
            return None
        if self.stop_threshold and self.stop_threshold < 100:
            return self.energy_full_wh * self.stop_threshold / 100.0
        return self.energy_full_wh

    @property
    def charge_hours(self) -> float | None:
        """Hours until charging stops, which is at the limit when one is set."""
        target = self.limit_energy_wh
        if target is None:
            return None
        return self.charge_hours_to(target)

    def projected_hours(self, energy_wh: float) -> float | None:
        """Hours a given amount of energy would last at the current draw.

        Only while discharging: when the battery is charging, power_now is
        the charge power, and dividing by it would answer a question nobody
        asked.
        """
        if not self.discharging or not self.power_w or self.power_w <= 0:
            return None
        return energy_wh / self.power_w


def _read_battery(path: Path) -> Battery:
    bat = Battery(name=path.name)
    bat.percent = _read_int(path / "capacity")
    bat.status = _read(path / "status")
    bat.cycle_count = _read_int(path / "cycle_count")

    # Charge thresholds are exposed under two different names depending on
    # the driver (standard kernel API vs. older thinkpad_acpi).
    for start_name, stop_name in (
        ("charge_control_start_threshold", "charge_control_end_threshold"),
        ("charge_start_threshold", "charge_stop_threshold"),
    ):
        start = _read_int(path / start_name)
        stop = _read_int(path / stop_name)
        if stop is not None:
            bat.start_threshold = start
            bat.stop_threshold = stop
            break

    # Energy-reporting batteries (µWh, µW) are the common case.
    energy_now = _read_int(path / "energy_now")
    energy_full = _read_int(path / "energy_full")
    energy_design = _read_int(path / "energy_full_design")
    power_now = _read_int(path / "power_now")

    voltage = _read_int(path / "voltage_now")  # µV

    if energy_now is None:
        # Charge-reporting batteries (µAh, µA) need the voltage to convert.
        charge_now = _read_int(path / "charge_now")
        charge_full = _read_int(path / "charge_full")
        charge_design = _read_int(path / "charge_full_design")
        if voltage:
            volts = voltage / 1e6
            if charge_now is not None:
                energy_now = int(charge_now * volts)
            if charge_full is not None:
                energy_full = int(charge_full * volts)
            if charge_design is not None:
                energy_design = int(charge_design * volts)

    if power_now is None:
        current = _read_int(path / "current_now")  # µA
        if current is not None and voltage:
            power_now = int(abs(current) * (voltage / 1e6))

    if power_now is not None:
        bat.power_w = abs(power_now) / 1e6
    if energy_now is not None:
        bat.energy_wh = energy_now / 1e6
    if energy_full is not None:
        bat.energy_full_wh = energy_full / 1e6
    if energy_design is not None:
        bat.energy_design_wh = energy_design / 1e6

    return bat


@dataclass
class TlpState:
    installed: bool = False
    enabled: bool | None = None
    mode: str = MODE_UNKNOWN
    manual: bool = False
    manual_mode: str = MODE_UNKNOWN
    config: dict[str, str] = field(default_factory=dict)


def _parse_run_conf(text: str) -> dict[str, str]:
    conf: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([A-Z0-9_]+)="?(.*?)"?$', line)
        if match:
            conf[match.group(1)] = match.group(2)
    return conf


def read_tlp_state() -> TlpState:
    state = TlpState()
    state.installed = shutil.which("tlp", path="/usr/sbin:/usr/bin:/sbin:/bin") is not None

    raw_conf = _read(TLP_RUN_CONF)
    if raw_conf:
        state.config = _parse_run_conf(raw_conf)
        enable = state.config.get("TLP_ENABLE")
        if enable is not None:
            state.enabled = enable == "1"

    last = _read(TLP_LAST_PWR)
    if last == "0":
        state.mode = MODE_AC
    elif last == "1":
        state.mode = MODE_BATTERY

    # TLP records a forced profile here: "0" = AC, "1" = battery, "n" = auto.
    manual = _read(TLP_MANUAL_MODE)
    if manual == "0":
        state.manual = True
        state.manual_mode = MODE_AC
    elif manual == "1":
        state.manual = True
        state.manual_mode = MODE_BATTERY

    return state


@dataclass
class PowerState:
    on_ac: bool | None = None
    batteries: list[Battery] = field(default_factory=list)
    tlp: TlpState = field(default_factory=TlpState)

    @property
    def battery(self) -> Battery | None:
        """The battery to show. Prefers a discharging one, else the first."""
        for bat in self.batteries:
            if bat.discharging:
                return bat
        return self.batteries[0] if self.batteries else None

    @property
    def total_power_w(self) -> float | None:
        values = [b.power_w for b in self.batteries if b.power_w]
        return sum(values) if values else None


def read_power_state() -> PowerState:
    state = PowerState()

    mains = _supplies_of_type("Mains")
    for supply in mains:
        online = _read_int(supply / "online")
        if online is not None:
            state.on_ac = bool(online)
            break

    state.batteries = [_read_battery(p) for p in _supplies_of_type("Battery")]
    state.tlp = read_tlp_state()
    return state


# --- extra live values, best effort -----------------------------------------


def read_abm_level() -> int | None:
    """AMD adaptive backlight level, if the panel exposes it."""
    for path in Path("/sys/class/drm").glob("card*/*/amdgpu/panel_power_savings"):
        value = _read_int(path)
        if value is not None:
            return value
    return None


def abm_supported() -> bool | None:
    """Whether adaptive backlight can actually take effect.

    The privileged helper records this, because deciding it needs debugfs.
    None means nobody has looked yet.
    """
    value = _read(ABM_SUPPORTED_FILE)
    if value is None:
        return None
    return value.strip() == "1"


def read_wifi_powersave() -> dict[str, str]:
    """Power-save state per wireless interface, read from sysfs only."""
    result: dict[str, str] = {}
    for phy in Path("/sys/class/ieee80211").glob("phy*"):
        for netdev in (phy / "device/net").glob("*"):
            flag = _read(netdev / "power/control")
            if flag:
                result[netdev.name] = flag
    return result
