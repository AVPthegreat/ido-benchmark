    return links


@register.filter
def add_nested_class(value):
    if isinstance(value, dict):
        return 'class=nested'
    if isinstance(value, list) and any(isinstance(item, (list, dict)) for item in value):
        return 'class=nested'
    return ''


# Bunch of stuff cloned from urlize
TRAILING_PUNCTUATION = ['.', ',', ':', ';', '.)', '"', "']", "'}", "'"]
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>'), ('[', ']'), ('&lt;', '&gt;'),
                        ('"', '"'), ("'", "'")]
word_split_re = re.compile(r'(\s+)')
simple_url_re = re.compile(r'^https?://\[?\w', re.IGNORECASE)
simple_url_2_re = re.compile(r'^www\.|^(?!http)\w[^@]+\.(com|edu|gov|int|mil|net|org)$', re.IGNORECASE)
simple_email_re = re.compile(r'^\S+@\S+\.\S+$')


def smart_urlquote_wrapper(matched_url):
    """
    Simple wrapper for smart_urlquote. ValueError("Invalid IPv6 URL") can
    be raised here, see issue #1386
    """
    try:
        return smart_urlquote(matched_url)
    except ValueError:
        return None


@register.filter
def break_long_headers(header):
    """
    Breaks headers longer than 160 characters (~page length)
    when possible (are comma separated)
    """
    if len(header) > 160 and ',' in header:
        header = mark_safe('<br> ' + ', <br>'.join(escape(header).split(',')))
    return header
