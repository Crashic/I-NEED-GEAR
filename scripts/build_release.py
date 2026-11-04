"""Сборка выполняется на Windows внутри GitHub Actions."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from updates import version_tuple


def build():
    os.chdir(ROOT)
    version = os.environ["RELEASE_VERSION"]
    version_tuple(version)
    version = version.removeprefix("v")
    Path("version.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
    toc = Path("addon/INEEDGEAR/INEEDGEAR.toc")
    toc.write_text(re.sub(r"(?m)^## Version:.*$", "## Version: " + version,
                          toc.read_text(encoding="utf-8")), encoding="utf-8")
    output = Path("release")
    output.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
               "--name", "INEEDGEAR", "--icon", "assets/icon.ico",
               "--add-data", "addon;addon", "--add-data", "assets;assets", "main.py"]
    subprocess.run(command, check=True)
    shutil.copy2(Path("dist/INEEDGEAR.exe"), output / "INEEDGEAR.exe")
    with zipfile.ZipFile(output / "INEEDGEAR-addon.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(Path("addon/INEEDGEAR").rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to("addon").as_posix())
    files = {}
    for name in ("INEEDGEAR.exe", "INEEDGEAR-addon.zip"):
        file = output / name
        files[name] = {"size": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(
        {"schema": 1, "version": version, "files": files}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Сборка и манифест подготовлены.")


if __name__ == "__main__":
    build()

