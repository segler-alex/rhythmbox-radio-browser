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

from radio_browser_source import RadioBrowserSource

gconf_keys = {'download_trys' : '/apps/rhythmbox/plugins/radio-browser/download_trys',
	'min_bitrate': '/apps/rhythmbox/plugins/radio-browser/min_bitrate',
	'outputpath': '/apps/rhythmbox/plugins/radio-browser/streamripper_outputpath'
	}

class RadioBrowserPlugin (rb.Plugin):
	def __init__(self):
		rb.Plugin.__init__(self)

	""" on plugin activation """
	def activate(self, shell):
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

		self.min_bitrate = gconf.client_get_default().get_string(gconf_keys['min_bitrate'])
		if not self.min_bitrate:
			self.min_bitrate = "96"
		gconf.client_get_default().set_string(gconf_keys['min_bitrate'], self.min_bitrate)

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

	""" immediately change gconf values in config dialog after user changed download trys """
	def download_trys_changed(self,spin):
		self.download_trys = str(self.spin_download_trys.get_value())
		gconf.client_get_default().set_string(gconf_keys['download_trys'], self.download_trys)

	""" immediately change gconf values in config dialog after user changed minimal bitrate """
	def download_bitrate_changed(self,spin):
		self.min_bitrate = str(self.spin_min_bitrate.get_value())
		gconf.client_get_default().set_string(gconf_keys['min_bitrate'], self.min_bitrate)

	""" immediately change gconf values in config dialog after user changed recorded music output directory """
	def outputpath_changed(self,entry):
		self.outputpath = self.entry_outputpath.get_text()
		gconf.client_get_default().set_string(gconf_keys['outputpath'], self.outputpath)

	""" on plugin deactivation """
	def deactivate(self, shell):
		uim = shell.get_ui_manager ()
		uim.remove_action_group(self.actiongroup)
		self.source.delete_thyself()
		self.source = None
