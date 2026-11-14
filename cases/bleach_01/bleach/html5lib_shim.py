                new_data = ''

            else:
                # If we're escaping the token, we want to escape the exact
                # original string. Since tokenizing also normalizes data
                # and this is a tag-like thing, we've lost some information.
                # So we go back through the stream to get the original
                # string and use that.
                new_data = self.stream.get_tag()

            new_token = {
                'type': CHARACTERS_TYPE,
                'data': new_data
            }

            self.currentToken = new_token
            self.tokenQueue.append(new_token)
            self.state = self.dataState
            return

        super(BleachHTMLTokenizer, self).emitCurrentToken()


class BleachHTMLParser(HTMLParser):
    """Parser that uses BleachHTMLTokenizer"""
    def __init__(self, tags, strip, consume_entities, **kwargs):
        """
        :arg tags: list of allowed tags--everything else is either stripped or
            escaped; if None, then this doesn't look at tags at all
        :arg strip: whether to strip disallowed tags (True) or escape them (False);
            if tags=None, then this doesn't have any effect
        :arg consume_entities: whether to consume entities (default behavior) or
            leave them as is when tokenizing (BleachHTMLTokenizer-added behavior)

        """
        self.tags = [tag.lower() for tag in tags] if tags is not None else None
        self.strip = strip
        self.consume_entities = consume_entities
        super(BleachHTMLParser, self).__init__(**kwargs)

    def _parse(self, stream, innerHTML=False, container='div', scripting=False, **kwargs):
        # Override HTMLParser so we can swap out the tokenizer for our own.
        self.innerHTMLMode = innerHTML
        self.container = container
        self.scripting = scripting
        self.tokenizer = BleachHTMLTokenizer(
            stream=stream,
            consume_entities=self.consume_entities,
            parser=self,
            **kwargs
        )
        self.reset()

        try:
            self.mainLoop()
        except ReparseException:
            self.reset()
            self.mainLoop()


def convert_entity(value):
    """Convert an entity (minus the & and ; part) into what it represents

    This handles numeric, hex, and text entities.

    :arg value: the string (minus the ``&`` and ``;`` part) to convert

    :returns: unicode character or None if it's an ambiguous ampersand that
        doesn't match a character entity

    """
    if value[0] == '#':
        if value[1] in ('x', 'X'):
            return six.unichr(int(value[2:], 16))
        return six.unichr(int(value[1:], 10))

    return ENTITIES.get(value, None)


def convert_entities(text):
    """Converts all found entities in the text
