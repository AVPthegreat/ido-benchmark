            return

        new_frames = []
        hidden = False
        for frame in self.frames:
            hide = frame.hide
            if hide in ('before', 'before_and_this'):
                new_frames = []
                hidden = False
                if hide == 'before_and_this':
                    continue
            elif hide in ('reset', 'reset_and_this'):
                hidden = False
                if hide == 'reset_and_this':
                    continue
            elif hide in ('after', 'after_and_this'):
                hidden = True
                if hide == 'after_and_this':
                    continue
            elif hide or hidden:
                continue
            new_frames.append(frame)

        # if we only have one frame and that frame is from the codeop
        # module, remove it.
        if len(new_frames) == 1 and self.frames[0].module == 'codeop':
            del self.frames[:]

        # if the last frame is missing something went terrible wrong :(
        elif self.frames[-1] in new_frames:
            self.frames[:] = new_frames

    def is_syntax_error(self):
        """Is it a syntax error?"""
        return isinstance(self.exc_value, SyntaxError)
    is_syntax_error = property(is_syntax_error)

    def exception(self):
        """String representation of the exception."""
        buf = traceback.format_exception_only(self.exc_type, self.exc_value)
        rv = ''.join(buf).strip()
        return rv.decode('utf-8', 'replace') if PY2 else rv
    exception = property(exception)

    def log(self, logfile=None):
        """Log the ASCII traceback into a file object."""
        if logfile is None:
            logfile = sys.stderr
        tb = self.plaintext.rstrip() + u'\n'
        if PY2:
            tb = tb.encode('utf-8', 'replace')
        logfile.write(tb)

    def paste(self):
        """Create a paste and return the paste id."""
        data = json.dumps({
            'description': 'Werkzeug Internal Server Error',
            'public': False,
            'files': {
                'traceback.txt': {
                    'content': self.plaintext
                }
            }
        }).encode('utf-8')
        try:
            from urllib2 import urlopen
        except ImportError:
            from urllib.request import urlopen
        rv = urlopen('https://api.github.com/gists', data=data)
        resp = json.loads(rv.read().decode('utf-8'))
        rv.close()
        return {
            'url': resp['html_url'],
            'id': resp['id']
        }

    def render_summary(self, include_title=True):
        """Render the traceback for the interactive console."""
        title = ''
        frames = []
        classes = ['traceback']
        if not self.frames:
            classes.append('noframe-traceback')

        if include_title:
            if self.is_syntax_error:
                title = u'Syntax Error'
            else:
                title = u'Traceback <em>(most recent call last)</em>:'

        for frame in self.frames:
            frames.append(u'<li%s>%s' % (
                frame.info and u' title="%s"' % escape(frame.info) or u'',
                frame.render()
            ))

        if self.is_syntax_error:
            description_wrapper = u'<pre class=syntaxerror>%s</pre>'
        else:
            description_wrapper = u'<blockquote>%s</blockquote>'

        return SUMMARY_HTML % {
            'classes':      u' '.join(classes),
            'title':        title and u'<h3>%s</h3>' % title or u'',
            'frames':       u'\n'.join(frames),
            'description':  description_wrapper % escape(self.exception)
        }

    def render_full(self, evalex=False, secret=None,
                    evalex_trusted=True):
        """Render the Full HTML page with the traceback info."""
        exc = escape(self.exception)
        return PAGE_HTML % {
            'evalex':           evalex and 'true' or 'false',
            'evalex_trusted':   evalex_trusted and 'true' or 'false',
            'console':          'false',
            'title':            exc,
            'exception':        exc,
            'exception_type':   escape(self.exception_type),
            'summary':          self.render_summary(include_title=False),
            'plaintext':        escape(self.plaintext),
            'plaintext_cs':     re.sub('-{2,}', '-', self.plaintext),
            'traceback_id':     self.id,
            'secret':           secret
        }

    def generate_plaintext_traceback(self):
        """Like the plaintext attribute but returns a generator"""
        yield u'Traceback (most recent call last):'
        for frame in self.frames:
            yield u'  File "%s", line %s, in %s' % (
                frame.filename,
                frame.lineno,
                frame.function_name
            )
            yield u'    ' + frame.current_line.strip()
        yield self.exception

    def plaintext(self):
        return u'\n'.join(self.generate_plaintext_traceback())
    plaintext = cached_property(plaintext)

    id = property(lambda x: id(x))


class Frame(object):

    """A single frame in a traceback."""

    def __init__(self, exc_type, exc_value, tb):
        self.lineno = tb.tb_lineno
        self.function_name = tb.tb_frame.f_code.co_name
        self.locals = tb.tb_frame.f_locals
        self.globals = tb.tb_frame.f_globals

        fn = inspect.getsourcefile(tb) or inspect.getfile(tb)
        if fn[-4:] in ('.pyo', '.pyc'):
            fn = fn[:-1]
        # if it's a file on the file system resolve the real filename.
        if os.path.isfile(fn):
            fn = os.path.realpath(fn)
