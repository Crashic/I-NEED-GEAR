"""Проверки границ загрузки, архивов и восстановления после ошибки."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

import updates


class UpdateTests(unittest.TestCase):
    def test_versions(self):
        self.assertGreater(updates.version_tuple("v1.10.0"), updates.version_tuple("1.9.9"))
        for value in ("1.0", "1.2.3; команда", "01.2.3", None):
            with self.assertRaises(ValueError):
                updates.version_tuple(value)

    def test_no_releases(self):
        with patch("updates.read_json", side_effect=urllib.error.HTTPError("", 404, "", {}, None)):
            self.assertIsNone(updates.latest_release("1.0.0"))

    def test_only_new_stable_release(self):
        for tag, expected in (("v1.0.0", False), ("v0.9.0", False), ("v1.0.1", True)):
            with patch("updates.read_json", return_value={"tag_name": tag}):
                self.assertEqual(bool(updates.latest_release("1.0.0")), expected)

    def test_asset_must_belong_to_repository(self):
        with self.assertRaises(ValueError):
            updates.asset_url({"assets": [{"name": "x", "browser_download_url": "https://example.org/x"}]}, "x")

    def test_download_hash_and_size(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "file"
            data = b"payload"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(data)) as request:
                updates.download("https://example.org", target, len(data), hashlib.sha256(data).hexdigest())
                self.assertNotIn("Authorization", request.call_args.args[0].headers)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):
                    updates.download("https://example.org", target, len(data), "0" * 64)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):
                    updates.download("https://example.org", target, len(data) - 1, "0" * 64)

    def test_archive_paths(self):
        for unsafe in ("../escape.lua", "INEEDGEAR/../../escape.lua", "INEEDGEAR\\escape.lua", "INEEDGEAR/file:stream"):
            with tempfile.TemporaryDirectory() as folder:
                archive = Path(folder) / "addon.zip"
                with zipfile.ZipFile(archive, "w") as package:
                    package.writestr(unsafe, "данные")
                with self.assertRaises(ValueError):
                    updates.extract_addon(archive, Path(folder) / "out")

    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "addon.zip"
            with zipfile.ZipFile(archive, "w") as package:
                for name in ("INEEDGEAR.lua", "INEEDGEAR.toc"):
                    package.writestr("INEEDGEAR/" + name, "данные")
            self.assertTrue((updates.extract_addon(archive, Path(folder) / "out") / "INEEDGEAR.lua").exists())

    def test_install_and_rollback(self):
        for fail in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target, source = root / "app.exe", root / "new.exe"
                target.write_bytes(b"old")
                source.write_bytes(b"new")
                addon, new_addon = root / "INEEDGEAR", root / "new-addon"
                addon.mkdir()
                new_addon.mkdir()
                (addon / "data.lua").write_text("старый")
                (new_addon / "data.lua").write_text("новый")
                plan = {"target": str(target), "source": str(source), "addon_target": str(addon),
                        "addon_source": str(new_addon), "sha256": hashlib.sha256(b"new").hexdigest()}
                with patch("updates.subprocess.Popen", side_effect=OSError("Ошибка запуска") if fail else None):
                    if fail:
                        with self.assertRaises(OSError):
                            updates.install_transaction(plan)
                    else:
                        updates.install_transaction(plan)
                self.assertEqual(target.read_bytes(), b"old" if fail else b"new")
                self.assertEqual((addon / "data.lua").read_text(), "старый" if fail else "новый")

    def test_manifest_selects_dev_asset(self):
        release = {"tag_name": "v1.0.1", "assets": [
            {"name": name, "browser_download_url": f"https://github.com/{updates.REPOSITORY}/releases/download/v1.0.1/{name}"}
            for name in ("manifest.json", "INEEDGEAR-DEV.exe", "INEEDGEAR-addon.zip")]}
        manifest = {"schema": 1, "version": "1.0.1", "files": {
            name: {"size": 1, "sha256": "0" * 64} for name in ("INEEDGEAR-DEV.exe", "INEEDGEAR-addon.zip")}}
        with tempfile.TemporaryDirectory() as folder, patch("updates.read_json", return_value=manifest), \
                patch("updates.download") as download, patch("updates.extract_addon"):
            plan = updates.prepare_update(release, folder, True, lambda message: None)
            try:
                self.assertTrue(download.call_args_list[0].args[0].endswith("INEEDGEAR-DEV.exe"))
                self.assertTrue(json.loads(plan.read_text(encoding="utf-8"))["source"].endswith("INEEDGEAR-DEV.exe"))
            finally:
                import shutil
                shutil.rmtree(plan.parent)


if __name__ == "__main__":
    unittest.main()
