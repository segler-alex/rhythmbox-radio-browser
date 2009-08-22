import rb
import gobject

class MySource(rb.BrowserSource):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        rb.BrowserSource.__init__(self,name="IcecastPlugin")
    def do_set_property(self, property, value):
        print "not implemented"
    def do_impl_get_browser_key (self):
        print "not implemented"
    def do_impl_get_paned_key (self):
        print "not implemented"
    def do_impl_pack_paned (self, paned):
        print "not implemented"
    def do_impl_show_entry_popup(self):
        print "not implemented"
    def do_impl_get_ui_actions(self):
        print "not implemented"
    def do_impl_get_status(self):
        print "not implemented"
    def do_impl_activate(self):
        print "not implemented"
    def do_impl_delete_thyself(self):
        print "not implemented"

class IcecastPlugin (rb.Plugin):
    def __init__(self):
        rb.Plugin.__init__(self)
    def activate(self, shell):
        db = shell.props.db
        entry_type = db.entry_register_type("IcecastEntryType")
        mysource = gobject.new (MySource, shell=shell, name=_("Icecast Source"), entry_type=entry_type)
        shell.append_source(mysource, None)
        shell.register_entry_type_for_source(mysource, entry_type)
        gobject.type_register(MySource)
    def deactivate(self, shell):
        del self.string
