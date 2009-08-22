import rb
import gobject

class IcecastSource(rb.BrowserSource):
    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE|gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        rb.BrowserSource.__init__(self,name="IcecastPlugin")
    def do_set_property(self, property, value):
        print "not implemented"
    def do_impl_get_browser_key (self):
        return "/apps/rhythmbox/plugins/magnatune/show_browser"
    def do_impl_get_paned_key (self):
        return "/apps/rhythmbox/plugins/magnatune/paned_position"
    def do_impl_pack_paned (self, paned):
        print "not implemented"
    def do_impl_show_entry_popup(self):
        print "not implemented"
    def do_impl_get_ui_actions(self):
        return []
    def do_impl_get_status(self):
        return (_("this is the icecast directory plugin"),None,0.0)
    def do_impl_activate(self):
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
