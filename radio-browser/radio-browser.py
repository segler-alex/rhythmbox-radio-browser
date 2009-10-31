#    This file is part of IcecastPlugin for Rhythmbox.
#
#    Copyright (C) 2009 <segler_alex@web.de>
#
#    IcecastPlugin is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    IcecastPlugin is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with IcecastPlugin.  If not, see <http://www.gnu.org/licenses/>.


import rb
import rhythmdb
import gobject
import xml.sax.handler
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

#TODO: should not be defined here, but I don't know where to get it from. HELP: much apreciated
RB_METADATA_FIELD_TITLE = 0
RB_METADATA_FIELD_GENRE = 4
RB_METADATA_FIELD_BITRATE = 20

class RadioStation:
	def __init__(self):
		self.listen_url = ""
		self.server_name = ""
		self.genre = ""
		self.bitrate = ""
		self.current_song = ""
		self.type = ""
		self.icon_src = ""
		self.homepage = ""
		self.listeners = ""
		self.server_type = ""
		self.language = ""
		self.country = ""
		self.votes = ""
		self.id = ""

class IcecastHandler(xml.sax.handler.ContentHandler):
	def __init__(self,model,parent):
		self.model = model
		self.parent = parent
		self.categories = {}
 
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

			char = self.entry.server_name[0:1].upper()

			if char >= 'A' and char <= 'Z':
				if char not in self.categories:
					self.categories[char] = self.model.append(self.parent,(char,None,None,None,None,None))
				parent = self.categories[char]
			else:
				if "#" not in self.categories:
					self.categories["#"] = self.model.append(self.parent,("#",None,None,None,None,None))
				parent = self.categories["#"]

			self.model.append(parent,(self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url,self.entry))
		self.currentEntry = ""

class ShoutcastHandler(xml.sax.handler.ContentHandler):
	def __init__(self,model,parent):
		self.model = model
		self.parent = parent
		self.genres = []
 
	def startElement(self, name, attributes):
		if name == "genre":
			self.genres.append(attributes.get("name"))
		if name == "tunein":
			self.tunein = attributes.get("base")
		if name == "station":
			self.entry = RadioStation()
			self.entry.type = "Shoutcast"
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("genre")
			self.entry.current_song = attributes.get("ct")
			self.entry.bitrate = attributes.get("br")
			self.entry.listen_id = attributes.get("id")
			self.entry.listeners = attributes.get("lc")
			self.entry.server_type = attributes.get("mt")
			try:
				self.entry.homepage = "http://shoutcast.com/directory/search_results.jsp?searchCrit=simple&s="+urllib.quote_plus(self.entry.server_name.replace("- [SHOUTcast.com]","").strip())
			except:
				self.entry.homepage = ""
			self.model.append(self.parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,"shoutcast:"+str(self.entry.listen_id),self.entry])

class LocalHandler(xml.sax.handler.ContentHandler):
	def __init__(self,model,parent):
		self.model = model
		self.parent = parent
		self.countries = []
		self.current_directory = self.parent
 
	def startElement(self, name, attributes):
		if name == "country":
			self.countries.append(attributes.get("name"))
			self.current_country = self.model.append(self.current_directory,[attributes.get("name"),None,None,None,None,None])
			self.current_directory = self.current_country
		if name == "category":
			self.current_category = self.model.append(self.current_directory,[attributes.get("name"),None,None,None,None,None])
			self.current_directory = self.current_category
		if name == "station":
			self.entry = RadioStation()
			self.entry.type = "Local"
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("genre")
			self.entry.listen_url = attributes.get("address")
			self.entry.bitrate = attributes.get("bitrate")
			self.entry.homepage = attributes.get("homepage")
			self.entry.icon_src = attributes.get("favicon")
			self.model.append(self.current_directory,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url,self.entry])
	def endElement(self, name):
		if name == "category":
			self.current_directory = self.current_country
		if name == "country":
			self.current_directory = self.parent

