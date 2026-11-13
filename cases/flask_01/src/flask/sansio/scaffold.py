        self.template_context_processors: dict[
            ft.AppOrBlueprintKey, list[ft.TemplateContextProcessorCallable]
        ] = defaultdict(list, {None: [_default_template_ctx_processor]})

        #: A data structure of functions to call to modify the keyword
        #: arguments passed to the view function, in the format
        #: ``{scope: [functions]}``. The ``scope`` key is the name of a
        #: blueprint the functions are active for, or ``None`` for all
        #: requests.
        #:
        #: To register a function, use the
        #: :meth:`url_value_preprocessor` decorator.
        #:
        #: This data structure is internal. It should not be modified
        #: directly and its format may change at any time.
        self.url_value_preprocessors: dict[
            ft.AppOrBlueprintKey,
            list[ft.URLValuePreprocessorCallable],
        ] = defaultdict(list)

        #: A data structure of functions to call to modify the keyword
        #: arguments when generating URLs, in the format
        #: ``{scope: [functions]}``. The ``scope`` key is the name of a
        #: blueprint the functions are active for, or ``None`` for all
        #: requests.
        #:
        #: To register a function, use the :meth:`url_defaults`
        #: decorator.
        #:
        #: This data structure is internal. It should not be modified
        #: directly and its format may change at any time.
        self.url_default_functions: dict[
            ft.AppOrBlueprintKey, list[ft.URLDefaultCallable]
        ] = defaultdict(list)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"

    def _check_setup_finished(self, f_name: str) -> None:
        raise NotImplementedError

    @property
    def static_folder(self) -> str | None:
        """The absolute path to the configured static folder. ``None``
        if no static folder is set.
        """
        if self._static_folder is not None:
            return os.path.join(self.root_path, self._static_folder)
        else:
            return None

    @static_folder.setter
    def static_folder(self, value: str | os.PathLike[str] | None) -> None:
        if value is not None:
            value = os.fspath(value).rstrip(r"\/")

        self._static_folder = value

    @property
    def has_static_folder(self) -> bool:
        """``True`` if :attr:`static_folder` is set.

        .. versionadded:: 0.5
        """
        return self.static_folder is not None

    @property
    def static_url_path(self) -> str | None:
        """The URL prefix that the static route will be accessible from.

        If it was not configured during init, it is derived from
        :attr:`static_folder`.
        """
        if self._static_url_path is not None:
            return self._static_url_path

        if self.static_folder is not None:
            basename = os.path.basename(self.static_folder)
            return f"/{basename}".rstrip("/")

        return None

    @static_url_path.setter
    def static_url_path(self, value: str | None) -> None:
        if value is not None:
            value = value.rstrip("/")

        self._static_url_path = value

    @cached_property
    def jinja_loader(self) -> BaseLoader | None:
        """The Jinja loader for this object's templates. By default this
        is a class :class:`jinja2.loaders.FileSystemLoader` to
        :attr:`template_folder` if it is set.

        .. versionadded:: 0.5
        """
        if self.template_folder is not None:
            return FileSystemLoader(os.path.join(self.root_path, self.template_folder))
        else:
            return None

    def _method_route(
        self,
        method: str,
        rule: str,
        options: dict[str, t.Any],
    ) -> t.Callable[[T_route], T_route]:
        if "methods" in options:
            raise TypeError("Use the 'route' decorator to use the 'methods' argument.")

        return self.route(rule, methods=[method], **options)

    @setupmethod
    def get(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Shortcut for :meth:`route` with ``methods=["GET"]``.

        .. versionadded:: 2.0
        """
        return self._method_route("GET", rule, options)

    @setupmethod
    def post(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Shortcut for :meth:`route` with ``methods=["POST"]``.

        .. versionadded:: 2.0
        """
        return self._method_route("POST", rule, options)

    @setupmethod
    def put(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Shortcut for :meth:`route` with ``methods=["PUT"]``.

        .. versionadded:: 2.0
        """
        return self._method_route("PUT", rule, options)

    @setupmethod
    def delete(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Shortcut for :meth:`route` with ``methods=["DELETE"]``.

        .. versionadded:: 2.0
        """
        return self._method_route("DELETE", rule, options)

    @setupmethod
    def patch(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Shortcut for :meth:`route` with ``methods=["PATCH"]``.

        .. versionadded:: 2.0
        """
        return self._method_route("PATCH", rule, options)

    @setupmethod
    def route(self, rule: str, **options: t.Any) -> t.Callable[[T_route], T_route]:
        """Decorate a view function to register it with the given URL
        rule and options. Calls :meth:`add_url_rule`, which has more
        details about the implementation.

        .. code-block:: python

            @app.route("/")
            def index():
                return "Hello, World!"

        See :ref:`url-route-registrations`.

        The endpoint name for the route defaults to the name of the view
        function if the ``endpoint`` parameter isn't passed.

        The ``methods`` parameter defaults to ``["GET"]``. ``HEAD`` and
        ``OPTIONS`` are added automatically.

        :param rule: The URL rule string.
        :param options: Extra options passed to the
            :class:`~werkzeug.routing.Rule` object.
        """

        def decorator(f: T_route) -> T_route:
            endpoint = options.pop("endpoint", None)
            self.add_url_rule(rule, endpoint, f, **options)
            return f

        return decorator

    @setupmethod
    def add_url_rule(
        self,
        rule: str,
        endpoint: str | None = None,
        view_func: ft.RouteCallable | None = None,
        provide_automatic_options: bool | None = None,
        **options: t.Any,
    ) -> None:
        """Register a rule for routing incoming requests and building
        URLs. The :meth:`route` decorator is a shortcut to call this
        with the ``view_func`` argument. These are equivalent:

        .. code-block:: python

            @app.route("/")
            def index():
                ...

        .. code-block:: python

            def index():
                ...

            app.add_url_rule("/", view_func=index)

        See :ref:`url-route-registrations`.

        The endpoint name for the route defaults to the name of the view
        function if the ``endpoint`` parameter isn't passed. An error
        will be raised if a function has already been registered for the
        endpoint.

        The ``methods`` parameter defaults to ``["GET"]``. ``HEAD`` is
        always added automatically, and ``OPTIONS`` is added
        automatically by default.

        ``view_func`` does not necessarily need to be passed, but if the
        rule should participate in routing an endpoint name must be
        associated with a view function at some point with the
        :meth:`endpoint` decorator.

        .. code-block:: python

            app.add_url_rule("/", endpoint="index")

            @app.endpoint("index")
            def index():
                ...

        If ``view_func`` has a ``required_methods`` attribute, those
        methods are added to the passed and automatic methods. If it
        has a ``provide_automatic_methods`` attribute, it is used as the
        default if the parameter is not passed.

