# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification for Sanction checK desktop application.
# Explicitly excludes GPL-licensed font (DarkGarden) bundled in ReportLab
# to ensure the built binary complies strictly with corporate permissive licensing.

datas = [
    ('config', 'config'),
    ('modules/screening/tiering_config.json', 'modules/screening'),
    ('config/fatf_lists.json', 'config'),
]

# ReportLab packaging filter: exclude DarkGarden font files
# DarkGarden (DarkGardenMK / DarkGarden-Regular.afm) is GNU GPL v2 copyleft.
# Sanction checK uses standard core PDF fonts (Helvetica) exclusively.
datas_filter = lambda d: 'DarkGarden' not in d[0] and 'darkgarden' not in d[0].lower()

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[d for d in datas if datas_filter(d)],
    hiddenimports=[
        'streamlit',
        'reportlab',
        'openpyxl',
        'yaml',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'reportlab.fonts.DarkGarden',
        'reportlab.fonts.DarkGardenMK',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SanctionCheck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
