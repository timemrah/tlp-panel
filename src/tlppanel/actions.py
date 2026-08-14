"""Privileged TLP commands, run through pkexec.

The GUI itself never runs as root. Each action spawns `pkexec tlp <verb>`,
which shows the desktop authentication dialog and runs only that one command.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable

from gi.repository import Gio, GLib

# pkexec resolves the policy by absolute path, so find the real binary.
_SEARCH_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def tlp_binary() -> str | None:
    return shutil.which("tlp", path=_SEARCH_PATH)


def pkexec_available() -> bool:
    return shutil.which("pkexec") is not None


class ActionError(Exception):
    """A privileged command failed or was cancelled."""


def run_tlp(verb: str, callback: Callable[[bool, str], None], *args: str) -> None:
    """Run `tlp <verb> [args]` asynchronously; callback gets (success, message)."""
    binary = tlp_binary()
    if binary is None:
        callback(False, "tlp binary not found")
        return
    if not pkexec_available():
        callback(False, "pkexec not found")
        return

    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        process = launcher.spawnv(["pkexec", binary, verb, *args])
    except GLib.Error as error:
        callback(False, error.message)
        return

    def _finished(proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            ok, stdout, _ = proc.communicate_utf8_finish(result)
        except GLib.Error as error:
            callback(False, error.message)
            return
        output = (stdout or "").strip()
        if proc.get_successful():
            callback(True, output)
        else:
            # pkexec exits 126/127 when the dialog is dismissed or authentication
            # fails; anything else is a genuine tlp error.
            callback(False, output or "authentication failed")

    process.communicate_utf8_async(None, None, _finished)


def set_auto(callback: Callable[[bool, str], None]) -> None:
    run_tlp("start", callback)


def set_battery_mode(callback: Callable[[bool, str], None]) -> None:
    run_tlp("bat", callback)


def set_ac_mode(callback: Callable[[bool, str], None]) -> None:
    run_tlp("ac", callback)


def full_charge(callback: Callable[[bool, str], None]) -> None:
    run_tlp("fullcharge", callback)


HELPER = "/usr/libexec/tlp-panel-helper"


def helper_available() -> bool:
    return os.access(HELPER, os.X_OK)


def _run_privileged(argv: list[str], callback: Callable[[bool, str], None]) -> None:
    """Spawn argv under pkexec and report the outcome asynchronously."""
    if not pkexec_available():
        callback(False, "pkexec not found")
        return

    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    )
    try:
        process = launcher.spawnv(["pkexec", *argv])
    except GLib.Error as error:
        callback(False, error.message)
        return

    def _finished(proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            _, stdout, _ = proc.communicate_utf8_finish(result)
        except GLib.Error as error:
            callback(False, error.message)
            return
        output = (stdout or "").strip()
        callback(proc.get_successful(), output or "authentication failed")

    process.communicate_utf8_async(None, None, _finished)


def set_charge_thresholds(
    start: int, stop: int, callback: Callable[[bool, str], None], battery: str = "BAT0"
) -> None:
    """Persist charge thresholds through the helper, and apply them now.

    Falls back to a one-off `tlp setcharge` when the helper is not installed,
    which applies the limit but does not survive a reboot.
    """
    if helper_available():
        _run_privileged([HELPER, "set-charge", str(start), str(stop), battery], callback)
    else:
        run_tlp("setcharge", callback, str(start), str(stop), battery)


def set_abm_levels(ac: int, bat: int, callback: Callable[[bool, str], None]) -> None:
    """Set the adaptive backlight level for both power sources."""
    if not helper_available():
        callback(False, "helper not installed")
        return
    _run_privileged([HELPER, "set-abm", str(ac), str(bat)], callback)


def set_wifi_power_saving(ac: str, bat: str, callback: Callable[[bool, str], None]) -> None:
    """Set Wi-Fi power saving ('on'/'off') for both power sources."""
    if not helper_available():
        callback(False, "helper not installed")
        return
    _run_privileged([HELPER, "set-wifi", ac, bat], callback)


def apply_mode_preset(preset: str, callback: Callable[[bool, str], None]) -> None:
    """Switch the system mode and the settings it implies, in one step.

    Falls back to a plain profile switch when the helper is missing, which
    changes the active profile but leaves Wi-Fi and device sleep alone.
    """
    if helper_available():
        _run_privileged([HELPER, "apply-preset", preset], callback)
        return
    run_tlp({"auto": "start", "bat": "bat", "ac": "ac"}[preset], callback)


def set_runtime_pm(ac: str, bat: str, callback: Callable[[bool, str], None]) -> None:
    """Set device runtime power management for both power sources.

    TLP's values are inverted against the user-facing wording: 'auto' lets a
    device sleep (saving power), 'on' keeps it awake.
    """
    if not helper_available():
        callback(False, "helper not installed")
        return
    _run_privileged([HELPER, "set-runtime-pm", ac, bat], callback)
