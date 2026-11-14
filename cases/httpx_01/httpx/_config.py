    def __init__(
        self,
        *,
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
        keepalive_expiry: float | None = 5.0,
    ) -> None:
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.max_connections == other.max_connections
            and self.max_keepalive_connections == other.max_keepalive_connections
            and self.keepalive_expiry == other.keepalive_expiry
        )

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return (
            f"{class_name}(max_connections={self.max_connections}, "
            f"max_keepalive_connections={self.max_keepalive_connections}, "
            f"keepalive_expiry={self.keepalive_expiry})"
        )


class Proxy:
    def __init__(
        self,
        url: URL | str,
        *,
        ssl_context: ssl.SSLContext | None = None,
        auth: tuple[str, str] | None = None,
        headers: HeaderTypes | None = None,
    ) -> None:
        url = URL(url)
        headers = Headers(headers)

        if url.scheme not in ("http", "https", "socks5", "socks5h"):
            raise ValueError(f"Unknown scheme for proxy URL {url!r}")

        if url.username or url.password:
            # Remove any auth credentials from the URL.
            auth = (url.username, url.password)
            url = url.copy_with(username=None, password=None)

        self.url = url
        self.auth = auth
        self.headers = headers
        self.ssl_context = ssl_context

    @property
    def raw_auth(self) -> tuple[bytes, bytes] | None:
        # The proxy authentication as raw bytes.
        return (
            None
            if self.auth is None
            else (self.auth[0].encode("utf-8"), self.auth[1].encode("utf-8"))
        )

    def __repr__(self) -> str:
        # The authentication is represented with the password component masked.
        auth = (self.auth[0], "********") if self.auth else None

        # Build a nice concise representation.
        url_str = f"{str(self.url)!r}"
        auth_str = f", auth={auth!r}" if auth else ""
        headers_str = f", headers={dict(self.headers)!r}" if self.headers else ""
        return f"Proxy({url_str}{auth_str}{headers_str})"


DEFAULT_TIMEOUT_CONFIG = Timeout(timeout=5.0)
DEFAULT_LIMITS = Limits(max_connections=100, max_keepalive_connections=20)
DEFAULT_MAX_REDIRECTS = 20
