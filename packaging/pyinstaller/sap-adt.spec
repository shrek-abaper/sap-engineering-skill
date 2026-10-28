# PyInstaller spec for the self-contained sap-adt runtime (onedir layout).
#
# Build via tools/build_runtime.py (sets cwd to the repo root). The build
# venv must have the package installed (`pip install -e .`) plus the bundled
# optional backends: keyring and cryptography.
#
# Deliberately bundled so the runtime is self-contained per spec §7.1:
#   - dist-info metadata of `sap-adt` (version reads importlib.metadata)
#   - keyring + its platform backends (Secret Service / Credential Manager /
#     Keychain — whichever exist at build time; runtime reports missing ones)
#   - cryptography (encrypted-file keystore fallback)
#   - certifi CA bundle (requests/urllib3 SSL verification)
#
# External system components are NOT bundled and remain capability-probed at
# runtime: Secret Service daemon, GPG/pass, Windows PowerShell (dpapi store).
import os

from PyInstaller.utils.hooks import copy_metadata

# Paths resolve from the spec file, not the invocation cwd. SPECPATH is the
# directory containing this spec (packaging/pyinstaller/), so two levels up.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPECPATH)))
_SRC = os.path.join(_REPO_ROOT, "src")

block_cipher = None

_datas = copy_metadata("sap-adt-cli")

a = Analysis(
    [os.path.join(_SRC, "sap_adt", "__main__.py")],
    pathex=[_SRC],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # Credential backends are selected at runtime from the keystore
        # registry; make the dynamic imports visible to the analysis.
        "keyring",
        "keyring.backends",
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives.kdf.scrypt",
        "certifi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not part of the runtime; keeps the image small and unambiguous.
        "tkinter", "matplotlib", "numpy", "pandas", "pytest", "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sap-adt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="sap-adt",
)
