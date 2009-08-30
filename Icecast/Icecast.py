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
    #print "element:"+name
    self.currentEntry = name;
    if name == "entry":
      self.server_name = ""
      self.listen_url = ""
      self.genre = ""
 
  def characters(self, data):
    #print "data:"+data
    if self.currentEntry == "server_name":
      self.server_name += data  
    elif self.currentEntry == "listen_url":
      self.listen_url += data
    elif self.currentEntry == "genre":
      self.genre += data
 
  def endElement(self, name):
    #print "endelement:"+name
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
#    def do_impl_get_browser_key (self):
#        return "/apps/rhythmbox/plugins/magnatune/show_browser"
#    def do_impl_get_paned_key (self):
#        return "/apps/rhythmbox/plugins/magnatune/paned_position"
#    def do_impl_pack_paned (self, paned):
#        print "not implemented"
#    def do_impl_show_entry_popup(self):
#        print "not implemented"
#    def do_impl_get_ui_actions(self):
#        return []
    def do_impl_get_status(self):
        return (_("this is the icecast directory plugin "),None,0.0)
    def do_impl_activate(self):
        if not self.hasActivated:
           shell = self.get_property('shell')
           db = shell.get_property('db')
           entry_type = self.get_property('entry-type')
           self.hasActivated = True
    
           self.catalogue_file_name = rb.find_user_cache_file("icecastdir.xml")
           self.catalogue_file = open(self.catalogue_file_name,"w")
           conn = httplib.HTTPConnection("dir.xiph.org")
           conn.request("GET", "/yp.xml")
           r1 = conn.getresponse()
           data = r1.read()
           self.catalogue_file.write(data)
           self.catalogue_file.close()

           handler = IcecastHandler()
           self.catalogue_file = open(self.catalogue_file_name,"r")
           xml.sax.parse(self.catalogue_file,handler)
           self.catalogue_file.close()
           self.__catalogue_loader = rb.ChunkLoader()
           for key,value in handler.mapping.iteritems():
              entry = db.entry_new(entry_type, value)
              db.set(entry, rhythmdb.PROP_TITLE, key)
              if key in handler.genre_mapping:
                 db.set(entry, rhythmdb.PROP_GENRE, handler.genre_mapping[key])
           db.commit();
        rb.BrowserSource.do_impl_activate (self)
    def do_impl_delete_thyself(self):
        print "not implemented"

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
