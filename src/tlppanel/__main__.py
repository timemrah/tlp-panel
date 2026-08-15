"""Application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib  # noqa: E402

from . import APP_ID, about, i18n  # noqa: E402
from .i18n import _  # noqa: E402
from .window import TlpPanelWindow  # noqa: E402


class TlpPanelApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._window: TlpPanelWindow | None = None

    def do_activate(self):  # noqa: N802 - GObject naming
        if self._window is None:
            self._window = TlpPanelWindow(application=self)
        self._window.present()

    def do_startup(self):  # noqa: N802 - GObject naming
        Adw.Application.do_startup(self)
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        language_action = Gio.SimpleAction.new_stateful(
            "language",
            GLib.VariantType.new("s"),
            GLib.Variant("s", i18n.choice()),
        )
        language_action.connect("activate", self._on_language)
        self.add_action(language_action)

    def _on_about(self, *_args) -> None:
        if self._window:
            about.build(self._window)

    def _on_language(self, action: Gio.SimpleAction, target: GLib.Variant) -> None:
        """Switch language by rebuilding the window.

        Every label is translated where its widget is built, so there is
        nothing to retranslate in place — a fresh window is both simpler and
        exactly as correct.
        """
        code = target.get_string()
        if code == i18n.choice():
            return

        i18n.save_choice(code)
        i18n.set_language(code)
        action.set_state(GLib.Variant("s", i18n.choice()))

        previous = self._window
        self._window = TlpPanelWindow(application=self)
        if previous is not None:
            self._window.set_default_size(*previous.get_default_size())
        self._window.present()
        if previous is not None:
            previous.close()


def main() -> int:
    app = TlpPanelApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
