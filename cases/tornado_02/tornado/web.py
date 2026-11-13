class RedirectHandler(RequestHandler):
    """Redirects the client to the given URL for all GET requests.

    You should provide the keyword argument ``url`` to the handler, e.g.::

        application = web.Application([
            (r"/oldpath", web.RedirectHandler, {"url": "/newpath"}),
        ])

    `RedirectHandler` supports regular expression substitutions. E.g., to
    swap the first and second parts of a path while preserving the remainder::

        application = web.Application([
            (r"/(.*?)/(.*?)/(.*)", web.RedirectHandler, {"url": "/{1}/{0}/{2}"}),
        ])

    The final URL is formatted with `str.format` and the substrings that match
    the capturing groups. In the above example, a request to "/a/b/c" would be
    formatted like::

        str.format("/{1}/{0}/{2}", "a", "b", "c")  # -> "/b/a/c"

    Use Python's :ref:`format string syntax <formatstrings>` to customize how
    values are substituted.

    .. versionchanged:: 4.5
       Added support for substitutions into the destination URL.

    .. versionchanged:: 5.0
       If any query arguments are present, they will be copied to the
       destination URL.
    """

    def initialize(self, url: str, permanent: bool = True) -> None:
        self._url = url
        self._permanent = permanent

    def get(self, *args: Any, **kwargs: Any) -> None:
        to_url = self._url.format(*args, **kwargs)
        if self.request.query_arguments:
            # TODO: figure out typing for the next line.
            to_url = httputil.url_concat(
                to_url,
                list(httputil.qs_to_qsl(self.request.query_arguments)),  # type: ignore
            )
        if to_url.startswith("//") and not self._url.startswith("//"):
            raise ValueError(
                "Redirect URL cannot start with '//' if template does not."
            )
        self.redirect(to_url, permanent=self._permanent)


class StaticFileHandler(RequestHandler):
    """A simple handler that can serve static content from a directory.

    A `StaticFileHandler` is configured automatically if you pass the
    ``static_path`` keyword argument to `Application`.  This handler
    can be customized with the ``static_url_prefix``, ``static_handler_class``,
    and ``static_handler_args`` settings.

    To map an additional path to this handler for a static data directory
    you would add a line to your application like::

        application = web.Application([
            (r"/content/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ])

    The handler constructor requires a ``path`` argument, which specifies the
    local root directory of the content to be served.

    Note that a capture group in the regex is required to parse the value for
    the ``path`` argument to the get() method (different than the constructor
    argument above); see `URLSpec` for details.

    To serve a file like ``index.html`` automatically when a directory is
    requested, set ``static_handler_args=dict(default_filename="index.html")``
    in your application settings, or add ``default_filename`` as an initializer
    argument for your ``StaticFileHandler``.

    Symlinks are not followed out of the directory being served: if a path
    resolves to a location outside it, the request is rejected with a 403
    error. Deployments that deliberately serve content through symlinks
    pointing elsewhere can set the ``allowed_symlink_directory`` initializer
    argument to a directory containing all of the intended targets, or to a
    list of such directories. It defaults to the ``path`` argument.

    To maximize the effectiveness of browser caching, this class supports
    versioned urls (by default using the argument ``?v=``).  If a version
    is given, we instruct the browser to cache this file indefinitely.
