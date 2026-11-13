        headers: dict[str, str] | httputil.HTTPHeaders | None = None,
        body: bytes | str | None = None,
        auth_username: str | None = None,
        auth_password: str | None = None,
        auth_mode: str | None = None,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        if_modified_since: float | datetime.datetime | None = None,
        follow_redirects: bool | None = None,
        max_redirects: int | None = None,
        user_agent: str | None = None,
        use_gzip: bool | None = None,
        network_interface: str | None = None,
        streaming_callback: None | (Callable[[bytes], Awaitable[None] | None]) = None,
        header_callback: Callable[[str], None] | None = None,
        prepare_curl_callback: Callable[[Any], None] | None = None,
        proxy_host: str | None = None,
        proxy_port: int | None = None,
        proxy_username: str | None = None,
        proxy_password: str | None = None,
        proxy_auth_mode: str | None = None,
        allow_nonstandard_methods: bool | None = None,
        validate_cert: bool | None = None,
        ca_certs: str | None = None,
        allow_ipv6: bool | None = None,
        client_key: str | None = None,
        client_cert: str | None = None,
        body_producer: None | (
            Callable[[Callable[[bytes], None]], "Future[None]"]
        ) = None,
        expect_100_continue: bool = False,
        decompress_response: bool | None = None,
        ssl_options: dict[str, Any] | ssl.SSLContext | None = None,
    ) -> None:
        r"""All parameters except ``url`` are optional.

        :arg str url: URL to fetch
        :arg str method: HTTP method, e.g. "GET" or "POST"
        :arg headers: Additional HTTP headers to pass on the request
        :type headers: `~tornado.httputil.HTTPHeaders` or `dict`
        :arg body: HTTP request body as a string (byte or unicode; if unicode
           the utf-8 encoding will be used)
        :type body: `str` or `bytes`
        :arg collections.abc.Callable body_producer: Callable used for
           lazy/asynchronous request bodies.
           It is called with one argument, a ``write`` function, and should
           return a `.Future`.  It should call the write function with new
           data as it becomes available.  The write function returns a
           `.Future` which can be used for flow control.
           Only one of ``body`` and ``body_producer`` may
           be specified.  ``body_producer`` is not supported on
           ``curl_httpclient``.  When using ``body_producer`` it is recommended
           to pass a ``Content-Length`` in the headers as otherwise chunked
           encoding will be used, and many servers do not support chunked
           encoding on requests.  New in Tornado 4.0
        :arg str auth_username: Username for HTTP authentication
        :arg str auth_password: Password for HTTP authentication
        :arg str auth_mode: Authentication mode; default is "basic".
           Allowed values are implementation-defined; ``curl_httpclient``
           supports "basic" and "digest"; ``simple_httpclient`` only supports
           "basic"
        :arg float connect_timeout: Timeout for initial connection in seconds,
           default 20 seconds (0 means no timeout)
        :arg float request_timeout: Timeout for entire request in seconds,
           default 20 seconds (0 means no timeout)
        :arg if_modified_since: Timestamp for ``If-Modified-Since`` header
        :type if_modified_since: `datetime` or `float`
        :arg bool follow_redirects: Should redirects be followed automatically
           or return the 3xx response? Default True.
        :arg int max_redirects: Limit for ``follow_redirects``, default 5.
        :arg str user_agent: String to send as ``User-Agent`` header
        :arg bool decompress_response: Request a compressed response from
           the server and decompress it after downloading.  Default is True.
           New in Tornado 4.0.
        :arg bool use_gzip: Deprecated alias for ``decompress_response``
           since Tornado 4.0.
        :arg str network_interface: Network interface or source IP to use for request.
           See ``curl_httpclient`` note below.
        :arg collections.abc.Callable streaming_callback: If set, ``streaming_callback`` will
           be run with each chunk of data as it is received, and
           ``HTTPResponse.body`` and ``HTTPResponse.buffer`` will be empty in
           the final response.
        :arg collections.abc.Callable header_callback: If set, ``header_callback`` will
           be run with each header line as it is received (including the
           first line, e.g. ``HTTP/1.0 200 OK\r\n``, and a final line
           containing only ``\r\n``.  All lines include the trailing newline
           characters).  ``HTTPResponse.headers`` will be empty in the final
           response.  This is most useful in conjunction with
           ``streaming_callback``, because it's the only way to get access to
           header data while the request is in progress.
        :arg collections.abc.Callable prepare_curl_callback: If set, will be called with
           a ``pycurl.Curl`` object to allow the application to make additional
           ``setopt`` calls.
        :arg str proxy_host: HTTP proxy hostname.  To use proxies,
           ``proxy_host`` and ``proxy_port`` must be set; ``proxy_username``,
           ``proxy_pass`` and ``proxy_auth_mode`` are optional.  Proxies are
           currently only supported with ``curl_httpclient``.
        :arg int proxy_port: HTTP proxy port
        :arg str proxy_username: HTTP proxy username
        :arg str proxy_password: HTTP proxy password
        :arg str proxy_auth_mode: HTTP proxy Authentication mode;
           default is "basic". supports "basic" and "digest"
        :arg bool allow_nonstandard_methods: Allow unknown values for ``method``
           argument? Default is False.
        :arg bool validate_cert: For HTTPS requests, validate the server's
           certificate? Default is True.
        :arg str ca_certs: filename of CA certificates in PEM format,
           or None to use defaults.  See note below when used with
           ``curl_httpclient``.
        :arg str client_key: Filename for client SSL key, if any.  See
           note below when used with ``curl_httpclient``.
        :arg str client_cert: Filename for client SSL certificate, if any.
           See note below when used with ``curl_httpclient``.
        :arg ssl.SSLContext ssl_options: `ssl.SSLContext` object for use in
           ``simple_httpclient`` (unsupported by ``curl_httpclient``).
           Overrides ``validate_cert``, ``ca_certs``, ``client_key``,
           and ``client_cert``.
        :arg bool allow_ipv6: Use IPv6 when available?  Default is True.
        :arg bool expect_100_continue: If true, send the
           ``Expect: 100-continue`` header and wait for a continue response
           before sending the request body.  Only supported with
           ``simple_httpclient``.

        .. note::

            When using ``curl_httpclient`` certain options may be
            inherited by subsequent fetches because ``pycurl`` does
            not allow them to be cleanly reset.  This applies to the
            ``ca_certs``, ``client_key``, ``client_cert``, and
            ``network_interface`` arguments.  If you use these
            options, you should pass them on every request (you don't
            have to always use the same values, but it's not possible
            to mix requests that specify these options with ones that
            use the defaults).

        .. versionadded:: 3.1
           The ``auth_mode`` argument.

        .. versionadded:: 4.0
           The ``body_producer`` and ``expect_100_continue`` arguments.

        .. versionadded:: 4.2
           The ``ssl_options`` argument.

        .. versionadded:: 4.5
           The ``proxy_auth_mode`` argument.

        .. versionchanged:: 6.6
           With ``simple_httpclient``, ``streaming_callback`` may be a
           coroutine; the next chunk is not read until it completes. This
           is not supported by ``curl_httpclient``.
        """
        # Note that some of these attributes go through property setters
        # defined below.
        self.headers = headers  # type: ignore
        if if_modified_since:
            self.headers["If-Modified-Since"] = httputil.format_timestamp(
                if_modified_since
            )
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        self.proxy_auth_mode = proxy_auth_mode
        self.url = url
        self.method = method
        self.body = body  # type: ignore
        self.body_producer = body_producer
        self.auth_username = auth_username
        self.auth_password = auth_password
        self.auth_mode = auth_mode
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.follow_redirects = follow_redirects
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        if decompress_response is not None:
            self.decompress_response: bool | None = decompress_response
        else:
            self.decompress_response = use_gzip
        self.network_interface = network_interface
        self.streaming_callback = streaming_callback
        self.header_callback = header_callback
        self.prepare_curl_callback = prepare_curl_callback
        self.allow_nonstandard_methods = allow_nonstandard_methods
        self.validate_cert = validate_cert
        self.ca_certs = ca_certs
        self.allow_ipv6 = allow_ipv6
        self.client_key = client_key
        self.client_cert = client_cert
        self.ssl_options = ssl_options
        self.expect_100_continue = expect_100_continue
        self.start_time = time.time()

    @property
    def headers(self) -> httputil.HTTPHeaders:
        # TODO: headers may actually be a plain dict until fairly late in
        # the process (AsyncHTTPClient.fetch), but practically speaking,
        # whenever the property is used they're already HTTPHeaders.
        return self._headers  # type: ignore

    @headers.setter
    def headers(self, value: dict[str, str] | httputil.HTTPHeaders) -> None:
        if value is None:
            self._headers = httputil.HTTPHeaders()
        else:
            self._headers = value

    @property
    def body(self) -> bytes:
        return self._body

    @body.setter
    def body(self, value: bytes | str) -> None:
        self._body = utf8(value)


