#    This file is part of IcecastPlugin for Rhythmbox.
#
#    Copyright (C) 2006 <segler_alex@web.de>
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

class RadioStation:
  def __init__(self):
    self.listen_url = ""
    self.server_name = ""
    self.genre = ""
    self.bitrate = ""
    self.current_song = ""

class IcecastHandler(xml.sax.handler.ContentHandler):
  def __init__(self):
    self.mapping = []
 
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
      self.mapping.append(self.entry)
    self.currentEntry = ""

class IcecastSource(rb.Source):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        self.hasActivated = False
        rb.Source.__init__(self,name="IcecastPlugin")

    def do_set_property(self, property, value):
        print "not implemented"

    def do_impl_get_status(self):
        if self.updating:
           if self.load_total_size > 0:
              progress = min (float(self.load_current_size) / self.load_total_size, 1.0)
           else:
              progress = -1.0
           return (_("Loading catalog"), None, progress)
        else:
           return (_("this is the icecast directory plugin "),None,0.0)

    def do_impl_activate(self):
        if not self.hasActivated:
           #self.__paned_box.set_property("visible", False)
           shell = self.get_property('shell')
           self.db = shell.get_property('db')
           self.entry_type = self.get_property('entry-type')
           self.hasActivated = True
    
           self.catalogue_file_name = rb.find_user_cache_file("icecastdir.xml")
           self.updating = False

           self.list_store = gtk.ListStore(str,str,str,str,str)
           self.list_store.set_sort_column_id(0,gtk.SORT_ASCENDING)
           self.tree_view = gtk.TreeView(self.list_store)
           self.tree_view.set_property("visible", True)

           column_title = gtk.TreeViewColumn("Title",gtk.CellRendererText(),text=0)
           column_title.set_resizable(True)
           self.tree_view.append_column(column_title)

           column_genre = gtk.TreeViewColumn("Genre",gtk.CellRendererText(),text=1)
           column_genre.set_resizable(True)
           self.tree_view.append_column(column_genre)

           column_bitrate = gtk.TreeViewColumn("Bitrate",gtk.CellRendererText(),text=2)
           column_bitrate.set_resizable(True)
           self.tree_view.append_column(column_bitrate)

           column_song = gtk.TreeViewColumn("Current Song",gtk.CellRendererText(),text=3)
           column_song.set_resizable(True)
           self.tree_view.append_column(column_song)

           self.tree_view.connect("row-activated",self.row_activated_handler)

           mywin = gtk.ScrolledWindow()
           mywin.add(self.tree_view)
           mywin.set_property("visible", True)
           mywin.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)
           self.pack_start(mywin)

           self.download_catalogue()
        rb.BrowserSource.do_impl_activate (self)

    def play_uri(self,uri):
        shell = self.get_property('shell')
        player = shell.get_player()
        #player.props.player.open(uri)
        shell.load_uri(uri,False)
        self.entry = shell.props.db.entry_lookup_by_location(uri)
        player.play_entry(self.entry)
        #shell.add_to_queue(uri)
        #shell.props.shell_player.play()


    def row_activated_handler(self,treeview,path,column):
        myiter = self.list_store.get_iter(path)
        uri = self.list_store.get_value(myiter,4)
        self.play_uri(uri)

    def do_impl_delete_thyself(self):
        print "not implemented"

    def download_catalogue_chunk_cb (self, result, total, out):
        if not result:
           # download finished
           self.updating = False
           self.catalogue_loader = None
           out.close()

           handler = IcecastHandler()
           self.catalogue_file = open(self.catalogue_file_name,"r")
           xml.sax.parse(self.catalogue_file,handler)
           self.catalogue_file.close()
           for station in handler.mapping:
              self.list_store.append([station.server_name,station.genre,station.bitrate,station.current_song,station.listen_url])

        elif isinstance(result, Exception):
           # complain
           pass
        else:
           # downloading...
           out.write(result)
           self.load_current_size += len(result)
           self.load_total_size = total
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
        group = rb.rb_source_group_get_by_name ("library")
        self.source = gobject.new (IcecastSource, shell=shell, name=_("icecast directory"), entry_type=entry_type,source_group=group)
        shell.append_source(self.source, None)
        shell.register_entry_type_for_source(self.source, entry_type)
        gobject.type_register(IcecastSource)
       
    def deactivate(self, shell):
        self.source.delete_thyself()
        self.source = None
