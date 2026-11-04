import os
import sys
import json
import shutil
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime, timezone

from supabase import create_client
from saved_variables import own_data, player_key

# ==========================================================
# Тёмная тема
# ==========================================================
DARK_BG      = "#1e1e1e"
DARK_BG2     = "#252526"
DARK_FG      = "#d4d4d4"
DARK_FG_DIM  = "#858585"
DARK_ACCENT  = "#0e639c"
DARK_BORDER  = "#3c3c3c"
DARK_ENTRY   = "#2d2d30"

def apply_dark_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=DARK_BG)
    style.configure(".",
        background=DARK_BG,
        foreground=DARK_FG,
        fieldbackground=DARK_ENTRY,
        bordercolor=DARK_BORDER,
        focuscolor=DARK_ACCENT,
        troughcolor=DARK_BG2,
    )

    style.configure("TFrame", background=DARK_BG)
    style.configure("TLabelframe", background=DARK_BG, bordercolor=DARK_BORDER)
    style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_FG)
    style.configure("TLabel", background=DARK_BG, foreground=DARK_FG)

    style.configure("TButton",
        background=DARK_BG2,
        foreground=DARK_FG,
        bordercolor=DARK_BORDER,
        focuscolor=DARK_ACCENT,
        padding=(6, 3),
    )
    style.map("TButton",
        background=[("active", DARK_ACCENT), ("pressed", "#0a4d7a")],
        foreground=[("active", "#ffffff")],
    )

    style.configure("TEntry",
        fieldbackground=DARK_ENTRY,
        foreground=DARK_FG,
        bordercolor=DARK_BORDER,
        insertcolor=DARK_FG,
    )

def enable_paste(root):
    """Включает Ctrl+V/C/X/A во всех Entry и Text."""
    for cls in ("Entry", "TEntry"):
        root.bind_class(cls, "<Control-v>", lambda e: e.widget.event_generate("<<Paste>>"))
        root.bind_class(cls, "<Control-c>", lambda e: e.widget.event_generate("<<Copy>>"))
        root.bind_class(cls, "<Control-x>", lambda e: e.widget.event_generate("<<Cut>>"))
        root.bind_class(cls, "<Control-a>", lambda e: (e.widget.select_range(0, "end"), "break")[1])

# ==========================================================
# Пути и настройки
# ==========================================================
from pathlib import Path
from queue import Queue, Empty
from tkinter import messagebox, simpledialog
import updates
from version import VERSION

IS_DEV = False
BASE_DIR = str(Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)))
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "INEEDGEAR"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = str(DATA_DIR / "settings.json")
LEGACY_SETTINGS = (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent) / "settings.json"
if not Path(SETTINGS_FILE).exists() and LEGACY_SETTINGS.exists():
    shutil.copy2(LEGACY_SETTINGS, SETTINGS_FILE)

SUPABASE_URL = "https://rhdioomvbgaqqbeulggx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJoZGlvb212YmdhcXFiZXVsZ2d4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE4MjQ5NTksImV4cCI6MjEwNzQwMDk1OX0.pHtZNuqKgPRIpxIZTA_dAfg8NJYyE8oWht4f7RTnqkw"

