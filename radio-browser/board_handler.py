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
import xml.sax.handler

from radio_station import RadioStation
from feed import Feed

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
