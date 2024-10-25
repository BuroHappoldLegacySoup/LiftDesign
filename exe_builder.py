import os
import subprocess

# Get the path to the current script's directory
script_dir = os.path.dirname(os.path.realpath(__file__))

# Get the path to the user's desktop
desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")

command = [
    'pyinstaller',
    '--noconfirm',
    '--onefile',
    '--noconsole',
    '--icon', os.path.join(script_dir, 'Elevator.ico'),
    '--exclude-module', '__pycache__',
    '--exclude', '.gitignore',
    '--clean',  # Clean PyInstaller cache and remove temporary files
    os.path.join(script_dir, 'gui.py'),
    '--distpath', desktop_dir
]

# Create a .spec file to have more control over the build process
spec_content = """
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['__pycache__'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Elevator.ico']
)
"""

# Write the spec file
with open('gui.spec', 'w') as f:
    f.write(spec_content)

print("Running PyInstaller with the following command:")
print(" ".join(command))

result = subprocess.run(command, capture_output=True, text=True)

print("PyInstaller Output:")
print(result.stdout)

if result.returncode != 0:
    print("Error occurred:")
    print(result.stderr)
else:
    print("PyInstaller completed successfully.")

# Clean up temporary files and directories after successful build
if result.returncode == 0:
    directories_to_clean = ['build', '__pycache__']
    files_to_clean = ['gui.spec']
    
    for directory in directories_to_clean:
        if os.path.exists(directory):
            try:
                subprocess.run(['rm', '-rf', directory] if os.name != 'nt' else ['rmdir', '/S', '/Q', directory])
                print(f"Cleaned up {directory} directory")
            except Exception as e:
                print(f"Error cleaning {directory}: {e}")
    
    for file in files_to_clean:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"Cleaned up {file}")
            except Exception as e:
                print(f"Error cleaning {file}: {e}")