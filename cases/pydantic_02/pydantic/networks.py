        yield cls.validate

    @classmethod
    def validate(cls, value: NetworkType) -> Union[IPv4Interface, IPv6Interface]:
        try:
            return IPv4Interface(value)
        except ValueError:
            pass

        try:
            return IPv6Interface(value)
        except ValueError:
            raise errors.IPvAnyInterfaceError()


class IPvAnyNetwork(_BaseNetwork):  # type: ignore
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(type='string', format='ipvanynetwork')

    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, value: NetworkType) -> Union[IPv4Network, IPv6Network]:
        # Assume IP Network is defined with a default value for ``strict`` argument.
        # Define your own class if you want to specify network address check strictness.
        try:
            return IPv4Network(value)
        except ValueError:
            pass

        try:
            return IPv6Network(value)
        except ValueError:
            raise errors.IPvAnyNetworkError()


pretty_email_regex = re.compile(r'([\w ]*?) *<(.*)> *')


def validate_email(value: Union[str]) -> Tuple[str, str]:
    """
    Email address validation using https://pypi.org/project/email-validator/
    Notes:
    * raw ip address (literal) domain parts are not allowed.
    * "John Doe <local_part@domain.com>" style "pretty" email addresses are processed
    * spaces are striped from the beginning and end of addresses but no error is raised
    """
    if email_validator is None:
        import_email_validator()
    m = pretty_email_regex.fullmatch(value)
    name: Union[str, None] = None
    if m:
        name, value = m.groups()
    email = value.strip()
    try:
        parts = email_validator.validate_email(email, check_deliverability=False)
    except email_validator.EmailNotValidError as e:
        raise errors.EmailError from e

    if hasattr(parts, 'normalized'):
        # email-validator >= 2
        email = parts.normalized
        assert email is not None
        name = name or parts.local_part
        return name, email
    else:
        # email-validator >1, <2
        at_index = email.index('@')
        local_part = email[:at_index]  # RFC 5321, local part must be case-sensitive.
        global_part = email[at_index:].lower()

        return name or local_part, local_part + global_part
