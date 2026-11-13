     :ref:`usage_templatelookup`.

    :param module_directory: Filesystem location where generated
     Python module files will be placed.

    :param module_filename: Overrides the filename of the generated
     Python module file. For advanced usage only.

    :param module_writer: A callable which overrides how the Python
     module is written entirely.  The callable is passed the
     encoded source content of the module and the destination
     path to be written to.   The default behavior of module writing
     uses a tempfile in conjunction with a file move in order
     to make the operation atomic.   So a user-defined module
     writing function that mimics the default behavior would be:

     .. sourcecode:: python

         import tempfile
         import os
         import shutil

         def module_writer(source, outputpath):
             (dest, name) = \\
                 tempfile.mkstemp(
                     dir=os.path.dirname(outputpath)
                 )

             os.write(dest, source)
             os.close(dest)
             shutil.move(name, outputpath)

         from mako.template import Template
         mytemplate = Template(
                         filename="index.html",
                         module_directory="/path/to/modules",
                         module_writer=module_writer
                     )

     The function is provided for unusual configurations where
     certain platform-specific permissions or other special
     steps are needed.

    :param output_encoding: The encoding to use when :meth:`.render`
     is called.
     See :ref:`usage_unicode` as well as :ref:`unicode_toplevel`.

    :param preprocessor: Python callable which will be passed
     the full template source before it is parsed. The return
     result of the callable will be used as the template source
     code.

    :param lexer_cls: A :class:`.Lexer` class used to parse
     the template.   The :class:`.Lexer` class is used by
     default.

     .. versionadded:: 0.7.4

    :param strict_undefined: Replaces the automatic usage of
     ``UNDEFINED`` for any undeclared variables not located in
     the :class:`.Context` with an immediate raise of
     ``NameError``. The advantage is immediate reporting of
     missing variables which include the name.

     .. versionadded:: 0.3.6

    :param uri: string URI or other identifier for this template.
     If not provided, the ``uri`` is generated from the filesystem
     path, or from the in-memory identity of a non-file-based
     template. The primary usage of the ``uri`` is to provide a key
     within :class:`.TemplateLookup`, as well as to generate the
     file path of the generated Python module file, if
     ``module_directory`` is specified.

    """

    lexer_cls = Lexer

    def __init__(
        self,
        text=None,
        filename=None,
        uri=None,
        format_exceptions=False,
        error_handler=None,
        lookup=None,
        output_encoding=None,
        encoding_errors="strict",
        module_directory=None,
        cache_args=None,
        cache_impl="beaker",
        cache_enabled=True,
        cache_type=None,
        cache_dir=None,
        cache_url=None,
        module_filename=None,
        input_encoding=None,
        module_writer=None,
        default_filters=None,
        buffer_filters=(),
        strict_undefined=False,
        imports=None,
        future_imports=None,
        enable_loop=True,
        preprocessor=None,
        lexer_cls=None,
        include_error_handler=None,
    ):
        if uri:
            self.module_id = re.sub(r"\W", "_", uri)
            self.uri = uri
        elif filename:
            self.module_id = re.sub(r"\W", "_", filename)
            drive, path = os.path.splitdrive(filename)
            path = os.path.normpath(path).replace(os.path.sep, "/")
            self.uri = path
        else:
            self.module_id = "memory:" + hex(id(self))
            self.uri = self.module_id

        u_norm = self.uri.lstrip("/")
        u_norm = os.path.normpath(u_norm)
        if u_norm.startswith(".."):
            raise exceptions.TemplateLookupException(
                'Template uri "%s" is invalid - '
                "it cannot be relative outside "
                "of the root path." % self.uri
            )

        self.input_encoding = input_encoding
        self.output_encoding = output_encoding
        self.encoding_errors = encoding_errors
        self.enable_loop = enable_loop
        self.strict_undefined = strict_undefined
        self.module_writer = module_writer

        if default_filters is None:
            self.default_filters = ["str"]
        else:
            self.default_filters = default_filters
        self.buffer_filters = buffer_filters

        self.imports = imports
        self.future_imports = future_imports
        self.preprocessor = preprocessor

        if lexer_cls is not None:
            self.lexer_cls = lexer_cls

        # if plain text, compile code in memory only
        if text is not None:
            (code, module) = _compile_text(self, text, filename)
            self._code = code
            self._source = text
            ModuleInfo(module, None, self, filename, code, text, uri)
        elif filename is not None:
            # if template filename and a module directory, load
            # a filesystem-based module file, generating if needed
            if module_filename is not None:
                path = module_filename
            elif module_directory is not None:
                path = os.path.abspath(
                    os.path.join(
                        os.path.normpath(module_directory), u_norm + ".py"
                    )
                )
            else:
                path = None
            module = self._compile_from_file(path, filename)
        else:
            raise exceptions.RuntimeException(
                "Template requires text or filename"
            )

        self.module = module
        self.filename = filename
        self.callable_ = self.module.render_body
        self.format_exceptions = format_exceptions
        self.error_handler = error_handler
        self.include_error_handler = include_error_handler
        self.lookup = lookup

        self.module_directory = module_directory

        self._setup_cache_args(
            cache_impl,
            cache_enabled,
            cache_args,
            cache_type,
            cache_dir,
            cache_url,
        )

    @util.memoized_property
    def reserved_names(self):
        if self.enable_loop:
            return codegen.RESERVED_NAMES
        else:
            return codegen.RESERVED_NAMES.difference(["loop"])

    def _setup_cache_args(
        self,
        cache_impl,
        cache_enabled,
        cache_args,
        cache_type,
        cache_dir,
        cache_url,
    ):
        self.cache_impl = cache_impl
        self.cache_enabled = cache_enabled
        self.cache_args = cache_args or {}
        # transfer deprecated cache_* args
        if cache_type:
            self.cache_args["type"] = cache_type
        if cache_dir:
            self.cache_args["dir"] = cache_dir
        if cache_url:
            self.cache_args["url"] = cache_url

    def _compile_from_file(self, path, filename):
        if path is not None:
            util.verify_directory(os.path.dirname(path))
            filemtime = os.stat(filename)[stat.ST_MTIME]
            if (
                not os.path.exists(path)
                or os.stat(path)[stat.ST_MTIME] < filemtime
            ):
                data = util.read_file(filename)
                _compile_module_file(
                    self, data, filename, path, self.module_writer
                )
            module = compat.load_module(self.module_id, path)
            if module._magic_number != codegen.MAGIC_NUMBER:
                data = util.read_file(filename)
                _compile_module_file(
                    self, data, filename, path, self.module_writer
                )
                module = compat.load_module(self.module_id, path)
            ModuleInfo(module, path, self, filename, None, None, None)
        else:
