"""Проверка импорта зависимостей и создания окна в собранных приложениях."""

from pathlib import Path
import subprocess
import tempfile
from PyInstaller.archive.readers import CArchiveReader


for name in ("INEEDGEAR.exe", "INEEDGEAR-DEV.exe"):
    archive = CArchiveReader(str(Path("release", name)))
    modules = archive.open_embedded_archive("PYZ.pyz").toc
    if ("developer" in modules) != (name == "INEEDGEAR-DEV.exe"):
        raise RuntimeError("Неверный состав модулей в сборке: " + name)
    with tempfile.TemporaryDirectory() as folder:
        marker = Path(folder) / "успех.txt"
        process = subprocess.run([str(Path("release", name).resolve()), "--smoke-test", str(marker)], timeout=90)
        if process.returncode != 0 or not marker.is_file():
            raise RuntimeError("Не удалось запустить собранное приложение: " + name)
        print("Запуск проверен: " + name)

