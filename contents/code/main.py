import os, json
from PyQt4.QtCore import SIGNAL
from PyKDE4 import plasmascript
from PyKDE4.plasma import Plasma
from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import KToolInvocation
from PyKDE4.kio import KDirWatch

class ChromiumRunner(plasmascript.Runner):
 
	def init(self):
		'''
		called upon creation to let us run any intialization
		tell the user how to use this runner
		'''
		self._bookmarks = []
		
		#FIXME: Should go to config
		self._pathBookmarks = os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Bookmarks' )

		self.setSyntaxes( [ Plasma.RunnerSyntax(":q:", "Search for :q: in your Chromium bookmarks") ] )

		# Initially read data
		self._readBookmarks()


		# Watch the files for changes
		self._watcher = KDirWatch(self)
		self._watcher.addFile( self._pathBookmarks )
		self.connect(self._watcher, SIGNAL('created(QString)'), self._updateData)
		self.connect(self._watcher, SIGNAL('dirty(QString)'), self._updateData)

	def _updateData(self, path):
		'''
		Called by KDirWatch if a watched dir has changed (dirty)
		'''
		if path == self._pathBookmarks:
			self._readBookmarks()
 
	def _readBookmarks(self):
		'''
		Read Chromium bookmarks
		'''
		if os.path.isfile( self._pathBookmarks ) and os.access( self._pathBookmarks, os.R_OK ):
			bfile = open( self._pathBookmarks, 'r' )
			bjson = json.load(bfile)
			bfile.close()
			
			self._bookmarks = []
			def walk( element ):
				for item in element:
					if item['type'] == 'url':
						tmp = {'url': item['url'], 'name': item['name'] }
						if not tmp in self._bookmarks:
							self._bookmarks.append( tmp )
					elif item['type'] == 'folder':
						walk( item['children'] )
			
			for key in bjson['roots']:
				if bjson['roots'][key]['children']:
					walk( bjson['roots'][key]['children'] )

	def match(self, context):
		'''
		Called by krunner to let us add actions for the user
		'''
		if not context.isValid() or not self._bookmarks:
			return
		
		matches = []
		for bookmark in self._bookmarks:
			if context.query().toLower() == bookmark['name'].lower():
				if not (Plasma.QueryMatch.ExactMatch, bookmark) in matches:
					matches.append( (Plasma.QueryMatch.ExactMatch, bookmark) )
			elif context.query().toLower() in bookmark['name'].lower():
				if not (Plasma.QueryMatch.PossibleMatch, bookmark) in matches:
					matches.append( (Plasma.QueryMatch.PossibleMatch, bookmark) )

		if not matches:
			return

		# strip the keyword and spaces
		q = context.query().trimmed()

		for match in matches:
			# Set location
			self._location = match[1]['url']

			# create an action for the user, and send it to krunner
			m = Plasma.QueryMatch(self.runner)
			m.setText( "%s: '%s'" % ( match[1]['name'], self._location  ) )
			m.setType( match[0] )
			m.setIcon( KIcon('bookmarks') )
			m.setData( q )
			context.addMatch(q, m)

	def run(self, context, match):
		'''
		called by KRunner when the user selects our action
		'''
		if self._location:
			KToolInvocation.invokeBrowser(self._location)

def CreateRunner(parent):
	'''
	called by krunner, must simply return an instance of the runner object
	'''
	return ChromiumRunner(parent)
