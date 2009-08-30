import rb
import rhythmdb
import gobject
import xml.sax.handler
import httplib
 
class IcecastHandler(xml.sax.handler.ContentHandler):
  def __init__(self):
    self.mapping = {}
    self.genre_mapping = {}
 
  def startElement(self, name, attributes):
    self.currentEntry = name;
    if name == "entry":
      self.server_name = ""
      self.listen_url = ""
      self.genre = ""
 
  def characters(self, data):
    if self.currentEntry == "server_name":
      self.server_name += data  
    elif self.currentEntry == "listen_url":
      self.listen_url += data
    elif self.currentEntry == "genre":
      self.genre += data
 
  def endElement(self, name):
    if name == "entry":
      self.mapping[self.server_name] = self.listen_url
      self.genre_mapping[self.server_name] = self.genre
    self.currentEntry = ""

class IcecastSource(rb.BrowserSource):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        self.hasActivated = False
        rb.BrowserSource.__init__(self,name="IcecastPlugin")

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
           shell = self.get_property('shell')
           self.db = shell.get_property('db')
           self.entry_type = self.get_property('entry-type')
           self.hasActivated = True
    
           self.catalogue_file_name = rb.find_user_cache_file("icecastdir.xml")
           self.updating = False

           self.download_catalogue()
        rb.BrowserSource.do_impl_activate (self)

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
           for key,value in handler.mapping.iteritems():
              entry = self.db.entry_new(self.entry_type, value)
              self.db.set(entry, rhythmdb.PROP_TITLE, key)
              if key in handler.genre_mapping:
                 self.db.set(entry, rhythmdb.PROP_GENRE, handler.genre_mapping[key])
           self.db.commit();

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
