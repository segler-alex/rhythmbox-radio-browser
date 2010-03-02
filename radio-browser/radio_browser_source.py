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

import xml.sax.saxutils

from radio_station import RadioStation
from record_process import RecordProcess

from feed import Feed
from local_handler import FeedLocal
from icecast_handler import FeedIcecast
from board_handler import FeedBoard

#TODO: should not be defined here, but I don't know where to get it from. HELP: much apreciated
RB_METADATA_FIELD_TITLE = 0
RB_METADATA_FIELD_GENRE = 4
RB_METADATA_FIELD_BITRATE = 20
BOARD_ROOT = "http://segler.bplaced.net/"

class RadioBrowserSource(rb.StreamingSource):
	__gproperties__ = {
		'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
	}

	def __init__(self):
		self.hasActivated = False
		self.loadedFiles = []
		self.createdGenres = {}
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
		self.notify_status_changed()

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
			self.filtered_list_store = self.sorted_list_store.filter_new()
			self.filtered_list_store.set_visible_func(self.list_store_visible_func)
			self.tree_view = gtk.TreeView(self.filtered_list_store)

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

			#column_song = gtk.TreeViewColumn("Current Song",gtk.CellRendererText(),text=3)
			#column_song.set_resizable(True)
			#column_song.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			#column_song.set_fixed_width(100)
			#column_song.set_expand(True)
			#self.tree_view.append_column(column_song)

			# add some more listeners for tree view...
			# - row double click
			self.tree_view.connect("row-activated",self.row_activated_handler)
			# - mouse click
			self.tree_view.connect("button-press-event",self.button_press_handler)
			# - selection change
			self.tree_view.connect("cursor-changed",self.treeview_cursor_changed_handler)

			# create icon view
			self.icon_view_store = gtk.ListStore(str,object,gtk.gdk.Pixbuf)
			self.icon_view_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
			self.filtered_icon_view_store = self.icon_view_store.filter_new()
			self.filtered_icon_view_store.set_visible_func(self.list_store_visible_func)
			self.icon_view = gtk.IconView(self.filtered_icon_view_store)
			self.icon_view.set_text_column(0)
			self.icon_view.set_pixbuf_column(2)
			self.icon_view.set_item_width(150)

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

	""" listener for selection changes """
	def treeview_cursor_changed_handler(self,treeview):
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

		# get selected item
		selection = self.tree_view.get_selection()
		model,iter = selection.get_selected()

		# if some item is selected
		if not iter == None:
			#path = self.sorted_list_store.convert_path_to_child_path(self.filtered_list_store.convert_path_to_child_path(model.get_path(iter)))
			obj = model.get_value(iter,1)

			if isinstance(obj,Feed):
				feed = obj
				add_label("Entry type","Feed")

				add_label("Description",feed.getDescription(),False)
				add_label("Feed homepage",feed.getHomepage())
				add_label("Feed source",feed.getSource())

				"""
				if station == "Shoutcast":
					add_label("Feed homepage","http://shoutcast.com/")
					add_label("Feed source","http://www.shoutcast.com/sbin/newxml.phtml")

				if station == "Bookmark":
					add_label("Description","User saved bookmarks")
					add_label("Feed source","local source")

				if station == "Recently":
					add_label("Description","Recently played streams")
					add_label("Feed source","local source")"""

			if isinstance(obj,RadioStation):
				station = obj
				add_label("Entry type","Internet radio station")
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
					print "downloading favicon: "+src
					try:
						urllib.urlretrieve(src,filepath)
					except:
						print "error while downloading favicon:"+src

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
					print "could not load icon : "+filepath
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
	def transmit_station(self):
		params = urllib.urlencode({'action':'clicked','name': self.station.server_name,'url': self.station.real_url,'source':self.station.type})
		f = urllib.urlopen(BOARD_ROOT+"?%s" % params)
		f.read()
		print "Transmit station '"+str(self.station.server_name)+"' OK"

	""" transmits title information to board """
	def transmit_title(self,title):
		params = urllib.urlencode({'action':'streaming','name': self.station.server_name,'url': self.station.real_url,'source':self.station.type,'title':title})
		f = urllib.urlopen(BOARD_ROOT+"?%s" % params)
		f.read()
		print "Transmit title '"+str(title)+"' OK"

	""" stream information listener """
	def info_available(self,player,uri,field,value):
		if field == RB_METADATA_FIELD_TITLE:
			self.title = value
			self.set_streaming_title(self.title)
			transmit_thread = threading.Thread(target = self.transmit_title,args = (value,))
			transmit_thread.setDaemon(True)
			transmit_thread.start()
			print "setting title to:"+value
           
		elif field == RB_METADATA_FIELD_GENRE:
			self.genre = value
			## causes warning: RhythmDB-WARNING **: trying to sync properties of non-editable file
			#self.shell.props.db.set(self.entry, rhythmdb.PROP_GENRE, value)
			#self.shell.props.db.commit()
			print "setting genre to:"+value

		elif field == RB_METADATA_FIELD_BITRATE:
			## causes warning: RhythmDB-WARNING **: trying to sync properties of non-editable file
			#self.shell.props.db.set(self.entry, rhythmdb.PROP_BITRATE, value/1000)
			#self.shell.props.db.commit()
			print "setting bitrate to:"+str(value/1000)

		else:
			print "unknwon info available ("+str(field)+"):"+str(value)

