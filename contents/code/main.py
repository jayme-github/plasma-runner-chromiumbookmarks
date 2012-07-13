import os, sqlite3
from shutil import copy2
from tempfile import mkstemp
from urlparse import urljoin
from urllib import urlencode
from PyKDE4 import plasmascript
from PyKDE4.plasma import Plasma
from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import KToolInvocation
 
class MsgBoxRunner(plasmascript.Runner):
 
	def init(self):
		# called upon creation to let us run any intialization
		# tell the user how to use this runner
		self._keywords = {}
		self._googleBaseURL = 'https://www.google.com/'
		self.addSyntax(Plasma.RunnerSyntax("<Chromium keyword> :q:", "Search for :q: using Chromium keyword"))
		# Copy Chromium Web Data as it is locked if Chromium running...
		if os.path.isfile( os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Web Data' ) ):
			fd, dbfile = mkstemp('chromiumkeywords')
			copy2( os.path.join( os.environ.get('HOME'), '.config/chromium/Default/Web Data' ), dbfile )
			conn = sqlite3.connect( dbfile )
			cur = conn.cursor()
			cur.execute('SELECT `short_name`, `keyword`, `url` FROM keywords;')
			for row in cur.fetchall():
				if not row[1] in self._keywords:
					self._keywords[ row[1] ] = (row[0], row[2])
			cur.close()
			os.unlink( dbfile )
		# Read last_known_google_url
		if os.path.isfile( os.path.join( os.environ.get('HOME'), '.config/chromium/Local State' ) ):
			localStateFile = open( os.path.join( os.environ.get('HOME'), '.config/chromium/Local State' ), 'r' )
			import json
			localStateJson = json.load( localStateFile )
			localStateFile.close()
			if 'browser' in localStateJson and 'last_known_google_url' in localStateJson['browser']	and localStateJson['browser']['last_known_google_url']:
				self._googleBaseURL = localStateJson['browser']['last_known_google_url']
			
 
	def match(self, context):
		# called by krunner to let us add actions for the user
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
		# called by KRunner when the user selects our action,		
		# so lets keep our promise
		if self._location:
			KToolInvocation.invokeBrowser(self._location)
 
 
def CreateRunner(parent):
	# called by krunner, must simply return an instance of the runner object
	return MsgBoxRunner(parent)
