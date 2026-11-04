"""Первичная загрузка исходников через API с локальным токеном, без его печати."""

import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from developer import local_token
from updates import API


def request(path, payload=None, method="GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    query = urllib.request.Request(API + path, data=data, method=method, headers={
        "User-Agent": "INEEDGEAR", "Authorization": "Bearer " + local_token(),
        "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(query, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Не выводим заголовки запросов и значения переменных среды.
        raise RuntimeError(f"GitHub отклонил операцию {method} {path}: HTTP {exc.code}") from None


def upload():
    repository = request("")
    branch = repository["default_branch"]
    head = request("/git/ref/heads/" + branch)["object"]["sha"]
    commit = request("/git/commits/" + head)
    paths = [Path(name) for name in (
        ".gitignore", "README.md", "requirements.txt", "version.py", "main.py", "main_dev.py",
        "developer.py", "updates.py", ".github/workflows/release.yml")]
    for directory in ("addon", "scripts", "tests"):
        paths.extend(file.relative_to(ROOT) for file in (ROOT / directory).rglob("*")
                     if file.is_file() and "__pycache__" not in file.parts)
    entries = []
    for path in sorted(set(paths)):
        content = (ROOT / path).read_text(encoding="utf-8")
        # Секреты запрещено загружать даже при случайном добавлении в исходник.
        import re
        if re.search(r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}", content):
            raise RuntimeError("В файле обнаружен токен: " + str(path))
        entries.append({"path": path.as_posix(), "mode": "100644", "type": "blob", "content": content})
    tree = request("/git/trees", {"base_tree": commit["tree"]["sha"], "tree": entries}, "POST")
    created = request("/git/commits", {"message": "Обновления приложения и аддона через GitHub Releases",
                      "tree": tree["sha"], "parents": [head]}, "POST")
    if request("/git/ref/heads/" + branch)["object"]["sha"] != head:
        raise RuntimeError("Ветка изменилась во время загрузки. Повторите после проверки изменений.")
    request("/git/refs/heads/" + branch, {"sha": created["sha"], "force": False}, "PATCH")
    print("Исходники загружены. Коммит: " + created["sha"])


if __name__ == "__main__":
    upload()
