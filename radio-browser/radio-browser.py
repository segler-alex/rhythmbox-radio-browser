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
import os

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

class IcecastHandler(xml.sax.handler.ContentHandler):
  def __init__(self,model,parent):
    self.model = model
    self.parent = parent
 
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
 
  def endElement(self, name):
    if name == "entry":
      self.model.append(self.parent,(self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url))
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
      self.model.append(self.parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,"shoutcast:"+str(self.entry.listen_id)])

class IcecastSource(rb.StreamingSource):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        self.hasActivated = False
        self.loadedFiles = []
        self.createdGenres = {}
        rb.StreamingSource.__init__(self,name="IcecastPlugin")

    def do_set_property(self, property, value):
        print "try to set property("+str(property)+") to value: "+str(value)

    def do_impl_get_status(self):
        if self.updating:
           if self.load_total_size > 0:
              progress = min (float(self.load_current_size) / self.load_total_size, 1.0)
           else:
              progress = -1.0
           return (_("Loading catalog.."), None, progress)
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

           self.cache_dir = rb.find_user_cache_file("icecast")
           if os.path.exists(self.cache_dir) is False:
              os.makedirs(self.cache_dir, 0700)
           self.updating = False

           self.filter_entry = gtk.Entry()
           self.filter_entry.connect("changed",self.filter_entry_changed)

           self.tree_store = gtk.TreeStore(str,str,str,str,str)
           self.sorted_list_store = gtk.TreeModelSort(self.tree_store)
           self.filtered_list_store = self.sorted_list_store.filter_new()
           self.filtered_list_store.set_visible_func(self.list_store_visible_func)
           self.tree_view = gtk.TreeView(self.filtered_list_store)

           column_title = gtk.TreeViewColumn("Title",gtk.CellRendererText(),text=0)
           column_title.set_resizable(True)
           column_title.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
           column_title.set_fixed_width(100)
           column_title.set_expand(True)
           self.tree_view.append_column(column_title)

           column_genre = gtk.TreeViewColumn("Genre",gtk.CellRendererText(),text=1)
           column_genre.set_resizable(True)
           column_genre.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
           column_genre.set_fixed_width(100)
           self.tree_view.append_column(column_genre)

           column_bitrate = gtk.TreeViewColumn("Bitrate",gtk.CellRendererText(),text=2)
           column_bitrate.set_resizable(True)
           column_bitrate.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
           column_bitrate.set_fixed_width(100)
           self.tree_view.append_column(column_bitrate)

           column_song = gtk.TreeViewColumn("Current Song",gtk.CellRendererText(),text=3)
           column_song.set_resizable(True)
           column_song.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
           column_song.set_fixed_width(100)
           column_song.set_expand(True)
           self.tree_view.append_column(column_song)
           self.tree_view.connect("row-activated",self.row_activated_handler)

           mywin = gtk.ScrolledWindow()
           mywin.add(self.tree_view)
           mywin.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)

           self.update_button = gtk.Button("Update catalogue")
           self.update_button.connect("clicked",self.update_button_clicked)

           filterbox = gtk.HBox()
           filterbox.pack_start(gtk.Label("Filter:"),False)
           filterbox.pack_start(self.filter_entry)

           mybox = gtk.VBox()
           mybox.pack_start(filterbox,False)
           mybox.pack_start(mywin)
           mybox.pack_start(self.update_button,False)

           self.pack_start(mybox)
           mybox.show_all()

           self.refill_list()
        rb.BrowserSource.do_impl_activate (self)

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

    #def playing_changed (self, sp, playing):
    #    print "playing changed"

    #def playing_entry_changed (self, sp, entry):
    #    print "playing entry changed"

    #def playing_song_property_changed (self, sp, uri, property, old, new):
    #    print "property changed "+str(new)

    def filter_entry_changed(self,gtk_entry):
        self.filtered_list_store.refilter()
        self.notify_status_changed()

    def list_store_visible_func(self,model,iter):
        # returns true if the row should be visible
        filter_string = self.filter_entry.get_text().lower()
        if len(model) == 0:
           return True
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

    def update_button_clicked(self,button):
        # delete cache files
        files = os.listdir(self.cache_dir)
        for filename in files:
           filepath = os.path.join(self.cache_dir, filename)
           os.unlink(filepath)
        # clear shortcut lists
        self.loadedFiles = []
        self.createdGenres = {}
        # start filling again
        self.refill_list()

    def play_uri(self,uri,title):
        player = self.shell.get_player()
        player.stop()

        self.entry = self.shell.props.db.entry_lookup_by_location(uri)
        if self.entry == None:
           #self.shell.props.db.entry_delete(self.entry)
        
           self.entry = self.shell.props.db.entry_new(self.entry_type, uri)
           self.shell.props.db.set(self.entry, rhythmdb.PROP_TITLE, title+" ("+uri+")")
           self.shell.props.db.commit()
        #shell.load_uri(uri,False)

        player.play_entry(self.entry)

    def row_activated_handler(self,treeview,path,column):
        myiter = self.tree_store.get_iter(self.sorted_list_store.convert_path_to_child_path(self.filtered_list_store.convert_path_to_child_path(path)))
        uri = self.tree_store.get_value(myiter,4)
        title = self.tree_store.get_value(myiter,0)

        if not uri == None:
           if uri.startswith("shoutcast:"):
              # special handling for shoutcast
              shoutcast_id = uri.split(":")[1];
              shoutcast_uri = "http://www.shoutcast.com"+self.tunein+"?id="+shoutcast_id
              self.download_shoutcast_playlist(shoutcast_uri,title)
           else:
              # presume its an icecast link
              self.play_uri(uri,title)
        else:
           if self.tree_store.is_ancestor(self.tree_iter_shoutcast,myiter):
              print "download genre "+title
              handler_stations = ShoutcastHandler(self.tree_store,myiter)
              self.refill_list_part(myiter,handler_stations,"shoutcast--"+title+".xml","http://www.shoutcast.com/sbin/newxml.phtml?genre="+title,True,False)

    def download_shoutcast_playlist(self,uri,title):
        print "starting download: "+uri
        self.hide_user()
        playlist_loader = rb.Loader()
        playlist_loader.get_url(uri,self.shoutcast_download_callback,uri,title)

    def shoutcast_download_callback(self,data,uri,title):
        self.hide_user(False)
        if data == None:
           print "shoutcast download failed:"+uri
        else:
           print "shoutcast download OK:"+uri
           lines = data.splitlines()
           for line in lines:
              if line.startswith("File"):
                 uri_single = line.split("=")[1];
                 print "playing uri:"+uri_single
                 self.play_uri(uri_single,title)
                 return
           print "could not find 'File' entry"

    def do_impl_delete_thyself(self):
        print "not implemented"

    def refill_list(self):
       # deactivate sorting
       self.sorted_list_store.reset_default_sort_func()
       #self.tree_view.set_model()
       if not "start" in self.loadedFiles:
          # delete old entries
          self.tree_store.clear()
          # create parent entries
          self.tree_iter_icecast = self.tree_store.append(None,("Icecast",None,None,None,None))
          self.tree_iter_shoutcast = self.tree_store.append(None,("Shoutcast",None,None,None,None))
          self.loadedFiles.append("start")

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
                parent = self.tree_store.append(self.tree_iter_shoutcast,[genre,None,None,None,None])
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
# returns: True .. if file is present and could be loaded
#          False .. if file was not there and download is in progress
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
          self.updating = True
          self.notify_status_changed()
          self.tree_view.set_sensitive(False)
          self.update_button.set_sensitive(False)
       else:
          self.updating = False
          self.notify_status_changed()
          self.tree_view.set_sensitive(True)
          self.update_button.set_sensitive(True)

    def download_catalogue(self,url,filename,loadchunks):
       self.hide_user()
       self.catalogue_file = open(filename,"w")
       if loadchunks:
          self.catalogue_loader = rb.ChunkLoader()
          self.catalogue_loader.get_url_chunks(url, 4*1024, True, self.download_catalogue_chunk_cb, self.catalogue_file)
       else:
          self.catalogue_loader = rb.Loader()
          self.catalogue_loader.get_url(url, self.download_catalogue_cb, self.catalogue_file)

    def download_catalogue_cb (self,result, out):
        if result == None:
           print "error while downloading"
        else:
           # download finished
           print "download finished"
           self.catalogue_loader = None
           out.write(result)
        out.close()
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

class RadioBrowserPlugin (rb.Plugin):
    def __init__(self):
        rb.Plugin.__init__(self)
    def activate(self, shell):
        db = shell.props.db
        entry_type = db.entry_register_type("RadioBrowserEntryType")
        entry_type.category = rhythmdb.ENTRY_STREAM
        group = rb.rb_source_group_get_by_name ("library")
        self.source = gobject.new (IcecastSource, shell=shell, name=_("Radio browser"), entry_type=entry_type,source_group=group)
        shell.append_source(self.source, None)
        shell.register_entry_type_for_source(self.source, entry_type)
        gobject.type_register(IcecastSource)

        width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
        icon = gtk.gdk.pixbuf_new_from_file_at_size(self.find_file("xiph-logo.png"), width, height)
        self.source.set_property( "icon",  icon) 
       
    def deactivate(self, shell):
        self.source.delete_thyself()
        self.source = None
