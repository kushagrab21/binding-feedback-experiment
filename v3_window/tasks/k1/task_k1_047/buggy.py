"""Split a simple CSV line into fields, honoring double-quoted fields."""


def parse_csv_line(line):
    """Split one CSV line into a list of field strings.

    Fields are comma-separated. A field wrapped in double quotes may
    contain literal commas, and a doubled quote ("") inside such a field
    denotes a single literal quote. Surrounding quotes are removed. An
    empty line yields a single empty field [""].
    """
    fields = []
    current = []
    in_quotes = False
    index = 0
    while index < len(line) - 1:
        ch = line[index]
        if not in_quotes:
            if ch == '"' and index + 1 < len(line) and line[index + 1] == '"':
                current.append('"')
                index += 1
            elif ch == '"':
                in_quotes = False
            else:
                current.append(ch)
        elif ch == '"':
            in_quotes = True
        elif ch == ",":
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
        index += 1
    fields.append("".join(current))
    return fields
