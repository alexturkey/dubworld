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
