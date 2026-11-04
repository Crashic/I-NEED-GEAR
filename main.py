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

from theme import (apply_dark_theme, DARK_BG, DARK_BG2, DARK_FG, DARK_FG_DIM,
                   DARK_ACCENT, DARK_BORDER, DARK_ENTRY)

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
from tkinter import messagebox
import updates
from version import VERSION
from changelog import HISTORY
from window_state import restore_position, window_rectangle

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
    "close_to_tray": False,
    "window_position": None,
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
    temporary = SETTINGS_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(temporary, SETTINGS_FILE)

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
        shutil.copy2(ADDON_DIR / "icon.tga", Path(target) / "icon.tga")
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
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Crashic.INEEDGEAR.Desktop.2")
        super().__init__()
        self.title(f"I NEED GEAR {VERSION}")
        self.geometry("450x480")
        self.resizable(False, False)

        apply_dark_theme(self)
        enable_paste(self)

        self.events = Queue()
        self.busy = False
        self.settings = load_settings()
        self.tray_icon = None
        self.changelog_window = None
        self.position_timer = None
        self._set_icon()
        self._build_main()
        restore_position(self, self.settings.get("window_position"))
        self.bind("<Configure>", self._position_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)
        self.after(1500, lambda: self.check_update(silent=True))

    def _set_icon(self):
        ico = os.path.join(BASE_DIR, "assets", "icon.ico")
        png = os.path.join(BASE_DIR, "assets", "icon.png")
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
        shell = tk.Frame(self, bg=DARK_BG, highlightbackground=DARK_BORDER, highlightthickness=1)
        shell.pack(fill="both", expand=True, padx=5, pady=5)
        header = tk.Frame(shell, bg=DARK_BG2, height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.brand_icon = tk.PhotoImage(file=str(Path(BASE_DIR) / "assets" / "icon.png")).subsample(16, 16)
        tk.Label(header, image=self.brand_icon, bg=DARK_BG2).pack(side="left", padx=(8, 7))
        tk.Label(header, text="I NEED GEAR", font=("Georgia", 12, "bold"),
                 fg=DARK_ACCENT, bg=DARK_BG2).pack(side="left")
        tk.Button(header, text=f"v{VERSION} ⓘ", command=self.show_changelog,
                  fg=DARK_ACCENT, bg=DARK_BG2, activebackground=DARK_BG2,
                  activeforeground="#ffe3a0", bd=0, cursor="hand2",
                  font=("Segoe UI", 8, "underline")).pack(side="right", padx=9)
        tk.Frame(shell, bg=DARK_BORDER, height=1).pack(fill="x")
        body = tk.Frame(shell, bg=DARK_BG)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg=DARK_BG2, width=106)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="РАЗДЕЛЫ", fg=DARK_FG_DIM, bg=DARK_BG2,
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=9, pady=(12, 6))
        self.nav_buttons = {}
        for key, text in (("home", "Обзор"), ("gear", "Аддон"), ("updates", "Обновления"), ("settings", "Настройки")):
            button = tk.Button(sidebar, text=text, anchor="w", bd=0, relief="flat",
                               bg=DARK_BG2, fg=DARK_ACCENT, activebackground="#44331d",
                               activeforeground="#ffe3a0", font=("Segoe UI", 9), padx=8, pady=7,
                               cursor="hand2", command=lambda page=key: self._select_page(page))
            button.pack(fill="x", padx=3, pady=1)
            self.nav_buttons[key] = button
        tk.Frame(sidebar, bg=DARK_BORDER, height=1).pack(fill="x", padx=8, pady=10)
        self.close_to_tray = tk.BooleanVar(value=self.settings.get("close_to_tray", False))
        self.check_off = tk.PhotoImage(file=str(Path(BASE_DIR) / "assets" / "check-off.png"))
        self.check_on = tk.PhotoImage(file=str(Path(BASE_DIR) / "assets" / "check-on.png"))
        tk.Checkbutton(sidebar, text="Закрывать\nв трей", variable=self.close_to_tray,
                       image=self.check_off, selectimage=self.check_on, compound="left", indicatoron=False,
                       bd=0, highlightthickness=0, relief="flat",
                       command=self._tray_setting_changed, bg=DARK_BG2, fg=DARK_FG_DIM,
                       activebackground=DARK_BG2, activeforeground=DARK_ACCENT,
                       selectcolor=DARK_BG2, font=("Segoe UI", 8), cursor="hand2",
                       justify="left", anchor="w").pack(fill="x", padx=4)
        tk.Label(sidebar, text="WoW Forever", bg=DARK_BG2, fg=DARK_FG_DIM,
                 font=("Segoe UI", 8)).pack(side="bottom", pady=10)
        tk.Frame(body, bg=DARK_BORDER, width=1).pack(side="left", fill="y")
        content = tk.Frame(body, bg=DARK_BG)
        content.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.page_title = tk.Label(content, anchor="w", font=("Georgia", 13), fg=DARK_FG, bg=DARK_BG)
        self.page_title.pack(fill="x")
        tk.Frame(content, bg=DARK_BORDER, height=1).pack(fill="x", pady=(6, 9))
        self.page_area = tk.Frame(content, bg=DARK_BG, height=242)
        self.page_area.pack(fill="x")
        self.page_area.pack_propagate(False)
        self.operation_panel = tk.Frame(self.page_area, bg=DARK_BG)
        self.page_hint = tk.Label(self.operation_panel, anchor="nw", justify="left", wraplength=285,
                                  fg=DARK_FG_DIM, bg=DARK_BG, font=("Segoe UI", 9))
        self.page_hint.pack(fill="x", pady=(2, 14))
        action_row = tk.Frame(self.operation_panel, bg=DARK_BG)
        action_row.pack(fill="x")
        self.action_label = tk.Label(action_row, fg=DARK_ACCENT, bg=DARK_BG,
                                     anchor="w", font=("Segoe UI", 9))
        self.action_label.pack(side="left")
        self.page_action = ttk.Button(action_row, style="Compact.TButton")
        self.page_action.pack(side="right")
        self.settings_panel = SettingsPanel(self.page_area, self.settings, self._on_settings_saved)
        tk.Label(content, text="Журнал событий", anchor="w", fg=DARK_ACCENT,
                 bg=DARK_BG, font=("Segoe UI", 9)).pack(fill="x", pady=(8, 5))
        journal = tk.Frame(content, bg=DARK_ENTRY, highlightbackground=DARK_BORDER, highlightthickness=1)
        journal.pack(fill="both", expand=True)
        self.log_box = tk.Text(journal, state="disabled", wrap="word", bg=DARK_ENTRY,
                               fg=DARK_FG, insertbackground=DARK_FG, relief="flat", bd=0,
                               padx=6, pady=5, font=("Segoe UI", 8), height=5, width=1)
        scrollbar = ttk.Scrollbar(journal, command=self.log_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=scrollbar.set)
        self.log_box.pack(fill="both", expand=True)
        self._select_page("home")

    def _select_page(self, page):
        self.operation_panel.pack_forget()
        self.settings_panel.pack_forget()
        if page == "settings":
            self.page_area.configure(height=242)
            self.page_title.configure(text="Настройки")
            self.settings_panel.pack(fill="both", expand=True)
        else:
            pages = {
                "home": ("Снаряжение", "Сохраните снаряжение в игре и закройте WoW. Затем отправьте свои данные и получите данные друзей.",
                         "Обмен данными", "Синхронизировать", self.on_update),
                "gear": ("Аддон", "Выберите папку AddOns в настройках и установите аддон. В игре окно открывается командой /ing.",
                         "Файлы аддона", "Установить", self.on_install),
                "updates": ("Обновления", "Обновляются программа и аддон. Перед установкой новой версии полностью закройте WoW.",
                            "Новая версия", "Проверить", self.on_update_addon),
            }
            self.page_area.configure(height=120)
            title, hint, label, action, command = pages[page]
            self.page_title.configure(text=title)
            self.page_hint.configure(text=hint)
            self.action_label.configure(text=label)
            self.page_action.configure(text=action, command=command)
            self.operation_panel.pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            button.configure(bg="#44331d" if key == page else DARK_BG2,
                             fg="#ffe3a0" if key == page else DARK_ACCENT)

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
                lambda: updates.prepare_update(release, folder, self.thread_log),
                self._launch_update))
        self._work(lambda: updates.latest_release(VERSION), ready)

    def _launch_update(self, plan):
        updates.launch_helper(plan)
        self._exit_app()

    def _position_changed(self, event):
        if event.widget is not self or self.state() != "normal":
            return
        if self.position_timer:
            self.after_cancel(self.position_timer)
        self.position_timer = self.after(500, self._save_position)

    def _save_position(self):
        self.position_timer = None
        if self.state() != "normal":
            return
        try:
            x, y, _, _ = window_rectangle(self)
            self.settings["window_position"] = {"x": x, "y": y}
            save_settings(self.settings)
        except (OSError, tk.TclError) as exc:
            self.log(f"Не удалось сохранить положение окна: {exc}")

    def _tray_setting_changed(self):
        self.settings["close_to_tray"] = self.close_to_tray.get()
        save_settings(self.settings)
        self.log("Закрытие в трей включено." if self.close_to_tray.get() else "Крестик полностью закрывает программу.")

    def _on_close(self):
        self._save_position()
        if not self.close_to_tray.get():
            self._exit_app()
            return
        if self.tray_icon is not None:
            if self.tray_icon.visible:
                self.withdraw()
            return
        try:
            import pystray
            from PIL import Image
            image = Image.open(Path(BASE_DIR) / "assets" / "icon.png").copy()
            icon = pystray.Icon("INEEDGEAR", image, "I NEED GEAR", menu=pystray.Menu(
                pystray.MenuItem("Открыть", lambda icon, item: self.events.put((self._show_from_tray, ())), default=True),
                pystray.MenuItem("Выйти", lambda icon, item: self.events.put((self._exit_app, ())))
            ))
            def run_tray():
                try:
                    def ready(icon):
                        icon.visible = True
                        self.events.put((self.withdraw, ()))
                    icon.run(setup=ready)
                except Exception as exc:
                    self.events.put((self._tray_failed, (str(exc),)))
            self.tray_icon = icon
            threading.Thread(target=run_tray, daemon=True).start()
        except Exception as exc:
            self._tray_failed(str(exc))

    def _tray_failed(self, message):
        if self.tray_icon:
            self.tray_icon.stop()
        self.tray_icon = None
        self.deiconify()
        self.log(f"Не удалось открыть значок в трее: {message}")

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _exit_app(self):
        self._save_position()
        for timer in self.tk.call("after", "info"):
            self.after_cancel(timer)
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.destroy()

    def show_changelog(self):
        if self.changelog_window is not None and self.changelog_window.winfo_exists():
            self.changelog_window.lift()
            self.changelog_window.focus_set()
            return
        window = tk.Toplevel(self)
        self.changelog_window = window
        window.title("История изменений — I NEED GEAR")
        window.geometry("420x400")
        window.resizable(False, False)
        window.transient(self)
        window.configure(bg=DARK_BG)
        if sys.platform.startswith("win"):
            window.iconbitmap(str(Path(BASE_DIR) / "assets" / "icon.ico"))
        tk.Label(window, text="Что нового", bg=DARK_BG, fg=DARK_ACCENT,
                 font=("Georgia", 18)).pack(anchor="w", padx=20, pady=(18, 12))
        area = tk.Frame(window, bg=DARK_ENTRY, highlightbackground=DARK_BORDER, highlightthickness=1)
        area.pack(fill="both", expand=True, padx=20)
        text = tk.Text(area, wrap="word", bg=DARK_ENTRY, fg=DARK_FG, bd=0,
                       padx=12, pady=10, font=("Segoe UI", 10), cursor="arrow")
        scrollbar = ttk.Scrollbar(area, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(fill="both", expand=True)
        text.tag_configure("version", foreground=DARK_ACCENT, font=("Segoe UI", 11, "bold"), spacing1=10, spacing3=5)
        for version, notes in HISTORY:
            text.insert("end", f"Версия {version}\n", "version")
            for note in notes:
                text.insert("end", f"• {note}\n")
        text.configure(state="disabled")
        ttk.Button(window, text="Закрыть", command=window.destroy).pack(anchor="e", padx=20, pady=14)
        window.bind("<Escape>", lambda event: window.destroy())
        window.update_idletasks()
        restore_position(window, {"x": self.winfo_rootx()+15, "y": self.winfo_rooty()+60})

    def open_settings(self):
        self._select_page("settings")

    def _on_settings_saved(self, s):
        s["window_position"] = self.settings.get("window_position")
        s["close_to_tray"] = self.close_to_tray.get()
        self.settings = s
        save_settings(s)
        self.log("💾 Настройки сохранены.")

# ==========================================================
# Окно настроек
# ==========================================================
class SettingsPanel(tk.Frame):
    def __init__(self, parent, settings, on_save):
        super().__init__(parent, bg=DARK_BG)
        self.settings = settings.copy()
        self.on_save = on_save
        self.columnconfigure(1, weight=1)
        self.vars = {}
        rows = (("addons_folder", "AddOns", True), ("local_folder", "Данные", True),
                ("local_filename", "Файл", False), ("player_key", "Персонаж", False))
        for row, (key, label, browse) in enumerate(rows):
            caption = tk.Label(self, text=label + (" ⓘ" if browse else ""), anchor="w", bg=DARK_BG, fg=DARK_ACCENT,
                               cursor="hand2" if browse else "", font=("Segoe UI", 9))
            caption.grid(row=row, column=0, sticky="w", padx=(0, 7), pady=5)
            if browse:
                caption.bind("<Button-1>", lambda event: self.show_folder_help())
            variable = tk.StringVar(value=settings.get(key, ""))
            self.vars[key] = variable
            ttk.Entry(self, textvariable=variable, width=10, font=("Segoe UI", 9)).grid(
                row=row, column=1, columnspan=1 if browse else 2, sticky="ew", pady=5)
            if browse:
                ttk.Button(self, text="…", width=2, style="Compact.TButton",
                           command=lambda field=key: self.pick_folder(field)).grid(row=row, column=2, padx=(4,0), pady=5)
        tk.Button(self, text="Где найти папки AddOns и SavedVariables?", command=self.show_folder_help,
                  bg=DARK_BG, fg=DARK_ACCENT, activebackground=DARK_BG, activeforeground="#ffe3a0",
                  bd=0, padx=0, pady=0, cursor="hand2", font=("Segoe UI", 8, "underline")).grid(
                      row=4, column=0, columnspan=3, sticky="w", pady=(5, 0))
        tk.Label(self, text="Персонаж: Ник-Реалм; пусто — автоматически.",
                 bg=DARK_BG, fg=DARK_FG_DIM, justify="left", anchor="w", wraplength=285,
                 font=("Segoe UI", 8)).grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 10))
        buttons = tk.Frame(self, bg=DARK_BG)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e")
        ttk.Button(buttons, text="Сбросить", style="Compact.TButton", command=self.reset).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="Сохранить", style="Compact.TButton", command=self.save).pack(side="left")

    def show_folder_help(self):
        existing = getattr(self, "folder_help", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        window = tk.Toplevel(self)
        self.folder_help = window
        window.title("Где найти папки")
        window.configure(bg=DARK_BG)
        window.geometry("410x330")
        window.resizable(False, False)
        window.transient(self.winfo_toplevel())
        tk.Label(window, text="Папки WoW Forever", bg=DARK_BG, fg=DARK_ACCENT,
                 font=("Georgia", 13)).pack(anchor="w", padx=16, pady=(14,10))
        text = (
            "AddOns — папка установки аддона:\n"
            "<игра>\\_forever_\\Interface\\AddOns\n\n"
            "Данные — настройки аддона вашего аккаунта:\n"
            "<игра>\\_forever_\\WTF\\Account\\\n"
            "<АККАУНТ>\\SavedVariables\n\n"
            "Внутри SavedVariables должен находиться INEEDGEARDB.lua.\n"
            "Он появится после сохранения снаряжения и выхода из игры.\n\n"
            "Указывайте конечные папки AddOns и SavedVariables, а не корень игры. "
            "Если папка клиента называется иначе, используйте её вместо _forever_."
        )
        tk.Label(window, text=text, justify="left", anchor="nw", wraplength=375,
                 bg=DARK_BG, fg=DARK_FG, font=("Segoe UI",9)).pack(fill="both", expand=True, padx=16)
        ttk.Button(window, text="Понятно", style="Compact.TButton", command=window.destroy).pack(anchor="e", padx=16,pady=12)
        window.bind("<Escape>", lambda event: window.destroy())
        root = self.winfo_toplevel()
        restore_position(window, {"x":root.winfo_rootx()+15,"y":root.winfo_rooty()+40})

    def pick_folder(self, key):
        title = "Выберите папку Interface\\AddOns" if key == "addons_folder" else "Выберите папку SavedVariables"
        folder = filedialog.askdirectory(parent=self, title=title, initialdir=self.vars[key].get() or None)
        if folder:
            self.vars[key].set(folder)

    def reset(self):
        for key, variable in self.vars.items():
            variable.set(self.settings.get(key, ""))

    def save(self):
        settings = self.settings.copy()
        settings.update({key: variable.get().strip() for key, variable in self.vars.items()})
        settings["local_filename"] = settings["local_filename"] or "INEEDGEARDB.lua"
        self.on_save(settings)
        self.settings = settings.copy()
        self.reset()


def run():
    if len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
        updates.apply_update(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        app = App()
        app.withdraw()
        app.update_idletasks()
        for page in ("gear", "updates", "settings", "home"):
            app._select_page(page)
            app.update_idletasks()
        app.show_changelog()
        app.changelog_window.update_idletasks()
        app.changelog_window.destroy()
        app.destroy()
        Path(sys.argv[2]).write_text("Запуск успешен", encoding="utf-8")
    else:
        App().mainloop()


if __name__ == "__main__":
    run()
