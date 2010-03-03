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

import threading
import gobject
import subprocess
import gtk

import xml.sax.saxutils

class RecordProcess(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.process = None # subprocess
		self.box = None # GUI Box
		self.info_box = None
		self.relay_port = None # port for listening to the recorded stream
		self.title = None
		self.uri = None
		self.thread = None
		self.song_info = ""
		self.server_name = ""
		self.stream_name = ""
		self.bitrate = ""

	def set_info_box(self):
		def add_label(title,value):
			if not value == "":
				label = gtk.Label()
				if value.startswith("http://"):
					label.set_markup("<b>"+xml.sax.saxutils.escape(title)+"</b>:<a href='"+xml.sax.saxutils.escape(value)+"'>"+value+"</a>")
				else:
					label.set_markup("<b>"+xml.sax.saxutils.escape(title)+"</b>:"+xml.sax.saxutils.escape(value))
				label.set_selectable(True)
				self.info_box.pack_start(label)		

		for widget in self.info_box.get_children():
			self.info_box.remove(widget)

		add_label("Server",self.server_name)
		add_label("Stream",self.stream_name)
		add_label("Current song",self.song_info)
		add_label("Bitrate",self.bitrate)
		add_label("Relay port",str(self.relay_port))

		self.info_box.show_all()

		return False

	def run(self):
		pout = self.process.stdout
		while self.process.poll()==None:
			line = ""
			
			while True:
				try:
					char = pout.read(1)
				except:
					print "exception"
					break

				if char == None or char == "":
					break

				if char == "\n":
					break
				if char == "\r":
					break
				line = line+char

			#print line
			if line.startswith("relay port"):
				self.relay_port = line.split(":")[1].strip()
			if line.startswith("stream"):
				self.stream_name = line.split(":")[1].strip()
			if line.startswith("server name"):
				self.server_name = line.split(":")[1].strip()
			if line.startswith("declared bitrate"):
				self.bitrate = line.split(":")[1].strip()
			if line.startswith("[ripping") or line.startswith("[skipping"):
				self.song_info = line[17:]
			gobject.idle_add(self.set_info_box)

		print "thread closed"
		self.box.get_parent().remove(self.box)
