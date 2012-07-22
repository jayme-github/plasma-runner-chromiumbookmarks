import os, sqlite3, json
from shutil import copy2
from tempfile import mkstemp
from urlparse import urljoin
from urllib import urlencode
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
		self._keywords = {}
		self._bookmarks = []
		
		#FIXME: Should go to config
		self._googleBaseURL = 'https://www.google.com/'
		self._pathWebData = os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Web Data' )
		self._pathLocalState = os.path.join( os.environ.get('HOME'), '.config/chromium/Local State' )
		self._pathBookmarks = os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Bookmarks' )

		self.setSyntaxes( [ Plasma.RunnerSyntax("<Chromium keyword> :q:", "Search for :q: using Chromium keyword"),
							Plasma.RunnerSyntax(":q:", "Search for :q: in your Chromium bookmarks") ] )

		# Initially read data
		self._readKeywords()
		self._readBookmarks()
		self._readLastKnownGoogleUrl()


		# Watch the files for changes
		self._watcher = KDirWatch(self)
		self._watcher.addFile( self._pathWebData )
		self._watcher.addFile( self._pathLocalState )
		self._watcher.addFile( self._pathBookmarks )
		self.connect(self._watcher, SIGNAL('created(QString)'), self._updateData)
		self.connect(self._watcher, SIGNAL('dirty(QString)'), self._updateData)

	def _updateData(self, path):
		'''
		Called by KDirWatch if a watched dir has changed (dirty)
		'''
		if path == self._pathWebData:
			self._readKeywords()
		elif path == self._pathLocalState:
			self._readLastKnownGoogleUrl()
		elif path == self._pathBookmarks:
			self._readBookmarks()
 
	def _readKeywords(self):
		'''
		Copy Chromium Web Data as it is locked if Chromium running...
		TODO: Is there a way to open sqlite db read-only if it is locked?
		'''
		if os.path.isfile( self._pathWebData ) and os.access( self._pathWebData, os.R_OK ):
			fd, dbfile = mkstemp('krunner-chromium')
			copy2( self._pathWebData, dbfile )
			conn = sqlite3.connect( dbfile )
			cur = conn.cursor()
			cur.execute('SELECT `short_name`, `keyword`, `url` FROM keywords;')
			self._keywords = {}
			for row in cur.fetchall():
				if not row[1] in self._keywords:
					self._keywords[ row[1] ] = (row[0], row[2])
			cur.close()
			os.unlink( dbfile )

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

	def _readLastKnownGoogleUrl(self):
		'''
		Read the last_known_google_url from "Local State"
		'''
		if os.path.isfile( self._pathLocalState ) and os.access( self._pathLocalState, os.R_OK ):
			localStateFile = open( self._pathLocalState, 'r' )
			localStateJson = json.load( localStateFile )
			localStateFile.close()
			if 'browser' in localStateJson and 'last_known_google_url' in localStateJson['browser']	and localStateJson['browser']['last_known_google_url']:
				self._googleBaseURL = localStateJson['browser']['last_known_google_url']

	def match(self, context):
		'''
		Called by krunner to let us add actions for the user
		'''
		if not context.isValid() or not self._keywords or not self._bookmarks:
			return
		
		# look for our keywords
		for keyword in self._keywords:
			if context.query().startsWith( keyword + ' ' ):
				# ignore less than 3 characters (in addition to the keyword)
				if len( context.query()[len(keyword):].trimmed() ) >= 3:
					self._matchKeyword( context, keyword )

		# look for bookmarks
		def queryInBookmarks(element):
			if context.query().toLower() in element['name'].lower():
				return element
		for match in filter( queryInBookmarks, self._bookmarks ):
			self._matchBookmark( context, match )

	def _matchBookmark(self, context, matchedBookmark):
		# strip the keyword and spaces
		q = context.query().trimmed()
		
		# Set location
		self._location = matchedBookmark['url']

		# create an action for the user, and send it to krunner
		m = Plasma.QueryMatch(self.runner)
		m.setText("%s: '%s'" % ( matchedBookmark['name'], self._location  ) )
		m.setType(Plasma.QueryMatch.ExactMatch)
		m.setIcon(KIcon("bookmarks")) 
		m.setData( q )
		context.addMatch(q, m)

	def _matchKeyword(self, context, matchedKeyword):
		'''
		Create QueryMatch instance for this keyword match
		'''
		# strip the keyword and spaces
		q = context.query()[len(matchedKeyword):].trimmed()
		
		# TODO: Default google search
		# Default google search URL is some freaky contruction like:
		# {google:baseURL}search?{google:RLZ}{google:acceptedSuggestion}{google:originalQueryForSuggestion}{google:searchFieldtrialParameter}{google:instantFieldTrialGroupParameter}sourceid=chrome&client=ubuntu&channel=cs&ie={inputEncoding}&q=%s
		# google:baseURL is in attr "last_known_google_url" in ~./config/chromium/Local State

		# Resuling URL for query "fofo" is something like:
		# https://www.google.de/search?aq=f&sourceid=chrome&client=ubuntu&channel=cs&ie=UTF-8&q=fofo
		
		if q:
			self._location = self._keywords[matchedKeyword][1].replace('{searchTerms}', q)
			# Quick workaround...
			if self._location.startswith( '{google:baseURL}' ):
				# Set "aq=f" if the user did not choose the query from the Google Suggest box.
				self._location = urljoin( self._googleBaseURL, 'search?' + urlencode( {'q': q, 'aq': 'f'} ) )

		# create an action for the user, and send it to krunner
		m = Plasma.QueryMatch(self.runner)
		m.setText("%s: '%s'" % (self._keywords[matchedKeyword][0], q) )
		m.setType(Plasma.QueryMatch.ExactMatch)
		m.setIcon(KIcon("chromium"))
		m.setData(q)
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
