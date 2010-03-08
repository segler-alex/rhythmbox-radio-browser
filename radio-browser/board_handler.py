#    This file is part of Radio-Browser-Plugin for Rhythmbox.
#
#    Copyright (C) 2009 <segler_alex@web.de>
#
#    Radio-Browser-Plugin is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Radio-Browser-Plugin is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Radio-Browser-Plugin.  If not, see <http://www.gnu.org/licenses/>.

import os
import gio
import urllib
import xml.sax.handler

from radio_station import RadioStation
from feed import Feed
from feed import FeedAction
from feed import FeedStationAction

class BoardHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.entries = []
 
	def startElement(self, name, attributes):
		if name == "station":
			self.entry = RadioStation()
			self.entry.type = "Board"
			self.entry.id = attributes.get("id")
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("tags")
			self.entry.genre = ",".join(self.entry.genre.split(" "))
			self.entry.listen_url = attributes.get("url")
			self.entry.language = attributes.get("language")
			self.entry.country = attributes.get("country")
			self.entry.votes = attributes.get("votes")
			self.entry.negativevotes = attributes.get("negativevotes")
			self.entry.homepage = attributes.get("homepage")
			self.entry.icon_src = attributes.get("favicon")
			self.entries.append(self.entry)

class FeedBoard(Feed):
	def __init__(self,cache_dir,status_change_handler):
		Feed.__init__(self)
		print "init board feed"
		self.handler = BoardHandler()
		self.cache_dir = cache_dir
		self.filename = os.path.join(self.cache_dir, "board.xml")
		self.uri = "http://segler.bplaced.net/xml.php"
		self.status_change_handler = status_change_handler

	def name(self):
		return "Board"

	""" vote for station on board """
	def vote_station(self,station):
		message = gtk.MessageDialog(message_format="Vote for station",buttons=gtk.BUTTONS_YES_NO,type=gtk.MESSAGE_QUESTION)
		message.format_secondary_text("Do you really want to vote for this station?")
		response = message.run()
		if response == gtk.RESPONSE_YES:
			params = urllib.urlencode({'action': 'vote','id': station.id})
			f = urllib.urlopen("http://segler.bplaced.net/?%s" % params)
			f.read()
			self.reset_feed("board.xml")
		message.destroy()

	""" mark station as bad on board """
	def bad_station(self,station):
		message = gtk.MessageDialog(message_format="Mark station as bad",buttons=gtk.BUTTONS_YES_NO,type=gtk.MESSAGE_WARNING)
		message.format_secondary_text("Do you really want to mark this radio station as bad?\n\nIt will eventually get deleted if enough people do that!\n\nMore information on that on the feeds homepage:\nhttp://segler.bplaced.net/")
		response = message.run()
		if response == gtk.RESPONSE_YES:
			params = urllib.urlencode({'action': 'negativevote','id': station.id})
			f = urllib.urlopen("http://segler.bplaced.net/?%s" % params)
			f.read()
			self.reset_feed("board.xml")
		message.destroy()

	""" post new station to board """
	def post_new_station_handler(self):
		builder_file = self.plugin.find_file("prefs.ui")
		builder = gtk.Builder()
		builder.add_from_file(builder_file)
		dialog = builder.get_object('post_station_dialog')

		dialog.StationName = builder.get_object("StationName")
		dialog.StationUrl = builder.get_object("StationURL")
		dialog.StationHomepage = builder.get_object("StationHomepage")
		dialog.StationFavicon = builder.get_object("StationFavicon")
		dialog.StationLanguage = builder.get_object("StationLanguage")
		dialog.StationCountry = builder.get_object("StationCountry")
		dialog.StationTags = builder.get_object("StationTags")

		LanguageList = gtk.ListStore(str)
		for language in self.board_languages:
			LanguageList.append([language])
		dialog.StationLanguage.set_model(LanguageList)
		dialog.StationLanguage.set_text_column(0)

		CountryList = gtk.ListStore(str)
		for country in self.board_countries:
			CountryList.append([country])
		dialog.StationCountry.set_model(CountryList)
		dialog.StationCountry.set_text_column(0)

		while True:
			def show_message(message):
				info_dialog = gtk.MessageDialog(parent=dialog,buttons=gtk.BUTTONS_OK,message_format=message)
				info_dialog.run()
				info_dialog.destroy()

			print "test"
			response = dialog.run()
			if response == 1:
				break
			if response == 0:
				Name = dialog.StationName.get_text().strip()
				URL = dialog.StationUrl.get_text().strip()
				Homepage = dialog.StationHomepage.get_text().strip()
				Favicon = dialog.StationFavicon.get_text().strip()
				Tags = dialog.StationTags.get_text().strip()
				Country = dialog.StationCountry.get_child().get_text().strip()
				Language = dialog.StationLanguage.get_child().get_text().strip()

				if Name == "" or URL == "":
					show_message("Name and URL are necessary")
					continue

				if not (URL.lower().startswith("http://") or URL.lower().startswith("mms://")):
					show_message("URL needs to start with http:// or mms://")
					continue

				if Homepage != "":
					if not Homepage.lower().startswith("http://"):
						show_message("Homepage URL needs to start with http://")
						continue

				if Favicon != "":
					if not Favicon.lower().startswith("http://"):
						show_message("Favicon URL needs to start with http://")
						continue
				
				params = urllib.urlencode({'action': 'add','name': Name, 'url': URL, 'homepage': Homepage,'favicon': Favicon, 'tags': Tags,'language': Language, 'country':Country})
				f = urllib.urlopen("http://segler.bplaced.net/?%s" % params)
				f.read()

				self.reset_feed("board.xml")
				show_message("Station posted")
				break

		dialog.destroy()

	def get_feed_actions(self):
		actions = []
		actions.append(FeedAction(self,"Post new station",self.post_new_station))
		return actions

	def get_station_actions(self):
		actions = []
		actions.append(FeedStationAction(self,"Vote +1",self.vote_station))
		actions.append(FeedStationAction(self,"Vote -1",self.bad_station))
		return actions
