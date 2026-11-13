
class Lexer(object):

    __metaclass__ = LexerMeta

    encoding = 'utf-8'
    stripall = False
    stripnl = False
    tabsize = 0
    flags = re.IGNORECASE | re.UNICODE

    tokens = {
        'root': [
            (r'--.*?(\r\n|\r|\n)', tokens.Comment.Single),
            # $ matches *before* newline, therefore we have two patterns
            # to match Comment.Single
            (r'--.*?$', tokens.Comment.Single),
            (r'(\r\n|\r|\n)', tokens.Newline),
            (r'\s+', tokens.Whitespace),
            (r'/\*', tokens.Comment.Multiline, 'multiline-comments'),
            (r':=', tokens.Assignment),
            (r'::', tokens.Punctuation),
            (r'[*]', tokens.Wildcard),
            (r'CASE\b', tokens.Keyword),  # extended CASE(foo)
            (r"`(``|[^`])*`", tokens.Name),
            (r"´(´´|[^´])*´", tokens.Name),
            (r'\$([^\W\d]\w*)?\$', tokens.Name.Builtin),
            (r'\?{1}', tokens.Name.Placeholder),
            (r'%\(\w+\)s', tokens.Name.Placeholder),
            (r'%s', tokens.Name.Placeholder),
            (r'[$:?]\w+', tokens.Name.Placeholder),
            # FIXME(andi): VALUES shouldn't be listed here
            # see https://github.com/andialbrecht/sqlparse/pull/64
            (r'VALUES', tokens.Keyword),
            (r'@[^\W\d_]\w+', tokens.Name),
            (r'[^\W\d_]\w*(?=[.(])', tokens.Name),  # see issue39
            (r'[-]?0x[0-9a-fA-F]+', tokens.Number.Hexadecimal),
            (r'[-]?[0-9]*(\.[0-9]+)?[eE][-]?[0-9]+', tokens.Number.Float),
            (r'[-]?[0-9]*\.[0-9]+', tokens.Number.Float),
            (r'[-]?[0-9]+', tokens.Number.Integer),
            (r"'(''|\\\\|\\'|[^'])*'", tokens.String.Single),
            # not a real string literal in ANSI SQL:
            (r'(""|".*?[^\\]")', tokens.String.Symbol),
            (r'(?<=[\w\]])(\[[^\]]*?\])', tokens.Punctuation.ArrayIndex),
            (r'(\[[^\]]+\])', tokens.Name),
            (r'((LEFT\s+|RIGHT\s+|FULL\s+)?(INNER\s+|OUTER\s+|STRAIGHT\s+)?|(CROSS\s+|NATURAL\s+)?)?JOIN\b', tokens.Keyword),
            (r'END(\s+IF|\s+LOOP)?\b', tokens.Keyword),
            (r'NOT NULL\b', tokens.Keyword),
            (r'CREATE(\s+OR\s+REPLACE)?\b', tokens.Keyword.DDL),
            (r'DOUBLE\s+PRECISION\b', tokens.Name.Builtin),
            (r'(?<=\.)[^\W\d_]\w*', tokens.Name),
            (r'[^\W\d_]\w*', is_keyword),
            (r'[;:()\[\],\.]', tokens.Punctuation),
            (r'[<>=~!]+', tokens.Operator.Comparison),
            (r'[+/@#%^&|`?^-]+', tokens.Operator),
        ],
        'multiline-comments': [
            (r'/\*', tokens.Comment.Multiline, 'multiline-comments'),
            (r'\*/', tokens.Comment.Multiline, '#pop'),
            (r'[^/\*]+', tokens.Comment.Multiline),
            (r'[/*]', tokens.Comment.Multiline),
        ]}

    def __init__(self):
        self.filters = []

    def add_filter(self, filter_, **options):
        from sqlparse.filters import Filter
        if not isinstance(filter_, Filter):
            filter_ = filter_(**options)
        self.filters.append(filter_)

    def _decode(self, text):
        if sys.version_info[0] == 3:
            if isinstance(text, str):
                return text
        if self.encoding == 'guess':
            try:
                text = text.decode('utf-8')
                if text.startswith(u'\ufeff'):
                    text = text[len(u'\ufeff'):]
            except UnicodeDecodeError:
                text = text.decode('latin1')
        else:
            try:
                text = text.decode(self.encoding)
            except UnicodeDecodeError:
                text = text.decode('unicode-escape')

        if self.tabsize > 0:
            text = text.expandtabs(self.tabsize)
        return text

    def get_tokens(self, text, unfiltered=False):
        """
        Return an iterable of (tokentype, value) pairs generated from
        `text`. If `unfiltered` is set to `True`, the filtering mechanism
        is bypassed even if filters are defined.

        Also preprocess the text, i.e. expand tabs and strip it if
        wanted and applies registered filters.
        """
        if isinstance(text, basestring):
            if self.stripall:
                text = text.strip()
            elif self.stripnl:
                text = text.strip('\n')

            if sys.version_info[0] < 3 and isinstance(text, unicode):
                text = StringIO(text.encode('utf-8'))
                self.encoding = 'utf-8'
            else:
                text = StringIO(text)

        def streamer():
            for i, t, v in self.get_tokens_unprocessed(text):
                yield t, v
        stream = streamer()
        if not unfiltered:
            stream = apply_filters(stream, self.filters, self)
        return stream

    def get_tokens_unprocessed(self, stream, stack=('root',)):
        """
        Split ``text`` into (tokentype, text) pairs.

        ``stack`` is the inital stack (default: ``['root']``)
        """
        pos = 0
        tokendefs = self._tokens  # see __call__, pylint:disable=E1101
        statestack = list(stack)
        statetokens = tokendefs[statestack[-1]]
        known_names = {}

        text = stream.read()
        text = self._decode(text)

        while 1:
            for rexmatch, action, new_state in statetokens:
                m = rexmatch(text, pos)
                if m:
                    # print rex.pattern
                    value = m.group()
                    if value in known_names:
                        yield pos, known_names[value], value
                    elif type(action) is tokens._TokenType:
                        yield pos, action, value
                    elif hasattr(action, '__call__'):
                        ttype, value = action(value)
                        known_names[value] = ttype
                        yield pos, ttype, value
                    else:
                        for item in action(self, m):
                            yield item
                    pos = m.end()
                    if new_state is not None:
                        # state transition
                        if isinstance(new_state, tuple):
                            for state in new_state:
                                if state == '#pop':
                                    statestack.pop()
