"""Double-click launcher: starts a hidden local backend and opens the client."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
STATE = Path.home() / '.codex/prompt-forge-client'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-open', action='store_true')
    args=parser.parse_args()
    STATE.mkdir(parents=True,exist_ok=True)
    ready=STATE/'server.json'
    def existing():
        try:
            info=json.loads(ready.read_text())
            origin,token=info['url'].split('/#',1)
            request=urllib.request.Request(origin+'/api/state',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(request,timeout=2) as response:
                if json.load(response).get('connected'):
                    return info
        except (OSError,ValueError):
            return None
    info=existing()
    if not info:
        ready.unlink(missing_ok=True)
        executable=Path(sys.executable)
        # pythonw avoids a console window on Windows; use python for other hosts.
        if os.name=='nt' and executable.with_name('pythonw.exe').exists():
            executable=executable.with_name('pythonw.exe')
        with (STATE/'startup.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([str(executable),'-u',str(ROOT/'server.py'),'--ready-file',str(ready)],
                cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                start_new_session=os.name!='nt')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError('Prompt Forge could not start. See '+str(STATE/'startup.log'))
            if ready.exists():
                info=existing()
                if info:break
            time.sleep(.3)
        if not info:raise RuntimeError('Codex did not start within 90 seconds. See '+str(STATE/'startup.log'))
    if not args.no_open:webbrowser.open(info['url'])
    if sys.stdout:print(json.dumps(info))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(exc),'Prompt Forge',0x10)
        else:raise
