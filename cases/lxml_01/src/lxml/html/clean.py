            for el in doc.iter():
                if el.tag not in allow_tags:
                    bad.append(el)
            if bad:
                if bad[0] is doc:
                    el = bad.pop(0)
                    el.tag = 'div'
                    el.attrib.clear()
                for el in bad:
                    el.drop_tag()
        if self.add_nofollow:
            for el in _find_external_links(doc):
                if not self.allow_follow(el):
                    rel = el.get('rel')
                    if rel:
                        if ('nofollow' in rel
                                and ' nofollow ' in (' %s ' % rel)):
                            continue
                        rel = '%s nofollow' % rel
                    else:
                        rel = 'nofollow'
                    el.set('rel', rel)

    def allow_follow(self, anchor):
        """
        Override to suppress rel="nofollow" on some anchors.
        """
        return False

    def allow_element(self, el):
        """
        Decide whether an element is configured to be accepted or rejected.

        :param el: an element.
        :return: true to accept the element or false to reject/discard it.
        """
        if el.tag not in self._tag_link_attrs:
            return False
        attr = self._tag_link_attrs[el.tag]
        if isinstance(attr, (list, tuple)):
            for one_attr in attr:
                url = el.get(one_attr)
                if not url:
                    return False
                if not self.allow_embedded_url(el, url):
                    return False
            return True
        else:
            url = el.get(attr)
            if not url:
                return False
            return self.allow_embedded_url(el, url)

    def allow_embedded_url(self, el, url):
        """
        Decide whether a URL that was found in an element's attributes or text
        if configured to be accepted or rejected.

        :param el: an element.
        :param url: a URL found on the element.
        :return: true to accept the URL and false to reject it.
        """
        if self.whitelist_tags is not None and el.tag not in self.whitelist_tags:
            return False
        scheme, netloc, path, query, fragment = urlsplit(url)
        netloc = netloc.lower().split(':', 1)[0]
        if scheme not in ('http', 'https'):
            return False
        if netloc in self.host_whitelist:
            return True
        return False

    def kill_conditional_comments(self, doc):
        """
        IE conditional comments basically embed HTML that the parser
        doesn't normally see.  We can't allow anything like that, so
        we'll kill any comments that could be conditional.
        """
        has_conditional_comment = _conditional_comment_re.search
        self._kill_elements(
            doc, lambda el: has_conditional_comment(el.text),
            etree.Comment)                

    def _kill_elements(self, doc, condition, iterate=None):
        bad = []
        for el in doc.iter(iterate):
            if condition(el):
                bad.append(el)
        for el in bad:
            el.drop_tree()

    def _remove_javascript_link(self, link):
        # links like "j a v a s c r i p t:" might be interpreted in IE
        new = _substitute_whitespace('', unquote_plus(link))
        if _is_javascript_scheme(new):
            # FIXME: should this be None to delete?
            return ''
        return link

    _substitute_comments = re.compile(r'/\*.*?\*/', re.S).sub

    def _has_sneaky_javascript(self, style):
        """
        Depending on the browser, stuff like ``e x p r e s s i o n(...)``
        can get interpreted, or ``expre/* stuff */ssion(...)``.  This
        checks for attempt to do stuff like this.

        Typically the response will be to kill the entire style; if you
        have just a bit of Javascript in the style another rule will catch
        that and remove only the Javascript from the style; this catches
        more sneaky attempts.
        """
        style = self._substitute_comments('', style)
        style = style.replace('\\', '')
        style = _substitute_whitespace('', style)
        style = style.lower()
        if 'javascript:' in style:
            return True
        if 'expression(' in style:
            return True
        if '</noscript' in style:
            # e.g. '<noscript><style><a title="</noscript><img src=x onerror=alert(1)>">'
            return True
        if _looks_like_tag_content(style):
            # e.g. '<math><style><img src=x onerror=alert(1)></style></math>'
            return True
        return False

    def clean_html(self, html):
        result_type = type(html)
        if isinstance(html, basestring):
            doc = fromstring(html)
        else:
            doc = copy.deepcopy(html)
        self(doc)
        return _transform_result(result_type, doc)

clean = Cleaner()
clean_html = clean.clean_html

############################################################
## Autolinking
############################################################

_link_regexes = [
    re.compile(r'(?P<body>https?://(?P<host>[a-z0-9._-]+)(?:/[/\-_.,a-z0-9%&?;=~]*)?(?:\([/\-_.,a-z0-9%&?;=~]*\))?)', re.I),
    # This is conservative, but autolinking can be a bit conservative:
    re.compile(r'mailto:(?P<body>[a-z0-9._-]+@(?P<host>[a-z0-9_.-]+[a-z]))', re.I),
    ]

_avoid_elements = ['textarea', 'pre', 'code', 'head', 'select', 'a']

_avoid_hosts = [
    re.compile(r'^localhost', re.I),
    re.compile(r'\bexample\.(?:com|org|net)$', re.I),
    re.compile(r'^127\.0\.0\.1$'),
    ]

_avoid_classes = ['nolink']

