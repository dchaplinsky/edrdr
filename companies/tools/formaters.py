def curformat(value):
    value = str(value)
    if value and value != "0":
        currency = ""
        if "$" in value:
            value = value.replace("$", "")
            currency = "USD "

        if "£" in value:
            value = value.replace("£", "")
            currency = "GBP "

        if "€" in value or "Є" in value:
            value = value.replace("€", "").replace("Є", "")
            currency = "EUR "

        try:
            return '{}{:,.0f}'.format(
                currency,
                float(value.replace(',', '.'))).replace(
                    ',', ' ').replace('.', ',')
        except ValueError:
            return value
    else:
        return ""


def ukr_plural(value, *args):
    value = int(value) % 100
    rem = value % 10
    if value > 4 and value < 20:
        return args[2]
    elif rem == 1:
        return args[0]
    elif rem > 1 and rem < 5:
        return args[1]
    else:
        return args[2]
