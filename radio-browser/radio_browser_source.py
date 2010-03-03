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

import rb
import rhythmdb
import gobject
import httplib
import gtk
import gconf
import os
import subprocess
import threading
import hashlib
import urllib
import webbrowser
import Queue
import pickle

import xml.sax.saxutils

from radio_station import RadioStation
from record_process import RecordProcess

from feed import Feed
from local_handler import FeedLocal
from icecast_handler import FeedIcecast
from shoutcast_handler import FeedShoutcast
from board_handler import FeedBoard

#TODO: should not be defined here, but I don't know where to get it from. HELP: much apreciated
RB_METADATA_FIELD_TITLE = 0
RB_METADATA_FIELD_GENRE = 4
RB_METADATA_FIELD_BITRATE = 20
BOARD_ROOT = "http://segler.bplaced.net/"
RECENTLY_USED_FILENAME = "recently.bin"

class RadioBrowserSource(rb.StreamingSource):
	__gproperties__ = {
		'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
	}

	def __init__(self):
		self.hasActivated = False
		rb.StreamingSource.__init__(self,name="RadioBrowserPlugin")

	def do_set_property(self, property, value):
		if property.name == 'plugin':
			self.plugin = value

	""" return list of actions that should be displayed in toolbar """
	def do_impl_get_ui_actions(self):
		return ["UpdateList"]

	def do_impl_get_status(self):
		if self.updating:
			progress = -1.0
			if self.load_total_size > 0:
				progress = min (float(self.load_current_size) / self.load_total_size, 1.0)
			return (self.load_status,None,progress)
		else:
			return (_("Nothing"),None,0.0)

	def update_download_status(self,filename,current, total):
		self.load_current_size = current
		self.load_total_size = total
		self.load_status = "Loading : "+filename

		gtk.gdk.threads_enter()
		self.notify_status_changed()
		gtk.gdk.threads_leave()

	""" on source actiavation, e.g. double click on source or playing something in this source """
	def do_impl_activate(self):
		# first time of activation -> add graphical stuff
		if not self.hasActivated:
			self.shell = self.get_property('shell')
			self.db = self.shell.get_property('db')
			self.entry_type = self.get_property('entry-type')
			self.hasActivated = True

			# add listener for stream infos
			sp = self.shell.get_player ()
			#sp.connect ('playing-song-changed',self.playing_entry_changed)
			#sp.connect ('playing-changed',self.playing_changed)
			#sp.connect ('playing-song-property-changed',self.playing_song_property_changed)
			sp.props.player.connect("info",self.info_available)

			# create cache dir
			self.cache_dir = rb.find_user_cache_file("radio-browser")
			if os.path.exists(self.cache_dir) is False:
				os.makedirs(self.cache_dir, 0700)
			self.icon_cache_dir = os.path.join(self.cache_dir,"icons")
			if os.path.exists(self.icon_cache_dir) is False:
				os.makedirs(self.icon_cache_dir,0700)
			self.updating = False
			self.load_current_size = 0
			self.load_total_size = 0
			self.load_status = ""

			# create the model for the view
			self.filter_entry = gtk.Entry()
			self.filter_entry.connect("changed",self.filter_entry_changed)

			self.tree_store = gtk.TreeStore(str,object)
			self.sorted_list_store = gtk.TreeModelSort(self.tree_store)
			#self.filtered_list_store = self.sorted_list_store.filter_new()
			#self.filtered_list_store.set_visible_func(self.list_store_visible_func)
			self.tree_view = gtk.TreeView(self.sorted_list_store)

			# create the view
			column_title = gtk.TreeViewColumn()#"Title",gtk.CellRendererText(),text=0)
			column_title.set_title("Title")
			renderer = gtk.CellRendererPixbuf()
			column_title.pack_start(renderer, expand=False)
			column_title.set_cell_data_func(renderer,self.model_data_func,"image")
			renderer = gtk.CellRendererText()
			column_title.pack_start(renderer, expand=True)
			column_title.add_attribute(renderer, 'text', 0)
			column_title.set_resizable(True)
			column_title.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			column_title.set_fixed_width(100)
			column_title.set_expand(True)
			self.tree_view.append_column(column_title)

			"""column_genre = gtk.TreeViewColumn("Tags",gtk.CellRendererText(),text=1)
			column_genre.set_resizable(True)
			column_genre.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			column_genre.set_fixed_width(100)
			self.tree_view.append_column(column_genre)

			column_bitrate = gtk.TreeViewColumn("Bitrate",gtk.CellRendererText(),text=2)
			column_bitrate.set_resizable(True)
			column_bitrate.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			column_bitrate.set_fixed_width(100)
			self.tree_view.append_column(column_bitrate)"""

			# add some more listeners for tree view...
			# - row double click
			self.tree_view.connect("row-activated",self.row_activated_handler)
			# - selection change
			self.tree_view.connect("cursor-changed",self.treeview_cursor_changed_handler)

			# create icon view
			self.icon_view = gtk.IconView()
			self.icon_view.set_text_column(0)
			self.icon_view.set_pixbuf_column(2)
			self.icon_view.set_item_width(150)
			self.icon_view.set_selection_mode(gtk.SELECTION_SINGLE)
			self.icon_view.connect("item-activated", self.on_item_activated_icon_view)
			self.icon_view.connect("selection-changed", self.on_selection_changed_icon_view)

			self.tree_view_container = gtk.ScrolledWindow()
			self.tree_view_container.set_shadow_type(gtk.SHADOW_IN)
			self.tree_view_container.add(self.tree_view)
			self.tree_view_container.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)

			self.icon_view_container = gtk.ScrolledWindow()
			self.icon_view_container.set_shadow_type(gtk.SHADOW_IN)
			self.icon_view_container.add(self.icon_view)
			self.icon_view_container.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)

			self.view = gtk.HBox()
			self.view.pack_start(self.tree_view_container)
			self.view.pack_start(self.icon_view_container)

			filterbox = gtk.HBox()
			filterbox.pack_start(gtk.Label("Filter:"),False)
			filterbox.pack_start(self.filter_entry)

			self.record_box = gtk.VBox()
			self.info_box = gtk.VBox()

			mybox = gtk.VBox()
			mybox.pack_start(filterbox,False)
			mybox.pack_start(self.view)
			mybox.pack_start(self.info_box,False)
			mybox.pack_start(self.record_box,False)

			self.pack_start(mybox)
			mybox.show_all()
			self.icon_view_container.hide_all()

			# initialize lists for recording streams and icon cache
			self.recording_streams = {}
			self.icon_cache = {}

			# start icon downloader thread
			# use queue for communication with thread
			# enqueued addresses will get downloaded
			self.icon_download_queue = Queue.Queue()
			self.icon_download_thread = threading.Thread(target = self.icon_download_worker)
			self.icon_download_thread.setDaemon(True)
			self.icon_download_thread.start()

			# first time filling of the model
			self.refill_list()

		rb.BrowserSource.do_impl_activate (self)

	""" listener on double click in search view """
	def on_item_activated_icon_view(self,widget,item):
		model = widget.get_model()
		station = model[item][1]

		self.play_uri(station)

	""" listener on selection change in search view """
	def on_selection_changed_icon_view(self,widget):
		model = widget.get_model()
		items = widget.get_selected_items()

		if len(items) == 1:
			obj = model[items[0]][1]
			self.update_info_box(obj)
	
	""" listener for selection changes """
	def treeview_cursor_changed_handler(self,treeview):
		# get selected item
		selection = self.tree_view.get_selection()
		model,iter = selection.get_selected()

		# if some item is selected
		if not iter == None:
			obj = model.get_value(iter,1)
			self.update_info_box(obj)

	def update_info_box(self,obj):
		# remove all old information in infobox
		for widget in self.info_box.get_children():
			self.info_box.remove(widget)

		# create new infobox
		info_container = gtk.Table(12,2)
		info_container.set_col_spacing(0,10)
		self.info_box_added_rows = 0

		# convinience method for adding new labels to infobox
		def add_label(title,value,shorten=True):
			if not value == "":
				if shorten:
					if len(value) > 53:
						short_value = value[0:50]+"..."
					else:
						short_value = value
				else:
					short_value = value

				label = gtk.Label()
				label.set_line_wrap(True)
				if value.startswith("http://") or value.startswith("mailto:"):
					label.set_markup("<a href='"+xml.sax.saxutils.escape(value)+"'>"+xml.sax.saxutils.escape(short_value)+"</a>")
				else:
					label.set_markup(xml.sax.saxutils.escape(short_value))
				label.set_selectable(True)
				label.set_alignment(0, 0)

				title_label = gtk.Label(title)
				title_label.set_alignment(1, 0)
				title_label.set_markup("<b>"+xml.sax.saxutils.escape(title)+"</b>")
				info_container.attach(title_label,0,1,self.info_box_added_rows,self.info_box_added_rows+1)
				info_container.attach(label,1,2,self.info_box_added_rows,self.info_box_added_rows+1)
				self.info_box_added_rows = self.info_box_added_rows+1

		if isinstance(obj,Feed):
			feed = obj
			add_label("Entry type","Feed")

			add_label("Description",feed.getDescription(),False)
			add_label("Feed homepage",feed.getHomepage())
			add_label("Feed source",feed.getSource())

			"""
			if station == "Bookmark":
				add_label("Description","User saved bookmarks")
				add_label("Feed source","local source")

			if station == "Recently":
				add_label("Description","Recently played streams")
				add_label("Feed source","local source")"""

		if isinstance(obj,RadioStation):
			station = obj
			add_label("Source feed",station.type)
			add_label("Name",station.server_name)
			add_label("Tags",station.genre)
			add_label("Bitrate",station.bitrate)
			add_label("Server type",station.server_type)
			add_label("Homepage",station.homepage)
			add_label("Current song (on last refresh)",station.current_song)
			add_label("Current listeners",station.listeners)
			add_label("Language",station.language)
			add_label("Country",station.country)
			add_label("Votes",station.votes)
			add_label("Negative votes",station.negativevotes)

		decorated_info_box = gtk.Frame("Info box")
		decorated_info_box.add(info_container)
		self.info_box.pack_start(decorated_info_box)
		self.info_box.show_all()

	""" icon download worker thread function """
	def icon_download_worker(self):
		while True:
			filepath,src = self.icon_download_queue.get()

			if os.path.exists(filepath) is False:
				if src.lower().startswith("http://"):
					try:
						urllib.urlretrieve(src,filepath)
					except:
						pass

			self.icon_download_queue.task_done()

	""" tries to load icon from disk and if found it saves it in cache returns it """
	def get_icon_pixbuf(self,filepath,return_value_not_found=None):
		if os.path.exists(filepath):
			width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_BUTTON)
			if filepath in self.icon_cache:
				return self.icon_cache[filepath]
			else:
				try:
					icon = gtk.gdk.pixbuf_new_from_file_at_size(filepath,width,height)
				except:
					icon = return_value_not_found
				self.icon_cache[filepath] = icon
			return icon
		return return_value_not_found

	""" data display function for tree view """
	def model_data_func(self,column,cell,model,iter,infostr):
		obj = model.get_value(iter,1)
		self.clef_icon = self.get_icon_pixbuf(self.plugin.find_file("note.png"))

		if infostr == "image":
			icon = None

			if isinstance(obj,RadioStation):
				station = obj
				# default icon
				icon = self.clef_icon

				# icons for special feeds
				if station.type == "Shoutcast":
					icon = self.get_icon_pixbuf(self.plugin.find_file("shoutcast-logo.png"))
				if station.type == "Icecast":
					icon = self.get_icon_pixbuf(self.plugin.find_file("xiph-logo.png"))
				if station.type == "Local":
					icon = self.get_icon_pixbuf(self.plugin.find_file("local-logo.png"))

				# most special icons, if the station has one for itsself
				if station.icon_src != "":
					hash_src = hashlib.md5(station.icon_src).hexdigest()
					filepath = os.path.join(self.icon_cache_dir, hash_src)
					if os.path.exists(filepath):
						icon = self.get_icon_pixbuf(filepath,self.clef_icon)
					else:
						# load icon
						self.icon_download_queue.put([filepath,station.icon_src])

			if icon is None:
				cell.set_property("stock-id",gtk.STOCK_DIRECTORY)
			else:
				cell.set_property("pixbuf",icon)

	""" transmits station information to board """
	def transmit_station(self,station):
		params = urllib.urlencode({'action':'clicked','name': station.server_name,'url': station.getRealURL(),'source':station.type})
		f = urllib.urlopen(BOARD_ROOT+"?%s" % params)
		f.read()
		print "Transmit station '"+str(station.server_name)+"' OK"

	""" transmits title information to board """
	"""def transmit_title(self,title):
		params = urllib.urlencode({'action':'streaming','name': self.station.server_name,'url': self.station.getRealURL(),'source':self.station.type,'title':title})
		f = urllib.urlopen(BOARD_ROOT+"?%s" % params)
		f.read()
		print "Transmit title '"+str(title)+"' OK"
	"""
	""" stream information listener """
	def info_available(self,player,uri,field,value):
		if field == RB_METADATA_FIELD_TITLE:
			self.title = value
			self.set_streaming_title(self.title)
			#transmit_thread = threading.Thread(target = self.transmit_title,args = (value,))
			#transmit_thread.setDaemon(True)
			#transmit_thread.start()
			#print "setting title to:"+value
           
		elif field == RB_METADATA_FIELD_GENRE:
			self.genre = value
			## causes warning: RhythmDB-WARNING **: trying to sync properties of non-editable file
			#self.shell.props.db.set(self.entry, rhythmdb.PROP_GENRE, value)
			#self.shell.props.db.commit()
			#print "setting genre to:"+value

		elif field == RB_METADATA_FIELD_BITRATE:
			## causes warning: RhythmDB-WARNING **: trying to sync properties of non-editable file
			#self.shell.props.db.set(self.entry, rhythmdb.PROP_BITRATE, value/1000)
			#self.shell.props.db.commit()
			#print "setting bitrate to:"+str(value/1000)
			pass

		else:
			print "Server sent unknown info '"+str(field)+"':'"+str(value)+"'"

