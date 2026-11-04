"""Запуск сборки GitHub Actions. Модуль исключён из пользовательской сборки."""

import json
import os
import urllib.request
import webbrowser

from updates import API, REPOSITORY, read_json, version_tuple


def local_token():
    token = os.environ.get("INEEDGEAR_GITHUB_TOKEN", "").strip()
    if not token and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                token = winreg.QueryValueEx(key, "INEEDGEAR_GITHUB_TOKEN")[0].strip()
        except FileNotFoundError:
            pass
    if not token:
        raise RuntimeError("Сохраните токен в переменной пользователя INEEDGEAR_GITHUB_TOKEN.")
    return token


def publish_release(version, log):
    version_tuple(version)
    version = version.removeprefix("v")
    repository = read_json(API)
    request = urllib.request.Request(
        API + "/actions/workflows/release.yml/dispatches",
        data=json.dumps({"ref": repository["default_branch"], "inputs": {"version": version}}).encode(),
        headers={"Authorization": "Bearer " + local_token(), "Accept": "application/vnd.github+json",
                 "User-Agent": "INEEDGEAR", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30):
        pass
    log(f"GitHub принял запрос сборки версии {version}. Это ещё не означает завершение публикации.")
    log("Статус сборки доступен на вкладке Actions репозитория.")
    webbrowser.open(f"https://github.com/{REPOSITORY}/actions/workflows/release.yml")

