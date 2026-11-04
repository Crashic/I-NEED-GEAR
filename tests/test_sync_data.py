"""Синхронизация не должна записывать в файл, которым управляет игра."""

import ast
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from saved_variables import player_key
from sync_data import read_snapshot, write_imports, lua_quote, IMPORT_FILENAME


class SyncTests(unittest.TestCase):
    def test_separate_import_preserves_game_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = root / "AddOns" / "INEEDGEAR"
            addon.mkdir(parents=True)
            (addon / "INEEDGEAR.toc").write_text("FriendsData.lua\nINEEDGEAR.lua\n", encoding="utf-8")
            source = root / "INEEDGEARDB.lua"
            original = b'INEEDGEARDB = { ["characters"] = { ["Player-Realm"] = { ["equipped"] = {} } }, ["imported"] = { ["Old"] = "old" } }'
            source.write_bytes(original)
            uploaded = []
            class Table:
                def upsert(self, row):
                    uploaded.append(row)
                    return SimpleNamespace(execute=lambda: None)
                def select(self, columns):
                    return SimpleNamespace(execute=lambda: SimpleNamespace(data=[
                        {"player_key": 'Friend"; MARK=true; --', "equipped": '"; MARK=true; --\n'}]))
            module = ast.parse(Path("main.py").read_text(encoding="utf-8"))
            function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "do_update")
            namespace = dict(os=os, Path=Path, datetime=datetime, timezone=timezone,
                             SUPABASE_URL="", SUPABASE_KEY="", IMPORT_FILENAME=IMPORT_FILENAME,
                             read_snapshot=read_snapshot, write_imports=write_imports,
                             extract_player_key=player_key,
                             create_client=lambda *args: SimpleNamespace(table=lambda name: Table()))
            exec(compile(ast.Module(body=[function], type_ignores=[]), "синхронизация", "exec"), namespace)
            messages = []
            namespace["do_update"]({"local_folder": str(root), "local_filename": source.name,
                                     "addons_folder": str(root / "AddOns"), "player_key": ""}, messages.append)
            self.assertEqual(source.read_bytes(), original)
            self.assertNotIn('"imported"', uploaded[0]["equipped"])
            imported = (addon / IMPORT_FILENAME).read_text(encoding="utf-8")
            self.assertIn('INEEDGEAR_IMPORTED = {', imported)
            self.assertIn(lua_quote('Friend"; MARK=true; --'), imported)
            self.assertIn(lua_quote('"; MARK=true; --\n'), imported)

    def test_empty_sync_clears_old_import(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_imports(folder, {"Друг": "предмет"})
            write_imports(folder, {})
            self.assertNotIn("Друг", path.read_text(encoding="utf-8"))

    def test_import_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                write_imports(folder, {"Друг": "a" * (256 * 1024 + 1)})
            self.assertFalse((Path(folder) / IMPORT_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()