class BoardHandler(xml.sax.handler.ContentHandler):
	def __init__(self,model,parent):
		self.model = model
		self.parent = parent
		self.tags = {}
		self.countries = {}
		self.languages = {}
 
	def startElement(self, name, attributes):
		try:
			self.iter_tags
		except:
			self.iter_tags = self.model.append(self.parent,["By Tag",None,None,None,None,None])
			self.iter_countries = self.model.append(self.parent,["By Country",None,None,None,None,None])
			self.iter_languages = self.model.append(self.parent,["By Language",None,None,None,None,None])
		if name == "station":
			self.entry = RadioStation()
			self.entry.type = "Board"
			self.entry.id = attributes.get("id")
			self.entry.server_name = attributes.get("name")
			self.entry.genre = attributes.get("tags")
			self.entry.listen_url = attributes.get("url")
			self.entry.language = attributes.get("language")
			self.entry.country = attributes.get("country")
			self.entry.votes = attributes.get("votes")
			self.entry.negativevotes = attributes.get("negativevotes")
			self.entry.homepage = attributes.get("homepage")
			self.entry.icon_src = attributes.get("favicon")

			if self.entry.country not in self.countries:
				if self.entry.country == "":
					parent = self.model.append(self.iter_countries,["Undefined",None,None,None,None,None])
				else:
					parent = self.model.append(self.iter_countries,[self.entry.country,None,None,None,None,None])
				self.countries[self.entry.country] = parent
			else:
				parent = self.countries[self.entry.country]

			self.model.append(parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url,self.entry])

			if self.entry.language not in self.languages:
				if self.entry.language == "":
					parent = self.model.append(self.iter_languages,["Undefined",None,None,None,None,None])
				else:
					parent = self.model.append(self.iter_languages,[self.entry.language,None,None,None,None,None])
				self.languages[self.entry.language] = parent
			else:
				parent = self.languages[self.entry.language]

			self.model.append(parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url,self.entry])

			tags = self.entry.genre.split(" ")
			for tag in tags:
				tag = tag.strip()
				if tag not in self.tags:
					if tag == "":
						parent = self.model.append(self.iter_tags,["Undefined",None,None,None,None,None])
					else:
						parent = self.model.append(self.iter_tags,[tag,None,None,None,None,None])
					self.tags[tag] = parent
				else:
					parent = self.tags[tag]

				self.model.append(parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url,self.entry])


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

