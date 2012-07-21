import os, sqlite3, json
import logging
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

logging.basicConfig(filename='/tmp/krunner-chromium.log', format='%(asctime)s [%(levelname)s]: %(message)s', level=logging.DEBUG)

class MsgBoxRunner(plasmascript.Runner):
 
	def init(self):
		'''
		called upon creation to let us run any intialization
		tell the user how to use this runner
		'''
		logging.debug( 'Krunner init...' )
		self._keywords = {}
		self._bookmarks = {}
		
		#FIXME: Should go to config
		self._googleBaseURL = 'https://www.google.com/'
		self._pathWebData = os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Web Data' )
		self._pathLocalState = os.path.join( os.environ.get('HOME'), '.config/chromium/Local State' )
		self._pathBookmarks = os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Bookmarks' )

		self.addSyntax( Plasma.RunnerSyntax("<Chromium keyword> :q:", "Search for :q: using Chromium keyword") )

		self._readKeywords()
		self._readBookmarks()
		self._readLastKnownGoogleUrl()


		#TODO:
		# KDirWatch for Web Data (not sure if this qould be a good idea, how often does this file change?)
		# KDirWatch for Local State file?
		self._watcher = KDirWatch(self)
		self._watcher.addFile( self._pathWebData )
		self._watcher.addFile( self._pathLocalState )
		self._watcher.addFile( self._pathBookmarks )
		self.connect(self._watcher, SIGNAL('dirty(QString)'), self._updateData)

	def _updateData(self, path):
		'''
		Called by KDirWatch if a watched dir has changed (dirty)
		'''
		logging.debug( 'received KDirWatch signal for file "%s"', path )
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
		logging.debug( '_readKeywords' )
		if os.path.isfile( self._pathWebData ) and os.access( self._pathWebData, os.R_OK ):
			fd, dbfile = mkstemp('krunner-chromium')
			copy2( self._pathWebData, dbfile )
			conn = sqlite3.connect( dbfile )
			cur = conn.cursor()
			cur.execute('SELECT `short_name`, `keyword`, `url` FROM keywords;')
			for row in cur.fetchall():
				if not row[1] in self._keywords:
					self._keywords[ row[1] ] = (row[0], row[2])
			cur.close()
			os.unlink( dbfile )

	def _readBookmarks(self):
		'''
		Read Chromium bookmarks
		'''
		logging.debug( '_readBookmarks' )
		if os.path.isfile( self._pathBookmarks ) and os.access( self._pathBookmarks, os.R_OK ):
			pass

	def _readLastKnownGoogleUrl(self):
		'''
		Read the last_known_google_url from "Local State"
		'''
		logging.debug( '_readLastKnownGoogleUrl' )
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
		if not context.isValid() or not self._keywords:
			return
 
		q = context.query()

		matchedKeyword = False
		# look for our keywords
		for keyword in self._keywords:
			if q.startsWith( keyword + ' ' ):
				matchedKeyword = keyword
				# Stop at first match...
				break
		if not matchedKeyword:
			return
 
		# ignore less than 3 characters (in addition to the keyword)
		if q.length < 7:
			return
 
		# strip the keyword and spaces
		q = q[len(matchedKeyword):]
		q = q.trimmed()
		
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


		# now create an action for the user, and send it to krunner
		m = Plasma.QueryMatch(self.runner)
		m.setText("%s: '%s'" % (self._keywords[matchedKeyword][0], q) )
		m.setType(Plasma.QueryMatch.ExactMatch)
		m.setIcon(KIcon("dialog-information"))
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
	return MsgBoxRunner(parent)
