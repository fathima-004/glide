"""Read raw finger contacts from a Windows Precision Touchpad.

Uses the Win32 Raw Input API (usage page 0x0D, usage 0x05) and hid.dll to
parse each report into a list of contacts: id, x, y (0..1) and tip (touching).
No third-party packages needed.
"""
import ctypes
import threading
from ctypes import wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid")

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RID_INPUT = 0x10000003
RIDI_PREPARSEDDATA = 0x20000005
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEHID = 2
HWND_MESSAGE = wt.HWND(-3)
HIDP_STATUS_SUCCESS = 0x00110000
HidP_Input = 0

PAGE_GENERIC, PAGE_DIGITIZER = 0x01, 0x0D
USAGE_X, USAGE_Y = 0x30, 0x31
USAGE_TOUCHPAD = 0x05
USAGE_TIP = 0x42
USAGE_CONTACT_ID = 0x51
USAGE_CONTACT_COUNT = 0x54

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE), ("wParam", WPARAM)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
                ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
                ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
                ("NumberLinkCollectionNodes", wt.USHORT), ("NumberInputButtonCaps", wt.USHORT),
                ("NumberInputValueCaps", wt.USHORT), ("NumberInputDataIndices", wt.USHORT),
                ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
                ("NumberOutputDataIndices", wt.USHORT), ("NumberFeatureButtonCaps", wt.USHORT),
                ("NumberFeatureValueCaps", wt.USHORT), ("NumberFeatureDataIndices", wt.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", wt.USHORT), ("LinkCollection", wt.USHORT), ("LinkUsage", wt.USHORT),
                ("LinkUsagePage", wt.USHORT), ("IsRange", ctypes.c_ubyte),
                ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
                ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
                ("BitSize", wt.USHORT), ("ReportCount", wt.USHORT), ("Reserved2", wt.USHORT * 5),
                ("UnitsExp", wt.ULONG), ("Units", wt.ULONG), ("LogicalMin", wt.LONG),
                ("LogicalMax", wt.LONG), ("PhysicalMin", wt.LONG), ("PhysicalMax", wt.LONG),
                ("Usage", wt.USHORT), ("_union_rest", wt.USHORT * 7)]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wt.UINT, wt.UINT]
user32.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputData.restype = wt.UINT
user32.GetRawInputDeviceInfoW.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT)]
user32.GetRawInputDeviceInfoW.restype = wt.UINT
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
kernel32.GetModuleHandleW.restype = wt.HMODULE

hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS),
                                  ctypes.POINTER(wt.USHORT), ctypes.c_void_p]
hid.HidP_GetValueCaps.restype = ctypes.c_long
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT,
                                   ctypes.POINTER(wt.ULONG), ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetUsageValue.restype = ctypes.c_long
hid.HidP_GetUsages.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, ctypes.POINTER(wt.USHORT),
                               ctypes.POINTER(wt.ULONG), ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetUsages.restype = ctypes.c_long


