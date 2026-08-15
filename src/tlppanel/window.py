"""Main window: live power status and one-click TLP actions.

Layout is two columns side by side, collapsing to one on narrow windows.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import actions, backend, i18n  # noqa: E402
from .i18n import N_, _, format_duration  # noqa: E402

REFRESH_SECONDS = 2
NARROW_WIDTH = 760
# How long to wait after the slider stops moving before applying the limit.
CHARGE_APPLY_DELAY_MS = 1200
CHARGE_MIN = 50
CHARGE_MAX = 100
CHARGE_STEP = 5
# Adaptive backlight accepts 0-4 in the amdgpu driver.
ABM_MAX = 4
SETTING_APPLY_DELAY_MS = 900
# Charge levels where the indicator changes colour.
LEVEL_GOOD = 50.0
LEVEL_LOW = 20.0

# Values are translated when displayed, so they are marked, not translated here.
STATUS_LABELS = {
    "charging": N_("Charging"),
    "discharging": N_("Discharging"),
    "full": N_("Full"),
    "not charging": N_("Not charging"),
    "unknown": N_("Unknown"),
}

# TLP reports these verbatim; mark them so the wording stays translatable.
WIFI_STATES = (N_("on"), N_("off"))

# Above this many frequency steps, labelling every mark crowds the scale.
CPU_LABEL_ALL_UP_TO = 6


def _format_ghz(khz: int) -> str:
    return f"{khz / 1_000_000:.1f}"


class TlpPanelWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("TLP Panel"))
        self.set_default_size(1000, 660)
        self.set_size_request(360, 480)

        self._busy = False
        self._mode_buttons: dict[str, Gtk.ToggleButton] = {}
        self._wifi_buttons: dict[str, Gtk.ToggleButton] = {}
        self._runtime_pm_buttons: dict[str, Gtk.ToggleButton] = {}
        self._suppress_toggle = False
        # Charge slider state: keep the user's position while they adjust it,
        # instead of letting the periodic refresh snap it back.
        self._suppress_charge = False
        self._charge_user_touched = False
        self._charge_timeout = 0
        self._suppress_abm = False
        self._abm_user_touched = False
        self._abm_timeout = 0
        self._suppress_wifi = False
        self._suppress_runtime_pm = False
        self._current_start: int | None = None
        self._current_stop: int | None = None
        # The frequency steps never change while the app runs, so read them once.
        self._cpu_limits = backend.read_cpu_freq_limits()
        self._cpu_conf: dict[str, int | None] = {"ac": None, "bat": None}
        self._suppress_cpu = False
        self._cpu_user_touched = False
        self._cpu_timeout = 0
        self._on_ac = True

        self._toasts = Adw.ToastOverlay()
        self.set_content(self._toasts)

        toolbar = Adw.ToolbarView()
        self._toasts.set_child(toolbar)
        toolbar.add_top_bar(self._build_header())

        self._banner = Adw.Banner()
        self._banner.set_revealed(False)
        toolbar.add_top_bar(self._banner)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        toolbar.set_content(scroller)

        clamp = Adw.Clamp(maximum_size=1100, tightening_threshold=900)
        scroller.set_child(clamp)

        # A grid, not two boxes: paired cards share a row, so each pair ends
        # up the same height.
        self._grid = Gtk.Grid(column_spacing=18, row_spacing=18)
        self._grid.set_column_homogeneous(True)
        self._grid.set_margin_top(18)
        self._grid.set_margin_bottom(18)
        self._grid.set_margin_start(18)
        self._grid.set_margin_end(18)
        clamp.set_child(self._grid)

        # Left card, right card — one tuple per row.
        self._card_rows = (
            (self._build_hero(), self._build_charge_limit_group()),
            (self._build_controls_card(), self._build_abm_group()),
            (self._build_battery_group(), self._build_runtime_group()),
        )
        self._two_columns = True
        self._attach_cards(two_columns=True)

        # One column when the window is too narrow to hold two.
        breakpoint_ = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse(f"max-width: {NARROW_WIDTH}px")
        )
        breakpoint_.connect("apply", lambda *_a: self._attach_cards(two_columns=False))
        breakpoint_.connect("unapply", lambda *_a: self._attach_cards(two_columns=True))
        self.add_breakpoint(breakpoint_)

        self.refresh()
        self._refresh_timeout = GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)
        # Switching language replaces this window while the app keeps running,
        # so its timers have to go with it rather than outlive the widgets.
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, *_args) -> bool:
        for attr in (
            "_refresh_timeout",
            "_charge_timeout",
            "_abm_timeout",
            "_cpu_timeout",
        ):
            source = getattr(self, attr, 0)
            if source:
                GLib.source_remove(source)
                setattr(self, attr, 0)
        return False

    def _attach_cards(self, two_columns: bool) -> None:
        """Place the cards in one or two columns, reusing the same widgets."""
        for left, right in self._card_rows:
            for card in (left, right):
                if card.get_parent() is self._grid:
                    self._grid.remove(card)
                # Cards stretch to their row height only when paired.
                card.set_vexpand(two_columns)

        row = 0
        for left, right in self._card_rows:
            if two_columns:
                self._grid.attach(left, 0, row, 1, 1)
                self._grid.attach(right, 1, row, 1, 1)
                row += 1
            else:
                self._grid.attach(left, 0, row, 2, 1)
                self._grid.attach(right, 0, row + 1, 2, 1)
                row += 2
        self._two_columns = two_columns

    # --- construction -------------------------------------------------------

    @staticmethod
    def _info_button(text: str) -> Gtk.MenuButton:
        """Small 'i' next to a group title; click reveals the explanation."""
        label = Gtk.Label(label=text)
        label.set_wrap(True)
        label.set_max_width_chars(38)
        label.set_xalign(0)
        label.set_margin_top(10)
        label.set_margin_bottom(10)
        label.set_margin_start(12)
        label.set_margin_end(12)

        popover = Gtk.Popover()
        popover.set_child(label)

        button = Gtk.MenuButton(icon_name="help-about-symbolic")
        button.set_popover(popover)
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(text)
        return button

    def _build_header(self) -> Gtk.Widget:
        header = Adw.HeaderBar()

        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text(_("Refresh"))
        refresh.connect("clicked", lambda *_a: self.refresh())
        header.pack_start(refresh)

        menu = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu.set_tooltip_text(_("Main menu"))
        model = Gio_menu()
        menu.set_menu_model(model)
        header.pack_end(menu)

        return header

    def _build_hero(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_margin_top(28)
        inner.set_margin_bottom(28)
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        inner.set_vexpand(True)
        inner.set_valign(Gtk.Align.CENTER)
        card.append(inner)

        self._watt_label = Gtk.Label(label="—")
        self._watt_label.add_css_class("title-1")
        inner.append(self._watt_label)

        self._watt_caption = Gtk.Label(label=_("Power draw"))
        self._watt_caption.add_css_class("dim-label")
        inner.append(self._watt_caption)

        self._battery_percent = 0.0
        self._battery_charging = False
        self._last_watts: float | None = None
        self._battery_area = Gtk.DrawingArea()
        self._battery_area.set_content_width(240)
        self._battery_area.set_content_height(58)
        self._battery_area.set_halign(Gtk.Align.CENTER)
        self._battery_area.set_margin_top(20)
        self._battery_area.set_draw_func(self._draw_battery)
        inner.append(self._battery_area)

        self._percent_label = Gtk.Label(label="")
        self._percent_label.add_css_class("heading")
        self._percent_label.set_margin_top(8)
        inner.append(self._percent_label)

        self._mode_caption = Gtk.Label(label="")
        self._mode_caption.add_css_class("dim-label")
        self._mode_caption.add_css_class("caption")
        self._mode_caption.set_wrap(True)
        self._mode_caption.set_justify(Gtk.Justification.CENTER)
        inner.append(self._mode_caption)

        return card

    def _make_segmented(
        self, items: tuple[tuple[str, str], ...], handler, store: dict
    ) -> Gtk.Widget:
        """A linked row of mutually exclusive toggles."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.add_css_class("linked")
        box.set_homogeneous(True)

        first: Gtk.ToggleButton | None = None
        for key, label in items:
            button = Gtk.ToggleButton(label=label)
            button.set_can_shrink(True)
            button.set_tooltip_text(label)
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.connect("toggled", handler, key)
            store[key] = button
            box.append(button)
        return box

    @staticmethod
    def _make_card() -> tuple[Gtk.Box, Gtk.Box]:
        """A padded card; returns (card, content box to fill)."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("card")

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        inner.set_margin_top(20)
        inner.set_margin_bottom(20)
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        # The card stretches to the row height; each block pins its title and
        # centres its own content in whatever space is left.
        inner.set_vexpand(True)
        card.append(inner)
        return card, inner

    def _control_block(
        self, title: str, control: Gtk.Widget, info: str | None = None
    ) -> Gtk.Widget:
        """One titled control inside the card."""
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        label.set_hexpand(True)
        label.add_css_class("heading")
        header.append(label)
        if info:
            header.append(self._info_button(info))

        block.append(header)
        # Some cards retitle themselves as the machine's state changes.
        block.title_label = label

        control.set_vexpand(True)
        control.set_valign(Gtk.Align.CENTER)
        block.append(control)

        block.set_vexpand(True)
        return block

    def _build_cpu_limit_block(self) -> Gtk.Widget:
        """Slider over the frequency ceilings this processor actually offers.

        Positions are step indexes, not kilohertz: the steps are rarely evenly
        spaced, and an index scale gives each one the same width.
        """
        steps = self._cpu_limits.steps
        self._cpu_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, max(1, len(steps) - 1), 1
        )
        self._cpu_scale.set_draw_value(False)
        self._cpu_scale.set_hexpand(True)
        for index, khz in enumerate(steps):
            label = _format_ghz(khz) if self._label_cpu_step(index, len(steps)) else None
            self._cpu_scale.add_mark(index, Gtk.PositionType.BOTTOM, label)
        self._cpu_scale.connect("value-changed", self._on_cpu_scale_changed)

        self._cpu_block = self._control_block(
            _("CPU speed limit"),
            self._cpu_scale,
            _(
                "Caps how fast the processor may run. The system mode sets it: "
                "battery saving picks the lowest step, full performance the "
                "highest, and automatic uses the lowest on battery and the "
                "highest on AC. Move the slider to override the limit for the "
                "power source in use; the next mode change resets it. A lower "
                "cap means less heat and a quieter fan, but work that takes "
                "twice as long can end up costing more energy, not less."
            ),
        )
        return self._cpu_block

    @staticmethod
    def _label_cpu_step(index: int, count: int) -> bool:
        """Label every mark when there are few, else thin them out."""
        if count <= CPU_LABEL_ALL_UP_TO:
            return True
        return index in (0, count - 1) or index % 2 == 0

    def _build_controls_card(self) -> Gtk.Widget:
        """Mode, Wi-Fi and device sleep share one card: all three pick how
        aggressively the machine saves power."""
        card, inner = self._make_card()

        inner.append(
            self._control_block(
                _("System mode"),
                self._make_segmented(
                    (
                        ("auto", _("Automatic")),
                        ("bat", _("Battery saving")),
                        ("ac", _("Full performance")),
                    ),
                    self._on_mode_toggled,
                    self._mode_buttons,
                ),
            )
        )

        self._wifi_block = self._control_block(
            _("Wi-Fi power saving"),
            self._make_segmented(
                (("auto", _("Automatic")), ("on", _("On")), ("off", _("Off"))),
                self._on_wifi_toggled,
                self._wifi_buttons,
            ),
            _(
                "Automatic keeps the radio awake on AC and lets it sleep on "
                "battery, which is TLP's default. Saving costs a little "
                "latency, and a few chipsets drop the connection when it is "
                "enabled — turn it off if your Wi-Fi becomes unreliable."
            ),
        )
        inner.append(self._wifi_block)

        self._runtime_pm_block = self._control_block(
            _("Sleep idle devices"),
            self._make_segmented(
                (("auto", _("Automatic")), ("on", _("On")), ("off", _("Off"))),
                self._on_runtime_pm_toggled,
                self._runtime_pm_buttons,
            ),
            _(
                "Lets idle PCI devices — the card reader, the sound chip, "
                "controllers — power down between uses. Automatic keeps them "
                "awake on AC and lets them sleep on battery. Individual "
                "devices can be exempted in the TLP configuration; the panel "
                "leaves those exemptions untouched."
            ),
        )
        inner.append(self._runtime_pm_block)

        return card

    def _build_charge_limit_group(self) -> Gtk.Widget:
        """Slider for the charge stop threshold. Hidden if unsupported."""
        self._charge_card, inner = self._make_card()

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        self._charge_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, CHARGE_MIN, CHARGE_MAX, CHARGE_STEP
        )
        self._charge_scale.set_draw_value(False)
        self._charge_scale.set_hexpand(True)
        for mark in range(CHARGE_MIN, CHARGE_MAX + 1, CHARGE_STEP):
            label = f"{mark}%" if mark % 10 == 0 else None
            self._charge_scale.add_mark(mark, Gtk.PositionType.BOTTOM, label)
        self._charge_scale.connect("value-changed", self._on_charge_scale_changed)
        content.append(self._charge_scale)

        # A one-off top-up belongs with the limit it temporarily overrides.
        self._btn_fullcharge = Gtk.Button(label=_("Charge to 100% once"))
        self._btn_fullcharge.add_css_class("destructive-action")
        self._btn_fullcharge.set_halign(Gtk.Align.CENTER)
        self._btn_fullcharge.set_margin_top(6)
        self._btn_fullcharge.connect("clicked", self._on_full_charge)
        content.append(self._btn_fullcharge)

        inner.append(
            self._control_block(
                _("Charge limit"),
                content,
                _(
                    "Lithium batteries age faster when kept near a full charge. "
                    "Stopping at 80% trades some runtime for a longer service life. "
                    "The slider writes the limit to the battery firmware, so it "
                    "survives reboots."
                ),
            )
        )
        return self._charge_card

    def _build_abm_group(self) -> Gtk.Widget:
        """The two display-and-processor ceilings: CPU speed, then adaptive
        backlight on AC and on battery.

        Either block can be unsupported on a given machine, so the card
        follows whichever ones remain visible.
        """
        self._abm_card, inner = self._make_card()

        inner.append(self._build_cpu_limit_block())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._abm_scales: dict[str, Gtk.Scale] = {}

        for key, label_text in (("ac", _("On AC power")), ("bat", _("On battery"))):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            label.add_css_class("caption")
            label.add_css_class("dim-label")
            content.append(label)

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, ABM_MAX, 1)
            scale.set_draw_value(False)
            scale.set_hexpand(True)
            for level in range(ABM_MAX + 1):
                scale.add_mark(level, Gtk.PositionType.BOTTOM, str(level))
            scale.connect("value-changed", self._on_abm_changed)
            self._abm_scales[key] = scale
            content.append(scale)

        self._abm_block = self._control_block(
            _("Adaptive backlight"),
            content,
            _(
                "The panel dims and shifts contrast to save power. Higher "
                "levels save more but wash out colours. 0 turns it off. "
                "Most people leave it off on AC and low on battery."
            ),
        )
        inner.append(self._abm_block)
        return self._abm_card

    @staticmethod
    def _property_row(title: str) -> tuple[Gtk.Widget, Gtk.Label]:
        """A name/value line; returns (row, value label)."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        name = Gtk.Label(label=title)
        name.set_xalign(0)
        name.add_css_class("dim-label")
        row.append(name)

        value = Gtk.Label(label="—")
        value.set_xalign(1)
        value.set_hexpand(True)
        value.set_selectable(True)
        row.append(value)
        return row, value

    def _build_battery_group(self) -> Gtk.Widget:
        card, inner = self._make_card()

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        row, self._val_health = self._property_row(_("Health"))
        content.append(row)
        row, self._val_cycles = self._property_row(_("Cycles"))
        content.append(row)
        row, self._val_limit = self._property_row(_("Charge limit"))
        content.append(row)

        inner.append(self._control_block(_("Battery"), content))
        return card

    def _build_runtime_group(self) -> Gtk.Widget:
        card, inner = self._make_card()

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        row, self._val_runtime_now = self._property_row(_("Right now"))
        content.append(row)
        self._row_runtime_capped, self._val_runtime_capped = self._property_row(
            _("At the charge limit")
        )
        content.append(self._row_runtime_capped)
        row, self._val_runtime_full = self._property_row(_("At 100%"))
        content.append(row)

        block = self._control_block(_("Estimated runtime"), content)
        self._runtime_title = block.title_label
        inner.append(block)
        return card

    @staticmethod
    def _level_colour(percent: float) -> tuple[float, float, float]:
        """Blue while healthy, sliding to amber then red as the charge drops."""

        def mix(a, b, t):
            return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

        blue = (0.21, 0.52, 0.89)
        amber = (0.96, 0.83, 0.18)
        red = (0.88, 0.11, 0.14)

        # Blue steps straight to amber at the threshold: interpolating between
        # them in RGB would pass through a muddy green.
        if percent >= LEVEL_GOOD:
            return blue
        span = max(0.0, percent) / LEVEL_GOOD
        return mix(red, amber, span)

    @staticmethod
    def _rounded_rect(cr, x, y, width, height, radius) -> None:
        radius = min(radius, width / 2, height / 2)
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -1.5708, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
        cr.arc(x + radius, y + height - radius, radius, 1.5708, 3.1416)
        cr.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        cr.close_path()

    def _draw_battery(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        """A battery outline whose interior fills with the current charge."""
        fg = area.get_color()  # follows the theme, light or dark

        nub_w = max(4.0, width * 0.022)
        border = 2.5
        body_w = width - nub_w - 2
        body_h = height
        radius = body_h * 0.28

        # shell
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
        cr.set_line_width(border)
        self._rounded_rect(cr, border / 2, border / 2, body_w - border, body_h - border, radius)
        cr.stroke()

        # terminal
        nub_h = body_h * 0.38
        self._rounded_rect(
            cr, body_w + 1, (body_h - nub_h) / 2, nub_w, nub_h, nub_w * 0.45
        )
        cr.fill()

        # charge
        inset = border + 2.5
        usable = body_w - 2 * inset
        fill_w = usable * max(0.0, min(100.0, self._battery_percent)) / 100.0
        if fill_w > 0.5:
            red, green, blue = self._level_colour(self._battery_percent)
            cr.set_source_rgb(red, green, blue)
            self._rounded_rect(
                cr, inset, inset, max(fill_w, radius * 0.6), body_h - 2 * inset, radius * 0.55
            )
            cr.fill()

        # percentage, written inside the shell
        text = f"{int(round(self._battery_percent))}%"
        cr.select_font_face("Cantarell", 0, 1)  # normal slant, bold weight
        cr.set_font_size(body_h * 0.42)
        extents = cr.text_extents(text)

        bolt_w = body_h * 0.34 if self._battery_charging else 0.0
        gap = body_h * 0.12 if self._battery_charging else 0.0
        total_w = extents.width + bolt_w + gap
        start_x = body_w / 2 - total_w / 2
        mid_y = body_h / 2

        def paint_contents() -> None:
            if self._battery_charging:
                unit = body_h * 0.24
                bx = start_x + bolt_w / 2
                cr.move_to(bx + unit * 0.25, mid_y - unit)
                cr.line_to(bx - unit * 0.55, mid_y + unit * 0.12)
                cr.line_to(bx - unit * 0.02, mid_y + unit * 0.12)
                cr.line_to(bx - unit * 0.25, mid_y + unit)
                cr.line_to(bx + unit * 0.55, mid_y - unit * 0.12)
                cr.line_to(bx + unit * 0.02, mid_y - unit * 0.12)
                cr.close_path()
                cr.fill()

            cr.move_to(
                start_x + bolt_w + gap - extents.x_bearing,
                mid_y - extents.height / 2 - extents.y_bearing,
            )
            cr.show_text(text)

        # Drawn twice, clipped either side of the fill edge: white over the
        # coloured part, theme colour over the empty part. A single colour
        # would vanish wherever the text crosses that edge.
        fill_edge = inset + fill_w

        cr.save()
        cr.rectangle(0, 0, fill_edge, body_h)
        cr.clip()
        cr.set_source_rgb(1, 1, 1)
        paint_contents()
        cr.restore()

        cr.save()
        cr.rectangle(fill_edge, 0, body_w - fill_edge, body_h)
        cr.clip()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.85)
        paint_contents()
        cr.restore()

    # --- refresh ------------------------------------------------------------

    def _tick(self) -> bool:
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def refresh(self) -> None:
        try:
            state = backend.read_power_state()
        except Exception:  # pragma: no cover - defensive, keep the UI alive
            self._banner.set_title(_("Reading power state failed"))
            self._banner.set_revealed(True)
            return

        self._update_banner(state)
        self._update_hero(state)
        self._update_battery(state)
        self._update_charge_limit(state)
        self._update_runtime(state)
        self._update_mode(state)
        self._update_cpu_limit(state)
        self._update_wifi(state)
        self._update_abm(state)
        self._update_runtime_pm(state)

    def _update_banner(self, state: backend.PowerState) -> None:
        if not state.tlp.installed:
            self._banner.set_title(
                f"{_('TLP is not installed')} — {_('Install it with: sudo apt install tlp')}"
            )
            self._banner.set_revealed(True)
            for button in list(self._mode_buttons.values()) + [self._btn_fullcharge]:
                button.set_sensitive(False)
            return
        if state.tlp.enabled is False:
            self._banner.set_title(_("TLP is installed but disabled"))
            self._banner.set_revealed(True)
            return
        if not state.batteries:
            self._banner.set_title(_("No battery found"))
            self._banner.set_revealed(True)
            return
        self._banner.set_revealed(False)

    def _update_hero(self, state: backend.PowerState) -> None:
        watts = state.total_power_w
        battery = state.battery

        # Right after the cable moves, the controller reports 0 W for a
        # second or two. Hold the previous figure while current should be
        # flowing, rather than blanking the headline number.
        if watts:
            self._last_watts = watts
        elif battery is None or not (battery.charging or battery.discharging):
            self._last_watts = None

        shown = watts or self._last_watts
        self._watt_label.set_label(f"{shown:.2f} W" if shown else "—")

        # While charging the battery reports charge power, not what the system
        # is consuming — labelling both the same way would be misleading.
        if battery and battery.charging:
            self._watt_caption.set_label(_("Charge power"))
        elif battery and battery.discharging:
            self._watt_caption.set_label(_("Power draw"))
        else:
            self._watt_caption.set_label(_("Idle on AC"))

        if battery and battery.percent is not None:
            self._battery_percent = float(battery.percent)
            self._battery_charging = battery.charging
            self._battery_area.queue_draw()
            status_key = (battery.status or "unknown").lower()
            status = _(STATUS_LABELS.get(status_key, battery.status or ""))
            parts = [status]
            # Time left either way: until empty when discharging, until the
            # charge limit when charging.
            remaining = format_duration(battery.runtime_hours) or format_duration(
                battery.charge_hours
            )
            if remaining:
                parts.append(remaining)
            self._percent_label.set_label(" · ".join(parts))
        else:
            self._battery_percent = 0.0
            self._battery_area.queue_draw()
            self._percent_label.set_label("—")

        if state.on_ac:
            self._mode_caption.set_label(_("On AC power"))
        elif state.on_ac is False:
            self._mode_caption.set_label(_("On battery"))
        else:
            self._mode_caption.set_label("")

    def _update_battery(self, state: backend.PowerState) -> None:
        battery = state.battery
        if battery is None:
            for value in (self._val_health, self._val_cycles, self._val_limit):
                value.set_label("—")
            return

        if battery.health_percent is not None:
            self._val_health.set_label(
                f"{battery.health_percent:.0f}%  "
                f"({battery.energy_full_wh:.1f} / {battery.energy_design_wh:.1f} Wh)"
            )
        else:
            self._val_health.set_label("—")

        self._val_cycles.set_label(
            str(battery.cycle_count) if battery.cycle_count is not None else "—"
        )

        if battery.stop_threshold is not None:
            if battery.start_threshold is not None:
                self._val_limit.set_label(
                    f"{battery.start_threshold}% – {battery.stop_threshold}%"
                )
            else:
                self._val_limit.set_label(f"{battery.stop_threshold}%")
        else:
            self._val_limit.set_label("—")

    def _update_charge_limit(self, state: backend.PowerState) -> None:
        battery = state.battery
        supported = battery is not None and battery.stop_threshold is not None
        self._charge_card.set_visible(bool(supported))
        if not supported:
            return

        self._current_start = battery.start_threshold
        self._current_stop = battery.stop_threshold

        if not self._charge_user_touched:
            self._suppress_charge = True
            self._charge_scale.set_value(battery.stop_threshold)
            self._suppress_charge = False

    def _on_charge_scale_changed(self, *_args) -> None:
        """Snap to whole steps, then apply once the user stops dragging."""
        if self._suppress_charge:
            return

        raw = self._charge_scale.get_value()
        snapped = round(raw / CHARGE_STEP) * CHARGE_STEP
        if snapped != raw:
            self._suppress_charge = True
            self._charge_scale.set_value(snapped)
            self._suppress_charge = False

        self._charge_user_touched = True
        if self._charge_timeout:
            GLib.source_remove(self._charge_timeout)
        self._charge_timeout = GLib.timeout_add(
            CHARGE_APPLY_DELAY_MS, self._apply_charge_after_delay
        )

    def _apply_charge_after_delay(self) -> bool:
        self._charge_timeout = 0
        self._suppress_abm = False
        self._abm_user_touched = False
        self._abm_timeout = 0
        self._suppress_wifi = False
        self._suppress_runtime_pm = False
        stop = int(round(self._charge_scale.get_value()))
        if self._current_stop is not None and stop == self._current_stop:
            self._charge_user_touched = False
            return GLib.SOURCE_REMOVE
        if self._busy:
            # Try again once the running action finishes.
            self._charge_timeout = GLib.timeout_add(
                CHARGE_APPLY_DELAY_MS, self._apply_charge_after_delay
            )
            return GLib.SOURCE_REMOVE

        start = max(0, stop - 5)

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            # Either way, let the next refresh resync the slider with hardware.
            self._charge_user_touched = False
            if ok:
                self._toasts.add_toast(
                    Adw.Toast.new(f"{_('Charge limit set to')} {stop}%")
                )
            else:
                self._toasts.add_toast(
                    Adw.Toast.new(message or _("Authentication failed or was cancelled"))
                )
            self.refresh()

        self._set_busy(True)
        actions.set_charge_thresholds(start, stop, done)
        return GLib.SOURCE_REMOVE

    def _update_runtime(self, state: backend.PowerState) -> None:
        battery = state.battery
        if battery is None:
            for value in (
                self._val_runtime_now,
                self._val_runtime_capped,
                self._val_runtime_full,
            ):
                value.set_label("—")
            return

        limit = battery.stop_threshold
        capped_shown = bool(battery.energy_full_wh and limit and limit < 100)
        self._row_runtime_capped.set_visible(capped_shown)

        # Keyed on the cable, not on whether current is flowing: a pack
        # sitting at its charge limit reports "not charging", and the card
        # should still be answering the charging question.
        if state.on_ac:
            # With the cable in, power_now is the charge rate, so the
            # machine's own consumption is unknown.
            self._runtime_title.set_label(_("Estimated charging time"))
            self._val_runtime_now.set_label("—")

            if capped_shown:
                to_limit = battery.charge_hours_to(battery.limit_energy_wh)
                self._val_runtime_capped.set_label(
                    f"{format_duration(to_limit) or '—'}  ({limit}%)"
                )
            if battery.energy_full_wh:
                to_full = battery.charge_hours_to(battery.energy_full_wh)
                self._val_runtime_full.set_label(format_duration(to_full) or "—")
            else:
                self._val_runtime_full.set_label("—")
            return

        self._runtime_title.set_label(_("Estimated runtime"))
        self._val_runtime_now.set_label(format_duration(battery.runtime_hours) or "—")

        if battery.energy_full_wh:
            if capped_shown:
                capped = battery.projected_hours(battery.limit_energy_wh)
                self._val_runtime_capped.set_label(
                    f"{format_duration(capped) or '—'}  ({limit}%)"
                )
            full = battery.projected_hours(battery.energy_full_wh)
            self._val_runtime_full.set_label(format_duration(full) or "—")
        else:
            self._val_runtime_full.set_label("—")

    def _update_mode(self, state: backend.PowerState) -> None:
        """Reflect the active profile without re-triggering the toggle handler."""
        if state.tlp.manual:
            key = "ac" if state.tlp.manual_mode == backend.MODE_AC else "bat"
        elif state.tlp.mode == backend.MODE_UNKNOWN:
            return
        else:
            key = "auto"

        self._suppress_toggle = True
        button = self._mode_buttons.get(key)
        if button is not None and not button.get_active():
            button.set_active(True)
        self._suppress_toggle = False

    def _sync_settings_card(self) -> None:
        """Hide the shared card only when both of its blocks are gone."""
        self._abm_card.set_visible(
            self._cpu_block.get_visible() or self._abm_block.get_visible()
        )

    def _update_cpu_limit(self, state: backend.PowerState) -> None:
        self._cpu_block.set_visible(
            self._cpu_limits.supported and actions.helper_available()
        )
        self._sync_settings_card()
        if not self._cpu_limits.supported:
            return

        self._on_ac = bool(state.on_ac)
        conf = state.tlp.config
        hardware_max = self._cpu_limits.hardware_max

        for key, name in (
            ("ac", "CPU_SCALING_MAX_FREQ_ON_AC"),
            ("bat", "CPU_SCALING_MAX_FREQ_ON_BAT"),
        ):
            raw = conf.get(name)
            try:
                value = int(raw) if raw else None
            except ValueError:
                value = None
            # Unset or zero means TLP leaves the ceiling alone, which is the
            # hardware maximum.
            self._cpu_conf[key] = value or hardware_max

        if self._cpu_user_touched:
            return

        current = self._cpu_conf["ac" if self._on_ac else "bat"]
        index = self._cpu_limits.steps.index(self._cpu_limits.nearest(current))
        self._suppress_cpu = True
        self._cpu_scale.set_value(index)
        self._suppress_cpu = False

    def _on_cpu_scale_changed(self, *_args) -> None:
        """Snap to a whole step, then apply once the user stops dragging."""
        if self._suppress_cpu:
            return

        raw = self._cpu_scale.get_value()
        snapped = round(raw)
        if snapped != raw:
            self._suppress_cpu = True
            self._cpu_scale.set_value(snapped)
            self._suppress_cpu = False

        self._cpu_user_touched = True
        if self._cpu_timeout:
            GLib.source_remove(self._cpu_timeout)
        self._cpu_timeout = GLib.timeout_add(SETTING_APPLY_DELAY_MS, self._apply_cpu_limit)

    def _apply_cpu_limit(self) -> bool:
        self._cpu_timeout = 0
        if self._busy:
            self._cpu_timeout = GLib.timeout_add(
                SETTING_APPLY_DELAY_MS, self._apply_cpu_limit
            )
            return GLib.SOURCE_REMOVE

        steps = self._cpu_limits.steps
        index = max(0, min(len(steps) - 1, int(round(self._cpu_scale.get_value()))))
        chosen = steps[index]

        # The slider edits the source in use; the other one keeps its ceiling.
        fallback = self._cpu_limits.hardware_max
        ac = chosen if self._on_ac else (self._cpu_conf["ac"] or fallback)
        bat = (self._cpu_conf["bat"] or fallback) if self._on_ac else chosen

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            self._cpu_user_touched = False
            self._toast_result(ok, message, N_("CPU speed limit updated"))

        self._set_busy(True)
        actions.set_cpu_freq_limits(int(ac), int(bat), done)
        return GLib.SOURCE_REMOVE

    def _update_abm(self, state: backend.PowerState) -> None:
        conf = state.tlp.config
        supported = backend.read_abm_level() is not None
        self._abm_block.set_visible(supported and actions.helper_available())
        self._sync_settings_card()

        # The knob may exist while the hardware ignores it entirely; the
        # sliders then stay greyed out rather than pretending to work.
        effective = backend.abm_supported()
        for scale in self._abm_scales.values():
            scale.set_sensitive(effective is not False)

        if not supported or self._abm_user_touched:
            return

        self._suppress_abm = True
        for key, suffix in (("ac", "ON_AC"), ("bat", "ON_BAT")):
            raw = conf.get(f"AMDGPU_ABM_LEVEL_{suffix}")
            try:
                value = int(raw) if raw is not None else 0
            except ValueError:
                value = 0
            self._abm_scales[key].set_value(max(0, min(ABM_MAX, value)))
        self._suppress_abm = False

    def _on_abm_changed(self, *_args) -> None:
        if self._suppress_abm:
            return
        self._abm_user_touched = True
        if self._abm_timeout:
            GLib.source_remove(self._abm_timeout)
        self._abm_timeout = GLib.timeout_add(SETTING_APPLY_DELAY_MS, self._apply_abm)

    def _apply_abm(self) -> bool:
        self._abm_timeout = 0
        if self._busy:
            self._abm_timeout = GLib.timeout_add(SETTING_APPLY_DELAY_MS, self._apply_abm)
            return GLib.SOURCE_REMOVE

        ac = int(round(self._abm_scales["ac"].get_value()))
        bat = int(round(self._abm_scales["bat"].get_value()))

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            self._abm_user_touched = False
            self._toast_result(ok, message, N_("Adaptive backlight updated"))

        self._set_busy(True)
        actions.set_abm_levels(ac, bat, done)
        return GLib.SOURCE_REMOVE

    def _update_wifi(self, state: backend.PowerState) -> None:
        conf = state.tlp.config
        self._wifi_block.set_visible(
            bool(backend.read_wifi_powersave()) and actions.helper_available()
        )

        ac = conf.get("WIFI_PWR_ON_AC")
        bat = conf.get("WIFI_PWR_ON_BAT")
        if ac is None or bat is None:
            return

        if ac == "off" and bat == "on":
            key = "auto"
        elif ac == "on" and bat == "on":
            key = "on"
        elif ac == "off" and bat == "off":
            key = "off"
        else:
            # Any other combination is user-made; leave the buttons alone.
            return

        self._suppress_wifi = True
        button = self._wifi_buttons.get(key)
        if button is not None and not button.get_active():
            button.set_active(True)
        self._suppress_wifi = False
        self._suppress_runtime_pm = False

    def _on_wifi_toggled(self, button: Gtk.ToggleButton, key: str) -> None:
        if self._suppress_wifi or not button.get_active() or self._busy:
            return

        pairs = {"off": ("off", "off"), "auto": ("off", "on"), "on": ("on", "on")}
        ac, bat = pairs[key]

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            self._toast_result(ok, message, N_("Wi-Fi power saving updated"))

        self._set_busy(True)
        actions.set_wifi_power_saving(ac, bat, done)

    def _toast_result(self, ok: bool, message: str, success_text: str) -> None:
        if ok:
            self._toasts.add_toast(Adw.Toast.new(_(success_text)))
        else:
            self._toasts.add_toast(
                Adw.Toast.new(message or _("Authentication failed or was cancelled"))
            )
        self.refresh()

    def _update_runtime_pm(self, state: backend.PowerState) -> None:
        conf = state.tlp.config
        self._runtime_pm_block.set_visible(actions.helper_available())

        ac = conf.get("RUNTIME_PM_ON_AC")
        bat = conf.get("RUNTIME_PM_ON_BAT")

        if ac is None or bat is None:
            return

        # 'auto' means the device may sleep, so it is the saving state.
        if ac == "on" and bat == "auto":
            key = "auto"
        elif ac == "auto" and bat == "auto":
            key = "on"
        elif ac == "on" and bat == "on":
            key = "off"
        else:
            return

        self._suppress_runtime_pm = True
        button = self._runtime_pm_buttons.get(key)
        if button is not None and not button.get_active():
            button.set_active(True)
        self._suppress_runtime_pm = False

    def _on_runtime_pm_toggled(self, button: Gtk.ToggleButton, key: str) -> None:
        if self._suppress_runtime_pm or not button.get_active() or self._busy:
            return

        pairs = {"off": ("on", "on"), "auto": ("on", "auto"), "on": ("auto", "auto")}
        ac, bat = pairs[key]

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            self._toast_result(ok, message, N_("Idle device sleep updated"))

        self._set_busy(True)
        actions.set_runtime_pm(ac, bat, done)

    # --- actions ------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in list(self._mode_buttons.values()) + [self._btn_fullcharge]:
            button.set_sensitive(not busy)
        self._charge_scale.set_sensitive(not busy)
        self._cpu_scale.set_sensitive(not busy)

    def _run(self, func, success_message: str) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def done(ok: bool, message: str) -> None:
            self._set_busy(False)
            if ok:
                self._toasts.add_toast(Adw.Toast.new(_(success_message)))
            else:
                self._toasts.add_toast(
                    Adw.Toast.new(message or _("Authentication failed or was cancelled"))
                )
            self.refresh()

        func(done)

    def _on_mode_toggled(self, button: Gtk.ToggleButton, key: str) -> None:
        if self._suppress_toggle or not button.get_active():
            return
        # The preset rewrites the frequency ceilings, so let the slider follow
        # it again even if the user had moved it by hand.
        self._cpu_user_touched = False
        if self._cpu_timeout:
            GLib.source_remove(self._cpu_timeout)
            self._cpu_timeout = 0
        messages = {
            "auto": N_("Mode switched to automatic"),
            "bat": N_("Battery saving applied"),
            "ac": N_("Full performance applied"),
        }
        self._run(
            lambda done: actions.apply_mode_preset(key, done),
            messages[key],
        )

    def _on_full_charge(self, *_args) -> None:
        self._run(actions.full_charge, N_("Charging to 100% this time"))


def Gio_menu():
    """Build the header menu model."""
    from gi.repository import Gio

    languages = Gio.Menu()
    for code, label in [(i18n.AUTO, _("System default"))] + [
        (code, i18n.LANGUAGE_NAMES.get(code, code)) for code in i18n.available_languages()
    ]:
        item = Gio.MenuItem.new(label, None)
        # A target turns these into a radio group tied to the action's state.
        item.set_action_and_target_value("app.language", GLib.Variant("s", code))
        languages.append_item(item)

    menu = Gio.Menu()
    menu.append_submenu(_("Language"), languages)
    menu.append(_("About"), "app.about")
    return menu
