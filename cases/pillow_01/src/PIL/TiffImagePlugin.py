        for legacy_api in (False, True):
            self._setitem(tag, value, legacy_api)

    def __getitem__(self, tag: int) -> Any:
        if tag not in self._tags_v1:  # unpack on the fly
            data = self._tagdata[tag]
            typ = self.tagtype[tag]
            size, handler = self._load_dispatch[typ]
            for legacy in (False, True):
                self._setitem(tag, handler(self, data, legacy), legacy)
        val = self._tags_v1[tag]
        if not isinstance(val, (tuple, bytes)):
            val = (val,)
        return val


# undone -- switch this pointer
ImageFileDirectory = ImageFileDirectory_v1


##
# Image plugin for TIFF files.


class TiffImageFile(ImageFile.ImageFile):
    format = "TIFF"
    format_description = "Adobe TIFF"
    _close_exclusive_fp_after_loading = False

    def __init__(
        self,
        fp: StrOrBytesPath | IO[bytes],
        filename: str | bytes | None = None,
    ) -> None:
        self.tag_v2: ImageFileDirectory_v2
        """ Image file directory (tag dictionary) """

        self.tag: ImageFileDirectory_v1
        """ Legacy tag entries """

        self._n_frames: int | None = None
        super().__init__(fp, filename)

    def _open(self) -> None:
        """Open the first image in a TIFF file"""

        # Header
        assert self.fp is not None
        ifh = self.fp.read(8)
        if ifh[2] == 43:
            ifh += self.fp.read(8)

        self.tag_v2 = ImageFileDirectory_v2(ifh)

        # setup frame pointers
        self.__first = self.__next = self.tag_v2.next
        self.__frame = -1
        self._fp = self.fp
        self._frame_pos: list[int] = []

        logger.debug("*** TiffImageFile._open ***")
        logger.debug("- __first: %s", self.__first)
        logger.debug("- ifh: %s", repr(ifh))  # Use repr to avoid str(bytes)

        # and load the first frame
        self._seek(0)

    @property
    def n_frames(self) -> int:
        current_n_frames = self._n_frames
        if current_n_frames is None:
            current = self.tell()
            self._seek(len(self._frame_pos))
            while self._n_frames is None:
                self._seek(self.tell() + 1)
            self.seek(current)
        assert self._n_frames is not None
        return self._n_frames

    def seek(self, frame: int) -> None:
        """Select a given frame as current image"""
        if not self._seek_check(frame):
            return
        self._seek(frame)
        if self._im is not None and (
            self.im.size != self._tile_size
            or self.im.mode != self.mode
            or self.readonly
        ):
            self._im = None

    def _seek(self, frame: int) -> None:
        if isinstance(self._fp, DeferredError):
            raise self._fp.ex
        self.fp = self._fp

        while len(self._frame_pos) <= frame:
            if not self.__next:
                msg = "no more images in TIFF file"
                raise EOFError(msg)
            logger.debug(
                "Seeking to frame %s, on frame %s, __next %s, location: %s",
                frame,
                self.__frame,
                self.__next,
                self.fp.tell(),
            )
            if self.__next >= 2**63:
                msg = "Unable to seek to frame"
                raise ValueError(msg)
            self.fp.seek(self.__next)
            self._frame_pos.append(self.__next)
            logger.debug("Loading tags, location: %s", self.fp.tell())
            self.tag_v2.load(self.fp)
            if self.tag_v2.next in self._frame_pos:
                # This IFD has already been processed
                # Declare this to be the end of the image
                self.__next = 0
            else:
                self.__next = self.tag_v2.next
            if self.__next == 0 and self._n_frames is None:
                self._n_frames = frame + 1
            if not hasattr(self, "is_animated"):
                self.is_animated = self.__next != 0
            self.__frame += 1
        self.fp.seek(self._frame_pos[frame])
        self.tag_v2.load(self.fp)
        if XMP in self.tag_v2:
            xmp = self.tag_v2[XMP]
            if isinstance(xmp, tuple) and len(xmp) == 1:
                xmp = xmp[0]
            self.info["xmp"] = xmp
        elif "xmp" in self.info:
            del self.info["xmp"]
        self._reload_exif()
        # fill the legacy tag/ifd entries
        self.tag = self.ifd = ImageFileDirectory_v1.from_v2(self.tag_v2)
        self.__frame = frame
        self._setup()

    def tell(self) -> int:
        """Return the current frame number"""
        return self.__frame

    def get_photoshop_blocks(self) -> dict[int, dict[str, bytes]]:
        """
        Returns a dictionary of Photoshop "Image Resource Blocks".
        The keys are the image resource ID. For more information, see
        https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/#50577409_pgfId-1037727

        :returns: Photoshop "Image Resource Blocks" in a dictionary.
        """
        blocks = {}
        val = self.tag_v2.get(ExifTags.Base.ImageResources)
        if val:
            while val.startswith(b"8BIM") and len(val) >= 12:
                id = i16(val[4:6])
                n = math.ceil((val[6] + 1) / 2) * 2
                try:
                    size = i32(val[6 + n : 10 + n])
                except struct.error:
                    break
                data = val[10 + n : 10 + n + size]
                blocks[id] = {"data": data}

                val = val[math.ceil((10 + n + size) / 2) * 2 :]
        return blocks

    def load(self) -> Image.core.PixelAccess | None:
        if self.tile and self.use_load_libtiff:
            return self._load_libtiff()
        return super().load()

    def load_prepare(self) -> None:
        if self._im is None:
            Image._decompression_bomb_check(self._tile_size)
            self.im = Image.core.new(self.mode, self._tile_size)
        ImageFile.ImageFile.load_prepare(self)

    def load_end(self) -> None:
        # allow closing if we're on the first frame, there's no next
        # This is the ImageFile.load path only, libtiff specific below.
        if not self.is_animated:
            self._close_exclusive_fp_after_loading = True

            # load IFD data from fp before it is closed
            exif = self.getexif()
            for key in TiffTags.TAGS_V2_GROUPS:
                if key not in exif:
                    continue
                exif.get_ifd(key)

        ImageOps.exif_transpose(self, in_place=True)
        if ExifTags.Base.Orientation in self.tag_v2:
            del self.tag_v2[ExifTags.Base.Orientation]

    def _load_libtiff(self) -> Image.core.PixelAccess | None:
        """Overload method triggered when we detect a compressed tiff
        Calls out to libtiff"""

        Image.Image.load(self)

        self.load_prepare()

        if not len(self.tile) == 1:
            msg = "Not exactly one tile"
            raise OSError(msg)

        extents = self.tile[0].extents
        args = self.tile[0].args

        # To be nice on memory footprint, if there's a
        # file descriptor, use that instead of reading
        # into a string in python.
        assert self.fp is not None
        try:
            fp = hasattr(self.fp, "fileno") and self.fp.fileno()
            # flush the file descriptor, prevents error on pypy 2.4+
            # should also eliminate the need for fp.tell
            # in _seek
            if hasattr(self.fp, "flush"):
                self.fp.flush()
        except OSError:
            # io.BytesIO have a fileno, but returns an OSError if
            # it doesn't use a file descriptor.
            fp = False

        if fp:
            assert isinstance(args, tuple)
            args_list = list(args)
            args_list[1] = fp
            args = tuple(args_list)

        decoder = Image._getdecoder(self.mode, "libtiff", args, self.decoderconfig)
        try:
            decoder.setimage(self.im, extents)
        except ValueError as e:
            msg = "Couldn't set the image"
            raise OSError(msg) from e

        close_self_fp = self._exclusive_fp and not self.is_animated
        if hasattr(self.fp, "getvalue"):
            # We've got a stringio like thing passed in. Yay for all in memory.