class _Device:
    """Parsed layout of one touchpad: which link collections hold fingers."""

    def __init__(self, hdevice):
        size = wt.UINT(0)
        user32.GetRawInputDeviceInfoW(hdevice, RIDI_PREPARSEDDATA, None, ctypes.byref(size))
        self.buf = ctypes.create_string_buffer(size.value)
        user32.GetRawInputDeviceInfoW(hdevice, RIDI_PREPARSEDDATA, self.buf, ctypes.byref(size))
        self.pp = ctypes.cast(self.buf, ctypes.c_void_p)

        caps = HIDP_CAPS()
        hid.HidP_GetCaps(self.pp, ctypes.byref(caps))
        n = wt.USHORT(caps.NumberInputValueCaps)
        vcaps = (HIDP_VALUE_CAPS * max(n.value, 1))()
        hid.HidP_GetValueCaps(HidP_Input, vcaps, ctypes.byref(n), self.pp)

        self.collections = {}  # link collection -> {"x": (min,max), "y": (min,max)}
        self.count_link = None
        for v in vcaps[: n.value]:
            if v.UsagePage == PAGE_GENERIC and v.Usage in (USAGE_X, USAGE_Y):
                key = "x" if v.Usage == USAGE_X else "y"
                self.collections.setdefault(v.LinkCollection, {})[key] = (v.LogicalMin, v.LogicalMax)
                if key == "x":
                    self.collections[v.LinkCollection]["phys_w"] = v.PhysicalMax - v.PhysicalMin
                else:
                    self.collections[v.LinkCollection]["phys_h"] = v.PhysicalMax - v.PhysicalMin
            elif v.UsagePage == PAGE_DIGITIZER and v.Usage == USAGE_CONTACT_COUNT:
                self.count_link = v.LinkCollection
        self.links = sorted(k for k, c in self.collections.items() if "x" in c and "y" in c)
        first = self.collections[self.links[0]] if self.links else {}
        w, h = first.get("phys_w") or 0, first.get("phys_h") or 0
        if not (w and h) and first:
            w = first["x"][1] - first["x"][0]
            h = first["y"][1] - first["y"][0]
        self.aspect = (w / h) if (w and h) else 1.6
        self.pending = []
        self.remaining = 0

    def _value(self, page, link, usage, report):
        out = wt.ULONG(0)
        st = hid.HidP_GetUsageValue(HidP_Input, page, link, usage, ctypes.byref(out),
                                    self.pp, report, len(report))
        return out.value if (st & 0xFFFFFFFF) == HIDP_STATUS_SUCCESS else None

    def _tip(self, link, report):
        lst = (wt.USHORT * 16)()
        ln = wt.ULONG(16)
        st = hid.HidP_GetUsages(HidP_Input, PAGE_DIGITIZER, link, lst, ctypes.byref(ln),
                                self.pp, report, len(report))
        if (st & 0xFFFFFFFF) != HIDP_STATUS_SUCCESS:
            return False
        return USAGE_TIP in lst[: ln.value]

    def parse(self, report):
        """Feed one HID report; returns a full frame (list of contacts) or None."""
        report = ctypes.create_string_buffer(bytes(report), len(report))
        count = self._value(PAGE_DIGITIZER, self.count_link or 0, USAGE_CONTACT_COUNT, report)
        if count:  # first report of a new frame (hybrid mode may split across reports)
            self.pending, self.remaining = [], count
        for link in self.links:
            if self.remaining <= 0:
                break
            c = self.collections[link]
            x = self._value(PAGE_GENERIC, link, USAGE_X, report)
            y = self._value(PAGE_GENERIC, link, USAGE_Y, report)
            cid = self._value(PAGE_DIGITIZER, link, USAGE_CONTACT_ID, report)
            if x is None or y is None:
                continue
            (x0, x1), (y0, y1) = c["x"], c["y"]
            self.pending.append({
                "id": cid if cid is not None else link,
                "x": min(max((x - x0) / max(x1 - x0, 1), 0.0), 1.0),
                "y": min(max((y - y0) / max(y1 - y0, 1), 0.0), 1.0),
                "tip": self._tip(link, report),
            })
            self.remaining -= 1
        if self.remaining <= 0 and self.pending:
            frame, self.pending = self.pending, []
            return frame
        return None


class TouchpadReader(threading.Thread):
    """Background thread. Calls on_frame(contacts, aspect) for every touch frame."""

    def __init__(self, on_frame):
        super().__init__(daemon=True)
        self.on_frame = on_frame
        self.devices = {}
        self.hwnd = None
        self.ready = threading.Event()
        self.error = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            try:
                self._handle(lparam)
            except Exception as e:  # never let a bad report kill the loop
                print("touchpad parse error:", e)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        if msg == 0x0312:  # WM_HOTKEY: Ctrl+Alt+Q quits Thottu
            import os
            os._exit(0)
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _handle(self, lparam):
        hsize = ctypes.sizeof(RAWINPUTHEADER)
        size = wt.UINT(0)
        user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), hsize)
        buf = ctypes.create_string_buffer(size.value)
        if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), hsize) != size.value:
            return
        header = RAWINPUTHEADER.from_buffer_copy(buf, 0)
        if header.dwType != RIM_TYPEHID:
            return
        size_hid = int.from_bytes(buf.raw[hsize:hsize + 4], "little")
        count = int.from_bytes(buf.raw[hsize + 4:hsize + 8], "little")
        dev = self.devices.get(header.hDevice)
        if dev is None:
            dev = self.devices[header.hDevice] = _Device(header.hDevice)
        data = buf.raw[hsize + 8:]
        for i in range(count):
            frame = dev.parse(data[i * size_hid:(i + 1) * size_hid])
            if frame is not None:
                self.on_frame(frame, dev.aspect)

    def run(self):
        self._proc = WNDPROC(self._wndproc)  # keep a reference
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = "ThottuTouchpadSink"
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "Thottu", 0, 0, 0, 0, 0,
                                           None, None, hinst, None)  # hidden top-level window
        rid = RAWINPUTDEVICE(PAGE_DIGITIZER, USAGE_TOUCHPAD, RIDEV_INPUTSINK, self.hwnd)
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            self.error = f"RegisterRawInputDevices failed ({ctypes.get_last_error()})"
            self.ready.set()
            return
        user32.RegisterHotKey(self.hwnd, 1, 0x0001 | 0x0002 | 0x4000, ord("Q"))  # Alt+Ctrl, no repeat
        self.ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
