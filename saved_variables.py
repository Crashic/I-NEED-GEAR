"""Чтение отдельных таблиц SavedVariables без исполнения Lua-кода."""

import re


def tokens(text, start):
    position = start
    while position < len(text):
        begin = position
        char = text[position]
        if char.isspace():
            position += 1
            continue
        if text.startswith("--", position):
            position = text.find("\n", position)
            if position == -1:
                return
            continue
        if char in ('"', "'"):
            position += 1
            while position < len(text):
                if text[position] == "\\":
                    position += 2
                elif text[position] == char:
                    position += 1
                    break
                else:
                    position += 1
            else:
                raise ValueError("Незавершённая строка в SavedVariables.")
        elif char.isalnum() or char == "_":
            position += 1
            while position < len(text) and (text[position].isalnum() or text[position] == "_"):
                position += 1
        else:
            position += 1
        yield text[begin:position], begin, position


def characters_table(text):
    assignment = re.search(r"\bINEEDGEARDB\s*=\s*\{", text)
    if not assignment:
        raise ValueError("В файле не найдена таблица INEEDGEARDB.")
    depth = 1
    recent = []
    found = None
    for token, start, end in tokens(text, assignment.end()):
        if token == "{" and depth == 1 and recent[-4:] in (
                ["[", '"characters"', "]", "="], ["[", "'characters'", "]", "="]):
            found = start
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if found is not None and depth == 1:
                return text[found:end]
            if depth == 0:
                break
        recent.append(token)
        recent = recent[-4:]
    raise ValueError("В файле не найдена полная таблица персонажей.")


def own_data(text):
    return 'INEEDGEARDB = {\n["characters"] = ' + characters_table(text) + ',\n}\n'


def player_key(text):
    table = characters_table(text)
    match = re.match(r'\{\s*\["([^"\\]+)"\]\s*=\s*\{', table)
    return match.group(1) if match else None

