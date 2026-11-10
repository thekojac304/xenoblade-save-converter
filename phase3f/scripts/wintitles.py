"""Print the titles of all top-level windows of processes named <exe> (read-only).   python wintitles.py Dolphin.exe"""
import ctypes, ctypes.wintypes as W, sys, subprocess
u = ctypes.windll.user32
name = sys.argv[1].lower()
pids = set()
out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
for line in out.splitlines():
    p = [x.strip('"') for x in line.split('","')]
    if p and p[0].lower() == name:
        pids.add(int(p[1]))
res = []
@ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
def cb(h, l):
    pid = W.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value in pids:
        n = u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
        if b.value: res.append((u.IsWindowVisible(h), b.value))
    return True
u.EnumWindows(cb, 0)
for v, t in res: print(v, t)
