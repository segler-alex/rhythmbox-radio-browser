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
import xml.sax.handler

from radio_station import RadioStation
from feed import Feed

class LocalHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.countries = []
		self.categories = []
		self.entries = []
		self.current_category = None
 
	def startElement(self, name, attributes):
		if name == "country":
			self.countries.append(attributes.get("name"))
			self.current_country = attributes.get("name")
		if name == "category":
			self.categories.append(attributes.get("name"))
			self.current_category = attributes.get("name")
		if name == "station":
			self.entry = RadioStation()
			self.entry.type = "Local"
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("genre")
			self.entry.listen_url = attributes.get("address")
			self.entry.bitrate = attributes.get("bitrate")
			if self.entry.bitrate is None:
				self.entry.bitrate = ""
			self.entry.homepage = attributes.get("homepage")
			self.entry.icon_src = attributes.get("favicon")
			if self.entry.icon_src is None:
				self.entry.icon_src = ""
			if self.current_category is not None:
				self.entry.country = self.current_country+"/"+self.current_category
			else:
				self.entry.country = self.current_country
			self.entries.append(self.entry)

	def endElement(self, name):
		if name == "category":
			self.current_category = None

class FeedLocal(Feed):
	def __init__(self,cache_dir,status_change_handler):
		Feed.__init__(self)
		print "init local feed"
		self.handler = LocalHandler()
		self.cache_dir = cache_dir
		self.filename = os.path.join(self.cache_dir, "local.xml")
		self.uri = "http://www.programmierecke.net/programmed/local.xml"
		self.status_change_handler = status_change_handler

	def name(self):
		return "Local"

	def getHomepage(self):
		return "mailto:segler_alex@web.de"
