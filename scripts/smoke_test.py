"""Проверка импорта зависимостей и создания окна в собранных приложениях."""

from pathlib import Path
import subprocess
import tempfile


for name in ("INEEDGEAR.exe",):
    with tempfile.TemporaryDirectory() as folder:
        marker = Path(folder) / "успех.txt"
        process = subprocess.run([str(Path("release", name).resolve()), "--smoke-test", str(marker)], timeout=90)
        if process.returncode != 0 or not marker.is_file():
            raise RuntimeError("Не удалось запустить собранное приложение: " + name)
        print("Запуск проверен: " + name)

