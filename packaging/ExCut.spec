# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all

block_cipher = None

import os

# 'onefile' or 'onedir'
build_mode = os.environ.get('BUILD_MODE', 'onedir')

# Manually collect PyQt6 binaries and plugins WITHOUT importing PyQt6
# This avoids ImportError: DLL load failed in Wine/Docker environments
import glob
import site

# Find PyQt6 directory in site-packages
pyqt6_dir = None
for site_pkg in site.getsitepackages():
    candidate = os.path.join(site_pkg, "PyQt6")
    if os.path.isdir(candidate):
        pyqt6_dir = candidate
        break

if not pyqt6_dir:
    # Fallback to standard location if site-packages search fails
    # This assumes standard Windows/Python layout in the container
    import sys
    pyqt6_dir = os.path.join(sys.prefix, "Lib", "site-packages", "PyQt6")

qt6_bin = os.path.join(pyqt6_dir, "Qt6", "bin")
qt6_plugins = os.path.join(pyqt6_dir, "Qt6", "plugins")

print(f"Manual Qt6 Search: Found PyQt6 at {pyqt6_dir}")

# Add all DLLs from Qt6/bin
extra_binaries = []
if os.path.exists(qt6_bin):
    for dll in glob.glob(os.path.join(qt6_bin, "*.dll")):
        # (source_path, dest_folder_in_bundle)
        extra_binaries.append((dll, os.path.join("PyQt6", "Qt6", "bin")))

# Add plugins dir
extra_datas = []
if os.path.exists(qt6_plugins):
    extra_datas.append((qt6_plugins, os.path.join("PyQt6", "Qt6", "plugins")))

tmp_ret = [[], [], []]

a = Analysis(
    ['../main.py'],
    pathex=['..'],
    binaries=extra_binaries,
    datas=extra_datas + [
        ('../src', 'src'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if build_mode == 'onedir':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ExCut',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=['icon.png'],
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='ExCut',
    )
else:
    # One-File mode
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='ExCut',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=['icon.png'],
    )
