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
import gconf
import gtk
from gettext import *

from radio_browser_source import RadioBrowserSource

gconf_keys = {'download_trys' : '/apps/rhythmbox/plugins/radio-browser/download_trys',
	'outputpath': '/apps/rhythmbox/plugins/radio-browser/streamripper_outputpath'
	}

class ConfigDialog (gtk.Dialog):
	def __init__(self,plugin):
		super(ConfigDialog,self).__init__()
		self.plugin = plugin

		self.add_button(gtk.STOCK_CLOSE,gtk.RESPONSE_CLOSE)

		table = gtk.Table(3,2)

		table.attach(gtk.Label(_("Trys to download file")),0,1,0,1)
		table.attach(gtk.Label(_("Streamripper output path")),0,1,1,2)

		self.spin_download_trys = gtk.SpinButton()
		#self.spin_download_trys.set_range(1,10)
		self.spin_download_trys.set_adjustment(gtk.Adjustment(value=1,lower=1,upper=10,step_incr=1))
		self.spin_download_trys.set_value(float(self.plugin.download_trys))
		self.spin_download_trys.connect("changed",self.download_trys_changed)
		table.attach(self.spin_download_trys,1,2,0,1)

		self.entry_outputpath = gtk.Entry()
		self.entry_outputpath.set_text(self.plugin.outputpath)
		self.entry_outputpath.connect("changed",self.outputpath_changed)
		table.attach(self.entry_outputpath,1,2,1,2)

		file_browser_button = gtk.Button(_("Browser"))
		file_browser_button.connect("clicked",self.on_file_browser)
		table.attach(file_browser_button,2,3,1,2)

		self.get_content_area().pack_start(table)

		self.set_title(_("Radio Browser Configuration"))
		self.set_size_request(420, 100)
		self.set_resizable(False)
		self.set_position(gtk.WIN_POS_CENTER)
		self.show_all()

	def on_file_browser(self,button):
		filew = gtk.FileChooserDialog("File selection",action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,buttons=(gtk.STOCK_CANCEL,
                                          gtk.RESPONSE_REJECT,
                                          gtk.STOCK_OK,
                                          gtk.RESPONSE_OK))
		filew.set_filename(self.plugin.outputpath)
		if filew.run() == gtk.RESPONSE_OK:
			self.entry_outputpath.set_text(filew.get_filename())
		filew.destroy()

	""" immediately change gconf values in config dialog after user changed download trys """
	def download_trys_changed(self,spin):
		self.plugin.download_trys = str(self.spin_download_trys.get_value())
		gconf.client_get_default().set_string(gconf_keys['download_trys'], self.plugin.download_trys)

	""" immediately change gconf values in config dialog after user changed recorded music output directory """
	def outputpath_changed(self,entry):
		self.plugin.outputpath = self.entry_outputpath.get_text()
		gconf.client_get_default().set_string(gconf_keys['outputpath'], self.plugin.outputpath)

class RadioBrowserPlugin (rb.Plugin):
	def __init__(self):
		rb.Plugin.__init__(self)

	""" on plugin activation """
	def activate(self, shell):
		# Get the translation file
		install('radio-browser')

		# register this source in rhythmbox
		db = shell.props.db
		entry_type = db.entry_register_type("RadioBrowserEntryType")
		entry_type.category = rhythmdb.ENTRY_STREAM
		group = rb.rb_source_group_get_by_name ("library")
		self.source = gobject.new (RadioBrowserSource, shell=shell, name=_("Radio browser"), entry_type=entry_type,source_group=group,plugin=self)
		shell.append_source(self.source, None)
		shell.register_entry_type_for_source(self.source, entry_type)
		gobject.type_register(RadioBrowserSource)

		# load plugin icon
		width, height = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
		filepath = self.find_file("radio-browser.png")
		if filepath:
			icon = gtk.gdk.pixbuf_new_from_file_at_size(filepath, width, height)
			self.source.set_property( "icon",  icon)

		self.actiongroup = gtk.ActionGroup('RadioBrowserActionGroup')

		# add "update-all" action to the toolbar
		action = gtk.Action('UpdateList', None, _("Update radio station list"), gtk.STOCK_GO_DOWN)
		action.connect('activate', lambda a: shell.get_property("selected-source").update_button_clicked())
		self.actiongroup.add_action(action)

		action = gtk.Action('ClearIconCache', None, _("Clear icon cache"), gtk.STOCK_CLEAR)
		action.connect('activate', lambda a: shell.get_property("selected-source").clear_iconcache_button_clicked())
		self.actiongroup.add_action(action)

		uim = shell.get_ui_manager ()
		uim.insert_action_group (self.actiongroup)
		uim.ensure_update()

		# try reading gconf entries and set default values if not readable
		self.download_trys = gconf.client_get_default().get_string(gconf_keys['download_trys'])
		if not self.download_trys:
			self.download_trys = "3"
		gconf.client_get_default().set_string(gconf_keys['download_trys'], self.download_trys)

		# set the output path of recorded music to xdg standard directory for music
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

	""" build plugin configuration dialog """
	def create_configure_dialog(self, dialog=None):
		if not dialog:
			dialog = ConfigDialog(self)
			dialog.connect("response",self.dialog_response)

		dialog.present()
		return dialog

	def dialog_response(self,dialog,response):
		dialog.hide()

	""" on plugin deactivation """
	def deactivate(self, shell):
		uim = shell.get_ui_manager ()
		uim.remove_action_group(self.actiongroup)
		self.source.delete_thyself()
		self.source = None