#	def playing_changed (self, sp, playing):
#		print "playing changed"

#	def playing_entry_changed (self, sp, entry):
#		print "playing entry changed"

#	def playing_song_property_changed (self, sp, uri, property, old, new):
#		print "property changed "+str(new)

	""" mouse button listener for treeview """
	def button_press_handler(self,widget,event):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			selection = self.tree_view.get_path_at_pos(x, y)
			# only display menu, if exactly one item is selected
			if selection is not None:
				path, col, cellx, celly = selection
				self.tree_view.grab_focus()
				self.tree_view.set_cursor(path, col, 0)
				iter = self.tree_store.get_iter(self.sorted_list_store.convert_path_to_child_path(self.filtered_list_store.convert_path_to_child_path(path)))

				title = self.tree_store.get_value(iter,0)
				uri = self.tree_store.get_value(iter,4)
				obj = self.tree_store.get_value(iter,5)

				menu = gtk.Menu()

				if uri == None:
					filename = None
					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_local):
						filename = "local.xml"

					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_icecast):
						filename = "icecast.xml"

					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_shoutcast):
						filename = "shoutcast-genres.xml"

					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_board):
						filename = "board.xml"
						additem = gtk.MenuItem("Post new station")
						additem.connect("activate",self.post_new_station_handler)
						menu.append(additem)

