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

class FeedAction:
	def __init__(self,feed,name,func):
		self.feed = feed
		self.name = name
		self.func = func

	def call(self,source):
		self.func(source)

class FeedStationAction:
	def __init__(self,feed,name,func):
		self.feed = feed
		self.name = name
		self.func = func

	def call(self,source,station):
		self.func(source,station)

class Feed:
	def __init__(self):
		self.loaded = False
		self.AutoDownload = True
		self.UpdateChecking = True

	def getSource(self):
		return self.uri

	def getDescription(self):
		return ""

	def getHomepage(self):
		return ""

	def setAutoDownload(self,autodownload):
		self.AutoDownload = autodownload

	def setUpdateChecking(self,updatechecking):
		self.UpdateChecking = updatechecking

	def copy_callback(self,current,total):
		self.status_change_handler(self.uri,current,total)

	def download(self):
		print "downloading "+self.uri
		try:
			os.remove(self.filename)
		except:
			pass

		remotefile = gio.File(self.uri)
		localfile = gio.File(self.filename)
		
		try:
			if not remotefile.copy(localfile,self.copy_callback):
				print "download failed"
				return False
		except:
			print "download failed"
			return False
			pass
		return True

	# only download if necessary
	def update(self):
		try:
			lf = gio.File(self.filename)
			lfi = lf.query_info(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
			local_mod = lfi.get_attribute_uint64(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
		except:
			print "could not load local file:"+self.filename
			self.download()
			return

		try:
			rf = gio.File(self.uri)
			rfi = rf.query_info(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
			remote_mod = rfi.get_attribute_uint64(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
		except:
			print "could not check remote file for modification time:"+self.uri
			self.download()
			return

		if remote_mod >= local_mod+24*60*60 or remote_mod == 0:
			print "Local file older than 1 day: remote("+str(remote_mod)+") local("+str(local_mod)+")"
			# change date is different -> download
			self.download()

	def load(self):
		print "loading "+self.filename
		try:
			xml.sax.parse(self.filename,self.handler)
		except:
			print "parse failed of "+self.filename

	def genres(self):
		if not os.path.isfile(self.filename) and not self.AutoDownload:
			return []

		if not self.loaded:
			if self.UpdateChecking:
				self.update()
			if not os.path.isfile(self.filename):
				download()
			self.load()
			self.loaded = True

		list = []
		for station in self.handler.entries:
			if station.genre is not None:
				for genre in station.genre.split(","):
					tmp = genre.strip().lower()
					if tmp not in list:
						list.append(tmp)
		return list

	def entries(self):
		if not os.path.isfile(self.filename) and not self.AutoDownload:
			return []

		if not self.loaded:
			if self.UpdateChecking:
				self.update()
			if not os.path.isfile(self.filename):
				download()
			self.load()
			self.loaded = True

		return self.handler.entries

	def force_redownload(self):
		self.handler.entries = []
		self.loaded = False
		try:
			os.remove(self.filename)
		except:
			pass
		pass

	def get_feed_actions(self):
		actions = []
		return actions

	def get_station_actions(self):
		actions = []
		return actions
