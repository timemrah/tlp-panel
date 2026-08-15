"""Application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from . import APP_ID, about  # noqa: E402
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

    def _on_about(self, *_args) -> None:
        if self._window:
            about.build(self._window)


def main() -> int:
    app = TlpPanelApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
