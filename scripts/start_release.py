"""Служебный запуск сборки; приложение этот скрипт не использует."""

import sys
from upload_project import request
from updates import version_tuple


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Укажите версию: python scripts/start_release.py 1.0.2")
    version = sys.argv[1]
    version_tuple(version)
    repository = request("")
    request("/actions/workflows/release.yml/dispatches", {
        "ref": repository["default_branch"], "inputs": {"version": version.removeprefix("v")}}, "POST")
    print("Сборка запущена: " + version)