#	def playing_changed (self, sp, playing):
#		print "playing changed"

#	def playing_entry_changed (self, sp, entry):
#		print "playing entry changed"

#	def playing_song_property_changed (self, sp, uri, property, old, new):
#		print "property changed "+str(new)

	""" vote for station on board """
	def vote_station(self,menuitem,station):
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
	def bad_station(self,menuitem,station):
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
	def post_new_station_handler(self,menuitem):
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

	def record_uri(self,uri,title):
		self.add_recently_played(uri,title)
		commandline = ["streamripper",uri,"-d",self.plugin.outputpath,"-r"]
		process = subprocess.Popen(commandline,stdout=subprocess.PIPE)

		left = gtk.VBox()
		left.pack_start(gtk.Label(title))

		right = gtk.VBox()
		play_button = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY,label="")
		right.pack_start(play_button)
		stop_button = gtk.Button(stock=gtk.STOCK_STOP,label="")
		right.pack_start(stop_button)

		box = gtk.HBox()
		box.pack_start(left)
		box.pack_start(right,False)
		decorated_box = gtk.Frame("Ripping stream")
		decorated_box.add(box)

		rp = RecordProcess()
		rp.process = process
		rp.title = title
		rp.uri = uri
		rp.box = decorated_box
		rp.info_box = left
		self.recording_streams[uri] = rp
		rp.start()

		play_button.connect("clicked",self.record_play_button_handler,uri)
		stop_button.connect("clicked",self.record_stop_button_handler,uri)
		
		self.record_box.pack_start(decorated_box)
		self.record_box.show_all()

	def record_play_button_handler(self,button,uri):
		rp = self.recording_streams[uri]
		self.station = RadioStation()
		self.station.server_name = rp.title
		self.station.listen_url = uri
		self.station.type = "local"
		self.generic_play_uri("http://127.0.0.1:"+rp.relay_port,rp.title)

	def record_stop_button_handler(self,button,uri):
		rp = self.recording_streams[uri]
		rp.process.terminate()

	""" listener for filter entry change """
	def filter_entry_changed(self,gtk_entry):
		if self.filter_entry.get_text() == "":
			self.tree_view_container.show_all()
			self.icon_view_container.hide_all()
		else:
			self.tree_view_container.hide_all()
			self.icon_view_container.show_all()

		self.icon_view.set_model()
		self.filtered_icon_view_store.refilter()
		self.icon_view.set_model(self.filtered_icon_view_store)
		self.notify_status_changed()

	""" callback for item filtering """
	def list_store_visible_func(self,model,iter):
		# returns true if the row should be visible
		if len(model) == 0:
			return True
		obj = model.get_value(iter,1)
		if isinstance(obj,RadioStation):
			station = obj
			try:
				bitrate = int(station.bitrate)
				min_bitrate = int(float(self.plugin.min_bitrate))
				if bitrate < min_bitrate:
					return False
			except:
				pass

			filter_string = self.filter_entry.get_text().lower()
	
			if filter_string == "":
				return True
			elif model.get_value(iter,0).lower().find(filter_string) >= 0:
				return True
			else:
				return False
		else:
			return True

	""" handler for update toolbar button """
	def update_button_clicked(self):
		if not self.updating:
			# delete cache files
			files = os.listdir(self.cache_dir)
			for filename in files:
				if filename.endswith("xml"):
					filepath = os.path.join(self.cache_dir, filename)
					os.unlink(filepath)
			# start filling again
			self.refill_list()

	""" starts playback of the station """
	def play_uri(self,station):
		# transmit station click to station board (statistic) """
		transmit_thread = threading.Thread(target = self.transmit_station,args = (station,))
		transmit_thread.setDaemon(True)
		transmit_thread.start()

		# add to recently played
		data = self.load_from_file(os.path.join(self.cache_dir,RECENTLY_USED_FILENAME))
		if data is None:
			data = {}
		if station.server_name not in data:
			self.tree_store.append(self.recently_iter,(station.server_name,station))
			data[station.server_name] = station
			self.save_to_file(os.path.join(self.cache_dir,RECENTLY_USED_FILENAME),data)

		# get player
		player = self.shell.get_player()
		player.stop()

		# create new entry to play
		self.entry = self.shell.props.db.entry_lookup_by_location(station.getRealURL())
		if self.entry == None:
			#self.shell.props.db.entry_delete(self.entry)

			self.entry = self.shell.props.db.entry_new(self.entry_type, station.getRealURL())
			self.shell.props.db.set(self.entry, rhythmdb.PROP_TITLE, station.server_name+" ("+station.getRealURL()+")")
			self.shell.props.db.commit()
		#shell.load_uri(uri,False)

		# start playback
		player.play()
		player.play_entry(self.entry,self)

	""" handler for double clicks in tree view """
	def row_activated_handler(self,treeview,path,column):
		model = treeview.get_model()
		myiter = model.get_iter(path)
		
		station = model.get_value(myiter,1)

		if station is not None:
			self.play_uri(station)

	def do_impl_delete_thyself(self):
		print "not implemented"

	def engines(self):
		yield FeedLocal(self.cache_dir,self.update_download_status)
		yield FeedIcecast(self.cache_dir,self.update_download_status)
		yield FeedBoard(self.cache_dir,self.update_download_status)
		yield FeedShoutcast(self.cache_dir,self.update_download_status)

	def get_stock_icon(self, name):
		theme = gtk.icon_theme_get_default()
		return theme.load_icon(name, 48, 0)

	def load_icon_file(self,filepath,value_not_found):
		icon = value_not_found
		try:
			icon = gtk.gdk.pixbuf_new_from_file_at_size(filepath,72,72)
		except:
			icon = value_not_found
		return icon

	def get_station_icon(self,station,default_icon):
		# default icon
		icon = default_icon

		# most special icons, if the station has one for itsself
		if station.icon_src != "":
			if station.icon_src is not None:
				hash_src = hashlib.md5(station.icon_src).hexdigest()
				filepath = os.path.join(self.icon_cache_dir, hash_src)
				if os.path.exists(filepath):
					icon = self.load_icon_file(filepath,icon)
				else:
					# load icon
					self.icon_download_queue.put([filepath,station.icon_src])
		return icon

	def refill_list_worker(self):
		print "refill list worker"
		self.tree_view.set_model()
		self.icon_view.set_model()

		self.updating = True
		# deactivate sorting
		self.icon_view_store = gtk.ListStore(str,object,gtk.gdk.Pixbuf)
		self.sorted_list_store.reset_default_sort_func()

		# delete old entries
		self.tree_store.clear()
		self.icon_view_store.clear()

		# preload most used icons
		note_icon = self.load_icon_file(self.plugin.find_file("note.png"),None)
		shoutcast_icon = self.load_icon_file(self.plugin.find_file("shoutcast-logo.png"),None)
		xiph_icon = self.load_icon_file(self.plugin.find_file("xiph-logo.png"),None)
		local_icon = self.load_icon_file(self.plugin.find_file("local-logo.png"),None)

		# add recently played list
		self.recently_iter = self.tree_store.append(None,("Recently played",None))
		data = self.load_from_file(os.path.join(self.cache_dir,RECENTLY_USED_FILENAME))
		if data is None:
			data = {}
		for name,station in data.items():
			self.tree_store.append(self.recently_iter,(name,station))

		for feed in self.engines():
			try:
				gtk.gdk.threads_enter()
				self.load_status = "loading feed '"+feed.name()+"'"
				self.notify_status_changed()
				gtk.gdk.threads_leave()

				# create main feed root item
				current_iter = self.tree_store.append(None,(feed.name(),feed))

				# initialize dicts for iters
				genres = {}
				countries = {}
				subcountries = {}

				# get genres
				genres_list = feed.genres()

				# add subitems for sorting
				genre_iter = self.tree_store.append(current_iter,(_("By Genres"),None))
				country_iter = self.tree_store.append(current_iter,(_("By Country"),None))
				for genre in genres_list:
					genres[genre] = self.tree_store.append(genre_iter,(genre,None))

				# load entries
				entries = feed.entries()

				gtk.gdk.threads_enter()
				self.load_status = "integrating feed '"+feed.name()+"'("+str(len(entries))+" items) into tree..."
				self.notify_status_changed()
				gtk.gdk.threads_leave()

				def short_name(name):
					maxlen = 50
					if len(name) > maxlen:
						return name[0:maxlen-3]+"..."
					else:
						return name

				self.load_total_size = len(entries)
				self.load_current_size = 0

				for station in entries:
					self.load_current_size += 1
					gtk.gdk.threads_enter()
					if self.load_current_size % 50 == 0:
						self.notify_status_changed()
					gtk.gdk.threads_leave()

					# default icon
					icon = note_icon
					# icons for special feeds
					if station.type == "Shoutcast":
						icon = shoutcast_icon
					if station.type == "Icecast":
						icon = xiph_icon
					if station.type == "Local":
						icon = local_icon
					self.icon_view_store.append((short_name(station.server_name),station,self.get_station_icon(station,icon)))

					# by genre
					if station.genre is not None:
						for genre in station.genre.split(","):
							genre = genre.strip().lower()
							if genre not in genres:
								genres[genre] = self.tree_store.append(genre_iter,(genre,None))
							self.tree_store.append(genres[genre],(station.server_name,station))

					# by country
					country_arr = station.country.split("/")
					if country_arr[0] not in countries:
						countries[country_arr[0]] = self.tree_store.append(country_iter,(country_arr[0],None))
					if len(country_arr) == 2:
						if station.country not in subcountries:
							subcountries[station.country] = self.tree_store.append(countries[country_arr[0]],(country_arr[1],None))
						self.tree_store.append(subcountries[station.country],(station.server_name,station))
					else:
						self.tree_store.append(countries[country_arr[0]],(station.server_name,station))

			except Exception,e:
				print "error with source:"+feed.name()
				print "error:"+str(e)

		# activate sorting
		self.sorted_list_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
		self.icon_view_store.set_sort_column_id(0,gtk.SORT_ASCENDING)

		# connect model to view
		self.filtered_icon_view_store = self.icon_view_store.filter_new()
		self.filtered_icon_view_store.set_visible_func(self.list_store_visible_func)

		self.tree_view.set_model(self.sorted_list_store)
		self.icon_view.set_model(self.filtered_icon_view_store)

		gtk.gdk.threads_enter()
		self.updating = False
		self.notify_status_changed()
		gtk.gdk.threads_leave()

	def refill_list(self):
		print "refill list"
		self.list_download_thread = threading.Thread(target = self.refill_list_worker)
		self.list_download_thread.setDaemon(True)
		self.list_download_thread.start()

	def load_from_file(self,filename):
		if not os.path.isfile(filename):
			return None

		try:
			f = open(filename,"r")
			p = pickle.Unpickler(f)
			data = p.load()
			f.close()
			return data
		except:
			print "load file did not work:"+filename
			return None

	def save_to_file(self,filename,obj):
		f = open(filename,"w")
		p = pickle.Pickler(f)
		p.dump(obj)
		f.close()