class RadioBrowserSource(rb.StreamingSource):
	__gproperties__ = {
		'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
	}

	def __init__(self):
		self.hasActivated = False
		self.loadedFiles = []
		self.createdGenres = {}
		rb.StreamingSource.__init__(self,name="IcecastPlugin")

	def do_set_property(self, property, value):
		if property.name == 'plugin':
			self.plugin = value

	def do_impl_get_ui_actions(self):
		return ["UpdateList"]

	def do_impl_get_status(self):
		if self.updating:
			if self.load_total_size > 0:
				progress = min (float(self.load_current_size) / self.load_total_size, 1.0)
			else:
				progress = -1.0
			return (_("Downloading ..")+" "+_("Try")+" "+str(self.download_try_no)+" "+_("of")+" "+str(self.download_try_max), None, progress)
		else:
			return (str(len(self.filtered_list_store))+_(" entries"),None,0.0)

	def do_impl_activate(self):
		if not self.hasActivated:
			self.shell = self.get_property('shell')
			self.db = self.shell.get_property('db')
			self.entry_type = self.get_property('entry-type')
			self.hasActivated = True

			sp = self.shell.get_player ()
			#sp.connect ('playing-song-changed',self.playing_entry_changed)
			#sp.connect ('playing-changed',self.playing_changed)
			#sp.connect ('playing-song-property-changed',self.playing_song_property_changed)
			sp.props.player.connect("info",self.info_available)

			self.cache_dir = rb.find_user_cache_file("radio-browser")
			if os.path.exists(self.cache_dir) is False:
				os.makedirs(self.cache_dir, 0700)
			self.icon_cache_dir = os.path.join(self.cache_dir,"icons")
			if os.path.exists(self.icon_cache_dir) is False:
				os.makedirs(self.icon_cache_dir,0700)
			self.updating = False

			self.filter_entry = gtk.Entry()
			self.filter_entry.connect("changed",self.filter_entry_changed)

			self.tree_store = gtk.TreeStore(str,str,str,str,str,object)
			self.sorted_list_store = gtk.TreeModelSort(self.tree_store)
			self.filtered_list_store = self.sorted_list_store.filter_new()
			self.filtered_list_store.set_visible_func(self.list_store_visible_func)
			self.tree_view = gtk.TreeView(self.filtered_list_store)

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

			column_genre = gtk.TreeViewColumn("Tags",gtk.CellRendererText(),text=1)
			column_genre.set_resizable(True)
			column_genre.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			column_genre.set_fixed_width(100)
			self.tree_view.append_column(column_genre)

			column_bitrate = gtk.TreeViewColumn("Bitrate",gtk.CellRendererText(),text=2)
			column_bitrate.set_resizable(True)
			column_bitrate.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			column_bitrate.set_fixed_width(100)
			self.tree_view.append_column(column_bitrate)

			#column_song = gtk.TreeViewColumn("Current Song",gtk.CellRendererText(),text=3)
			#column_song.set_resizable(True)
			#column_song.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			#column_song.set_fixed_width(100)
			#column_song.set_expand(True)
			#self.tree_view.append_column(column_song)
			self.tree_view.connect("row-activated",self.row_activated_handler)
			self.tree_view.connect("button-press-event",self.button_press_handler)
			self.tree_view.connect("cursor-changed",self.treeview_cursor_changed_handler)

			mywin = gtk.ScrolledWindow()
			mywin.set_shadow_type(gtk.SHADOW_IN)
			mywin.add(self.tree_view)
			mywin.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)

			filterbox = gtk.HBox()
			filterbox.pack_start(gtk.Label("Filter:"),False)
			filterbox.pack_start(self.filter_entry)

			self.record_box = gtk.VBox()
			self.info_box = gtk.VBox()

			mybox = gtk.VBox()
			mybox.pack_start(filterbox,False)
			mybox.pack_start(mywin)
			mybox.pack_start(self.info_box,False)
			mybox.pack_start(self.record_box,False)

			self.pack_start(mybox)
			mybox.show_all()

			self.refill_list()

			self.recording_streams = {}
			self.icon_cache = {}
			self.icon_download_queue = Queue.Queue()
			self.icon_download_thread = threading.Thread(target = self.icon_download_worker)
			self.icon_download_thread.setDaemon(True)
			self.icon_download_thread.start()

		rb.BrowserSource.do_impl_activate (self)

	def treeview_cursor_changed_handler(self,treeview):
		for widget in self.info_box.get_children():
			self.info_box.remove(widget)

		info_container = gtk.Table(10,2)
		info_container.set_col_spacing(0,10)
		self.info_box_added_rows = 0

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
				if value.startswith("http://"):
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

		selection = self.tree_view.get_selection()
		model,iter = selection.get_selected()
		if not iter == None:
			path = self.sorted_list_store.convert_path_to_child_path(self.filtered_list_store.convert_path_to_child_path(model.get_path(iter)))

			if path == self.tree_store.get_path(self.tree_iter_board):
				add_label("Entry type","Feed")
				add_label("Description","If you cannot find your favorite station in the other feeds, just post it here with right click!",False)
				add_label("Feed homepage","http://segler.bplaced.net")
				add_label("Feed source","http://segler.bplaced.net/xml.php")

			if path == self.tree_store.get_path(self.tree_iter_local):
				add_label("Entry type","Feed")
				add_label("Feed admin","segler_alex@web.de")
				add_label("Feed source","http://www.programmierecke.net/programmed/local.xml")

			if path == self.tree_store.get_path(self.tree_iter_shoutcast):
				add_label("Entry type","Feed")
				add_label("Feed homepage","http://shoutcast.com/")
				add_label("Feed source","http://www.shoutcast.com/sbin/newxml.phtml")

			if path == self.tree_store.get_path(self.tree_iter_icecast):
				add_label("Entry type","Feed")
				add_label("Feed homepage","http://dir.xiph.org")
				add_label("Feed source","http://dir.xiph.org/yp.xml")

			if path == self.tree_store.get_path(self.tree_iter_bookmarks):
				add_label("Entry type","Feed")
				add_label("Description","User saved bookmarks")
				add_label("Feed source","local source")

			if path == self.tree_store.get_path(self.tree_iter_recently_played):
				add_label("Entry type","Feed")
				add_label("Description","Recently played streams")
				add_label("Feed source","local source")

			obj = model.get_value(iter,5)

			if obj is not None:
				add_label("Entry type","Internet radio station")
				add_label("Name",obj.server_name)
				add_label("Tags",obj.genre)
				add_label("Bitrate",obj.bitrate)
				add_label("Server type",obj.server_type)
				add_label("Homepage",obj.homepage)
				add_label("Current song (on last refresh)",obj.current_song)
				add_label("Current listeners",obj.listeners)
				add_label("Language",obj.language)
				add_label("Country",obj.country)
				add_label("Votes",obj.votes)
				add_label("Negative votes",obj.negativevotes)

			decorated_info_box = gtk.Frame("Info box")
			decorated_info_box.add(info_container)
			self.info_box.pack_start(decorated_info_box)
			self.info_box.show_all()

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


	def get_icon_pixbuf(self,filepath,return_value_not_found=None):
		if os.path.exists(filepath):
			width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
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

	def model_data_func(self,column,cell,model,iter,infostr):
		obj = model.get_value(iter,5)
		current_iter = self.sorted_list_store.convert_iter_to_child_iter(None,self.filtered_list_store.convert_iter_to_child_iter(iter))
		self.clef_icon = self.get_icon_pixbuf(self.plugin.find_file("clef.png"))
		icon = self.clef_icon

		if infostr == "image":
			if obj is not None:
				if not obj.icon_src == "":
					hash_src = hashlib.md5(obj.icon_src).hexdigest()
					filepath = os.path.join(self.icon_cache_dir, hash_src)
					if os.path.exists(filepath):
						icon = self.get_icon_pixbuf(filepath,self.clef_icon)
					else:
						# load icon
						self.icon_download_queue.put([filepath,obj.icon_src])
				else:
					icon = self.clef_icon

			if self.tree_store.get_path(current_iter) == self.tree_store.get_path(self.tree_iter_icecast):
				icon = self.get_icon_pixbuf(self.plugin.find_file("xiph-logo.png"))
			if self.tree_store.get_path(current_iter) == self.tree_store.get_path(self.tree_iter_shoutcast):
				icon = self.get_icon_pixbuf(self.plugin.find_file("shoutcast-logo.ico"))
			#if self.tree_store.is_ancestor(self.tree_iter_icecast,current_iter):
			#	icon = None

			cell.set_property("pixbuf",icon)

	def info_available(self,player,uri,field,value):
		if field == RB_METADATA_FIELD_TITLE:
			self.title = value
			self.set_streaming_title(self.title)
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

	def post_new_station_handler(self,menuitem):
		builder_file = self.plugin.find_file("prefs.ui")
		builder = gtk.Builder()
		builder.add_from_file(builder_file)
		dialog = builder.get_object('post_station_dialog')

		#dialog.OKButton = builder.get_object('OKButton')
		#dialog.OKButton.connect("clicked",dialog_OK_clicked,dialog)
		#dialog.CancelButton = builder.get_object('CancelButton')
		#dialog.CancelButton.connect("clicked",dialog_Cancel_clicked,dialog)

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

				if not URL.lower().startswith("http://"):
					show_message("URL needs to start with http://")
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
		play_button = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY)
		right.pack_start(play_button)
		stop_button = gtk.Button(stock=gtk.STOCK_STOP)
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
		self.generic_play_uri("http://127.0.0.1:"+rp.relay_port,rp.title)

	def record_stop_button_handler(self,button,uri):
		rp = self.recording_streams[uri]
		rp.process.terminate()

	def filter_entry_changed(self,gtk_entry):
		self.filtered_list_store.refilter()
		self.notify_status_changed()

	def list_store_visible_func(self,model,iter):
		# returns true if the row should be visible
		if len(model) == 0:
			return True

		if not model.get_value(iter,2) == None:
			try:
				bitrate = int(model.get_value(iter,2))
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
		elif model.get_value(iter,1) == None:
			return True
		elif model.get_value(iter,1).lower().find(filter_string) >= 0:
			return True
		else:
			return False

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
		self.add_recently_played(uri,title)
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
		uri = self.tree_store.get_value(myiter,4)
		title = self.tree_store.get_value(myiter,0)

		if not uri == None:
			self.generic_play_uri(uri,title)
		else:
			if self.tree_store.is_ancestor(self.tree_iter_shoutcast,myiter):
				print "download genre "+title
				handler_stations = ShoutcastHandler(self.tree_store,myiter)
				self.refill_list_part(myiter,handler_stations,"shoutcast--"+title+".xml","http://www.shoutcast.com/sbin/newxml.phtml?genre="+title,True,False)

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

	def refill_list(self):
		# deactivate sorting
		self.sorted_list_store.reset_default_sort_func()
		#self.tree_view.set_model()
		if not "start" in self.loadedFiles:
			# delete old entries
			self.tree_store.clear()
			# create parent entries
			self.tree_iter_local = self.tree_store.append(None,("Local",None,None,None,None,None))
			self.tree_iter_icecast = self.tree_store.append(None,("Icecast",None,None,None,None,None))
			self.tree_iter_shoutcast = self.tree_store.append(None,("Shoutcast",None,None,None,None,None))
			self.tree_iter_recently_played = self.tree_store.append(None,("Recently played",None,None,None,None,None))
			self.tree_iter_bookmarks = self.tree_store.append(None,("Bookmarks",None,None,None,None,None))
			self.tree_iter_board = self.tree_store.append(None,("Public station board",None,None,None,None,None))

			self.recently_played = {}
			self.bookmarks = {}
			self.load_from_file("recently.save",self.tree_iter_recently_played,self.recently_played)
			self.load_from_file("bookmarks.save",self.tree_iter_bookmarks,self.bookmarks)
			self.loadedFiles.append("start")

		# load local streams
		if self.refill_list_part(self.tree_iter_local,LocalHandler(self.tree_store,self.tree_iter_local),"local.xml","http://www.programmierecke.net/programmed/local.xml") == "downloading":
			return
		# load public board streams
		handler = BoardHandler(self.tree_store,self.tree_iter_board)
		if self.refill_list_part(self.tree_iter_board,handler,"board.xml","http://segler.bplaced.net/xml.php") == "downloading":
			return
		self.board_languages = handler.languages
		self.board_countries = handler.countries
		# load icecast streams
		if self.refill_list_part(self.tree_iter_icecast,IcecastHandler(self.tree_store,self.tree_iter_icecast),"icecast.xml","http://dir.xiph.org/yp.xml") == "downloading":
			return
		# load shoutcast genres
		handler_genres = ShoutcastHandler(self.tree_store,self.tree_iter_shoutcast)
		retval = self.refill_list_part(self.tree_iter_shoutcast,handler_genres,"shoutcast-genres.xml","http://www.shoutcast.com/sbin/newxml.phtml",loadchunks=False)
		if retval == "downloading":
			return
		if retval == "loaded":
			self.genres = handler_genres.genres
		# load shoutcast stations genre by genre
		for genre in self.genres:
			if not "shoutcast--"+genre+".xml" in self.loadedFiles:
				if genre in self.createdGenres:
					parent = self.createdGenres[genre]
				else:
					# add entry for genre
					parent = self.tree_store.append(self.tree_iter_shoutcast,[genre,None,None,None,None,None])
					self.createdGenres[genre] = parent
				# add stations under that new entry
				handler_stations = ShoutcastHandler(self.tree_store,parent)
				retval = self.refill_list_part(parent,handler_stations,"shoutcast--"+genre+".xml","http://www.shoutcast.com/sbin/newxml.phtml?genre="+genre,False,False)
				if retval == "downloading":
					return
				if retval == "loaded":
					self.tunein = handler_stations.tunein;

		# activate sorting
		#self.tree_view.set_model(self.filtered_list_store)
		self.sorted_list_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
		# change status
		self.notify_status_changed()

	# Description
	# ===========
	# try to load xml information from a file with a given handler,
	# if file is not present, start downloading it from url
	# returns: "loaded" .. if file is present and could be loaded
	#          "downloading" .. if file was not there and download is in progress
    #          "finished" .. if nothing was done at all
	def refill_list_part(self,parent,handler,filename,url,trydownload=True,loadchunks=True):
		if filename in self.loadedFiles:
			#print "do not fill:"+filename
			return "finished"
		filepath = os.path.join(self.cache_dir, filename)
		try:
			self.catalogue_file = open(filepath,"r")
			print "loading "+filename
			try:
				xml.sax.parse(self.catalogue_file,handler)
			except:
				print "parse failed of "+filename
				if trydownload:
					print "redownloading ... "+url
					self.download_catalogue(url,filepath,loadchunks)
					return "downloading"
				else:
					return "finished"
			self.catalogue_file.close()
			self.loadedFiles.append(filename)
			return "loaded"
		except IOError:
			if trydownload:
				print "downloading "+url
				self.download_catalogue(url,filepath,loadchunks)
				return "downloading"
			else:
				return "finished"

	def hide_user(self, hide=True):
		if hide:
			self.load_current_size = 0
			self.load_total_size = 0
			self.download_try_no = 1
			self.download_try_max = int(float(self.plugin.download_trys))
			self.updating = True
			self.notify_status_changed()
			self.tree_view.set_sensitive(False)
            # how do i get the widget of the toolbar button????
			#self.shell.get_ui_manager ().get_widget('/Toolbar/UpdateList').set_sensitive(False)
		else:
			self.updating = False
			self.notify_status_changed()
			self.tree_view.set_sensitive(True)
			# how do i get the widget of the toolbar button????
			#self.shell.get_ui_manager ().get_widget('/Toolbar/UpdateList').set_sensitive(False)

	def download_catalogue(self,url,filename,loadchunks):
		self.hide_user()
		self.catalogue_file = open(filename,"w")
		if loadchunks:
			self.catalogue_loader = rb.ChunkLoader()
			self.catalogue_loader.get_url_chunks(url, 4*1024, True, self.download_catalogue_chunk_cb, self.catalogue_file)
		else:
			self.catalogue_loader = rb.Loader()
			self.catalogue_loader.get_url(url, self.download_catalogue_cb, url)

	def download_catalogue_cb (self,result, url):
		if result == None:
			self.download_try_no+=1
			if self.download_try_no > self.download_try_max:
				print "error while downloading"
			else:
				self.notify_status_changed()
				self.catalogue_loader = rb.Loader()
				self.catalogue_loader.get_url(url, self.download_catalogue_cb, url)
				return
		else:
			# download finished
			print "download finished"
			self.catalogue_loader = None
			self.catalogue_file.write(result)
		self.catalogue_file.close()
		self.hide_user(False)
		self.refill_list()

	def download_catalogue_chunk_cb (self, result, total, out):
		if not result:
			# download finished
			print "download finished"
			self.catalogue_loader = None
			out.close()
			self.hide_user(False)
			self.refill_list()
		elif isinstance(result, Exception):
			# complain
			print "download error!!!"+result.message
			out.close()
			self.hide_user(False)
			self.refill_list()
			pass
		else:
			# downloading...
			out.write(result)
			self.load_current_size += len(result)
			self.load_total_size = total
			self.notify_status_changed()

