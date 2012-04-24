import os, sqlite3
from shutil import copy2
from tempfile import mkstemp
from PyKDE4 import plasmascript
from PyKDE4.plasma import Plasma
from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import KToolInvocation
 
class MsgBoxRunner(plasmascript.Runner):
 
	def init(self):
		# called upon creation to let us run any intialization
		# tell the user how to use this runner
		self._keywords = {}
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
 
		# strip the keyword and leading space
		q = q[len(matchedKeyword):]
		q = q.trimmed()
		if q:
			self._localtion = self._keywords[matchedKeyword][1].replace('{searchTerms}', q)
 
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
		if self._localtion:
			KToolInvocation.invokeBrowser(self._localtion)
 
 
def CreateRunner(parent):
	# called by krunner, must simply return an instance of the runner object
	return MsgBoxRunner(parent)
