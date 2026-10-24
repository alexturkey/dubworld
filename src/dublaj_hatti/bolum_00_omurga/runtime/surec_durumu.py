from __future__ import annotations

import os

WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WINDOWS_STILL_ACTIVE_EXIT_CODE = 259
WINDOWS_ERROR_ACCESS_DENIED = 5
MAX_PROCESS_ID = 0xFFFFFFFF


def _windows_process_is_alive(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ctypes.get_last_error() == WINDOWS_ERROR_ACCESS_DENIED
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == WINDOWS_STILL_ACTIVE_EXIT_CODE
    finally:
        kernel32.CloseHandle(handle)


def process_is_alive(pid: int) -> bool:
    if pid <= 0 or pid > MAX_PROCESS_ID:
        return False
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _windows_process_start(pid: int) -> str:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME),) * 4)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        zamanlar = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *(ctypes.byref(z) for z in zamanlar)):
            return ""
        olusma = zamanlar[0]
        return f"win:{(olusma.dwHighDateTime << 32) | olusma.dwLowDateTime}"
    finally:
        kernel32.CloseHandle(handle)


def _linux_process_start(pid: int) -> str:
    try:
        stat = open(f"/proc/{pid}/stat", encoding="ascii", errors="replace").read()  # noqa: SIM115
    except OSError:
        return ""
    alanlar = stat[stat.rfind(")") + 2:].split()  # süreç adı boşluk ve ')' içerebilir
    return f"linux:{alanlar[19]}" if len(alanlar) > 19 else ""  # 22. alan: starttime (açılıştan beri tik)


def process_start_time(pid: int) -> str:
    """Sürecin işletim sistemi başlangıç damgası (karşılaştırma için opak metin); okunamazsa "".

    PID'ler yeniden kullanılır: kayıttaki PID'nin bugün yaşıyor olması, kaydı yazan sürecin yaşadığını
    göstermez (Düzeltme A, D3). Kayda PID ile birlikte bu damga yazılır ve `process_matches` ile denetlenir.
    """
    if pid <= 0 or pid > MAX_PROCESS_ID:
        return ""
    if os.name == "nt":
        return _windows_process_start(pid)
    return _linux_process_start(pid)


def process_matches(pid: int, start: str = "") -> bool:
    """Kaydı yazan süreç hâlâ yaşıyor mu: PID canlı ve (damga biliniyorsa) başlangıç damgası aynı.

    Damgasız eski kayıtlar ya da damgası okunamayan süreçler için yalnız canlılığa bakılır (önceki davranış).
    """
    if not process_is_alive(pid):
        return False
    if not start:
        return True
    simdiki = process_start_time(pid)
    return not simdiki or simdiki == start
