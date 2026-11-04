"""Анонимная загрузка релизов и замена приложения после его закрытия."""

import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

REPOSITORY = "Crashic/I-NEED-GEAR"
API = f"https://api.github.com/repos/{REPOSITORY}"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
LATEST_MANIFEST_URL = RELEASES_URL + "/latest/download/manifest.json"
MAX_DOWNLOAD = 300 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError("Неверная версия: требуется формат 1.2.3.")
    return tuple(map(int, value.removeprefix("v").split(".")))


def read_json(url):
    # Здесь намеренно нет заголовка авторизации, даже в версии разработчика.
    request = urllib.request.Request(url, headers={"User-Agent": "INEEDGEAR", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Ответ сервера слишком большой.")
    return json.loads(data)


def latest_release(current):
    try:
        # Публичный файл релиза не расходует лимит анонимного REST API.
        manifest = read_json(LATEST_MANIFEST_URL)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (403, 429):
            raise RuntimeError("GitHub временно ограничил скачивание. Попробуйте позднее.") from exc
        raise
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValueError("Неизвестный формат манифеста обновлений.")
    version = manifest.get("version")
    if version_tuple(version) <= version_tuple(current):
        return None
    tag = "v" + version.removeprefix("v")
    names = ("INEEDGEAR.exe", "INEEDGEAR-DEV.exe", "INEEDGEAR-addon.zip")
    if not isinstance(manifest.get("files"), dict) or any(name not in manifest["files"] for name in names):
        raise ValueError("В манифесте отсутствуют файлы обновления.")
    # После определения версии все загрузки привязаны к одному релизу.
    # Если latest изменится во время установки, файлы разных версий не смешаются.
    base = RELEASES_URL + "/download/" + tag + "/"
    return {"tag_name": tag, "assets": [
        {"name": name, "browser_download_url": base + name}
        for name in (*names, "manifest.json")
    ]}


def asset_url(release, name):
    matches = [asset for asset in release.get("assets", []) if asset.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"В релизе отсутствует единственный файл {name}.")
    url = matches[0]["browser_download_url"]
    prefix = f"https://github.com/{REPOSITORY}/releases/download/"
    if not url.startswith(prefix):
        raise ValueError("Файл размещён вне репозитория обновлений.")
    return url


def download(url, target, expected_size, expected_hash):
    if type(expected_size) is not int or not 0 < expected_size <= MAX_DOWNLOAD:
        raise ValueError("Недопустимый размер файла обновления.")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        raise ValueError("Неверная контрольная сумма обновления.")
    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(url, headers={"User-Agent": "INEEDGEAR"})
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as output:
        while chunk := response.read(128 * 1024):
            total += len(chunk)
            if total > expected_size:
                raise ValueError("Размер загрузки превышает заявленный.")
            output.write(chunk)
            digest.update(chunk)
    if total != expected_size or digest.hexdigest() != expected_hash:
        raise ValueError("Загруженный файл повреждён: размер или SHA-256 не совпадает.")


def extract_addon(archive, destination):
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if not entries or len(entries) > 1000 or sum(item.file_size for item in entries) > 50 * 1024 * 1024:
            raise ValueError("Недопустимый размер архива аддона.")
        paths = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            if ("\\" in item.filename or ":" in item.filename or path.is_absolute()
                    or ".." in path.parts or not path.parts or path.parts[0] != "INEEDGEAR"
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Недопустимый путь в архиве аддона.")
            normalized = str(path).casefold()
            if normalized in paths:
                raise ValueError("Повторяющийся путь в архиве аддона.")
            paths.add(normalized)
        package.extractall(destination)
    addon = Path(destination) / "INEEDGEAR"
    if not all((addon / name).is_file() for name in ("INEEDGEAR.lua", "INEEDGEAR.toc")):
        raise ValueError("В архиве нет обязательных файлов аддона.")
    return addon


def prepare_update(release, addons_folder, is_dev, log):
    manifest = read_json(asset_url(release, "manifest.json"))
    if manifest.get("schema") != 1 or version_tuple(manifest.get("version")) != version_tuple(release["tag_name"]):
        raise ValueError("Манифест не соответствует релизу.")
    folder = Path(addons_folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Папка AddOns не найдена.")
    root = Path(tempfile.mkdtemp(prefix="ineedgear-update-"))
    executable_name = "INEEDGEAR-DEV.exe" if is_dev else "INEEDGEAR.exe"
    try:
        for name in (executable_name, "INEEDGEAR-addon.zip"):
            metadata = manifest["files"][name]
            log(f"Скачивание: {name}")
            download(asset_url(release, name), root / name, metadata["size"], metadata["sha256"])
        extract_addon(root / "INEEDGEAR-addon.zip", root / "unpacked")
        plan = {
            "pid": os.getpid(), "target": str(Path(sys.executable).resolve()),
            "source": str(root / executable_name), "addon_target": str(folder / "INEEDGEAR"),
            "addon_source": str(root / "unpacked" / "INEEDGEAR"),
            "sha256": manifest["files"][executable_name]["sha256"],
        }
        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return plan_path
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def launch_helper(plan_path):
    helper = Path(plan_path).parent / "updater.exe"
    shutil.copy2(sys.executable, helper)
    subprocess.Popen([str(helper), "--apply-update", str(plan_path)], cwd=str(helper.parent),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)


def wait_for_process(pid):
    if os.name != "nt":
        raise RuntimeError("Автозамена приложения поддерживается только в Windows.")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return  # Процесс уже завершился.
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise RuntimeError("Приложение не завершилось за две минуты.")
    finally:
        kernel.CloseHandle(handle)


def replace_with_retry(source, target):
    for attempt in range(30):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 29:
                raise
            time.sleep(0.5)


def install_transaction(plan):
    """Оба компонента заменяются с восстановлением при ошибке установки."""
    target = Path(plan["target"])
    source = Path(plan["source"])
    addon_target = Path(plan["addon_target"])
    addon_source = Path(plan["addon_source"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != plan["sha256"]:
        raise ValueError("Файл приложения изменился после проверки.")
    backup = target.with_name(target.name + ".previous")
    # Подготовленные файлы находятся на том же диске, что и место установки.
    staged_exe = target.with_name(target.name + ".pending")
    addon_stage = Path(tempfile.mkdtemp(prefix=".ing-stage-", dir=addon_target.parent))
    addon_backup = addon_stage / "previous"
    moved_exe = moved_addon = installed_addon = False
    try:
        shutil.copy2(source, staged_exe)
        shutil.copytree(addon_source, addon_stage / "new")
        replace_with_retry(target, backup)
        moved_exe = True
        replace_with_retry(staged_exe, target)
        if addon_target.exists():
            os.replace(addon_target, addon_backup)
            moved_addon = True
        os.replace(addon_stage / "new", addon_target)
        installed_addon = True
        subprocess.Popen([str(target)], cwd=str(target.parent))
    except Exception:
        if installed_addon:
            shutil.rmtree(addon_target)
        if moved_addon:
            os.replace(addon_backup, addon_target)
        if moved_exe:
            replace_with_retry(backup, target)
        raise
    finally:
        staged_exe.unlink(missing_ok=True)
        # При неудачном восстановлении резервная папка сохраняется для ручного ремонта.
        if not addon_backup.exists():
            shutil.rmtree(addon_stage, ignore_errors=True)
    if addon_backup.exists():
        saved = addon_target.with_name("INEEDGEAR.previous")
        try:
            if saved.exists():
                shutil.rmtree(saved)
            os.replace(addon_backup, saved)
            shutil.rmtree(addon_stage, ignore_errors=True)
        except OSError:
            pass  # Установка завершена; резервная копия остаётся в служебной папке.


def apply_update(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    try:
        wait_for_process(int(plan["pid"]))
        install_transaction(plan)
    except Exception as exc:
        message = f"Обновление не установлено: {exc}\nРезервные файлы сохранены рядом с программой и аддоном."
        Path(plan_path).with_name("error.txt").write_text(message, encoding="utf-8")
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, "I NEED GEAR", 0x10)

