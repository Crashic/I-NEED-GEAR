"""Обмен через раздельные файлы: SavedVariables только читается."""

import os
from pathlib import Path
import time
from saved_variables import own_data

IMPORT_FILENAME = "FriendsData.lua"


def lua_quote(value):
    return '"' + ''.join(
        '\\' + format(ord(char), '03d') if ord(char) < 32 else
        '\\' + char if char in ('"', '\\') else char for char in value
    ) + '"'


def read_snapshot(path):
    path = Path(path)
    for attempt in range(3):
        try:
            before = path.stat()
            if before.st_size > 4 * 1024 * 1024:
                raise ValueError("Файл персонажей слишком большой.")
            with path.open("r", encoding="utf-8") as source:
                text = source.read(4 * 1024 * 1024 + 1)
            after = path.stat()
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                raise ValueError("Игра ещё записывает файл.")
            return own_data(text)
        except (ValueError, OSError, UnicodeError):
            if attempt == 2:
                raise ValueError("Не удалось прочитать данные. Сохраните снаряжение кнопкой аддона и повторите синхронизацию.") from None
            time.sleep(0.1)


def write_imports(addon_folder, imports):
    if len(imports) > 500:
        raise ValueError("Слишком много персонажей для одного импорта.")
    lines = ["-- Данные друзей. Создаются приложением; игра этот файл не сохраняет.\n", "INEEDGEAR_IMPORTED = {\n"]
    total = 0
    for name, data in sorted(imports.items()):
        if not isinstance(name, str) or not isinstance(data, str) or not name or len(name) > 160:
            raise ValueError("Недопустимые данные персонажа.")
        size = len(data.encode("utf-8"))
        total += size
        if size > 256 * 1024 or total > 4 * 1024 * 1024:
            raise ValueError("Данные персонажей превышают допустимый размер.")
        lines.append(f"    [{lua_quote(name)}] = {lua_quote(data)},\n")
    lines.append("}\n")
    target = Path(addon_folder) / IMPORT_FILENAME
    temporary = target.with_suffix(".lua.tmp")
    temporary.write_text(''.join(lines), encoding="utf-8")
    os.replace(temporary, target)
    return target
