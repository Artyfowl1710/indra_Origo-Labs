"""Reset an unlinked local WhatsApp session; keep all other channel settings intact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from contextlib import closing

import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/"indra/SIH-26/hermes-agent"
HOME=ROOT/"data/indra-auto-home"
STATE=HOME/"whatsapp-reset.json"
os.environ["HERMES_HOME"]=str(HOME)
sys.path.insert(0,str(CORE))
from hermes_cli.config import save_env_value, write_platform_config_field
from hermes_cli.phone_numbers import normalize_phone_allowlist
from hermes_cli.web_server_messaging import _whatsapp_session_path


def telegram_fingerprint():
    env=dotenv_values(HOME/".env")
    return hashlib.sha256(json.dumps({k:v for k,v in env.items() if k.startswith("TELEGRAM_")},sort_keys=True).encode()).hexdigest()


def client():
    log=(ROOT/"logs/origo-product-backend.log").read_text(encoding="utf-8",errors="replace")
    ports=list(dict.fromkeys(reversed(re.findall(r"INDRA_DASHBOARD_READY port=([0-9]+)",log))))[:5]
    for port in ports:
        origin="http://127.0.0.1:"+port
        connection=httpx.Client(base_url=origin,timeout=httpx.Timeout(8,connect=.8),trust_env=False)
        try:
            html=connection.get("/channels").text
            match=re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*("(?:\\.|[^"\\])*")',html)
            if match:
                connection.headers["X-Hermes-Session-Token"]=json.loads(match[1])
            result=connection.get("/api/messaging/platforms")
            if result.is_success and Path(result.json().get("env_path","")).resolve()==(HOME/".env").resolve():
                return connection
        except (httpx.HTTPError,ValueError,OSError):
            pass
        connection.close()
    raise RuntimeError("Open the current Indra desktop so its authenticated WhatsApp setup is available.")


def prepare(phone):
    number=normalize_phone_allowlist(phone,"IN")
    if "," in number or not re.fullmatch(r"91[6-9][0-9]{9}",number):
        raise ValueError("Supply the single Indian owner mobile number.")
    before=telegram_fingerprint()
    session=_whatsapp_session_path().resolve()
    if not session.is_relative_to(HOME.resolve()) or session==HOME.resolve():
        raise ValueError("WhatsApp session must be inside the selected private profile.")
    save_env_value("WHATSAPP_MODE","self-chat")
    save_env_value("WHATSAPP_ALLOWED_USERS",number)
    save_env_value("WHATSAPP_DM_POLICY","pairing")
    save_env_value("WHATSAPP_ENABLED","false")
    write_platform_config_field("whatsapp","enabled",False)
    log_path=HOME/"logs/whatsapp-reset-gateway.log"
    with log_path.open("w",encoding="utf-8") as log:
        result=subprocess.run([sys.executable,"-m","hermes_cli.main","gateway","restart"],
                              cwd=CORE,env=os.environ.copy(),stdout=log,stderr=log,timeout=90)
    if result.returncode:
        raise RuntimeError("Gateway restart failed; WhatsApp remains disabled. Inspect the reset gateway log.")
    for _ in range(40):
        if not (session/"bridge.pid").exists():
            break
        time.sleep(.25)
    else:
        raise RuntimeError("The old WhatsApp bridge has not released its session; nothing was moved.")
    backup=session.parent/("session-unlinked-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    if not backup.resolve().is_relative_to(HOME.resolve()) or backup.exists():
        raise ValueError("Unsafe or occupied backup destination.")
    moved=session.exists()
    if moved:
        shutil.move(str(session),str(backup))
    session.mkdir(parents=True,exist_ok=True)
    unchanged=telegram_fingerprint()==before
    if not unchanged:
        raise RuntimeError("Telegram settings changed concurrently; review before pairing.")
    STATE.write_text(json.dumps({"phone":number,"mode":"self-chat","telegram_fingerprint":before}),encoding="utf-8")
    print(json.dumps({"reset":True,"mode":"self-chat","owner":"*******"+number[-4:],
                      "old_session_backed_up":moved,"telegram_settings_unchanged":unchanged}),flush=True)


def pair():
    state=json.loads(STATE.read_text())
    with closing(client()) as connection:
        response=connection.post("/api/messaging/whatsapp/onboarding/start",json={
            "mode":"self-chat","allowed_users":state["phone"],"default_country":"IN"})
        response.raise_for_status()
        payload=response.json()
        state["pairing_id"]=payload["pairing_id"]
        STATE.write_text(json.dumps(state),encoding="utf-8")
        for _ in range(45):
            response=connection.get("/api/messaging/whatsapp/onboarding/"+state["pairing_id"])
            response.raise_for_status()
            payload=response.json()
            if payload.get("qr_payload"):
                output=ROOT/"data/phone-pairing/whatsapp-self-chat.png"
                output.parent.mkdir(parents=True,exist_ok=True)
                from hermes_constants import find_node_executable
                node=find_node_executable("node") or shutil.which("node")
                module=next((p for p in (CORE/"node_modules/qrcode",CORE/"web/node_modules/qrcode") if p.exists()),None)
                if not node or module is None:
                    raise RuntimeError("The installed QR renderer is unavailable.")
                code="const fs=require('node:fs');require(process.argv[1]).toFile(process.argv[2],JSON.parse(fs.readFileSync(0,'utf8')).payload,{width:640,margin:3}).catch(()=>process.exit(1));"
                generated=subprocess.run([node,"-e",code,str(module),str(output)],
                    input=json.dumps({"payload":payload["qr_payload"]}),text=True,encoding="utf-8",
                    capture_output=True,timeout=20)
                if generated.returncode:
                    raise RuntimeError("The QR renderer could not create the pairing image.")
                print(json.dumps({"status":payload["status"],"mode":payload["mode"],"qr_image":str(output)}),flush=True)
                return
            if payload.get("status") in {"error","expired","cancelled"}:
                raise RuntimeError("Pairing could not start; inspect WhatsApp setup diagnostics.")
            time.sleep(1)
    raise RuntimeError("Pairing has not produced a QR code yet.")


def finish():
    state=json.loads(STATE.read_text())
    with closing(client()) as connection:
        path="/api/messaging/whatsapp/onboarding/"+state["pairing_id"]
        response=connection.get(path);response.raise_for_status();payload=response.json()
        if payload.get("status")!="connected":
            print(json.dumps({"status":payload.get("status"),"needs_phone_scan":True}),flush=True)
            return
        if payload.get("account_phone")!=state["phone"]:
            raise RuntimeError("The scanned WhatsApp account does not match the requested owner; it was not enabled.")
        response=connection.post(path+"/apply",json={"mode":"self-chat","allowed_users":state["phone"],"default_country":"IN"})
        response.raise_for_status()
        env=dotenv_values(HOME/".env")
        print(json.dumps({"paired":True,"mode":env.get("WHATSAPP_MODE"),
                          "owner_restricted":env.get("WHATSAPP_ALLOWED_USERS")==state["phone"],
                          "telegram_settings_unchanged":telegram_fingerprint()==state["telegram_fingerprint"],
                          "gateway_restart_started":response.json().get("restart_started")}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","pair","finish"])
    parser.add_argument("--phone")
    args=parser.parse_args()
    if args.action=="prepare":prepare(args.phone)
    elif args.action=="pair":pair()
    else:finish()
