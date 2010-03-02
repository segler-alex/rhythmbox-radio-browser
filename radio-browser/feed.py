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

class Feed:
	def getSource(self):
		return self.uri

	def getDescription(self):
		return ""

	def getHomepage(self):
		return ""

	def copy_callback(self,current,total):
		self.status_change_handler(self.uri,current,total)

	def download(self):
		print "downloading "+self.uri
		try:
			os.remove(self.filename)
		except:
			print "File unlink failed:"+self.filename

		remotefile = gio.File(self.uri)
		localfile = gio.File(self.filename)
		
		if not remotefile.copy(localfile,self.copy_callback):
			print "download failed"

	# only download if necessary
	def update(self):
		try:
			lf = gio.File(self.filename)
			lfi = lf.query_info(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
			local_mod = lfi.get_attribute_uint64(gio.FILE_ATTRIBUTE_TIME_MODIFIED)

			rf = gio.File(self.uri)
			rfi = rf.query_info(gio.FILE_ATTRIBUTE_TIME_MODIFIED)
			remote_mod = rfi.get_attribute_uint64(gio.FILE_ATTRIBUTE_TIME_MODIFIED)

			if remote_mod >= local_mod+24*60*60:
				print "Local file older than 1 day :remote("+str(remote_mod)+") local("+str(local_mod)+")"
				# change date is different -> download
				self.download()
		except:
			# file not found -> download
			self.download()

	def load(self):
		print "loading "+self.filename
		try:
			xml.sax.parse(self.filename,self.handler)
		except:
			print "parse failed of "+self.filename

	def genres(self):
		list = []
		for station in self.handler.entries:
			for genre in station.genre.split(","):
				list.append(genre)

	def entries(self):
		self.update()
		self.load()
		return self.handler.entries
