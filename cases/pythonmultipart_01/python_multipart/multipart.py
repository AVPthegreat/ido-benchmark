class File:
    """This class represents an uploaded file.  It handles writing file data to
    either an in-memory file or a temporary file on-disk, if the optional
    threshold is passed.

    There are some options that can be passed to the File to change behavior
    of the class.  Valid options are as follows:

    | Name                  | Type  | Default | Description |
    |-----------------------|-------|---------|-------------|
    | UPLOAD_DIR            | `str` | None    | The directory to store uploaded files in. If this is None, a temporary file will be created in the system's standard location. |
    | UPLOAD_DELETE_TMP     | `bool`| True    | Delete automatically created TMP file |
    | UPLOAD_KEEP_FILENAME  | `bool`| False   | Whether or not to keep the filename of the uploaded file. If True, then the filename will be converted to a safe representation (e.g. by removing any invalid path segments), and then saved with the same name). Otherwise, a temporary name will be used. |
    | UPLOAD_KEEP_EXTENSIONS| `bool`| False   | Whether or not to keep the uploaded file's extension. If False, the file will be saved with the default temporary extension (usually ".tmp"). Otherwise, the file's extension will be maintained. Note that this will properly combine with the UPLOAD_KEEP_FILENAME setting. |
    | MAX_MEMORY_FILE_SIZE  | `int` | 1 MiB   | The maximum number of bytes of a File to keep in memory. By default, the contents of a File are kept into memory until a certain limit is reached, after which the contents of the File are written to a temporary file. This behavior can be disabled by setting this value to an appropriately large value (or, for example, infinity, such as `float('inf')`. |

    Args:
        file_name: The name of the file that this [`File`][python_multipart.File] represents.
        field_name: The name of the form field that this file was uploaded with.  This can be None, if, for example,
            the file was uploaded with Content-Type application/octet-stream.
        config: The configuration for this File.  See above for valid configuration keys and their corresponding values.
    """  # noqa: E501

    def __init__(self, file_name: bytes | None, field_name: bytes | None = None, config: FileConfig = {}) -> None:
        # Save configuration, set other variables default.
        self.logger = logging.getLogger(__name__)
        self._config = config
        self._in_memory = True
        self._bytes_written = 0
        self._fileobj: BytesIO | BufferedRandom = BytesIO()

        # Save the provided field/file name.
        self._field_name = field_name
        self._file_name = file_name

        # Our actual file name is None by default, since, depending on our
        # config, we may not actually use the provided name.
        self._actual_file_name: bytes | None = None

        # Split the extension from the filename.
        if file_name is not None:
            # Extract just the basename to avoid directory traversal
            basename = os.path.basename(file_name)
            base, ext = os.path.splitext(basename)
            self._file_base = base
            self._ext = ext

    @property
    def field_name(self) -> bytes | None:
        """The form field associated with this file.  May be None if there isn't
        one, for example when we have an application/octet-stream upload.
        """
        return self._field_name

    @property
    def file_name(self) -> bytes | None:
        """The file name given in the upload request."""
        return self._file_name

    @property
    def actual_file_name(self) -> bytes | None:
        """The file name that this file is saved as.  Will be None if it's not
        currently saved on disk.
        """
        return self._actual_file_name

    @property
    def file_object(self) -> BytesIO | BufferedRandom:
        """The file object that we're currently writing to.  Note that this
        will either be an instance of a :class:`io.BytesIO`, or a regular file
        object.
        """
        return self._fileobj

    @property
    def size(self) -> int:
        """The total size of this file, counted as the number of bytes that
        currently have been written to the file.
        """
        return self._bytes_written

    @property
    def in_memory(self) -> bool:
        """A boolean representing whether or not this file object is currently
        stored in-memory or on-disk.
        """
        return self._in_memory

    def flush_to_disk(self) -> None:
        """If the file is already on-disk, do nothing.  Otherwise, copy from
        the in-memory buffer to a disk file, and then reassign our internal
        file object to this new disk file.

        Note that if you attempt to flush a file that is already on-disk, a
        warning will be logged to this module's logger.
        """
        if not self._in_memory:
            self.logger.warning("Trying to flush to disk when we're not in memory")
            return

        # Go back to the start of our file.
        self._fileobj.seek(0)

        # Open a new file.
        new_file = self._get_disk_file()

        # Copy the file objects.
        shutil.copyfileobj(self._fileobj, new_file)

        # Seek to the new position in our new file.
        new_file.seek(self._bytes_written)

        # Reassign the fileobject.
        old_fileobj = self._fileobj
        self._fileobj = new_file

        # We're no longer in memory.
        self._in_memory = False

        # Close the old file object.
        old_fileobj.close()

    def _get_disk_file(self) -> BufferedRandom:
        """This function is responsible for getting a file object on-disk for us."""
        self.logger.info("Opening a file on disk")

        file_dir = self._config.get("UPLOAD_DIR")
        keep_filename = self._config.get("UPLOAD_KEEP_FILENAME", False)
        keep_extensions = self._config.get("UPLOAD_KEEP_EXTENSIONS", False)
        delete_tmp = self._config.get("UPLOAD_DELETE_TMP", True)
        tmp_file: None | BufferedRandom = None

        # If we have a directory and are to keep the filename...
        if file_dir is not None and keep_filename:
            self.logger.info("Saving with filename in: %r", file_dir)

            # Build our filename.
            # TODO: what happens if we don't have a filename?
            fname = self._file_base + self._ext if keep_extensions else self._file_base

            path = os.path.join(file_dir, fname)  # type: ignore[arg-type]
            try:
                self.logger.info("Opening file: %r", path)
                tmp_file = open(path, "w+b")
            except OSError:
                tmp_file = None

                self.logger.exception("Error opening temporary file")
                raise FileError("Error opening temporary file: %r" % path)
        else:
            # Build options array.
            # Note that on Python 3, tempfile doesn't support byte names.  We
            # encode our paths using the default filesystem encoding.
            suffix = self._ext.decode(sys.getfilesystemencoding()) if keep_extensions else None

            if file_dir is None:
                dir = None
            elif isinstance(file_dir, bytes):
                dir = file_dir.decode(sys.getfilesystemencoding())
            else:
                dir = file_dir  # pragma: no cover

            # Create a temporary (named) file with the appropriate settings.
            self.logger.info(
