# -*- mode: python -*-
# PyInstaller spec file for Vacation Calendar Updater
# Works on Windows, Linux, and via Docker+Wine for Windows builds

block_cipher = None

a = Analysis(['app/__main__.py'],
             pathex=['.'],
             binaries=[],
             datas=[('client_secret.json', '.'), ('app.ico', '.')],
             hiddenimports=[
                  # PySide6 modules - collected via hook
             ],
             hookspath=['/var/mnt/Disk2/vacation_calendar_updater/hooks'],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='VacationCalendarUpdater',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False,
          icon='app.ico')