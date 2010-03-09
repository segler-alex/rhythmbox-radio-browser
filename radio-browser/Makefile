DESTDIR=
SUBDIR=/usr/lib/rhythmbox/plugins/radio-browser/

all:
clean:
	- rm radio-browser.pyc

install:
	install -d $(DESTDIR)$(SUBDIR)
	install -m 644 *.py $(DESTDIR)$(SUBDIR)
	install -m 644 *.png $(DESTDIR)$(SUBDIR)
	install -m 644 radio-browser.rb-plugin $(DESTDIR)$(SUBDIR)
	install -m 644 prefs.ui $(DESTDIR)$(SUBDIR)
