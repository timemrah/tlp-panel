"""About dialog.

Hand-built rather than AdwAboutDialog: that widget renders the developer
line as plain text, so the maintainer's address could neither sit beside the
name nor be a link. Everything AdwAboutDialog would have provided for this
project fits in the rows below.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from . import APP_ID, __version__  # noqa: E402
from .i18n import _  # noqa: E402

DEVELOPER = "Mehmet Emrah Tunçel"
EMAIL = "timemrah@gmail.com"
PROJECT_URL = "https://github.com/timemrah/tlp-panel"
ISSUES_URL = f"{PROJECT_URL}/issues"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

# The theme accent colours links, and that accent is whatever the user chose.
# This one is fixed to the blue of the application icon.
LINK_COLOUR = "#3584e4"


def _link_row(title: str, url: str) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title)
    row.set_activatable(True)
    row.add_suffix(Gtk.Image.new_from_icon_name("adw-external-link-symbolic"))
    row.connect("activated", lambda *_a: Gtk.UriLauncher.new(url).launch(None, None, None, None))
    return row


def build(parent: Gtk.Window) -> Adw.Dialog:
    dialog = Adw.Dialog()
    dialog.set_title(_("About"))
    dialog.set_content_width(400)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.add_css_class("flat")
    toolbar.add_top_bar(header)
    dialog.set_child(toolbar)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(12)
    box.set_margin_bottom(24)
    box.set_margin_start(24)
    box.set_margin_end(24)
    toolbar.set_content(box)

    icon = Gtk.Image.new_from_icon_name(APP_ID)
    icon.set_pixel_size(112)
    box.append(icon)

    name = Gtk.Label(label=_("TLP Panel"))
    name.add_css_class("title-1")
    name.set_margin_top(6)
    box.append(name)

    # One line, with the address as a coloured link beside the name.
    byline = Gtk.Label()
    byline.set_use_markup(True)
    byline.set_markup(
        f'{DEVELOPER} · <a href="mailto:{EMAIL}">'
        f'<span foreground="{LINK_COLOUR}">{EMAIL}</span></a>'
    )
    byline.set_wrap(True)
    byline.set_justify(Gtk.Justification.CENTER)
    box.append(byline)

    version = Gtk.Label(label=__version__)
    version.add_css_class("caption")
    version.add_css_class("dim-label")
    version.set_margin_bottom(10)
    box.append(version)

    rows = Gtk.ListBox()
    rows.set_selection_mode(Gtk.SelectionMode.NONE)
    rows.add_css_class("boxed-list")
    rows.append(_link_row(_("Project page"), PROJECT_URL))
    rows.append(_link_row(_("Report an issue"), ISSUES_URL))
    rows.append(_link_row(_("Licence: GPL-3.0-or-later"), LICENSE_URL))
    box.append(rows)

    dialog.present(parent)
    return dialog
