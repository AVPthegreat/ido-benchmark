    if (byteLen + digits >= Math.pow(10, digits)) {
      digits += 1
    }
    const len = digits + byteLen
    return len + s
  }

  static parse(str: string, ex?: HeaderData, g: boolean = false) {
    return new Pax(merge(parseKV(str), ex), g)
  }
}

const merge = (a: HeaderData, b?: HeaderData) =>
  b ? Object.assign({}, b, a) : a

const parseKV = (str: string) =>
  str
    .replace(/\n$/, '')
    .split('\n')
    .reduce(parseKVLine, Object.create(null))

const parseKVLine = (set: Record<string, unknown>, line: string) => {
  const n = parseInt(line, 10)

  // XXX Values with \n in them will fail this.
  // Refactor to not be a naive line-by-line parse.
  if (n !== Buffer.byteLength(line) + 1) {
    return set
  }

  line = line.slice((n + ' ').length)
  const kv = line.split('=')
  const r = kv.shift()

  if (!r) {
    return set
  }

  const k = r.replace(/^SCHILY\.(dev|ino|nlink)/, '$1')

  const v = kv.join('=').replace(/\0.*/, '')
  set[k] =
    /^([A-Z]+\.)?([mac]|birth|creation)time$/.test(k) ?
      new Date(Number(v) * 1000)
    : /^[0-9]+$/.test(v) ? +v
    : v
  return set
}
