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

class IcecastHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.entries = []
 
	def startElement(self, name, attributes):
		self.currentEntry = name;
		if name == "entry":
			self.entry = RadioStation()
			self.type = "Icecast"
 
	def characters(self, data):
		if self.currentEntry == "server_name":
			self.entry.server_name += data  
		elif self.currentEntry == "listen_url":
			self.entry.listen_url += data
		elif self.currentEntry == "genre":
			self.entry.genre += data
		elif self.currentEntry == "current_song":
			self.entry.current_song += data
		elif self.currentEntry == "bitrate":
			self.entry.bitrate += data
		elif self.currentEntry == "server_type":
			self.entry.server_type += data
 
	def endElement(self, name):
		if name == "entry":
			try:
				self.entry.homepage = "http://dir.xiph.org/search?search="+urllib.quote_plus(self.entry.server_name)
			except:
				self.entry.homepage = ""
			self.entry.genre = ",".join(self.entry.genre.split(" "))
			self.entries.append(self.entry)

		self.currentEntry = ""

class FeedIcecast(Feed):
	def __init__(self,cache_dir,status_change_handler):
		print "init icecast feed"
		self.handler = IcecastHandler()
		self.cache_dir = cache_dir
		self.filename = os.path.join(self.cache_dir, "icecast.xml")
		self.uri = "http://dir.xiph.org/yp.xml"
		self.status_change_handler = status_change_handler

	def name(self):
		return "Icecast"
