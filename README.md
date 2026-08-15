<div align="center">

<img src="docs/icon.png" width="104" alt="">

# TLP Panel

**See what your laptop is doing with power — and change it, without a terminal.**

![Platform](https://img.shields.io/badge/Platform-Linux-333333?style=for-the-badge&logo=linux&logoColor=white)
![Debian](https://img.shields.io/badge/Debian%20%C2%B7%20Ubuntu-.deb%20package-A81D33?style=for-the-badge&logo=debian&logoColor=white)
![GTK](https://img.shields.io/badge/GTK%204%20%C2%B7%20libadwaita-4A86CF?style=for-the-badge&logo=gnome&logoColor=white)
![Licence](https://img.shields.io/badge/Licence-GPL--3.0-2C7A2C?style=for-the-badge)

<br>

<img src="docs/screenshot.png" width="760" alt="TLP Panel showing power draw, charge limit, system mode and estimated runtime">

</div>

<br>

## A Linux desktop application

TLP Panel is a **GTK4 / libadwaita** app for **Linux laptops**. It reads the
kernel's own power interfaces and drives
[TLP](https://linrunner.de/tlp/) — the battery-life tool that ships with most
distributions.

It is published as a **`.deb` package** for Debian 13 and Ubuntu 24.04 or
newer, and runs on any desktop, GNOME or otherwise.

> **Linux only.** Everything it reads lives in `/sys` and `/run/tlp`, and
> everything it changes goes through TLP. There is no Windows or macOS build,
> and nothing to port — those systems have neither.

<br>

## Why it exists

**TLP has no interface.** It is excellent and invisible: a set of rules applied
at boot and whenever the power cable moves. To see what it is doing you run
`tlp-stat` as root and read a wall of text.

**The one GUI that exists edits settings, not state.** TLPUI is a capable
editor for TLP's ~200 configuration options. It does not tell you your current
draw, which profile is active, or how long the battery will last.

**Those are the questions people actually ask.** How many watts am I burning?
Will this last the flight? Why is the fan on while I am doing nothing? TLP
Panel answers them on one screen, and puts the handful of settings worth
changing next to the answers.

**And it tells you when a knob is fake.** Some power settings exist in `/sys`,
accept a value, store it, and change nothing — the hardware never wired them
up. That is worse than not offering them. This app checks, and says so.

<br>

## Install

### Debian · Ubuntu

Add the repository once, and updates arrive with the rest of your system:

```sh
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSL -o /etc/apt/keyrings/tlp-panel.asc \
  https://timemrah.github.io/tlp-panel/apt/tlp-panel.asc

echo "deb [signed-by=/etc/apt/keyrings/tlp-panel.asc] https://timemrah.github.io/tlp-panel/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/tlp-panel.list

sudo apt update
sudo apt install tlp-panel
```

Dependencies come with it. If TLP is not installed yet, `apt` pulls it in.

Prefer a single file? Download the `.deb` from
[**Releases**](https://github.com/timemrah/tlp-panel/releases/latest) and run
`sudo apt install ./tlp-panel_*_all.deb` — but then each update is another
download.

### Arch Linux

```sh
yay -S tlp-panel
```

### From source

```sh
sudo apt install tlp python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 polkitd
git clone https://github.com/timemrah/tlp-panel.git
cd tlp-panel
sudo make install
```

Launch **TLP Panel** from your application grid, or run `tlp-panel`.

| Command | |
|---|---|
| `make run` | try it without installing |
| `sudo make uninstall` | remove a source install |
| `dpkg-buildpackage -us -uc -b` | build the `.deb` yourself |

<br>

## What it shows

| | |
|---|---|
| **Power draw** | Watts, live, straight from the battery. While charging it reports charge power and says so — the two are not the same number. |
| **Battery** | Charge, health as current capacity against design capacity, and cycle count. |
| **Estimated runtime** | How long the charge will last: right now, at a full pack, and at your charge limit. Plugged in, it counts up to those instead. |

## What it changes

Every control writes to `/etc/tlp.d/90-tlp-panel.conf` and applies at once, so
settings survive a reboot.

| | |
|---|---|
| **System mode** | Automatic follows the cable. Battery saving and Full performance pin one profile — and apply the three settings below as a preset. |
| **Charge limit** | Stop charging at a chosen percentage, written to the battery firmware. Plus a one-off *charge to 100%* for the day before a trip. |
| **CPU speed limit** | How fast the processor may run, in the steps it actually offers. Automatic caps it on battery and lifts the cap on AC; the slider overrides the source in use. |
| **Wi-Fi power saving** | Let the radio sleep on battery only, always, or never. |
| **Sleep idle devices** | Whether idle PCI devices may power down. Your per-device exemptions are left alone. |
| **Adaptive backlight** | AMD panel power saving, separately for AC and battery. |

<br>

## Honest about your hardware

Controls appear only when they can do something:

- **Adaptive backlight** runs on the display microcontroller. On several AMD
  APUs that firmware is never loaded, so the kernel accepts a level, stores it,
  and nothing happens. TLP Panel detects this and leaves the sliders greyed
  out.
- **Charge limits** appear only when the battery exposes thresholds.
- **The CPU speed limit** offers the frequencies the scaling driver reports.
  Drivers that publish a list of P-states give exactly those; drivers that take
  any value in a range get an evenly spaced set. A processor with a single
  frequency has nothing to choose, so the slider stays away.
- **Wi-Fi and device sleep** appear only when there is something to control.

<br>

## Under the hood

The window runs as your user, never as root. Everything on screen comes from
files any user can read:

| Value | Source |
|---|---|
| Draw, charge, health, cycles, thresholds | `/sys/class/power_supply/BAT*` |
| Mains state | `/sys/class/power_supply/*/online` |
| Active and forced profile | `/run/tlp/last_pwr`, `/run/tlp/manual_mode` |
| Effective TLP settings | `/run/tlp/run.conf` |

Batteries reporting charge in µAh instead of energy in µWh are converted using
the reported voltage, so machines without `power_now` still show watts.

Changes go through `pkexec` to `/usr/libexec/tlp-panel-helper`, a shell script
that takes a fixed set of verbs with validated arguments and writes only
allowlisted keys. It never passes an argument to a shell. Both polkit actions
are `auth_admin_keep`, so a run of adjustments asks once.

<br>

## Translating

The interface follows your locale. English is the source language; Turkish
ships with it. A new language is one dictionary in `src/tlppanel/i18n.py` —
there are no catalogues to compile.

`make check` fails when a translatable string has no entry, so a language
cannot quietly rot.

<br>

## Licence

GPL-3.0-or-later.

TLP is a separate project by Thomas Koch, licensed GPL-2.0+; this panel only
calls its command-line interface.
