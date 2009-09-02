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

class IcecastHandler(xml.sax.handler.ContentHandler):
  def __init__(self,model):
    self.model = model
 
  def startElement(self, name, attributes):
    self.currentEntry = name;
    if name == "entry":
      self.entry = RadioStation()
 
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
      self.model.append([self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,self.entry.listen_url])
    self.currentEntry = ""

class IcecastSource(rb.StreamingSource):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        self.hasActivated = False
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

           self.catalogue_file_name = rb.find_user_cache_file("icecastdir.xml")
           self.updating = False

           self.list_store = gtk.ListStore(str,str,str,str,str)
           self.list_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
           self.filtered_list_store = self.list_store.filter_new()
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
           self.update_button.set_sensitive(False)
           self.update_button.connect("clicked",self.update_button_clicked)

           self.filter_entry = gtk.Entry()
           self.filter_entry.connect("changed",self.filter_entry_changed)

           filterbox = gtk.HBox()
           filterbox.pack_start(gtk.Label("Filter:"),False)
           filterbox.pack_start(self.filter_entry)

           mybox = gtk.VBox()
           mybox.pack_start(filterbox,False)
           mybox.pack_start(mywin)
           mybox.pack_start(self.update_button,False)

           self.pack_start(mybox)
           mybox.show_all()

           self.download_catalogue()
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
        if filter_string == "":
           return True
        elif model.get_value(iter,0).lower().find(filter_string) >= 0:
           return True
        elif model.get_value(iter,1).lower().find(filter_string) >= 0:
           return True
        else:
           return False

    def update_button_clicked(self,button):
        self.update_button.set_sensitive(False)
        self.download_catalogue()

    def play_uri(self,uri,title):
        self.entry = self.shell.props.db.entry_lookup_by_location(uri)
        if not self.entry == None:
           self.shell.props.db.entry_delete(self.entry)
        
        self.entry = self.shell.props.db.entry_new(self.entry_type, uri)
        self.shell.props.db.set(self.entry, rhythmdb.PROP_TITLE, title+" ("+uri+")")
        self.shell.props.db.commit()
        #shell.load_uri(uri,False)

        player = self.shell.get_player()
        player.stop()
        player.play_entry(self.entry)

    def row_activated_handler(self,treeview,path,column):
        myiter = self.list_store.get_iter(self.filtered_list_store.convert_path_to_child_path(path))
        uri = self.list_store.get_value(myiter,4)
        title = self.list_store.get_value(myiter,0)
        self.play_uri(uri,title)

    def do_impl_delete_thyself(self):
        print "not implemented"

    def download_catalogue_chunk_cb (self, result, total, out):
        if not result:
           # download finished
           self.updating = False
           self.catalogue_loader = None
           out.close()
           self.refill_list()
           self.update_button.set_sensitive(True)

        elif isinstance(result, Exception):
           # complain
           pass
        else:
           # downloading...
           out.write(result)
           self.load_current_size += len(result)
           self.load_total_size = total
           self.notify_status_changed()

    def refill_list(self):
       self.list_store.clear()
       handler = IcecastHandler(self.list_store)
       self.catalogue_file = open(self.catalogue_file_name,"r")
       xml.sax.parse(self.catalogue_file,handler)
       self.catalogue_file.close()
       
       #self.tree_view.columns_autosize()
       self.notify_status_changed()

    def download_catalogue(self):
       self.load_current_size = 0
       self.load_total_size = 0
       self.updating = True
       self.catalogue_file = open(self.catalogue_file_name,"w")
       self.catalogue_loader = rb.ChunkLoader()
       self.catalogue_loader.get_url_chunks("http://dir.xiph.org/yp.xml", 4*1024, True, self.download_catalogue_chunk_cb, self.catalogue_file)

class IcecastPlugin (rb.Plugin):
    def __init__(self):
        rb.Plugin.__init__(self)
    def activate(self, shell):
        db = shell.props.db
        entry_type = db.entry_register_type("IcecastEntryType")
        entry_type.category = rhythmdb.ENTRY_STREAM
        group = rb.rb_source_group_get_by_name ("library")
        self.source = gobject.new (IcecastSource, shell=shell, name=_("Icecast"), entry_type=entry_type,source_group=group)
        shell.append_source(self.source, None)
        shell.register_entry_type_for_source(self.source, entry_type)
        gobject.type_register(IcecastSource)

        width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
        icon = gtk.gdk.pixbuf_new_from_file_at_size(self.find_file("xiph-logo.png"), width, height)
        self.source.set_property( "icon",  icon) 
       
    def deactivate(self, shell):
        self.source.delete_thyself()
        self.source = None
