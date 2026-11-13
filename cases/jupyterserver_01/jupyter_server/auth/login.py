import os
import re
import uuid
from urllib.parse import urlparse

from tornado.escape import url_escape

from ..base.handlers import JupyterHandler
from .security import passwd_check, set_password


class LoginFormHandler(JupyterHandler):
    """The basic tornado login handler

    accepts login form, passed to IdentityProvider.process_login_form.
    """

    def _render(self, message=None):
        """Render the login form."""
        self.write(
            self.render_template(
                "login.html",
                next=url_escape(self.get_argument("next", default=self.base_url)),
                message=message,
            )
        )

    def _redirect_safe(self, url, default=None):
        """Redirect if url is on our PATH

        Full-domain redirects are allowed if they pass our CORS origin checks.

        Otherwise use default (self.base_url if unspecified).
        """
        if default is None:
            default = self.base_url
        # protect chrome users from mishandling unescaped backslashes.
        # \ is not valid in urls, but some browsers treat it as /
        # instead of %5C, causing `\\` to behave as `//`
        url = url.replace("\\", "%5C")
        parsed = urlparse(url)
        if parsed.netloc or not (parsed.path + "/").startswith(self.base_url):
            # require that next_url be absolute path within our path
            allow = False
            # OR pass our cross-origin check
            if parsed.netloc:
                # if full URL, run our cross-origin check:
                origin = f"{parsed.scheme}://{parsed.netloc}"
                origin = origin.lower()
                if self.allow_origin:
                    allow = self.allow_origin == origin
                elif self.allow_origin_pat:
                    allow = bool(re.match(self.allow_origin_pat, origin))
            if not allow:
                # not allowed, use default
                self.log.warning("Not allowing login redirect to %r" % url)
                url = default
        self.redirect(url)

    def get(self):
        """Get the login form."""
        if self.current_user:
            next_url = self.get_argument("next", default=self.base_url)
            self._redirect_safe(next_url)
        else:
            self._render()

    def post(self):
        """Post a login."""
        user = self.current_user = self.identity_provider.process_login_form(self)
        if user is None:
            self.set_status(401)
            self._render(message={"error": "Invalid credentials"})
            return

        self.log.info(f"User {user.username} logged in.")
        self.identity_provider.set_login_cookie(self, user)
        next_url = self.get_argument("next", default=self.base_url)
        self._redirect_safe(next_url)


class LegacyLoginHandler(LoginFormHandler):
    """Legacy LoginHandler, implementing most custom auth configuration.

    Deprecated in jupyter-server 2.0.
    Login configuration has moved to IdentityProvider.