gconf_keys = {'download_trys' : '/apps/rhythmbox/plugins/radio-browser/download_trys',
	'min_bitrate': '/apps/rhythmbox/plugins/radio-browser/min_bitrate',
	'outputpath': '/apps/rhythmbox/plugins/radio-browser/streamripper_outputpath'
	}

class RadioBrowserPlugin (rb.Plugin):
	def __init__(self):
		rb.Plugin.__init__(self)
	def activate(self, shell):
		db = shell.props.db
		entry_type = db.entry_register_type("RadioBrowserEntryType")
		entry_type.category = rhythmdb.ENTRY_STREAM
		group = rb.rb_source_group_get_by_name ("library")
		self.source = gobject.new (RadioBrowserSource, shell=shell, name=_("Radio browser"), entry_type=entry_type,source_group=group,plugin=self)
		shell.append_source(self.source, None)
		shell.register_entry_type_for_source(self.source, entry_type)
		gobject.type_register(RadioBrowserSource)

		width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
		filepath = self.find_file("xiph-logo.png")
		if filepath:
			icon = gtk.gdk.pixbuf_new_from_file_at_size(filepath, width, height)
			self.source.set_property( "icon",  icon)

		action = gtk.Action('UpdateList', None, _("Update radio station list"), gtk.STOCK_GO_DOWN)
		action.connect('activate', lambda a: shell.get_property("selected-source").update_button_clicked())
		self.actiongroup = gtk.ActionGroup('RadioBrowserActionGroup')
		self.actiongroup.add_action(action)
	
		uim = shell.get_ui_manager ()
		uim.insert_action_group (self.actiongroup)
		uim.ensure_update()

		# initialize gconf entries
		self.download_trys = gconf.client_get_default().get_string(gconf_keys['download_trys'])
		if not self.download_trys:
			self.download_trys = "3"
		gconf.client_get_default().set_string(gconf_keys['download_trys'], self.download_trys)

		self.min_bitrate = gconf.client_get_default().get_string(gconf_keys['min_bitrate'])
		if not self.min_bitrate:
			self.min_bitrate = "96"
		gconf.client_get_default().set_string(gconf_keys['min_bitrate'], self.min_bitrate)

		self.outputpath = gconf.client_get_default().get_string(gconf_keys['outputpath'])
		if not self.outputpath:
			self.outputpath = os.path.expanduser("~")
			# try to read xdg music dir
			try:
				f = open(self.outputpath+"/.config/user-dirs.dirs","r")
			except IOError:
				print "xdg user dir file not found"
			else:
				for line in f:
					if line.startswith("XDG_MUSIC_DIR"):
						self.outputpath = os.path.expandvars(line.split("=")[1].strip().strip('"'))
						print self.outputpath
				f.close()
		gconf.client_get_default().set_string(gconf_keys['outputpath'], self.outputpath)

	def create_configure_dialog(self, dialog=None):
		if not dialog:
			builder_file = self.find_file("prefs.ui")
			builder = gtk.Builder()
			builder.add_from_file(builder_file)
			dialog = builder.get_object('radio_browser_prefs')
			dialog.connect("response",self.dialog_response)
			self.spin_download_trys = builder.get_object('SpinButton_DownloadTrys')
			self.spin_download_trys.connect("changed",self.download_trys_changed)
			self.spin_min_bitrate = builder.get_object('SpinButton_Bitrate')
			self.spin_min_bitrate.connect("changed",self.download_bitrate_changed)
			self.entry_outputpath = builder.get_object('Entry_OutputPath')
			self.entry_outputpath.connect("changed",self.outputpath_changed)

			self.spin_download_trys.set_value(float(self.download_trys))
			self.spin_min_bitrate.set_value(float(self.min_bitrate))
			self.entry_outputpath.set_text(self.outputpath)

		dialog.present()
		return dialog

	def dialog_response(self,dialog,response):
		dialog.hide()

	def download_trys_changed(self,spin):
		self.download_trys = str(self.spin_download_trys.get_value())
		gconf.client_get_default().set_string(gconf_keys['download_trys'], self.download_trys)

	def download_bitrate_changed(self,spin):
		self.min_bitrate = str(self.spin_min_bitrate.get_value())
		gconf.client_get_default().set_string(gconf_keys['min_bitrate'], self.min_bitrate)

	def outputpath_changed(self,entry):
		self.outputpath = self.entry_outputpath.get_text()
		gconf.client_get_default().set_string(gconf_keys['outputpath'], self.outputpath)
       
	def deactivate(self, shell):
		uim = shell.get_ui_manager ()
		uim.remove_action_group(self.actiongroup)
		self.source.delete_thyself()
		self.source = None
