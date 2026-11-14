
    def __getitem__(self, opt_name: str) -> Any:
        if opt_name not in self:
            return None
        return self.attributes[opt_name].value

    def __contains__(self, name: object) -> bool:
        return name in self.attributes

    def add_to_list(self, name: str, item: Any) -> None:
        """Append *item* to the :class:`list` setting with the specified *name*
        if *item* is not already in that list.

        This change is applied regardless of the priority of the *name*
        setting. The setting priority is not affected by this change either.
        """
        value: list[str] = self.getlist(name)
        if item not in value:
            self.set(name, [*value, item], self.getpriority(name) or 0)

    def remove_from_list(self, name: str, item: Any) -> None:
        """Remove *item* from the :class:`list` setting with the specified
        *name*.

        If *item* is missing, raise :exc:`ValueError`.

        This change is applied regardless of the priority of the *name*
        setting. The setting priority is not affected by this change either.
        """
        value: list[str] = self.getlist(name)
        if item not in value:
            raise ValueError(f"{item!r} not found in the {name} setting ({value!r}).")
        self.set(name, [v for v in value if v != item], self.getpriority(name) or 0)

    def get(self, name: str, default: Any = None) -> Any:  # pylint: disable=arguments-renamed
        """
        Get a setting value without affecting its original type.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        if name == "CONCURRENT_REQUESTS_PER_IP" and (
            isinstance(self[name], int) and self[name] != 0
        ):
            warnings.warn(
                "The CONCURRENT_REQUESTS_PER_IP setting is deprecated, use CONCURRENT_REQUESTS_PER_DOMAIN instead.",
                ScrapyDeprecationWarning,
                stacklevel=2,
            )

        if name == "DNS_RESOLVER":
            warnings.warn(
                "The DNS_RESOLVER setting is deprecated, please use "
                "TWISTED_DNS_RESOLVER instead.",
                ScrapyDeprecationWarning,
                stacklevel=2,
            )

        return self[name] if self[name] is not None else default

    def getbool(self, name: str, default: bool = False) -> bool:
        """
        Get a setting value as a boolean.

        ``1``, ``'1'``, `True`` and ``'True'`` return ``True``,
        while ``0``, ``'0'``, ``False``, ``'False'`` and ``None`` return ``False``.

        For example, settings populated through environment variables set to
        ``'0'`` will return ``False`` when using this method.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        got = self.get(name, default)
        try:
            return bool(int(got))
        except ValueError:
            if got in {"True", "true"}:
                return True
            if got in {"False", "false"}:
                return False
            raise ValueError(
                "Supported values for boolean settings "
                "are 0/1, True/False, '0'/'1', "
                "'True'/'False' and 'true'/'false'"
            ) from None

    def getint(self, name: str, default: int = 0) -> int:
        """
        Get a setting value as an int.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        return int(self.get(name, default))

    def getfloat(self, name: str, default: float = 0.0) -> float:
        """
        Get a setting value as a float.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        return float(self.get(name, default))

    def getlist(self, name: str, default: list[Any] | None = None) -> list[Any]:
        """
        Get a setting value as a list. If the setting original type is a list,
        a copy of it will be returned. If it's a string it will be evaluated as
        a JSON list, or split by "," as a fallback. If it is an empty string,
        an empty list will be returned.

        For example, settings populated through environment variables set to
        ``'one,two'`` or ``'["one", "two"]'`` will return a list ['one', 'two']
        when using this method.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        value = self.get(name, default or [])
        if not value:
            return []
        if isinstance(value, str):
            try:
                value_loaded = json.loads(value)
            except ValueError:
                value_loaded = None
            value = value_loaded if isinstance(value_loaded, list) else value.split(",")
        return list(value)

    def getdict(
        self, name: str, default: dict[Any, Any] | None = None
    ) -> dict[Any, Any]:
        """
        Get a setting value as a dictionary. If the setting original type is a
        dictionary, a copy of it will be returned. If it is a string it will be
        evaluated as a JSON dictionary. In the case that it is a
        :class:`~scrapy.settings.BaseSettings` instance itself, it will be
        converted to a dictionary, containing all its current settings values
        as they would be returned by :meth:`~scrapy.settings.BaseSettings.get`,
        and losing all information about priority and mutability.

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        value = self.get(name, default or {})
        if isinstance(value, str):
            value = json.loads(value)
        return dict(value)

    def getdictorlist(
        self,
        name: str,
        default: dict[Any, Any] | list[Any] | tuple[Any, ...] | None = None,
    ) -> dict[Any, Any] | list[Any]:
        """Get a setting value as either a :class:`dict` or a :class:`list`.

        If the setting is already a dict or a list, a copy of it will be
        returned.

        If it is a string it will be evaluated as JSON, or as a comma-separated
        list of strings as a fallback.

        For example, settings populated from the command line will return:

        -   ``{'key1': 'value1', 'key2': 'value2'}`` if set to
            ``'{"key1": "value1", "key2": "value2"}'``

        -   ``['one', 'two']`` if set to ``'["one", "two"]'`` or ``'one,two'``

        :param name: the setting name
        :type name: str

        :param default: the value to return if no setting is found
        :type default: object
        """
        value = self.get(name, default)
        if value is None:
            return {}
        if isinstance(value, str):
            try:
                value_loaded = json.loads(value)
                if not isinstance(value_loaded, (dict, list)):
                    raise ValueError(
                        f"JSON string for setting '{name}' must evaluate to a dict or list, "
                        f"got {type(value_loaded).__name__}: {value_loaded!r}"
                    )
                return value_loaded
            except ValueError:
                return value.split(",")
        if isinstance(value, tuple):
            return list(value)
        if not isinstance(value, (dict, list)):
            raise ValueError(
                f"Setting '{name}' must be a dict, list, tuple, or string, "
                f"got {type(value).__name__}: {value!r}"
            )
        return copy.deepcopy(value)

    def getwithbase(self, name: str) -> BaseSettings:
        """Get a composition of a dictionary-like setting and its ``_BASE``
        counterpart.

        Use
        :meth:`~scrapy.settings.BaseSettings.get_component_priority_dict_with_base`
        instead if the setting is a :ref:`component priority dictionary
        <component-priority-dictionaries>`.

        :param name: name of the dictionary-like setting
        :type name: str
        """
        if not isinstance(name, str):
            raise ValueError(f"Base setting key must be a string, got {name}")
        compbs = BaseSettings()
        compbs.update(self[name + "_BASE"])
        compbs.update(self[name])
        return compbs

    def get_component_priority_dict_with_base(self, name: str) -> BaseSettings:
        """Get a composition of a component priority dictionary setting and
        its ``_BASE`` counterpart.

        Keys are resolved to their import path for deduplication and then
        restored to their latest input representation.

        :param name: name of the component priority dictionary setting
        :type name: str
        """
        if not isinstance(name, str):
            raise ValueError(f"Base setting key must be a string, got {name}")

        normalized_keys = {}
        obj_keys = set()

        def track_loaded_key(k: Any) -> None:
            if k not in obj_keys:
                obj_keys.add(k)
                return
            logger.warning(
                f"Setting {name} contains multiple keys that refer to the "
                f"same object: {global_object_name(k)}. Only the last one will "
                f"be kept."
            )

        def normalize_key(key: Any) -> str:
