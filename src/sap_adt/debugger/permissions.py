"""Windows current-user-only DACLs, without relying on POSIX chmod emulation."""
import ctypes
from ctypes import wintypes
import re
import subprocess


def windows_private(path, directory=False, create=False):
    who = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                         capture_output=True, timeout=10, check=True)
    match = re.search(rb"S-1-\d+(?:-\d+)+", who.stdout)
    if not match:
        raise ValueError("Could not identify Windows debugger state owner")
    sid = match[0].decode("ascii")
    expected = "D:P(A;" + ("OICI" if directory else "") + ";FA;;;" + sid + ")"
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = api.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    release = kernel.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    if create:
        sd = ctypes.c_void_p()
        if not convert(expected, 1, ctypes.byref(sd), None):
            raise ValueError("Could not create private debugger DACL")
        try:
            set_security = api.SetFileSecurityW
            set_security.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
            set_security.restype = wintypes.BOOL
            if not set_security(str(path), 0x80000004, sd):
                raise ValueError("Could not protect Windows debugger state")
        finally:
            release(sd)
    get_security = api.GetFileSecurityW
    get_security.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    get_security.restype = wintypes.BOOL
    needed = wintypes.DWORD()
    get_security(str(path), 4, None, 0, ctypes.byref(needed))
    if not 0 < needed.value <= 65536:
        raise ValueError("Could not verify debugger DACL")
    buffer = ctypes.create_string_buffer(needed.value)
    if not get_security(str(path), 4, buffer, needed.value, ctypes.byref(needed)):
        raise ValueError("Could not read debugger DACL")
    stringify = api.ConvertSecurityDescriptorToStringSecurityDescriptorW
    stringify.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                         ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
    stringify.restype = wintypes.BOOL
    text = ctypes.c_void_p()
    if not stringify(buffer, 1, 4, ctypes.byref(text), None):
        raise ValueError("Could not inspect debugger DACL")
    try:
        if ctypes.wstring_at(text) != expected:
            raise ValueError("Windows debugger state is not private to this user")
    finally:
        release(text)
