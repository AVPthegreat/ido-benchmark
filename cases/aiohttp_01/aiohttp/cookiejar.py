        heapq.heappush(self._expire_heap, (when, cookie_key))
        self._expirations[cookie_key] = when

    def update_cookies(self, cookies: LooseCookies, response_url: URL = URL()) -> None:
        """Update cookies."""
        hostname = response_url.raw_host

        if not self._unsafe and is_ip_address(hostname):
            # Don't accept cookies from IPs
            return

        if isinstance(cookies, Mapping):
            cookies = cookies.items()

        for name, cookie in cookies:
            if not isinstance(cookie, Morsel):
                tmp = SimpleCookie()
                tmp[name] = cookie  # type: ignore[assignment]
                cookie = tmp[name]

            domain = cookie["domain"]

            # ignore domains with trailing dots
            if domain and domain[-1] == ".":
                domain = ""
                del cookie["domain"]

            if domain and domain[0] == ".":
                # Remove leading dot
                domain = domain[1:]
                cookie["domain"] = domain

            if domain and hostname and not self._is_domain_match(domain, hostname):
                # Setting cookies for different domains is not allowed
                continue

            path = cookie["path"]
            if not path or path[0] != "/":
                # Set the cookie's path to the response path
                path = response_url.path
                if not path.startswith("/"):
                    path = "/"
                else:
                    # Cut everything from the last slash to the end
                    path = "/" + path[1 : path.rfind("/")]
                cookie["path"] = path
            path = path.rstrip("/")

            if not domain and hostname is not None:
                self._host_only_cookies.add((hostname, path, name))
                domain = cookie["domain"] = hostname
            else:
                # A cookie with an explicit Domain attribute replaces any
                # host-only cookie with the same (domain, path, name) identity.
                self._host_only_cookies.discard((domain, path, name))

            if max_age := cookie["max-age"]:
                try:
                    delta_seconds = int(max_age)
                    # https://datatracker.ietf.org/doc/html/rfc6265#section-5.2.2
                    if delta_seconds <= 0:
                        max_age_expiration = 0.0
                    else:
                        # Cap first to protect against OverflowError on next line.
                        delta_seconds = min(delta_seconds, self.MAX_TIME)
                        max_age_expiration = min(
                            time.time() + delta_seconds, self.MAX_TIME
                        )
                    self._expire_cookie(max_age_expiration, domain, path, name)
                except ValueError:
                    cookie["max-age"] = ""

            elif expires := cookie["expires"]:
                if expire_time := self._parse_date(expires):
                    self._expire_cookie(expire_time, domain, path, name)
                else:
                    cookie["expires"] = ""

            key = (domain, path)
            if self._cookies[key].get(name) != cookie:
                # Don't blow away the cache if the same
                # cookie gets set again
                self._cookies[key][name] = cookie
                self._morsel_cache[key].pop(name, None)

        self._do_expiration()

    def filter_cookies(self, request_url: URL = URL()) -> "BaseCookie[str]":
        """Returns this jar's cookies filtered by their attributes."""
        # We always use BaseCookie now since all
        # cookies set on on filtered are fully constructed
        # Morsels, not just names and values.
        filtered: BaseCookie[str] = BaseCookie()
        if not self._cookies:
            # Skip do_expiration() if there are no cookies.
            return filtered
        self._do_expiration()
        if not self._cookies:
            # Skip rest of function if no non-expired cookies.
            return filtered
        if type(request_url) is not URL:
            warnings.warn(
                "filter_cookies expects yarl.URL instances only,"
                f"and will stop working in 4.x, got {type(request_url)}",
                DeprecationWarning,
                stacklevel=2,
            )
            request_url = URL(request_url)
        hostname = request_url.raw_host or ""

        is_not_secure = request_url.scheme not in ("https", "wss")
        if is_not_secure and self._treat_as_secure_origin:
            request_origin = URL()
            with contextlib.suppress(ValueError):
                request_origin = request_url.origin()
            is_not_secure = request_origin not in self._treat_as_secure_origin

        # Send shared cookie
        key = ("", "")
        for c in self._cookies[key].values():
            # Check cache first
            if c.key in self._morsel_cache[key]:
                filtered[c.key] = self._morsel_cache[key][c.key]
                continue

            # Build and cache the morsel
            mrsl_val = self._build_morsel(c)
            self._morsel_cache[key][c.key] = mrsl_val
            filtered[c.key] = mrsl_val

        if is_ip_address(hostname):
            if not self._unsafe:
                return filtered
            domains: Iterable[str] = (hostname,)
        else:
            # Get all the subdomains that might match a cookie (e.g. "foo.bar.com", "bar.com", "com")
            domains = itertools.accumulate(
                reversed(hostname.split(".")), _FORMAT_DOMAIN_REVERSED
            )

        # Get all the path prefixes that might match a cookie (e.g. "", "/foo", "/foo/bar")
        paths = itertools.accumulate(request_url.path.split("/"), _FORMAT_PATH)
        # Create every combination of (domain, path) pairs.
        pairs = itertools.product(domains, paths)

        path_len = len(request_url.path)
        # Point 2: https://www.rfc-editor.org/rfc/rfc6265.html#section-5.4
        for p in pairs:
            if p not in self._cookies:
                continue
            for name, cookie in self._cookies[p].items():
                domain = cookie["domain"]

                if domain != hostname and p + (name,) in self._host_only_cookies:
                    continue

                # Skip edge case when the cookie has a trailing slash but request doesn't.
                if len(cookie["path"]) > path_len:
                    continue

                if is_not_secure and cookie["secure"]:
                    continue

                # We already built the Morsel so reuse it here
                if name in self._morsel_cache[p]:
                    filtered[name] = self._morsel_cache[p][name]
                    continue

                # Build and cache the morsel
                mrsl_val = self._build_morsel(cookie)
                self._morsel_cache[p][name] = mrsl_val
                filtered[name] = mrsl_val

        return filtered

    def _build_morsel(self, cookie: Morsel[str]) -> Morsel[str]:
        """Build a morsel for sending, respecting quote_cookie setting."""
        if self._quote_cookie and cookie.coded_value and cookie.coded_value[0] == '"':
            return preserve_morsel_with_coded_value(cookie)
        morsel: Morsel[str] = Morsel()
        if self._quote_cookie:
            value, coded_value = _SIMPLE_COOKIE.value_encode(cookie.value)
        else:
            coded_value = value = cookie.value
        # We use __setstate__ instead of the public set() API because it allows us to
        # bypass validation and set already validated state. This is more stable than
        # setting protected attributes directly and unlikely to change since it would
        # break pickling.
        morsel.__setstate__({"key": cookie.key, "value": value, "coded_value": coded_value})  # type: ignore[attr-defined]
        return morsel

    @staticmethod
    def _is_domain_match(domain: str, hostname: str) -> bool:
        """Implements domain matching adhering to RFC 6265."""
        if hostname == domain:
            return True

        if not hostname.endswith(domain):
            return False

        non_matching = hostname[: -len(domain)]

        if not non_matching.endswith("."):
            return False

        return not is_ip_address(hostname)

    @classmethod
    def _parse_date(cls, date_str: str) -> int | None:
        """Implements date string parsing adhering to RFC 6265."""
        if not date_str:
            return None

        found_time = False
        found_day = False
        found_month = False
        found_year = False

        hour = minute = second = 0
        day = 0
        month = 0
        year = 0

        for token_match in cls.DATE_TOKENS_RE.finditer(date_str):

            token = token_match.group("token")

            if not found_time:
                time_match = cls.DATE_HMS_TIME_RE.match(token)
                if time_match:
                    found_time = True
                    hour, minute, second = (int(s) for s in time_match.groups())
                    continue

            if not found_day:
                day_match = cls.DATE_DAY_OF_MONTH_RE.match(token)
                if day_match:
                    found_day = True
                    day = int(day_match.group())
                    continue
