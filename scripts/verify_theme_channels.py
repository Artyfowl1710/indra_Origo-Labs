"""Own isolated backend/renderer acceptance for the three requested product themes."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
import httpx

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/"indra/SIH-26/hermes-agent"


def main():
    output=ROOT/"data/test-results"/("theme-channels-"+uuid.uuid4().hex)
    home=output/"home"
    home.mkdir(parents=True)
    (home/"config.yaml").write_text(json.dumps({
        "model":{"provider":"custom","default":"fixture-text","base_url":"http://127.0.0.1:1/v1"},
        "terminal":{"backend":"docker","cwd":str(home)},
        "security":{"untrusted_content_guard":True},
        "delegation":{"max_concurrent_children":3,"subagent_auto_approve":False},
        "fallback_model":None,
    }),encoding="utf-8")
    env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","USERPROFILE","APPDATA","LOCALAPPDATA","TEMP","TMP","COMSPEC","PROGRAMFILES","PROGRAMFILES(X86)"}}
    env.update(HERMES_HOME=str(home),HERMES_DESKTOP="1",PYTHONUTF8="1")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1",0))
        port=listener.getsockname()[1]
    origin=f"http://127.0.0.1:{port}"
    with (output/"backend.log").open("w",encoding="utf-8") as log:
        backend=subprocess.Popen([sys.executable,"-m","hermes_cli.main","dashboard","--no-open","--skip-build","--host","127.0.0.1","--port",str(port)],cwd=CORE,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(160):
                if backend.poll() is not None:raise RuntimeError("Fixture backend exited")
                try:
                    if httpx.get(origin+"/overview",timeout=1,trust_env=False).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.2)
            else:raise RuntimeError("Fixture backend startup timed out")
            electron=CORE/"apps/desktop/node_modules/electron/dist/electron.exe"
            with (output/"electron.log").open("w",encoding="utf-8") as electron_log:
                result=subprocess.run(["powershell.exe","-NoProfile","-File",str(ROOT/"scripts/run_theme_renderer.ps1"),"-Origin",origin,"-OutputDirectory",str(output)],cwd=ROOT,env=env,stdout=electron_log,stderr=electron_log,timeout=240)
            if not (output/"acceptance.json").exists():
                raise RuntimeError(f"Electron exited {result.returncode} before acceptance; inspect {output}")
            checks=json.loads((output/"acceptance.json").read_text())
            print(json.dumps({"checks":len(checks),"passed":sum(bool(row["passed"]) for row in checks),"output":str(output)}))
            if result.returncode or not all(row["passed"] for row in checks):raise RuntimeError("Native theme acceptance failed; inspect fixture output")
            (ROOT/"data/test-results/theme-channels-acceptance.json").write_text(json.dumps({"output":str(output),"checks":checks},indent=2),encoding="utf-8")
        finally:
            backend.terminate()
            try:backend.wait(timeout=10)
            except subprocess.TimeoutExpired:backend.kill();backend.wait(timeout=5)


if __name__=="__main__":main()
