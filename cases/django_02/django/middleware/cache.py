class UpdateCacheMiddleware(MiddlewareMixin):
    """
    Response-phase cache middleware that updates the cache if the response is
    cacheable.

    Must be used as part of the two-part update/fetch cache middleware.
    UpdateCacheMiddleware must be the first piece of middleware in MIDDLEWARE
    so that it'll get called last during the response phase.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
        self.page_timeout = None
        self.key_prefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
        self.cache_alias = settings.CACHE_MIDDLEWARE_ALIAS

    @property
    def cache(self):
        return caches[self.cache_alias]

    def _should_update_cache(self, request, response):
        return hasattr(request, "_cache_update_cache") and request._cache_update_cache

    def process_response(self, request, response):
        """Set the cache, if needed."""
        if not self._should_update_cache(request, response):
            # We don't need to update the cache, just return.
            return response

        if response.streaming or response.status_code not in (200, 304):
            return response

        # Don't cache responses that set a user-specific (and maybe security
        # sensitive) cookie in response to a cookie-less request.
        if (
            not request.COOKIES
            and response.cookies
            and has_vary_header(response, "Cookie")
        ):
            return response

        # Don't cache responses when the Cache-Control header is set to
        # private, no-cache, or no-store.
        cache_control = response.get("Cache-Control", "").lower()
        if cache_control and any(
            directive in cache_control
            for directive in (
                "private",
                "no-cache",
                "no-store",
            )
        ):
            return response

        # Don't cache responses when the Vary header contains '*'.
        if has_vary_header(response, "*"):
            return response

        # Page timeout takes precedence over the "max-age" and the default
        # cache timeout.
        timeout = self.page_timeout
        if timeout is None:
            # The timeout from the "max-age" section of the "Cache-Control"
            # header takes precedence over the default cache timeout.
            timeout = get_max_age(response)
            if timeout is None:
                timeout = self.cache_timeout
            elif timeout == 0:
                # max-age was set to 0, don't cache.
                return response
        patch_response_headers(response, timeout)
        if timeout and response.status_code == 200:
            cache_key = learn_cache_key(
                request, response, timeout, self.key_prefix, cache=self.cache
            )
            if hasattr(response, "render") and callable(response.render):
                response.add_post_render_callback(
                    lambda r: self.cache.set(cache_key, r, timeout)
                )
            else:
                self.cache.set(cache_key, response, timeout)
        return response


class FetchFromCacheMiddleware(MiddlewareMixin):
