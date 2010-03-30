#!/bin/sh

DESTDIR=~/.gnome2/rhythmbox/plugins/radio-browser

install -d $DESTDIR
cp *.py $DESTDIR
cp *.png $DESTDIR
cp radio-browser.rb-plugin $DESTDIR
