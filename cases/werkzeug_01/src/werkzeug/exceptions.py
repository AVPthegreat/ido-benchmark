from __future__ import annotations

import typing as t
import wsgiref.types as wt
from datetime import datetime
from http import HTTPStatus

from markupsafe import escape
from markupsafe import Markup

if t.TYPE_CHECKING:
    from .datastructures.auth import WWWAuthenticate
    from .wrappers.response import Response as WSGIResponse


class HTTPException(Exception):
    """An HTTP error status as an exception. It can be converted to an HTML
    response describing the error, and called as a WSGI application.

    All the exceptions take the following two keyword parameters to customize
    the error. Certain exceptions may take other arguments based on the headers
    they need to return.

    :param description: Override the default error page description.
    :param response: Use this response instead of generating one. This allows
        using the exception for flow control, while completely controlling the
        response.

    .. versionchanged:: 2.1
        The ``wrap`` class method was removed.
    """

    code: int | None = None
    name: str = ""
    description: str = ""

    _override_get_description = False
    _override_get_body = False
    _override_get_headers = False
    _override_get_response = False

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)

        # Skip special subclasses that inherit `code`.
        if "code" in cls.__dict__ and cls.code is not None:
            # Automatically fill in `name` from the `HTTPStatus` enum.
            if not cls.name:
                try:
                    cls.name = HTTPStatus(cls.code).phrase
                except ValueError:
                    pass

            # Automatically add the standard info to the top of the doc.
            title = f"{cls.code} {cls.name}"
            doc = (
                f"{title}\n\n{cls.description}\n\nhttps://developer.mozilla.org"
                f"/en-US/docs/Web/HTTP/Reference/Status/{cls.code}"
            )

            if not cls.__doc__:
                cls.__doc__ = doc
            elif not cls.__doc__.lstrip().startswith(title):
                cls.__doc__ = f"{doc}\n\n{cls.__doc__.lstrip()}"

        for name in ("get_description", "get_body", "get_headers", "get_response"):
            if getattr(cls, name) is not getattr(HTTPException, name):
                if name != "get_response":
                    import warnings

                    warnings.warn(
                        f"The '{name}' method is deprecated and will be removed in"
                        " Werkzeug 4.0. Override 'get_response' instead.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

                setattr(cls, f"_override_{name}", True)

    def __init__(
        self, description: str | None = None, response: WSGIResponse | None = None
    ) -> None:
        super().__init__()

        if description is not None:
            self.description = description

        self.response = response

    def get_description(self, environ: None = None, scope: None = None) -> str:
        """The description as an HTML paragraph. HTML characters are escaped,
        and newlines are replaced with ``<br>``.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_description' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_description()

    def _get_description(self) -> str:
        # TODO remove after deprecation
        description = escape(self.description).replace("\n", Markup("<br>"))
        return f"<p>{description}</p>"

    def get_body(self, environ: None = None, scope: None = None) -> str:
        """The HTML error page.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_body' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_body()

    def _get_body(self) -> str:
        # TODO remove after deprecation
        if self._override_get_description:
            description = self.get_description()
        else:
            description = self._get_description()

        title = f"{self.code} {escape(self.name)}"
        return (
            "<!doctype html>\n<html lang=en>\n<head>\n<meta charset=utf-8>\n"
            f"<title>{title}</title>\n</head>\n<body>\n<h1>{title}</h1>\n"
            f"{description}\n</body>\n</html>\n"
        )

    def get_headers(
        self, environ: None = None, scope: None = None
    ) -> list[tuple[str, str]]:
        """The headers to send with the response.

        .. deprecated:: 3.2
            Will be removed in Werkzeug 4.0. Use ``get_response`` instead.
        """
        import warnings

        warnings.warn(
            "The 'get_headers' method is deprecated and will be removed in"
            " Werkzeug 4.0. Use 'get_response' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return [("Content-Type", "text/html; charset=utf-8")]

    def get_response(self, environ: None = None, scope: None = None) -> WSGIResponse:
        """Get the response for this error. If :attr:`response` was given when
        creating the error, it will be returned. Otherwise, a default response
        with an HTML error page and any error-specific headers is built.

        .. versionchanged:: 3.2
            The ``environ`` and ``scope`` parameters are deprecated and will be
            removed in Werkzeug 4.0.
        """
        from .wrappers.request import Request
        from .wrappers.response import Response

        if self.response is not None:
            return self.response

