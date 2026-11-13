def parseNestedParens(s, handleLiteral=1):
    """
    Parse an s-exp-like string into a more useful data structure.

    @type s: L{bytes}
    @param s: The s-exp-like string to parse

    @rtype: L{list} of L{bytes} and L{list}
    @return: A list containing the tokens present in the input.

    @raise MismatchedNesting: Raised if the number or placement
    of opening or closing parenthesis is invalid.
    """
    s = s.strip()
    inQuote = 0
    contentStack = [[]]
    try:
        i = 0
        L = len(s)
        while i < L:
            c = s[i : i + 1]
            if inQuote:
                if c == b"\\":
                    contentStack[-1].append(s[i : i + 2])
                    i += 2
                    continue
                elif c == b'"':
                    inQuote = not inQuote
                contentStack[-1].append(c)
                i += 1
            else:
                if c == b'"':
                    contentStack[-1].append(c)
                    inQuote = not inQuote
                    i += 1
                elif handleLiteral and c == b"{":
                    end = s.find(b"}", i)
                    if end == -1:
                        raise ValueError("Malformed literal")
                    literalSize = int(s[i + 1 : end])
                    if literalSize < 0:
                        raise ValueError("Illegal literal size")
                    contentStack[-1].append((s[end + 3 : end + 3 + literalSize],))
                    i = end + 3 + literalSize
                elif c == b"(" or c == b"[":
                    contentStack.append([])
                    i += 1
                elif c == b")" or c == b"]":
                    contentStack[-2].append(contentStack.pop())
                    i += 1
                else:
                    contentStack[-1].append(c)
                    i += 1
    except IndexError:
        raise MismatchedNesting(s)
    if len(contentStack) != 1:
        raise MismatchedNesting(s)
    return collapseStrings(contentStack[0])


def _quote(s):
    qu = _matchingString('"', s)
    esc = _matchingString("\x5c", s)
    return qu + s.replace(esc, esc + esc).replace(qu, esc + qu) + qu


def _literal(s: bytes) -> bytes:
    return b"{%d}\r\n%b" % (len(s), s)


class DontQuoteMe:
    def __init__(self, value):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


_ATOM_SPECIALS = b'(){ %*"'


def _needsQuote(s):
