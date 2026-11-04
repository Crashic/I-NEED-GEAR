"""Загрузка файлов с временным токеном GitHub Actions; токен не входит в сборку."""

import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from updates import version_tuple


def request(url, data=None, method="GET", binary=False):
    headers = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
               "User-Agent": "INEEDGEAR", "Accept": "application/vnd.github+json",
               "Content-Type": "application/octet-stream" if binary else "application/json"}
    body = data if binary else json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, method=method, headers=headers), timeout=120) as response:
        return json.load(response) if response.status != 204 else None


def publish():
    folder = ROOT / "release"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    version_tuple(version)
    api = "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"]
    try:
        latest = request(api + "/releases/latest")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    else:
        if version_tuple(version) <= version_tuple(latest["tag_name"]):
            raise ValueError("Новая версия должна быть выше последнего опубликованного релиза.")
    tag = "v" + version
    try:
        release = request(api + "/releases", {
            "tag_name": tag, "target_commitish": os.environ["RELEASE_COMMIT"],
            "name": "I NEED GEAR " + version, "draft": True, "prerelease": False,
            "body": "Программа для всех: INEEDGEAR.exe. Аддон: INEEDGEAR-addon.zip."}, "POST")
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            raise
        # Незавершённый черновик можно повторно заполнить, опубликованный релиз не изменяем.
        drafts = request(api + "/releases?per_page=100")
        release = next((item for item in drafts if item["tag_name"] == tag and item["draft"]), None)
        if release is None:
            raise RuntimeError("Релиз уже существует или версия недопустима.") from exc
        for asset in release.get("assets", []):
            request(asset["url"], method="DELETE")
    for name in [*manifest["files"], "manifest.json"]:
        url = release["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(name)
        result = request(url, (folder / name).read_bytes(), "POST", binary=True)
        if result["size"] != (folder / name).stat().st_size:
            raise RuntimeError("Размер загруженного файла не совпал: " + name)
    request(release["url"], {"draft": False, "make_latest": "true"}, "PATCH")
    print("Релиз опубликован: " + tag)


if __name__ == "__main__":
    publish()

