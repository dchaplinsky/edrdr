import phonenumbers


def truncate_phone(phone):
    return (
        phone.strip()
        .replace("(", "")
        .replace(")", "")
        .replace("-", "")
        .replace(" ", "")
    )


def format_phone(phone):
    try:
        parsed = phonenumbers.parse(phone, "UA")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return truncate_phone(phone)


def phone_variants(phone):
    def delim(phone, divider):
        if len(phone) == 7:
            return divider.join([phone[:3], phone[3:5], phone[5:]])
        elif len(phone) == 6:
            return divider.join([phone[:2], phone[2:4], phone[4:]])
        else:
            return phone

    if not phone:
        return set()

    res = set([phone.strip()])

    stripped_phone = truncate_phone(phone)

    res.add(stripped_phone)
    default = None

    try:
        parsed = phonenumbers.parse(phone, "UA")

        for fmt in [
            phonenumbers.PhoneNumberFormat.NATIONAL,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL,
            phonenumbers.PhoneNumberFormat.E164,
        ]:
            formatted = phonenumbers.format_number(parsed, fmt)
            if fmt == phonenumbers.PhoneNumberFormat.E164:
                default = formatted
            res.add(formatted)
    except phonenumbers.NumberParseException:
        pass

    if default:
        res.add(default.replace("+", ""))
        res.add(default.replace("+3", ""))
        res.add(default.replace("+38", ""))
        no_code = default.replace("+38", "")
        res.add("({}) {}".format(no_code[:3], no_code[3:]))
        res.add("({}) {}".format(no_code[:3], delim(no_code[3:], "-")))
        res.add("({}) {}".format(no_code[:3], delim(no_code[3:], " ")))
        res.add("+38 ({}) {}".format(no_code[:3], no_code[3:]))
        res.add("+38 ({}) {}".format(no_code[:3], delim(no_code[3:], "-")))
        res.add("+38 ({}) {}".format(no_code[:3], delim(no_code[3:], "")))

    return set(filter(None, res))
