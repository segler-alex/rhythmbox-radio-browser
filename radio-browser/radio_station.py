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
		self.negativevotes = ""
		self.id = ""

	def getRealURL(self):
		return self.listen_url