DEFAULT_SETTINGS = {
    "addons_folder": "",
    "local_folder": "",
    "local_filename": "INEEDGEARDB.lua",
    "player_key": "",
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(s):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ==========================================================
# Тексты файлов аддона (вшиты в программу)
# ==========================================================
ADDON_DIR = Path(BASE_DIR) / "addon" / "INEEDGEAR"
ADDON_TOC = (ADDON_DIR / "INEEDGEAR.toc").read_text(encoding="utf-8")
ADDON_LUA = (ADDON_DIR / "INEEDGEAR.lua").read_text(encoding="utf-8")

# ==========================================================
# Утилиты
# ==========================================================
def extract_player_key(lua_text):
    try:
        return player_key(lua_text)
    except ValueError:
        return None


def lua_quote(value):
    return '"' + ''.join(
        '\\' + format(ord(char), '03d') if ord(char) < 32 else
        '\\' + char if char in ('"', '\\') else char
        for char in value
    ) + '"'

def append_imports_to_db(local_path, imports, log_fn):
    with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    marker = "\n-- === IMPORTED DATA (auto) ===\n"
    if marker in text:
        text = text.split(marker)[0]

    text += marker
    text += "INEEDGEARDB = INEEDGEARDB or {}\n"
    text += "INEEDGEARDB.imported = {\n"
    for name, raw in imports.items():
        text += f"    [{lua_quote(name)}] = {lua_quote(raw)},\n"
    text += "}\n"

    shutil.copy2(local_path, local_path + ".ing-backup")
    temporary = local_path + ".ing-tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(temporary, local_path)
    log_fn(f"💾 Импорт дописан в файл аддона ({len(imports)} персонажей)")

# ==========================================================
# Установка аддона (вшитая версия)
# ==========================================================
def install_addon(addons_folder, log_fn):
    if not addons_folder or not os.path.isdir(addons_folder):
        log_fn("❌ Папка AddOns не указана или не существует.")
        return

    target = os.path.join(addons_folder, "INEEDGEAR")
    try:
        os.makedirs(target, exist_ok=True)
    except PermissionError:
        log_fn("❌ Нет прав на запись. Запусти программу от имени администратора.")
        return
    except Exception as e:
        log_fn(f"❌ Ошибка создания папки: {e}")
        return

    try:
        with open(os.path.join(target, "INEEDGEAR.toc"), "w", encoding="utf-8") as f:
            f.write(ADDON_TOC)
        with open(os.path.join(target, "INEEDGEAR.lua"), "w", encoding="utf-8") as f:
            f.write(ADDON_LUA)
        log_fn(f"✅ Аддон установлен в: {target}")
        log_fn("💡 Зайди в игру и набери /ing")
    except PermissionError:
        log_fn("❌ Нет прав на запись. Запусти программу от имени администратора.")
    except Exception as e:
        log_fn(f"❌ Ошибка записи файлов: {e}")

# ==========================================================
# Обновление через Supabase
# ==========================================================
def do_update(settings, log_fn):
    local_folder = settings["local_folder"]
    local_file = settings["local_filename"]
    url = SUPABASE_URL
    key = SUPABASE_KEY

    if not local_folder or not os.path.isdir(local_folder):
        log_fn("❌ Папка SavedVariables не указана или не существует.")
        return

    local_path = os.path.join(local_folder, local_file)
    if not os.path.exists(local_path):
        log_fn(f"❌ Файл аддона не найден: {local_path}")
        log_fn("💡 Зайди в игру, нажми «Сохранить снаряжение», выйди из игры и попробуй снова.")
        return

    with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
        local_text = f.read()

    player_key = settings.get("player_key") or extract_player_key(local_text)
    if not player_key:
        log_fn("Не удалось определить персонажа. Укажите ключ Ник-Реалм в настройках.")
        return
    log_fn(f"👤 Игрок: {player_key}")

    try:
        log_fn("🔌 Подключение к Supabase...")
        supabase = create_client(url, key)

        row = {
            "player_key": player_key,
            "equipped": own_data(local_text),
            "wishlist": "",
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("characters").upsert(row).execute()
        log_fn(f"⬆️ Загружено в Supabase: {player_key}")

        log_fn("📥 Скачиваю данные других игроков...")
        response = supabase.table("characters").select("*").execute()
        rows = response.data or []
        log_fn(f"   Получено записей: {len(rows)}")

        imports = {}
        for r in rows:
            pk = r.get("player_key", "")
            raw = r.get("equipped", "")
            if pk and pk != player_key and raw:
                imports[pk] = raw
                log_fn(f"   ⬇️ {pk}")

        if imports:
            append_imports_to_db(local_path, imports, log_fn)
        else:
            append_imports_to_db(local_path, {}, log_fn)
            log_fn("ℹ️ Данных других игроков пока нет.")

        log_fn("✅ Готово.")

    except Exception as e:
        log_fn(f"❌ Ошибка: {e}")

# ==========================================================
# Главное окно
# ==========================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"I NEED GEAR {VERSION}" + (" [DEV]" if IS_DEV else ""))
        self.geometry("460x620")
        self.resizable(False, False)

        apply_dark_theme(self)
        enable_paste(self)

        self.events = Queue()
        self.busy = False
        self.settings = load_settings()
        self._set_icon()
        self._build_main()
        self.after(100, self._poll_events)
        self.after(1500, lambda: self.check_update(silent=True))

    def _set_icon(self):
        ico = os.path.join(BASE_DIR, "icon.ico")
        png = os.path.join(BASE_DIR, "icon.png")
        try:
            if sys.platform.startswith("win") and os.path.exists(ico):
                self.iconbitmap(ico)
            elif os.path.exists(png):
                img = tk.PhotoImage(file=png)
                self.iconphoto(True, img)
                self._icon_ref = img
        except Exception:
            pass

    def _build_main(self):
        for w in self.winfo_children():
            w.destroy()

        tk.Label(
            self,
            text="I NEED GEAR",
            font=("Segoe UI", 16, "bold"),
            justify="center",
            bg=DARK_BG,
            fg=DARK_FG,
        ).pack(pady=(18, 12))

        ttk.Button(self, text="Синхронизировать снаряжение", command=self.on_update, width=28)\
            .pack(pady=4, ipady=5)

        ttk.Button(self, text="Установить аддон", command=self.on_install, width=28)\
            .pack(pady=4, ipady=5)

        ttk.Button(self, text="Проверить обновление", command=self.on_update_addon, width=28)\
            .pack(pady=4, ipady=5)

        ttk.Button(self, text="Настройки", command=self.open_settings, width=28)\
            .pack(pady=4, ipady=5)

        if IS_DEV:
            ttk.Button(self, text="Опубликовать обновление", command=self.on_publish, width=28).pack(pady=4, ipady=5)

        self.log_box = tk.Text(
            self, height=9, width=46, state="disabled", wrap="word",
            bg=DARK_ENTRY, fg=DARK_FG, insertbackground=DARK_FG,
            relief="flat", highlightthickness=1,
            highlightbackground=DARK_BORDER, highlightcolor=DARK_ACCENT,
        )
        self.log_box.pack(padx=12, pady=(12, 12), fill="both", expand=True)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                callback, args = self.events.get_nowait()
                try:
                    callback(*args)
                except Exception as exc:
                    self.log(f"Ошибка операции: {exc}")
        except Empty:
            pass
        self.after(100, self._poll_events)

    def _work(self, task, done=None):
        if self.busy:
            self.log("Дождитесь завершения текущей операции.")
            return
        self.busy = True
        def worker():
            try:
                result = task()
                if done:
                    self.events.put((done, (result,)))
            except Exception as exc:
                self.events.put((self.log, (f"Ошибка: {exc}",)))
            finally:
                self.events.put((setattr, (self, "busy", False)))
        threading.Thread(target=worker, daemon=True).start()

    def thread_log(self, message):
        self.events.put((self.log, (message,)))

    def on_update(self):
        if not messagebox.askokcancel("Синхронизация", "Перед синхронизацией полностью закройте WoW. Игра может перезаписать файл данных. Продолжить?"):
            return
        settings = self.settings.copy()
        self._work(lambda: do_update(settings, self.thread_log))

    def on_install(self):
        folder = self.settings.get("addons_folder", "")
        self._work(lambda: install_addon(folder, self.thread_log))

    def on_update_addon(self):
        self.check_update()

    def check_update(self, silent=False):
        def ready(release):
            if release is None:
                if not silent:
                    self.log("Обновлений пока нет.")
                return
            if not messagebox.askyesno("Обновление", f"Доступна версия {release['tag_name']}. Закройте WoW перед установкой. Скачать и установить?"):
                return
            folder = self.settings.get("addons_folder", "")
            if not folder or not os.path.isdir(folder):
                self.log("Сначала укажите папку AddOns в настройках.")
                return
            if not getattr(sys, "frozen", False):
                self.log("Автозамена доступна в собранном .exe. Из исходников обновляйте проект через GitHub.")
                return
            # Обработчик очереди освободит флаг занятости перед запуском скачивания.
            self.after(100, lambda: self._work(
                lambda: updates.prepare_update(release, folder, IS_DEV, self.thread_log),
                self._launch_update))
        self._work(lambda: updates.latest_release(VERSION), ready)

    def _launch_update(self, plan):
        updates.launch_helper(plan)
        self.destroy()

    def on_publish(self):
        if not IS_DEV:
            return
        version = simpledialog.askstring("Публикация", "Версия нового релиза (например, 1.0.1):")
        if not version:
            return
        from developer import publish_release
        self._work(lambda: publish_release(version.strip(), self.thread_log))

    def open_settings(self):
        SettingsWindow(self, self.settings, self._on_settings_saved)

    def _on_settings_saved(self, s):
        self.settings = s
        save_settings(s)
        self.log("💾 Настройки сохранены.")

# ==========================================================
# Окно настроек
# ==========================================================
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, settings, on_save):
        super().__init__(parent)
        apply_dark_theme(self)
        self.title("Настройки")
        self.geometry("460x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.settings = settings.copy()
        self.on_save = on_save
        self._build()

    def _build(self):
        pad = {"padx": 12, "pady": 6}

        # --- Папка AddOns ---
        f0 = ttk.LabelFrame(self, text="Папка AddOns игры")
        f0.pack(fill="x", **pad)

        self.var_addons = tk.StringVar(value=self.settings.get("addons_folder", ""))
        ttk.Entry(f0, textvariable=self.var_addons, width=42)\
            .grid(row=0, column=0, padx=6, pady=6, sticky="we")
        ttk.Button(f0, text="Обзор...", command=self.pick_addons)\
            .grid(row=0, column=1, padx=6, pady=6)

        tk.Label(
            f0,
            text="Пример: C:\\Games\\WoW Forever\\_retail_\\Interface\\AddOns",
            justify="left", anchor="w", fg=DARK_FG_DIM, bg=DARK_BG,
            font=("Segoe UI", 8)
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

        # --- Папка SavedVariables ---
        f1 = ttk.LabelFrame(self, text="Папка SavedVariables игры")
        f1.pack(fill="x", **pad)

        self.var_folder = tk.StringVar(value=self.settings["local_folder"])
        ttk.Entry(f1, textvariable=self.var_folder, width=42)\
            .grid(row=0, column=0, padx=6, pady=6, sticky="we")
        ttk.Button(f1, text="Обзор...", command=self.pick_folder)\
            .grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(f1, text="Имя файла аддона:").grid(row=1, column=0, sticky="w", padx=6)
        self.var_local_file = tk.StringVar(value=self.settings["local_filename"])
        ttk.Entry(f1, textvariable=self.var_local_file, width=36)\
            .grid(row=2, column=0, columnspan=2, sticky="we", padx=6, pady=(0, 6))

        # --- Идентификация ---
        f3 = ttk.LabelFrame(self, text="Идентификация (необязательно)")
        f3.pack(fill="x", **pad)

        ttk.Label(f3, text='Ключ персонажа "Ник-Реалм" (если пусто — возьмётся из файла):')\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=3)
        self.var_player = tk.StringVar(value=self.settings.get("player_key", ""))
        ttk.Entry(f3, textvariable=self.var_player, width=42)\
            .grid(row=1, column=0, columnspan=2, sticky="we", padx=6, pady=(0, 6))

        # --- Подсказка ---
        f_hint = ttk.LabelFrame(self, text="Подсказка: как найти папки")
        f_hint.pack(fill="x", **pad)

        hint_text = (
            "AddOns: <игра>\\_retail_\\Interface\\AddOns\n"
            "SavedVariables: <игра>\\_retail_\\WTF\\Account\\<АККАУНТ>\\SavedVariables"
        )

        tk.Label(
            f_hint, text=hint_text, justify="left", anchor="w",
            fg=DARK_FG_DIM, bg=DARK_BG,
            font=("Segoe UI", 8), wraplength=400
        ).pack(side="left", fill="x", expand=True, padx=6, pady=6)

        # --- Кнопки ---
        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=10)
        ttk.Button(btns, text="Сохранить", command=self.save).pack(side="right", padx=6)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="right", padx=6)

    def pick_addons(self):
        folder = filedialog.askdirectory(title="Выберите папку Interface\\AddOns")
        if folder:
            self.var_addons.set(folder)

    def pick_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку SavedVariables")
        if folder:
            self.var_folder.set(folder)

    def save(self):
        s = self.settings.copy()
        s["addons_folder"] = self.var_addons.get().strip()
        s["local_folder"] = self.var_folder.get().strip()
        s["local_filename"] = self.var_local_file.get().strip() or "INEEDGEARDB.lua"
        s["player_key"] = self.var_player.get().strip()
        self.on_save(s)
        self.destroy()

def run():
    if len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
        updates.apply_update(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        app = App()
        app.withdraw()
        app.update_idletasks()
        app.destroy()
        Path(sys.argv[2]).write_text("Запуск успешен", encoding="utf-8")
    else:
        App().mainloop()


if __name__ == "__main__":
    run()
