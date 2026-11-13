                        curl.info["headers"],  # type: ignore
                    )
                except Exception as e:
                    # If there was an error in setup, pass it on
                    # to the callback. Note that allowing the
                    # error to escape here will appear to work
                    # most of the time since we are still in the
                    # caller's original stack frame, but when
                    # _process_queue() is called from
                    # _finish_pending_requests the exceptions have
                    # nowhere to go.
                    curl.reset()
                    self._free_list.append(curl)
                    callback(HTTPResponse(request=request, code=599, error=e))
                else:
                    self._multi.add_handle(curl)

            if not started:
                break

    def _finish(
        self,
        curl: pycurl.Curl,
        curl_error: int | None = None,
        curl_message: str | None = None,
    ) -> None:
        info = curl.info  # type: ignore
        curl.info = None  # type: ignore
        self._multi.remove_handle(curl)
        streaming_buffer = info["streaming_buffer"]
        body_too_large = info["body_too_large"]
        if streaming_buffer is not None:
            body_too_large = body_too_large or streaming_buffer.body_too_large
            # Make sure everything that was received reaches the
            # streaming_callback before the final response.
            try:
                streaming_buffer.finish()
            except Exception:
                self.handle_callback_exception(info["request"].streaming_callback)
        buffer = info["buffer"]
        if curl_error:
            assert curl_message is not None
            if body_too_large:
                curl_message = "body exceeded max_body_size of %d bytes" % (
                    self.max_body_size,
                )
            error: CurlError | None = CurlError(curl_error, curl_message)
            assert error is not None
            code = error.code
            effective_url = None
            buffer.close()
            buffer = None
        else:
            error = None
            code = curl.getinfo(pycurl.HTTP_CODE)
            effective_url = curl.getinfo(pycurl.EFFECTIVE_URL)
            buffer.seek(0)
        # the various curl timings are documented at
        # http://curl.haxx.se/libcurl/c/curl_easy_getinfo.html
        time_info = dict(
            queue=info["curl_start_ioloop_time"] - info["queue_start_time"],
            namelookup=curl.getinfo(pycurl.NAMELOOKUP_TIME),
            connect=curl.getinfo(pycurl.CONNECT_TIME),
            appconnect=curl.getinfo(pycurl.APPCONNECT_TIME),
            pretransfer=curl.getinfo(pycurl.PRETRANSFER_TIME),
            starttransfer=curl.getinfo(pycurl.STARTTRANSFER_TIME),
            total=curl.getinfo(pycurl.TOTAL_TIME),
            redirect=curl.getinfo(pycurl.REDIRECT_TIME),
        )
        try:
            info["callback"](
                HTTPResponse(
                    request=info["request"],
                    code=code,
                    headers=info["headers"],
                    buffer=buffer,
                    effective_url=effective_url,
                    error=error,
                    reason=info["headers"].get("X-Http-Reason", None),
                    request_time=self.io_loop.time() - info["curl_start_ioloop_time"],
                    start_time=info["curl_start_time"],
                    time_info=time_info,
                )
            )
        except Exception:
            self.handle_callback_exception(info["callback"])
        curl.reset()
        self._free_list.append(curl)

    def handle_callback_exception(self, callback: Any) -> None:
        app_log.error("Exception in callback %r", callback, exc_info=True)

    def _curl_create(self) -> pycurl.Curl:
        return pycurl.Curl()

    def _curl_setup_request(
        self,
        curl: pycurl.Curl,
        request: HTTPRequest,
        buffer: BytesIO,
        headers: httputil.HTTPHeaders,
    ) -> None:
        if curl_log.isEnabledFor(logging.DEBUG):
            curl.setopt(pycurl.VERBOSE, 1)
            curl.setopt(pycurl.DEBUGFUNCTION, self._curl_debug)
        if hasattr(
            pycurl, "PROTOCOLS"
        ):  # PROTOCOLS first appeared in pycurl 7.19.5 (2014-07-12)
            curl.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTP | pycurl.PROTO_HTTPS)
            curl.setopt(pycurl.REDIR_PROTOCOLS, pycurl.PROTO_HTTP | pycurl.PROTO_HTTPS)

        curl.setopt(pycurl.URL, native_str(request.url))

        # libcurl's magic "Expect: 100-continue" behavior causes delays
        # with servers that don't support it (which include, among others,
        # Google's OpenID endpoint).  Additionally, this behavior has
        # a bug in conjunction with the curl_multi_socket_action API
        # (https://sourceforge.net/tracker/?func=detail&atid=100976&aid=3039744&group_id=976),
        # which increases the delays.  It's more trouble than it's worth,
        # so just turn off the feature (yes, setting Expect: to an empty
        # value is the official way to disable this)
        if "Expect" not in request.headers:
            request.headers["Expect"] = ""

        # libcurl adds Pragma: no-cache by default; disable that too
        if "Pragma" not in request.headers:
            request.headers["Pragma"] = ""

        encoded_headers = [
            b"%s: %s"
            % (native_str(k).encode("ASCII"), native_str(v).encode("ISO8859-1"))
            for k, v in request.headers.get_all()
        ]
        for line in encoded_headers:
            if CR_OR_LF_RE.search(line):
                raise ValueError("Illegal characters in header (CR or LF): %r" % line)
        curl.setopt(pycurl.HTTPHEADER, encoded_headers)

        curl.setopt(
            pycurl.HEADERFUNCTION,
            functools.partial(
                self._curl_header_callback, headers, request.header_callback
            ),
        )
        write_function: Callable[[bytes], int]
        if request.streaming_callback:

            if gen.is_coroutine_function(
                request.streaming_callback
            ) or inspect.iscoroutinefunction(request.streaming_callback):
                raise TypeError(
                    "'CurlAsyncHTTPClient' does not support async streaming_callbacks."
                )

            streaming_buffer = _CurlStreamingBuffer(
                self, curl, request.streaming_callback
            )
            curl.info["streaming_buffer"] = streaming_buffer  # type: ignore
            write_function = streaming_buffer.write
        else:
            # Count the buffered body against max_body_size, as
            # _CurlStreamingBuffer does for the streaming case. Here the
            # whole body is held in memory, so a response that decompresses
            # past the limit cannot be retrieved at all -- only refused
            # before it exhausts memory. libcurl's CURLOPT_MAXFILESIZE is
            # no help: outside of very recent versions it is measured
            # against the compressed size, which a bomb keeps small.
            def write_function(chunk: bytes) -> int:
                if buffer.tell() + len(chunk) > self.max_body_size:
                    curl.info["body_too_large"] = True  # type: ignore
                    # Writing less than we were given makes libcurl fail
                    # the transfer with CURLE_WRITE_ERROR; _finish uses the
                    # flag above to replace its message with ours.
                    return 0
                return buffer.write(chunk)

        curl.setopt(pycurl.WRITEFUNCTION, write_function)
        curl.setopt(pycurl.FOLLOWLOCATION, request.follow_redirects)
        curl.setopt(pycurl.MAXREDIRS, request.max_redirects)
        assert request.connect_timeout is not None
        curl.setopt(pycurl.CONNECTTIMEOUT_MS, int(1000 * request.connect_timeout))
        assert request.request_timeout is not None
        curl.setopt(pycurl.TIMEOUT_MS, int(1000 * request.request_timeout))
        if request.user_agent:
            curl.setopt(pycurl.USERAGENT, native_str(request.user_agent))
        else:
            curl.setopt(pycurl.USERAGENT, "Mozilla/5.0 (compatible; pycurl)")
        if request.network_interface:
            curl.setopt(pycurl.INTERFACE, request.network_interface)
        if request.decompress_response:
            curl.setopt(pycurl.ENCODING, "gzip,deflate")
        else:
            curl.setopt(pycurl.ENCODING, None)
        if request.proxy_host and request.proxy_port:
            curl.setopt(pycurl.PROXY, request.proxy_host)
            curl.setopt(pycurl.PROXYPORT, request.proxy_port)
            if request.proxy_username:
                assert request.proxy_password is not None
                credentials = httputil.encode_username_password(
                    request.proxy_username, request.proxy_password
                )
                curl.setopt(pycurl.PROXYUSERPWD, credentials)

            if request.proxy_auth_mode is None or request.proxy_auth_mode == "basic":
                curl.setopt(pycurl.PROXYAUTH, pycurl.HTTPAUTH_BASIC)
            elif request.proxy_auth_mode == "digest":
                curl.setopt(pycurl.PROXYAUTH, pycurl.HTTPAUTH_DIGEST)
            else:
                raise ValueError(
                    "Unsupported proxy_auth_mode %s" % request.proxy_auth_mode
                )
        else:
            try:
                curl.unsetopt(pycurl.PROXY)
            except TypeError:  # not supported, disable proxy
                curl.setopt(pycurl.PROXY, "")
            curl.unsetopt(pycurl.PROXYUSERPWD)
        if request.validate_cert:
            curl.setopt(pycurl.SSL_VERIFYPEER, 1)
            curl.setopt(pycurl.SSL_VERIFYHOST, 2)
        else:
            curl.setopt(pycurl.SSL_VERIFYPEER, 0)
            curl.setopt(pycurl.SSL_VERIFYHOST, 0)
        if request.ca_certs is not None:
            curl.setopt(pycurl.CAINFO, request.ca_certs)
        else:
            # There is no way to restore pycurl.CAINFO to its default value
            # (Using unsetopt makes it reject all certificates).
            # I don't see any way to read the default value from python so it
            # can be restored later.  We'll have to just leave CAINFO untouched
            # if no ca_certs file was specified, and require that if any
            # request uses a custom ca_certs file, they all must.
            pass

        if request.allow_ipv6 is False:
            # Curl behaves reasonably when DNS resolution gives an ipv6 address
            # that we can't reach, so allow ipv6 unless the user asks to disable.
            curl.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)
        else:
            curl.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_WHATEVER)

        # Set the request method through curl's irritating interface which makes
