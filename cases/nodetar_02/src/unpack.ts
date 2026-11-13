        process.getuid && process.getuid() === 0
      )
    } else {
      this.preserveOwner = !!opt.preserveOwner
    }

    this.processUid =
      (this.preserveOwner || this.setOwner) && process.getuid ?
        process.getuid()
      : undefined
    this.processGid =
      (this.preserveOwner || this.setOwner) && process.getgid ?
        process.getgid()
      : undefined

    // prevent excessively deep nesting of subfolders
    // set to `Infinity` to remove this restriction
    this.maxDepth =
      typeof opt.maxDepth === 'number' ?
        opt.maxDepth
      : DEFAULT_MAX_DEPTH

    // mostly just for testing, but useful in some cases.
    // Forcibly trigger a chown on every entry, no matter what
    this.forceChown = opt.forceChown === true

    // turn ><?| in filenames into 0xf000-higher encoded forms
    this.win32 = !!opt.win32 || isWindows

    // do not unpack over files that are newer than what's in the archive
    this.newer = !!opt.newer

    // do not unpack over ANY files
    this.keep = !!opt.keep

    // do not set mtime/atime of extracted entries
    this.noMtime = !!opt.noMtime

    // allow .., absolute path entries, and unpacking through symlinks
    // without this, warn and skip .., relativize absolutes, and error
    // on symlinks in extraction path
    this.preservePaths = !!opt.preservePaths

    // unlink files and links before writing. This breaks existing hard
    // links, and removes symlink directories rather than erroring
    this.unlink = !!opt.unlink

    this.cwd = normalizeWindowsPath(
      path.resolve(opt.cwd || process.cwd()),
    )
    this.strip = Number(opt.strip) || 0
    // if we're not chmodding, then we don't need the process umask
    this.processUmask =
      !this.chmod ? 0
      : typeof opt.processUmask === 'number' ? opt.processUmask
      : umask()
    this.umask =
      typeof opt.umask === 'number' ? opt.umask : this.processUmask

    // default mode for dirs created as parents
    this.dmode = opt.dmode || 0o0777 & ~this.umask
    this.fmode = opt.fmode || 0o0666 & ~this.umask

    this.on('entry', entry => this[ONENTRY](entry))
  }

  // a bad or damaged archive is a warning for Parser, but an error
  // when extracting.  Mark those errors as unrecoverable, because
  // the Unpack contract cannot be met.
  warn(code: string, msg: string | Error, data: WarnData = {}) {
    if (code === 'TAR_BAD_ARCHIVE' || code === 'TAR_ABORT') {
      data.recoverable = false
    }
    return super.warn(code, msg, data)
  }

  [MAYBECLOSE]() {
    if (this[ENDED] && this[PENDING] === 0) {
      this.emit('prefinish')
      this.emit('finish')
      this.emit('end')
    }
  }

  // return false if we need to skip this file
  // return true if the field was successfully sanitized
  [STRIPABSOLUTEPATH](
    entry: ReadEntry,
    field: 'path' | 'linkpath',
  ): boolean {
    const p = entry[field]
    const { type } = entry
    if (!p || this.preservePaths) return true

    // strip off the root
    const [root, stripped] = stripAbsolutePath(p)
    const parts = stripped.replace(/\\/g, '/').split('/')

    if (
      parts.includes('..') ||
      /* c8 ignore next */
      (isWindows && /^[a-z]:\.\.$/i.test(parts[0] ?? ''))
    ) {
      // For linkpath, check if the resolved path escapes cwd rather than
      // just rejecting any path with '..' - relative symlinks like
      // '../sibling/file' are valid if they resolve within the cwd.
      // For paths, they just simply may not ever use .. at all.
      if (field === 'path' || type === 'Link') {
        this.warn('TAR_ENTRY_ERROR', `${field} contains '..'`, {
          entry,
          [field]: p,
        })
        // not ok!
        return false
      } else {
        // Resolve linkpath relative to the entry's directory.
        // `path.posix` is safe to use because we're operating on
        // tar paths, not a filesystem.
        const entryDir = path.posix.dirname(entry.path)
        const resolved = path.posix.normalize(
          path.posix.join(entryDir, parts.join('/'))
        )
        // If the resolved path escapes (starts with ..), reject it
        if (resolved.startsWith('../') || resolved === '..') {
          this.warn(
            'TAR_ENTRY_ERROR',
            `${field} escapes extraction directory`,
            {
              entry,
              [field]: p,
            },
          )
          return false
        }
      }
    }

    if (root) {
      // ok, but triggers warning about stripping root
      entry[field] = String(stripped)
      this.warn(
        'TAR_ENTRY_INFO',
        `stripping ${root} from absolute ${field}`,
        {
          entry,
          [field]: p,
        },
      )
    }
    return true
  }

  // no IO, just string checking for absolute indicators
  [CHECKPATH](entry: ReadEntry) {
    const p = normalizeWindowsPath(entry.path)
    const parts = p.split('/')

    if (this.strip) {
      if (parts.length < this.strip) {
        return false
      }
      if (entry.type === 'Link') {
        const linkparts = normalizeWindowsPath(
          String(entry.linkpath),
        ).split('/')
        if (linkparts.length >= this.strip) {
          entry.linkpath = linkparts.slice(this.strip).join('/')
        } else {
          return false
        }
      }
      parts.splice(0, this.strip)
      entry.path = parts.join('/')
    }

    if (isFinite(this.maxDepth) && parts.length > this.maxDepth) {
      this.warn('TAR_ENTRY_ERROR', 'path excessively deep', {
        entry,
        path: p,
        depth: parts.length,
        maxDepth: this.maxDepth,
      })
      return false
    }

    if (
      !this[STRIPABSOLUTEPATH](entry, 'path') ||
      !this[STRIPABSOLUTEPATH](entry, 'linkpath')
    ) {
      return false
    }

    if (path.isAbsolute(entry.path)) {
      entry.absolute = normalizeWindowsPath(path.resolve(entry.path))
    } else {
      entry.absolute = normalizeWindowsPath(
        path.resolve(this.cwd, entry.path),
      )
    }

    // if we somehow ended up with a path that escapes the cwd, and we are
    // not in preservePaths mode, then something is fishy!  This should have
    // been prevented above, so ignore this for coverage.
    /* c8 ignore start - defense in depth */
    if (
      !this.preservePaths &&
      typeof entry.absolute === 'string' &&
      entry.absolute.indexOf(this.cwd + '/') !== 0 &&
      entry.absolute !== this.cwd
    ) {
      this.warn('TAR_ENTRY_ERROR', 'path escaped extraction target', {
        entry,
        path: normalizeWindowsPath(entry.path),
        resolvedPath: entry.absolute,
        cwd: this.cwd,
      })
      return false
    }
    /* c8 ignore stop */

    // an archive can set properties on the extraction directory, but it
    // may not replace the cwd with a different kind of thing entirely.
    if (
      entry.absolute === this.cwd &&
      entry.type !== 'Directory' &&
      entry.type !== 'GNUDumpDir'
    ) {
      return false
    }

    // only encode : chars that aren't drive letter indicators
    if (this.win32) {
      const { root: aRoot } = path.win32.parse(String(entry.absolute))
      entry.absolute =
        aRoot + wc.encode(String(entry.absolute).slice(aRoot.length))
      const { root: pRoot } = path.win32.parse(entry.path)
      entry.path = pRoot + wc.encode(entry.path.slice(pRoot.length))
    }

    return true
  }
