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
from datetime import datetime

import xml.sax.saxutils

from radio_station import RadioStation

class RecordProcess(threading.Thread,gtk.VBox):
	def __init__(self,station,outputpath):
		# init base classes
		threading.Thread.__init__(self)
		gtk.VBox.__init__(self)

		# make shortcuts
		title = station.server_name
		uri = station.getRealURL()
		self.relay_port = ""
		self.server_name = ""
		self.bitrate = ""
		self.song_info = ""
		self.stream_name = ""
		self.filesize = ""
		self.song_start = datetime.now()

		# prepare streamripper
		commandline = ["streamripper",uri,"-d",outputpath,"-r"]
		self.process = subprocess.Popen(commandline,stdout=subprocess.PIPE)

		# infobox
		left = gtk.Table(12,2)
		left.set_col_spacing(0,10)
		self.info_box = left

		right = gtk.VBox()
		play_button = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY,label="")
		right.pack_start(play_button)
		stop_button = gtk.Button(stock=gtk.STOCK_STOP,label="")
		right.pack_start(stop_button)

		box = gtk.HBox()
		box.pack_start(left)
		box.pack_start(right,False)
		decorated_box = gtk.Frame(_("Ripping stream"))
		decorated_box.add(box)

		play_button.connect("clicked",self.record_play_button_handler,uri)
		stop_button.connect("clicked",self.record_stop_button_handler)
		
		# song list
		self.songlist = gtk.TreeView()
		self.songlist_store = gtk.ListStore(str,str,str)
		self.songlist.set_model(self.songlist_store)

		column_time = gtk.TreeViewColumn(_("Time"),gtk.CellRendererText(),text=0)
#		column_time.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		self.songlist.append_column(column_time)

		column_title = gtk.TreeViewColumn(_("Title"),gtk.CellRendererText(),text=1)
#		column_title.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		self.songlist.append_column(column_title)

		column_size = gtk.TreeViewColumn(_("Filesize"),gtk.CellRendererText(),text=2)
#		column_title.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		self.songlist.append_column(column_size)

		tree_view_container = gtk.ScrolledWindow()
		tree_view_container.set_shadow_type(gtk.SHADOW_IN)
		tree_view_container.add(self.songlist)
		tree_view_container.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)

		self.pack_start(decorated_box,False)
		self.pack_start(tree_view_container)
		self.show_all()

	def set_info_box(self):
		self.added_lines = 0
		def add_label(title,value):
			if not value == "":
				label = gtk.Label()
				if value.startswith("http://"):
					label.set_markup("<a href='"+xml.sax.saxutils.escape(value)+"'>"+value+"</a>")
				else:
					label.set_markup(xml.sax.saxutils.escape(value))
				label.set_selectable(True)
				label.set_alignment(0, 0)

				title_label = gtk.Label()
				title_label.set_alignment(1, 0)
				title_label.set_markup("<b>"+xml.sax.saxutils.escape(title)+"</b>")

				self.info_box.attach(title_label,0,1,self.added_lines,self.added_lines+1)
				self.info_box.attach(label,1,2,self.added_lines,self.added_lines+1)
				self.added_lines += 1

		for widget in self.info_box.get_children():
			self.info_box.remove(widget)

		add_label(_("Server"),self.server_name)
		add_label(_("Stream"),self.stream_name)
		add_label(_("Current song"),self.song_info)
		playing_time = datetime.now()-self.song_start
		add_label(_("Playing time"),"{0:02d}:{1:02d}".format(playing_time.seconds/60,playing_time.seconds%60))
		add_label(_("Filesize"),self.filesize)
		add_label(_("Bitrate"),self.bitrate)
		add_label(_("Relay port"),str(self.relay_port))

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
				song = line[17:len(line)-10]
				# add old song to list, after recording title changed to new song
				if self.song_info != song:
					if self.song_info != "":
						self.songlist_store.append((str(self.song_start),self.song_info,self.filesize))
					self.song_info = song
					self.song_start = datetime.now()
				self.filesize = line[len(line)-8:len(line)-1].strip()

			gobject.idle_add(self.set_info_box)

		print "thread closed"
		self.get_parent().remove(self)

	def stop(self):
		if self.process.poll() is None:
			self.process.terminate()

	def record_play_button_handler(self,button,uri):
		rp = self.recording_streams[uri]
		station = RadioStation()
		station.server_name = rp.title
		station.listen_url = "http://127.0.0.1:"+rp.relay_port
		station.type = "local"
		#self.play_uri(station)

	def record_stop_button_handler(self,button):
		self.process.terminate()
