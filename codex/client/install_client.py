"""Install a self-contained local copy and desktop launcher (Python/Codex required)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

source=Path(__file__).resolve().parents[1]
destination=Path.home()/'.local/share/prompt-forge/codex'
for name in ('client','prompt-forge'):
    shutil.copytree(source/name,destination/name,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
launcher=destination/'client/launch.pyw'
if os.name=='nt':
    python=Path(sys.executable).with_name('pythonw.exe')
    quote=lambda s: "'"+str(s).replace("'","''")+"'"
    script="\n".join([
        "$desktop=[Environment]::GetFolderPath('Desktop')",
        "$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Prompt Forge.lnk'))",
        '$shortcut.TargetPath='+quote(python),
        '$shortcut.Arguments='+quote('"'+str(launcher)+'"'),
        '$shortcut.WorkingDirectory='+quote(launcher.parent),
        "$shortcut.Description='Prompt Forge — private preprocessing before Codex'",
        '$shortcut.Save()',
    ])
    subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
else:
    folder=Path.home()/'.local/bin';folder.mkdir(parents=True,exist_ok=True)
    import shlex
    entry=folder/'prompt-forge-chat'
    entry.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(launcher))+' "$@"\n')
    entry.chmod(0o755)
print('Installed client:',launcher)
print('Windows: open Prompt Forge on your desktop. Other hosts: prompt-forge-chat.')
