PREFIX ?= /usr/local
DESTDIR ?=

APP_ID := io.github.timemrah.TlpPanel
PYTHON ?= python3

BINDIR := $(DESTDIR)$(PREFIX)/bin
LIBDIR := $(DESTDIR)$(PREFIX)/lib/tlp-panel
DATADIR := $(DESTDIR)$(PREFIX)/share
POLKITDIR := $(DESTDIR)/usr/share/polkit-1/actions

.PHONY: all install uninstall run check clean

all:
	@echo "Nothing to build — pure Python. Run 'make install' (as root) or 'make run'."

run:
	PYTHONPATH=src $(PYTHON) -m tlppanel

check:
	$(PYTHON) -m compileall -q src/tlppanel
	@desktop-file-validate data/$(APP_ID).desktop && echo "desktop file OK"
	@$(PYTHON) -c "import xml.dom.minidom as m; m.parse('data/$(APP_ID).policy')" && echo "polkit policy OK"
	@appstreamcli validate --no-net data/$(APP_ID).metainfo.xml
	@sh -n data/tlp-panel-helper && echo "helper script OK"
	@$(PYTHON) tools/check-translations.py

install:
	install -d $(LIBDIR)/tlppanel
	install -m 644 src/tlppanel/*.py $(LIBDIR)/tlppanel/
	install -d $(BINDIR)
	install -m 755 bin/tlp-panel $(BINDIR)/tlp-panel
	sed -i 's|@LIBDIR@|$(PREFIX)/lib/tlp-panel|' $(BINDIR)/tlp-panel
	install -d $(DATADIR)/applications
	install -m 644 data/$(APP_ID).desktop $(DATADIR)/applications/
	install -d $(DATADIR)/metainfo
	install -m 644 data/$(APP_ID).metainfo.xml $(DATADIR)/metainfo/
	install -d $(DATADIR)/icons/hicolor/scalable/apps
	install -m 644 data/$(APP_ID).svg $(DATADIR)/icons/hicolor/scalable/apps/
	install -d $(POLKITDIR)
	install -m 644 data/$(APP_ID).policy $(POLKITDIR)/
	install -d $(DESTDIR)/usr/libexec
	install -m 755 data/tlp-panel-helper $(DESTDIR)/usr/libexec/tlp-panel-helper
	install -d $(DATADIR)/man/man1
	install -m 644 data/tlp-panel.1 $(DATADIR)/man/man1/tlp-panel.1
ifeq ($(DESTDIR),)
	-gtk-update-icon-cache -f -t $(DATADIR)/icons/hicolor 2>/dev/null
	-update-desktop-database $(DATADIR)/applications 2>/dev/null
	-/usr/libexec/tlp-panel-helper probe >/dev/null 2>&1
endif
	@echo "Installed. Launch it from your app grid or run: tlp-panel"

uninstall:
	rm -rf $(LIBDIR)
	rm -f $(BINDIR)/tlp-panel
	rm -f $(DATADIR)/applications/$(APP_ID).desktop
	rm -f $(DATADIR)/metainfo/$(APP_ID).metainfo.xml
	rm -f $(DATADIR)/icons/hicolor/scalable/apps/$(APP_ID).svg
	rm -f $(DATADIR)/man/man1/tlp-panel.1
	rm -f $(POLKITDIR)/$(APP_ID).policy
	rm -f $(DESTDIR)/usr/libexec/tlp-panel-helper
	rm -rf $(DESTDIR)/var/lib/tlp-panel
	-gtk-update-icon-cache -f -t $(DATADIR)/icons/hicolor 2>/dev/null
	@echo "Removed."

clean:
	find src -name '__pycache__' -type d -exec rm -rf {} +
