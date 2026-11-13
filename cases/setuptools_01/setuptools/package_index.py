        if dist is not None:
            return dist.location
        return None

    def gen_setup(self, filename, fragment, tmpdir):
        match = EGG_FRAGMENT.match(fragment)
        dists = (
            match
            and [
                d
                for d in interpret_distro_name(filename, match.group(1), None)
                if d.version
            ]
            or []
        )

        if len(dists) == 1:  # unambiguous ``#egg`` fragment
            basename = os.path.basename(filename)

            # Make sure the file has been downloaded to the temp dir.
            if os.path.dirname(filename) != tmpdir:
                dst = os.path.join(tmpdir, basename)
                if not (os.path.exists(dst) and os.path.samefile(filename, dst)):
                    shutil.copy2(filename, dst)
                    filename = dst

            with open(os.path.join(tmpdir, 'setup.py'), 'w', encoding="utf-8") as file:
                file.write(
                    "from setuptools import setup\n"
                    f"setup(name={dists[0].project_name!r}, version={dists[0].version!r}, py_modules=[{os.path.splitext(basename)[0]!r}])\n"
                )
            return filename

        elif match:
            raise DistutilsError(
                f"Can't unambiguously interpret project/version identifier {fragment!r}; "
                "any dashes in the name or version should be escaped using "
                f"underscores. {dists!r}"
            )
        else:
            raise DistutilsError(
                "Can't process plain .py files without an '#egg=name-version'"
                " suffix to enable automatic setup script generation."
            )

    dl_blocksize = 8192

    def _download_to(self, url, filename):
        self.info("Downloading %s", url)
        # Download the file
        fp = None
        try:
            checker = HashChecker.from_url(url)
            fp = self.open_url(url)
            if isinstance(fp, urllib.error.HTTPError):
                raise DistutilsError(f"Can't download {url}: {fp.code} {fp.msg}")
            headers = fp.info()
            blocknum = 0
            bs = self.dl_blocksize
            size = -1
            if "content-length" in headers:
                # Some servers return multiple Content-Length headers :(
                sizes = headers.get_all('Content-Length')
                size = max(map(int, sizes))
                self.reporthook(url, filename, blocknum, bs, size)
            with open(filename, 'wb') as tfp:
                while True:
                    block = fp.read(bs)
                    if block:
                        checker.feed(block)
                        tfp.write(block)
                        blocknum += 1
                        self.reporthook(url, filename, blocknum, bs, size)
                    else:
                        break
                self.check_hash(checker, filename, tfp)
            return headers
        finally:
            if fp:
                fp.close()

    def reporthook(self, url, filename, blocknum, blksize, size) -> None:
        pass  # no-op

    # FIXME:
    def open_url(self, url, warning=None):  # noqa: C901  # is too complex (12)
        if url.startswith('file:'):
            return local_open(url)
        try:
            return open_with_auth(url, self.opener)
        except (ValueError, http.client.InvalidURL) as v:
            msg = ' '.join([str(arg) for arg in v.args])
            if warning:
                self.warn(warning, msg)
            else:
                raise DistutilsError(f'{url} {msg}') from v
        except urllib.error.HTTPError as v:
            return v
        except urllib.error.URLError as v:
            if warning:
                self.warn(warning, v.reason)
            else:
                raise DistutilsError(f"Download error for {url}: {v.reason}") from v
        except http.client.BadStatusLine as v:
            if warning:
                self.warn(warning, v.line)
            else:
                raise DistutilsError(
                    f'{url} returned a bad status line. The server might be '
                    f'down, {v.line}'
                ) from v
        except (http.client.HTTPException, OSError) as v:
            if warning:
                self.warn(warning, v)
            else:
                raise DistutilsError(f"Download error for {url}: {v}") from v

    @staticmethod
    def _resolve_download_filename(url, tmpdir):
        """
        >>> import pathlib
        >>> du = PackageIndex._resolve_download_filename
        >>> root = getfixture('tmp_path')
        >>> url = 'https://files.pythonhosted.org/packages/a9/5a/0db.../setuptools-78.1.0.tar.gz'
        >>> str(pathlib.Path(du(url, root)).relative_to(root))
        'setuptools-78.1.0.tar.gz'

        Ensures the target is always in tmpdir.

        >>> url = 'https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys'
        >>> du(url, root)
        Traceback (most recent call last):
        ...
        ValueError: Invalid filename...
        """
        name, _fragment = egg_info_for_url(url)
        if name:
            while '..' in name:
                name = name.replace('..', '.').replace('\\', '_')
        else:
            name = "__downloaded__"  # default if URL has no path contents

        if name.endswith('.egg.zip'):
            name = name[:-4]  # strip the extra .zip before download

        filename = os.path.join(tmpdir, name)

        # ensure path resolves within the tmpdir
        if not filename.startswith(str(tmpdir)):
            raise ValueError(f"Invalid filename {filename}")

        return filename

    def _download_url(self, url, tmpdir):
        """
        Determine the download filename.
        """
        filename = self._resolve_download_filename(url, tmpdir)
        return self._download_vcs(url, filename) or self._download_other(url, filename)

    @staticmethod
    def _resolve_vcs(url):
        """
        >>> rvcs = PackageIndex._resolve_vcs
        >>> rvcs('git+http://foo/bar')
        'git'
        >>> rvcs('hg+https://foo/bar')
        'hg'
        >>> rvcs('git:myhost')
        'git'
        >>> rvcs('hg:myhost')
        >>> rvcs('http://foo/bar')
        """
        scheme = urllib.parse.urlsplit(url).scheme
        pre, sep, _post = scheme.partition('+')
        # svn and git have their own protocol; hg does not
        allowed = set(['svn', 'git'] + ['hg'] * bool(sep))
        return next(iter({pre} & allowed), None)

    def _download_vcs(self, url, spec_filename):
        vcs = self._resolve_vcs(url)
        if not vcs:
            return None
        if vcs == 'svn':
            raise DistutilsError(
                f"Invalid config, SVN download is not supported: {url}"
            )

        filename, _, _ = spec_filename.partition('#')
        url, rev = self._vcs_split_rev_from_url(url)

        self.info(f"Doing {vcs} clone from {url} to {filename}")
        subprocess.check_call([vcs, 'clone', '--quiet', url, filename])

        co_commands = dict(
            git=[vcs, '-C', filename, 'checkout', '--quiet', rev],
            hg=[vcs, '--cwd', filename, 'up', '-C', '-r', rev, '-q'],
        )
        if rev is not None:
            self.info(f"Checking out {rev}")
            subprocess.check_call(co_commands[vcs])

        return filename

    def _download_other(self, url, filename):
        scheme = urllib.parse.urlsplit(url).scheme
        if scheme == 'file':  # pragma: no cover
            return urllib.request.url2pathname(urllib.parse.urlparse(url).path)
        # raise error if not allowed
        self.url_ok(url, True)
        return self._attempt_download(url, filename)

    def scan_url(self, url) -> None:
        self.process_url(url, True)

    def _attempt_download(self, url, filename):
        headers = self._download_to(url, filename)
        if 'html' in headers.get('content-type', '').lower():
            return self._invalid_download_html(url, headers, filename)
        else:
            return filename

    def _invalid_download_html(self, url, headers, filename):
        os.unlink(filename)
        raise DistutilsError(f"Unexpected HTML page found at {url}")

    @staticmethod
    def _vcs_split_rev_from_url(url):
        """
        Given a possible VCS URL, return a clean URL and resolved revision if any.

        >>> vsrfu = PackageIndex._vcs_split_rev_from_url
        >>> vsrfu('git+https://github.com/pypa/setuptools@v69.0.0#egg-info=setuptools')
        ('https://github.com/pypa/setuptools', 'v69.0.0')
        >>> vsrfu('git+https://github.com/pypa/setuptools#egg-info=setuptools')
        ('https://github.com/pypa/setuptools', None)
        >>> vsrfu('http://foo/bar')
        ('http://foo/bar', None)
        """
        parts = urllib.parse.urlsplit(url)

        clean_scheme = parts.scheme.split('+', 1)[-1]

        # Some fragment identification fails
        no_fragment_path, _, _ = parts.path.partition('#')

        pre, sep, post = no_fragment_path.rpartition('@')
        clean_path, rev = (pre, post) if sep else (post, None)

        resolved = parts._replace(
            scheme=clean_scheme,
            path=clean_path,
            # discard the fragment
            fragment='',
        ).geturl()

        return resolved, rev

    def debug(self, msg, *args) -> None:
        log.debug(msg, *args)

    def info(self, msg, *args) -> None:
        log.info(msg, *args)

    def warn(self, msg, *args) -> None:
        log.warn(msg, *args)


# This pattern matches a character entity reference (a decimal numeric
# references, a hexadecimal numeric reference, or a named reference).