#					if self.tree_store.is_ancestor(self.tree_iter_shoutcast,iter):
#						filename = "shoutcast--"+title+".xml"

					if filename is not None:
						redownloaditem = gtk.MenuItem("Redownload")
						redownloaditem.connect("activate",self.redownload_handler,filename)
						menu.append(redownloaditem)
					
					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_recently_played):
						filename = "recently.save"
						clearitem = gtk.MenuItem("Clear")
						clearitem.connect("activate",self.clear_recently_handler,filename,self.recently_played)
						menu.append(clearitem)

					if self.tree_store.get_path(iter) == self.tree_store.get_path(self.tree_iter_bookmarks):
						filename = "bookmarks.save"
						clearitem = gtk.MenuItem("Clear")
						clearitem.connect("activate",self.clear_recently_handler,filename,self.bookmarks)
						menu.append(clearitem)

					if filename is None:
						return
				else:
					playitem = gtk.MenuItem("Play")
					playitem.connect("activate",self.play_handler,False,uri,title)
					menu.append(playitem)

					if self.tree_store.is_ancestor(self.tree_iter_bookmarks,iter):
						bookmarkitem = gtk.MenuItem("Delete bookmark")
						bookmarkitem.connect("activate",self.delete_bookmark_handler,uri,iter)
					else:
						bookmarkitem = gtk.MenuItem("Bookmark")
						bookmarkitem.connect("activate",self.bookmark_handler,uri,title)

					menu.append(bookmarkitem)

					if obj is not None:
						if not obj.homepage == "":
							homepageitem = gtk.MenuItem("Homepage")
							homepageitem.connect("activate",self.homepage_handler,obj.homepage)
							menu.append(homepageitem)
						if obj.type == "Board":
							voteitem = gtk.MenuItem("Vote! (You like this station)")
							voteitem.connect("activate",self.vote_station,obj)
							menu.append(voteitem)

							voteitem = gtk.MenuItem("Mark as bad station (station does not work)")
							voteitem.connect("activate",self.bad_station,obj)
							menu.append(voteitem)

					if not uri.startswith("mms:"):
						try:
							process = subprocess.Popen("streamripper",stdout=subprocess.PIPE)
							process.communicate()
							process.wait()
						except(OSError):
							print "streamripper not found"
						else:
							recorditem = gtk.MenuItem("Record")
							recorditem.connect("activate",self.play_handler,True,uri,title)
							menu.append(recorditem)

				menu.show_all()
				menu.popup(None,None,None,event.button,event.time)

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

	def homepage_handler(self,menuitem,homepage):
		webbrowser.open(homepage)

	def clear_recently_handler(self,menuitem,filename,itemlist):
		itemlist = {}
		self.save_to_file(filename,itemlist.items())
		# clear shortcut lists
		self.loadedFiles = []
		self.createdGenres = {}
		# start filling again
		self.refill_list()

	def reset_feed(self,filename):
		filepath = os.path.join(self.cache_dir, filename)
		os.unlink(filepath)
		print "redownload "+filepath

		# clear shortcut lists
		self.loadedFiles = []
		self.createdGenres = {}
		# start filling again
		self.refill_list()

	def redownload_handler(self,menuitem,filename):
		self.reset_feed(filename)

	def play_handler(self,menuitem,record,uri,title):
		self.generic_play_uri(uri,title,record)

	def bookmark_handler(self,menuitem,uri,title):
		if not self.bookmarks.has_key(uri):
			self.bookmarks[uri] = title
			self.tree_store.append(self.tree_iter_bookmarks,(title,None,None,None,uri,None))
			self.save_to_file("bookmarks.save",self.bookmarks.items())

	def delete_bookmark_handler(self,menuitem,uri,iter):
		if self.bookmarks.has_key(uri):
			del self.bookmarks[uri]
			self.save_to_file("bookmarks.save",self.bookmarks.items())
			self.tree_store.remove(iter)

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

	def filter_entry_changed(self,gtk_entry):
		if self.filter_entry.get_text() == "":
			self.tree_view_container.show_all()
			self.icon_view_container.hide_all()
		else:
			self.tree_view_container.hide_all()
			self.icon_view_container.show_all()

		#self.filtered_list_store.refilter()
		self.filtered_icon_view_store.refilter()
		self.notify_status_changed()

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

	def update_button_clicked(self):
		if not self.updating:
			# delete cache files
			files = os.listdir(self.cache_dir)
			for filename in files:
				if filename.endswith("xml"):
					filepath = os.path.join(self.cache_dir, filename)
					os.unlink(filepath)
			# clear shortcut lists
			self.loadedFiles = []
			self.createdGenres = {}
			# start filling again
			self.refill_list()

	def play_uri(self,uri,title):
		self.station.real_url = uri
		transmit_thread = threading.Thread(target = self.transmit_station)
		transmit_thread.setDaemon(True)
		transmit_thread.start()
		#self.add_recently_played(uri,title)
		player = self.shell.get_player()
		player.stop()

		self.entry = self.shell.props.db.entry_lookup_by_location(uri)
		if self.entry == None:
			#self.shell.props.db.entry_delete(self.entry)

			self.entry = self.shell.props.db.entry_new(self.entry_type, uri)
			self.shell.props.db.set(self.entry, rhythmdb.PROP_TITLE, title+" ("+uri+")")
			self.shell.props.db.commit()
		#shell.load_uri(uri,False)

		player.play()
		player.play_entry(self.entry,self)

	def generic_play_uri(self,uri,title,record=False):
		if uri.startswith("shoutcast:"):
			# special handling for shoutcast
			shoutcast_id = uri.split(":")[1];
			shoutcast_uri = "http://www.shoutcast.com"+self.tunein+"?id="+shoutcast_id
			self.download_shoutcast_playlist(shoutcast_uri,title,record)
		else:
			# presume its an icecast link
			if record == True:
				self.record_uri(uri,title)
			else:
				self.play_uri(uri,title)

	def row_activated_handler(self,treeview,path,column):
		myiter = self.tree_store.get_iter(self.sorted_list_store.convert_path_to_child_path(self.filtered_list_store.convert_path_to_child_path(path)))
		
		title = self.tree_store.get_value(myiter,0)
		self.station = self.tree_store.get_value(myiter,1)

		if self.station is not None:
			uri = self.station.getRealURL()
			self.play_uri(uri,title)
			"""else:
				if self.tree_store.is_ancestor(self.tree_iter_shoutcast,myiter):
					filename = "shoutcast--"+title+".xml"

					if filename in self.loadedFiles:
						self.loadedFiles.remove(filename)

					filepath = os.path.join(self.cache_dir, filename)
					if os.path.exists(filepath):
						os.unlink(filepath)
					print "download genre "+title
					handler_stations = ShoutcastHandler(self.tree_store,myiter)
					self.refill_list_part(myiter,handler_stations,filename,"http://www.shoutcast.com/sbin/newxml.phtml?genre="+title,True,False)"""

	def download_shoutcast_playlist(self,uri,title,record):
		print "starting download: "+uri
		self.hide_user()
		playlist_loader = rb.Loader()
		playlist_loader.get_url(uri,self.shoutcast_download_callback,uri,title,record)

	def shoutcast_download_callback(self,data,uri,title,record):
		if data == None:
			self.download_try_no+=1
			if self.download_try_no > self.download_try_max:
				print "shoutcast download failed:"+uri
				self.hide_user(False)
			else:
				self.notify_status_changed()
				playlist_loader = rb.Loader()
				playlist_loader.get_url(uri,self.shoutcast_download_callback,uri,title,record)
		else:
			self.hide_user(False)
			print "shoutcast download OK:"+uri
			lines = data.splitlines()
			for line in lines:
				if line.startswith("File"):
					uri_single = line.split("=")[1];
					print "playing uri:"+uri_single
					if record == True:
						self.record_uri(uri_single,title)
					else:
						self.play_uri(uri_single,title)
					return
			print "could not find 'File' entry"

	def do_impl_delete_thyself(self):
		print "not implemented"

	def load_from_file(self,filename,tree_iter,itemlist):
		itemlist.clear()
		filepath = os.path.join(self.cache_dir, filename)
		if os.path.exists(filepath):
			f = open(filepath,"r")
			lines = f.readlines()
			for i in range(0,len(lines)/2):
				title = lines[(i)*2].strip("\n")
				uri = lines[(i)*2+1].strip("\n")

				itemlist[uri] = title
				self.tree_store.append(tree_iter,(title,None,None,None,uri,None))
			f.close()

	def save_to_file(self,filename,items):
		filepath = os.path.join(self.cache_dir, filename)
		f = open(filepath,"w")
		for (key,value) in items:
			f.write(value+"\n")
			f.write(key+"\n")
		f.close()

	def add_recently_played(self,uri,title):
		if not self.recently_played.has_key(uri):
			self.recently_played[uri] = title
			self.tree_store.append(self.tree_iter_recently_played,(title,None,None,None,uri,None))
			self.save_to_file("recently.save",self.recently_played.items())

	def engines(self):
		yield FeedLocal(self.cache_dir,self.update_download_status)
		yield FeedIcecast(self.cache_dir,self.update_download_status)
		yield FeedBoard(self.cache_dir,self.update_download_status)

	def get_stock_icon(self, name):
		theme = gtk.icon_theme_get_default()
		return theme.load_icon(name, 48, 0)

	def load_icon_file(self,filepath,value_not_found):
		icon = value_not_found
		try:
			icon = gtk.gdk.pixbuf_new_from_file_at_size(filepath,72,72)
		except:
			icon = value_not_found
			#print "could not load icon : "+filepath
		return icon

	def get_station_icon(self,station):
		# default icon
		icon = self.load_icon_file(self.plugin.find_file("note.png"),None)

		# icons for special feeds
		if station.type == "Shoutcast":
			icon = self.load_icon_file(self.plugin.find_file("shoutcast-logo.png"),icon)
		if station.type == "Icecast":
			icon = self.load_icon_file(self.plugin.find_file("xiph-logo.png"),icon)

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
		self.updating = True
		# deactivate sorting
		self.sorted_list_store.reset_default_sort_func()

		# delete old entries
		gtk.gdk.threads_enter()
		self.tree_store.clear()
		self.icon_view_store.clear()
		gtk.gdk.threads_leave()

		for feed in self.engines():
			try:
				entries = feed.entries()
				current_iter = self.tree_store.append(None,(feed.name(),feed))

				gtk.gdk.threads_enter()
				genre_iter = self.tree_store.append(current_iter,(_("By Genres"),None))
				country_iter = self.tree_store.append(current_iter,(_("By Country"),None))
				gtk.gdk.threads_leave()

				genres = {}
				countries = {}
				subcountries = {}

				def short_name(name):
					maxlen = 30
					if len(name) > maxlen:
						return name[0:maxlen-3]+"..."
					else:
						return name

				gtk.gdk.threads_enter()
				for station in entries:
					self.load_status = "integrating into tree..."
					self.icon_view_store.append((short_name(station.server_name),station,self.get_station_icon(station)))

					# by genre
					if station.genre is not None:
						for genre in station.genre.split(","):
							genre = genre.strip(" ")
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
				gtk.gdk.threads_leave()

			except Exception,e:
				print "error with source:"+feed.name()
				print "error:"+str(e)
				gtk.gdk.threads_leave()

		# activate sorting
		self.sorted_list_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
		self.updating = False

	def refill_list(self):
		print "refill list"
		self.list_download_thread = threading.Thread(target = self.refill_list_worker)
		self.list_download_thread.setDaemon(True)
		self.list_download_thread.start()
