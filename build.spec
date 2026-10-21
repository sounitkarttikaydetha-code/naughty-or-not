# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification for Naughty or not desktop application.
# Explicitly excludes GPL-licensed font (DarkGarden) bundled in ReportLab
# to ensure the built binary complies strictly with corporate permissive licensing.

from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

# Collect Streamlit static web assets and metadata
streamlit_datas = collect_data_files('streamlit')
streamlit_metadata = copy_metadata('streamlit')
webview_datas = collect_data_files('webview')

datas = [
    ('app.py', '.'),
    ('config', 'config'),
    ('modules', 'modules'),
    ('assets', 'assets'),
    ('USER_GUIDE.pdf', '.'),
    ('THIRD_PARTY_NOTICES.md', '.'),
    ('LICENSE', '.'),
] + streamlit_datas + streamlit_metadata + webview_datas

# ReportLab packaging filter: exclude DarkGarden font files
# DarkGarden (DarkGardenMK / DarkGarden-Regular.afm) is GNU GPL v2 copyleft.
# Naughty or not uses standard core PDF fonts (Helvetica) exclusively.
datas_filter = lambda d: 'DarkGarden' not in str(d[0]) and 'darkgarden' not in str(d[0]).lower()

hidden_imports = (
    collect_submodules('streamlit')
    + collect_submodules('webview')
    + [
        'streamlit.web.bootstrap',
        'streamlit.runtime.scriptrunner.magic_expressions',
        'truststore',
        'keyring',
        'keyring.backends.Windows',
        'clr_loader',
        'pythonnet',
        'rapidfuzz',
        'reportlab',
        'openpyxl',
        'pypdf',
        'yaml',
        'sqlite3',
    ]
)

a = Analysis(
    ['desktop_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[d for d in datas if datas_filter(d)],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pytest',
        'ruff',
        'mypy',
        'reportlab.fonts.DarkGarden',
        'reportlab.fonts.DarkGardenMK',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Naughty or not',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NaughtyOrNot',
)
