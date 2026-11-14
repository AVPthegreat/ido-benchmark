        return component

    component = to_str(component)

    # Fast path: an ASCII component that consists only of allowed characters
    # and contains no '%' needs neither encoding nor percent-normalization.
    # Components containing '%' always take the general path below because
    # how '%' is treated depends on whether the whole component is already
    # percent-encoded.
    if (
        "%" not in component
        and component.isascii()
        and all(map(allowed_chars.__contains__, component))
    ):
        return component

    # Normalize existing percent-encoded bytes.
    # Try to see if the component we're encoding is already percent-encoded
    # so we can skip all '%' characters but still encode all others.
    component, percent_encodings = _PERCENT_RE.subn(
        lambda match: match.group(0).upper(), component
    )

    uri_bytes = component.encode("utf-8", "surrogatepass")
    is_percent_encoded = percent_encodings == uri_bytes.count(b"%")
    encoded_component = bytearray()

    # Iterating over bytes yields integers; 0x25 is '%'.
    for byte_ord in uri_bytes:
        if (is_percent_encoded and byte_ord == 0x25) or (
            byte_ord < 128 and chr(byte_ord) in allowed_chars
        ):
            encoded_component.append(byte_ord)
        else:
            encoded_component += b"%%%02X" % byte_ord

    return encoded_component.decode()


def _remove_path_dot_segments(path: str) -> str:
    # Fast path: without a '.' or '..' segment there is nothing to remove.
    if "/." not in path and not path.startswith("."):
        return path

    # See http://tools.ietf.org/html/rfc3986#section-5.2.4 for pseudo-code
    segments = path.split("/")  # Turn the path into a list of segments
    output = []  # Initialize the variable to use to store output

    for segment in segments:
        # '.' is the current directory, so ignore it, it is superfluous
        if segment == ".":
            continue
        # Anything other than '..', should be appended to the output
        if segment != "..":
            output.append(segment)
        # In this case segment == '..', if we can, we should pop the last
        # element
        elif output:
            output.pop()

    # If the path starts with '/' and the output is empty or the first string
    # is non-empty
    if path.startswith("/") and (not output or output[0]):
        output.insert(0, "")

    # If the path starts with '/.' or '/..' ensure we add one more empty
    # string to add a trailing '/'
    if path.endswith(("/.", "/..")):
        output.append("")

    return "/".join(output)


@typing.overload
def _normalize_host(host: None, scheme: str | None) -> None: ...


@typing.overload
def _normalize_host(host: str, scheme: str | None) -> str: ...


def _normalize_host(host: str | None, scheme: str | None) -> str | None:
    if host:
        invalid_host_char = _HOST_INVALID_CHAR_RE.search(host)
        if invalid_host_char:
            raise LocationParseError(
                f"Host {host!r} contains invalid character "
                f"{invalid_host_char.group()!r}"
            )
        if scheme in _NORMALIZABLE_SCHEMES:
            is_ipv6 = _IPV6_ADDRZ_RE.match(host)
            if is_ipv6:
                # IPv6 hosts of the form 'a::b%zone' are encoded in a URL as
                # such per RFC 6874: 'a::b%25zone'. Unquote the ZoneID
                # separator as necessary to return a valid RFC 4007 scoped IP.
                match = _ZONE_ID_RE.search(host)
                if match:
                    start, end = match.span(1)
                    zone_id = host[start:end]

                    if zone_id.startswith("%25") and zone_id != "%25":
                        zone_id = zone_id[3:]
                    else:
                        zone_id = zone_id[1:]
                    zone_id = _PERCENT_RE.sub(
                        partial(_normalize_zone_id_percent_encoding, error_host=host),
                        zone_id,
                    )
                    zone_id = _encode_invalid_chars(zone_id, _UNRESERVED_CHARS)
                    return f"{host[:start].lower()}%{zone_id}{host[end:]}"
                else:
                    return host.lower()
            elif not _IPV4_RE.match(host):
                # Fast path: for an ASCII host without percent-encoding,
                # IDNA-encoding each label reduces to lower-casing it.
                if "%" not in host and host.isascii():
                    return host.lower()
                if "%" in host:
                    address, separator, zone = host.partition("%")
                    if ":" in address and host.isascii() and _IPV6_RE.match(address):
                        # Native IPv6 zone names may be case-sensitive.
                        return f"{address.lower()}{separator}{zone}"
                    host = _HOST_PERCENT_RE.sub(_normalize_host_percent_encoding, host)
                return to_str(
                    b".".join([_idna_encode(label) for label in host.split(".")]),
                    "ascii",
                )
    return host


def _decode_percent_encoding(match: re.Match[str], *, error_host: str) -> str:
    percent_encoded_octet = match.group(0)
    decoded_octet = chr(int(percent_encoded_octet[1:], 16))
    # Keep this narrower than _HOST_INVALID_CHAR_RE because "%20" is valid
    # percent-encoding and remains encoded.
    if decoded_octet < "\x20" or decoded_octet == "\x7f":
        raise LocationParseError(
            f"Host {error_host!r} contains invalid percent-encoded "
            f"control character {percent_encoded_octet!r}"
        )
    return decoded_octet


def _normalize_host_percent_encoding(match: re.Match[str]) -> str:
    # Reject invalid percent encodings
    if match.group(0) == "%":
        raise LocationParseError(f"{match.string!r} is not a valid host")
    decoded_octet = _decode_percent_encoding(match, error_host=match.string)
    if decoded_octet in _UNRESERVED_CHARS:
        return decoded_octet
    return match.group(0).upper()


def _normalize_zone_id_percent_encoding(
    match: re.Match[str], *, error_host: str
) -> str:
    _decode_percent_encoding(match, error_host=error_host)
