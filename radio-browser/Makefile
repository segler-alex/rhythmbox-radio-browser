DESTDIR=
SUBDIR=/usr/lib/rhythmbox/plugins/radio-browser/

all:
clean:
	- rm radio-browser.pyc

install:
	install -d $(DESTDIR)$(SUBDIR)
	install radio-browser.py $(DESTDIR)$(SUBDIR)
	install radio-browser.rb-plugin $(DESTDIR)$(SUBDIR)
	install prefs.ui $(DESTDIR)$(SUBDIR)
	install xiph-logo.png $(DESTDIR)$(SUBDIR)
	install shoutcast-logo.ico $(DESTDIR)$(SUBDIR)
	install clef.png $(DESTDIR)$(SUBDIR)
