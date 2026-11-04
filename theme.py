"""Оформление в духе игровых окон: бронза, золото и тёмная кожа."""

from tkinter import ttk

DARK_BG = "#15120f"
DARK_BG2 = "#211b15"
DARK_FG = "#eee3cf"
DARK_FG_DIM = "#a99a80"
DARK_ACCENT = "#d8b45a"
DARK_BORDER = "#78562d"
DARK_ENTRY = "#100e0c"


def apply_dark_theme(root):
    root.configure(bg=DARK_BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=DARK_BG, foreground=DARK_FG,
                    fieldbackground=DARK_ENTRY, bordercolor=DARK_BORDER,
                    troughcolor=DARK_ENTRY, focuscolor=DARK_ACCENT, font=("Segoe UI", 10))
    style.configure("TFrame", background=DARK_BG)
    style.configure("TLabelframe", background=DARK_BG, bordercolor=DARK_BORDER, relief="solid")
    style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_ACCENT)
    style.configure("TLabel", background=DARK_BG, foreground=DARK_FG)
    style.configure("TButton", background="#651c16", foreground="#f0ce79",
                    bordercolor=DARK_BORDER, lightcolor="#ad7741", darkcolor="#2a130d",
                    padding=(12, 8), borderwidth=2, relief="raised")
    style.map("TButton", background=[("disabled", "#29231c"), ("pressed", "#45120f"), ("active", "#8b2b20")],
              foreground=[("disabled", DARK_FG_DIM), ("active", "#ffe5a0")])
    style.configure("Compact.TButton", padding=(6, 4), font=("Segoe UI", 9))
    style.configure("TEntry", fieldbackground=DARK_ENTRY, foreground=DARK_FG,
                    bordercolor=DARK_BORDER, insertcolor=DARK_FG, padding=5)
    style.configure("Vertical.TScrollbar", background=DARK_BORDER, arrowcolor=DARK_ACCENT,
                    troughcolor=DARK_ENTRY, bordercolor=DARK_BG,
                    lightcolor=DARK_BORDER, darkcolor=DARK_BORDER)

