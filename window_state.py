"""Положение окна с учётом рабочих областей подключённых мониторов."""

import os


def fit_position(position, size, areas):
    if not isinstance(position, dict) or any(type(position.get(key)) is not int for key in ("x", "y")):
        return None
    x, y = position["x"], position["y"]
    width, height = size
    for left, top, right, bottom in areas:
        if left <= x and top <= y and x + min(width, right-left) <= right and y + min(height, bottom-top) <= bottom:
            return x, y
    if not areas:
        return None
    # При отключённом мониторе возвращаем окно на ближайшую доступную рабочую область.
    left, top, right, bottom = min(areas, key=lambda area:
        max(area[0]-x, 0, x-area[2])**2 + max(area[1]-y, 0, y-area[3])**2)
    return max(left, min(x, right-width)), max(top, min(y, bottom-height))


def native_window(window):
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    api.GetAncestor.restype = wintypes.HWND
    api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    api.GetWindowRect.restype = wintypes.BOOL
    handle = api.GetAncestor(window.winfo_id(), 2)
    return api, handle


def window_rectangle(window):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api, handle = native_window(window)
        rect = wintypes.RECT()
        if not api.GetWindowRect(handle, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top
    return window.winfo_x(), window.winfo_y(), window.winfo_width(), window.winfo_height()


def restore_position(window, position):
    window.update_idletasks()
    _, _, width, height = window_rectangle(window)
    areas = []
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api, handle = native_window(window)
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                          ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        def collect(monitor, dc, rect, data):
            info = MonitorInfo()
            info.size = ctypes.sizeof(info)
            if api.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.work
                areas.append((r.left, r.top, r.right, r.bottom))
            return True
        callback = callback_type(collect)
        api.EnumDisplayMonitors(None, None, callback, 0)
    else:
        areas.append((0, 0, window.winfo_screenwidth(), window.winfo_screenheight()))
    target = fit_position(position, (width, height), areas)
    if target is None:
        return
    x, y = target
    if os.name == "nt":
        api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
        if not api.SetWindowPos(handle, None, x, y, 0, 0, 0x0015):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        window.geometry(f"+{x}+{y}")
