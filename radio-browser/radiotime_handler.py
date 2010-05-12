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

class RadioTimeRadioStation(RadioStation):
	def getRealURL(self):
		if self.listen_url == "":
			try:
				url = "http://opml.radiotime.com/Tune.ashx?id="+self.listen_id
				remote = gio.File(url)
				data,datalen,tag = remote.load_contents()

				lines = data.splitlines()
				for line in lines:
					if not line.startswith("#"):
						self.listen_url = line
						print "playing uri:"+self.listen_url
			except:
				return None
		if self.listen_url == "":
			return None
		else:
			return self.listen_url

class RadioTimeHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.genres = []
		self.entries = []
 
	def startElement(self, name, attributes):
		if name == "outline":
			if attributes.get("type") == "audio":
				self.entry = RadioTimeRadioStation()
				self.entry.type = "RadioTime"
				self.entry.server_name = attributes.get("text")
				self.entry.bitrate = attributes.get("bitrate")
				self.entry.reliability = attributes.get("reliability")
				self.entry.listen_id = attributes.get("guide_id")
				self.entry.genre = ""
				self.entry.genre_id = attributes.get("genre_id")
				self.entry.icon_src = attributes.get("image")
				self.entry.server_type = attributes.get("formats")
				self.entry.homepage = ""
				self.entries.append(self.entry)

class FeedRadioTime(Feed):
	def __init__(self,cache_dir,status_change_handler):
		Feed.__init__(self)
		print "init radiotime feed"
		self.handler = RadioTimeHandler()
		self.cache_dir = cache_dir
		self.filename = os.path.join(self.cache_dir, "radiotime-local.xml")
		self.uri = "http://opml.radiotime.com/Browse.ashx?c=local"
		self.status_change_handler = status_change_handler

	def name(self):
		return "RadioTime"

	def getHomepage(self):
		return "http://radiotime.com/"
