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
	install -d $(DESTDIR)$(LOCALEDIR)de/LC_MESSAGES
	install -d $(DESTDIR)$(LOCALEDIR)fr/LC_MESSAGES
	install -d $(DESTDIR)$(LOCALEDIR)es/LC_MESSAGES
	install -d $(DESTDIR)$(LOCALEDIR)it/LC_MESSAGES
	install -d $(DESTDIR)$(LOCALEDIR)bg/LC_MESSAGES
	msgfmt -c lang/de.po -o $(DESTDIR)$(LOCALEDIR)de/LC_MESSAGES/radio-browser.mo
	msgfmt -c lang/fr.po -o $(DESTDIR)$(LOCALEDIR)fr/LC_MESSAGES/radio-browser.mo
	msgfmt -c lang/es.po -o $(DESTDIR)$(LOCALEDIR)es/LC_MESSAGES/radio-browser.mo
	msgfmt -c lang/it.po -o $(DESTDIR)$(LOCALEDIR)it/LC_MESSAGES/radio-browser.mo
	msgfmt -c lang/bg.po -o $(DESTDIR)$(LOCALEDIR)bg/LC_MESSAGES/radio-browser.mo
