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

class ShoutcastRadioStation(RadioStation):
	def getRealURL(self):
		if self.listen_url == "":
			# download from "http://www.shoutcast.com"+self.tunein+"?id="+shoutcast_id
			url = "http://www.shoutcast.com"+self.tunein+"?id="+self.listen_id
			remote = gio.File(url)
			data,datalen,tag = remote.load_contents()

			lines = data.splitlines()
			for line in lines:
				if line.startswith("File"):
					self.listen_url = line.split("=")[1];
					print "playing uri:"+self.listen_url
			
		return self.listen_url

class ShoutcastHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.genres = []
		self.entries = {}
 
	def startElement(self, name, attributes):
		if name == "genre":
			self.genres.append(attributes.get("name"))
		if name == "tunein":
			self.tunein = attributes.get("base")
		if name == "station":
			self.entry = ShoutcastRadioStation()
			self.entry.tunein = self.tunein
			self.entry.type = "Shoutcast"
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("genre").lower()
			self.entry.genre = ",".join(self.entry.genre.split(" "))
			self.entry.current_song = attributes.get("ct")
			self.entry.bitrate = attributes.get("br")
			self.entry.listen_id = attributes.get("id")
			self.entry.listeners = attributes.get("lc")
			self.entry.server_type = attributes.get("mt")
			try:
				self.entry.homepage = "http://shoutcast.com/directory/search_results.jsp?searchCrit=simple&s="+urllib.quote_plus(self.entry.server_name.replace("- [SHOUTcast.com]","").strip())
			except:
				self.entry.homepage = ""
			self.entries[self.entry.server_name] = self.entry

class FeedShoutcast(Feed):
	def __init__(self,cache_dir,status_change_handler):
		print "init shoutcast feed"
		self.handler = ShoutcastHandler()
		self.cache_dir = cache_dir
		self.filename = os.path.join(self.cache_dir, "shoutcast-genre.xml")
		self.uri = "http://www.shoutcast.com/sbin/newxml.phtml"
		self.status_change_handler = status_change_handler

	def name(self):
		return "Shoutcast"

	def getHomepage(self):
		return "http://shoutcast.com/"

	def update(self):
		self.status_change_handler(self.uri,0,0)
		while not self.download():
			pass
		self.load()
		genres = self.handler.genres

		for i in range(0,len(genres)):
			genre = genres[i]
			self.uri = "http://www.shoutcast.com/sbin/newxml.phtml?genre="+genre
			self.filename = os.path.join(self.cache_dir, "shoutcast-"+genre+".xml")
			self.status_change_handler(self.uri,i,len(genres))
			tries = 0
			if not os.path.isfile(self.filename):
				while not self.download():
					tries += 1
					if tries >= 10:
						break
			self.load()

	def genres(self):
		try:
			self.loaded
		except:
			self.loaded = False

		if not self.loaded:
			if not os.path.isfile(self.filename):
				self.download()
			self.load()
			self.loaded = True

		return self.handler.genres

	def entries(self):
		#entrylist = []
		genres = self.genres()
		for genre in genres:
			filename = os.path.join(self.cache_dir, "shoutcast-"+genre+".xml")
			try:
				#self.handler = ShoutcastHandler()
				xml.sax.parse(filename,self.handler)
				#entrylist.extend(self.handler.entries)
			except:
				pass

		return self.handler.entries.values()
