DESTDIR=
SUBDIR=/usr/lib/rhythmbox/plugins/radio-browser/
LOCALEDIR=/usr/share/locale/

all:
clean:
	- rm *.pyc

install:
	install -d $(DESTDIR)$(SUBDIR)
	install -m 644 *.py $(DESTDIR)$(SUBDIR)
	install -m 644 *.png $(DESTDIR)$(SUBDIR)
	install -m 644 radio-browser.rb-plugin $(DESTDIR)$(SUBDIR)
	install -m 644 prefs.ui $(DESTDIR)$(SUBDIR)
	cd lang;./lang.sh $(DESTDIR)$(LOCALEDIR)
