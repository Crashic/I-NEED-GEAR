"""Первичная загрузка исходников через API с локальным токеном, без его печати."""

import json
import base64
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from updates import API


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
        raise RuntimeError("Не настроен локальный токен для обслуживания репозитория.")
    return token


def request(path, payload=None, method="GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    query = urllib.request.Request(API + path, data=data, method=method, headers={
        "User-Agent": "INEEDGEAR", "Authorization": "Bearer " + local_token(),
        "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(query, timeout=60) as response:
            return json.load(response) if response.status != 204 else None
    except urllib.error.HTTPError as exc:
        # Не выводим заголовки запросов и значения переменных среды.
        raise RuntimeError(f"GitHub отклонил операцию {method} {path}: HTTP {exc.code}") from None


def upload():
    repository = request("")
    branch = repository["default_branch"]
    head = request("/git/ref/heads/" + branch)["object"]["sha"]
    commit = request("/git/commits/" + head)
    paths = [Path(name) for name in (
        ".gitignore", "README.md", "requirements.txt", "version.py", "main.py",
        "updates.py", "theme.py", "saved_variables.py", ".github/workflows/release.yml")]
    for directory in ("addon", "assets", "scripts", "tests"):
        paths.extend(file.relative_to(ROOT) for file in (ROOT / directory).rglob("*")
                     if file.is_file() and "__pycache__" not in file.parts)
    entries = []
    # Пути явно удаляемых файлов передаются аргументами при обслуживании репозитория.
    removed = sys.argv[1:]
    remote_tree = request("/git/trees/" + commit["tree"]["sha"] + "?recursive=1")
    existing = {entry["path"] for entry in remote_tree["tree"]}
    for name in removed:
        if name in existing:
            entries.append({"path": name, "mode": "100644", "type": "blob", "sha": None})
    for path in sorted(set(paths)):
        if path.suffix.lower() in (".png", ".ico", ".tga"):
            blob = request("/git/blobs", {"encoding": "base64", "content": base64.b64encode((ROOT / path).read_bytes()).decode("ascii")}, "POST")
            entries.append({"path": path.as_posix(), "mode": "100644", "type": "blob", "sha": blob["sha"]})
            continue
        content = (ROOT / path).read_text(encoding="utf-8")
        # Секреты запрещено загружать даже при случайном добавлении в исходник.
        import re
        if re.search(r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}", content):
            raise RuntimeError("В файле обнаружен токен: " + str(path))
        entries.append({"path": path.as_posix(), "mode": "100644", "type": "blob", "content": content})
    tree = request("/git/trees", {"base_tree": commit["tree"]["sha"], "tree": entries}, "POST")
    created = request("/git/commits", {"message": "Игровое оформление приложения и аддона, иконка ING",
                      "tree": tree["sha"], "parents": [head]}, "POST")
    if request("/git/ref/heads/" + branch)["object"]["sha"] != head:
        raise RuntimeError("Ветка изменилась во время загрузки. Повторите после проверки изменений.")
    request("/git/refs/heads/" + branch, {"sha": created["sha"], "force": False}, "PATCH")
    print("Исходники загружены. Коммит: " + created["sha"])


if __name__ == "__main__":
    upload()
