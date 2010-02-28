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
			self.entry.server_type = attributes.get("mt")
			try:
				self.entry.homepage = "http://shoutcast.com/directory/search_results.jsp?searchCrit=simple&s="+urllib.quote_plus(self.entry.server_name.replace("- [SHOUTcast.com]","").strip())
			except:
				self.entry.homepage = ""
			self.model.append(self.parent,[self.entry.server_name,self.entry.genre,self.entry.bitrate,self.entry.current_song,"shoutcast:"+str(self.entry.listen_id),self.entry])
