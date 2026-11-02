"""Real local-model coding + goal acceptance, isolated profile/project and Docker tools."""
from pathlib import Path
import hashlib,json,os,re,socket,subprocess,sys,time
import uuid
from urllib.parse import quote
import httpx,yaml
from dotenv import dotenv_values
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1];CORE=ROOT/"indra/SIH-26/hermes-agent"
GUARDED="--content-guard" in sys.argv
NATIVE_REVIEW="--native-review-probe" in sys.argv
OUT=ROOT/("data/test-results/real-project-goal-guarded" if GUARDED else "data/test-results/real-project-goal")
TEST_COMMANDS={"python -m unittest -v","python -m unittest -q","cd /workspace && python -m unittest -v",
               "cd /workspace && python -m unittest -v test_invoice.InvoiceTests","cd /workspace && python -m unittest test_invoice.InvoiceTests -v"}
TESTS='''import unittest
from invoice import invoice_total
class InvoiceTests(unittest.TestCase):
    def test_quantity(self):self.assertEqual(invoice_total([{"quantity":2,"unit_price":"10.00"}]),"20.00")
    def test_discount(self):self.assertEqual(invoice_total([{"quantity":2,"unit_price":"10.00"}],"0.10"),"18.00")
    def test_rounding(self):self.assertEqual(invoice_total([{"quantity":3,"unit_price":"0.335"}]),"1.01")
    def test_empty(self):self.assertEqual(invoice_total([]),"0.00")
    def test_invalid_discount(self):
        with self.assertRaises(ValueError):invoice_total([],"1.1")
    def test_negative_discount(self):
        with self.assertRaises(ValueError):invoice_total([],"-0.1")
    def test_precise_discount_boundary(self):
        with self.assertRaises(ValueError):invoice_total([],"1.000000000000000001")
    def test_full_discount(self):self.assertEqual(invoice_total([{"quantity":2,"unit_price":"10.00"}],"1"),"0.00")
    def test_valid_precise_discount(self):self.assertEqual(invoice_total([{"quantity":2,"unit_price":"10.00"}],"0.999999999999999999"),"0.00")
if __name__=="__main__":unittest.main()
'''

def main():
    OUT.mkdir(parents=True,exist_ok=True);project=OUT/"project";project.mkdir(exist_ok=True);home=OUT/"profile";home.mkdir(exist_ok=True)
    if NATIVE_REVIEW:
        (OUT/"native-review-request.json").unlink(missing_ok=True)
        (OUT/"native-review-response.json").unlink(missing_ok=True)
    (project/"invoice.py").write_text('def invoice_total(lines, discount="0"):\n    return str(sum(float(line["unit_price"]) for line in lines))\n',encoding="utf-8")
    (project/"test_invoice.py").write_text(TESTS,encoding="utf-8")
    (project/"README.md").write_text("Invoice totals: multiply price by quantity, subtract discount fraction, use Decimal ROUND_HALF_UP to two places, return a two-decimal string. Discounts must be from zero to one. Edit invoice.py only; never alter the tests.\n",encoding="utf-8")
    baseline=hashlib.sha256((project/"invoice.py").read_bytes()).hexdigest();test_hash=hashlib.sha256((project/"test_invoice.py").read_bytes()).hexdigest()
    readme_hash=hashlib.sha256((project/"README.md").read_bytes()).hexdigest()
    active=ROOT/"data/indra-auto-home";source=yaml.safe_load((active/"config.yaml").read_text(encoding="utf-8"));provider=source["providers"]["origo-local"]
    cfg={"model":{"provider":"custom:origo-local","default":"origo-qwen35","base_url":provider["base_url"],"key_env":"ORIGO_LOCAL_INFERENCE_KEY","max_tokens":2048},"providers":{"origo-local":provider},
         "agent":{"max_turns":12},"terminal":{"backend":"docker","cwd":str(project),"docker_image":"indra-documents:1","docker_mount_cwd_to_workspace":True,"docker_network":False,"docker_forward_env":[],"container_cpu":1,"container_memory":768,"container_persistent":False,"docker_persist_across_processes":False,"docker_orphan_reaper":False},
         "auxiliary":{"goal_judge":{"provider":"custom:origo-local","model":"origo-qwen35","base_url":provider["base_url"],"max_tokens":2048}},"security":{"untrusted_content_guard":GUARDED}}
    (home/"config.yaml").write_text(yaml.safe_dump(cfg),encoding="utf-8")
    key=dotenv_values(active/".env").get(provider.get("key_env","ORIGO_LOCAL_INFERENCE_KEY"),"")
    # Fail before starting a goal if the desktop-owned router has exited.
    httpx.get(provider["base_url"].removesuffix("/v1")+"/health",headers={"Authorization":"Bearer "+key},timeout=5,trust_env=False).raise_for_status()
    (home/".env").write_text("ORIGO_LOCAL_INFERENCE_KEY="+key+"\n",encoding="utf-8")
    with socket.socket() as listener:listener.bind(("127.0.0.1",0));port=listener.getsockname()[1]
    env={k:v for k,v in os.environ.items() if not k.endswith(("_API_KEY","_TOKEN"))}
    env.update(HERMES_HOME=str(home),HERMES_DESKTOP="1",HERMES_TUI_TOOLSETS="file,terminal",PYTHONUTF8="1")
    report={"model":"origo-qwen35","judge":"real configured local model","tool_backend":"docker","cloud_keys_copied":False,"content_guard_enabled":GUARDED,"approval_responder":"fixture oracle, not a human test","events":[],"passed":False};started=time.monotonic()
    with (OUT/"backend.log").open("w",encoding="utf-8") as log:
        child=subprocess.Popen([sys.executable,"-m","hermes_cli.main","dashboard","--no-open","--skip-build","--host","127.0.0.1","--port",str(port)],cwd=CORE,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        try:
            origin=f"http://127.0.0.1:{port}"
            for _ in range(120):
                if child.poll() is not None:raise RuntimeError("Fixture backend exited")
                try:
                    response=httpx.get(origin+"/chat",timeout=1,trust_env=False)
                    if response.status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.5)
            else:raise RuntimeError("Fixture backend startup timed out")
            token=json.loads(re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*("(?:\\.|[^"\\])*")',response.text).group(1))
            with connect(origin.replace("http:","ws:")+"/api/ws?token="+quote(token),origin=origin,max_size=8*1024*1024,open_timeout=20) as ws:
                seq=0;session="";stored_session="";native_checked=False
                def send(method,params):
                    nonlocal seq
                    seq+=1;rid="fixture-"+str(seq);ws.send(json.dumps({"jsonrpc":"2.0","id":rid,"method":method,"params":params}));return rid
                def event(row):
                    nonlocal native_checked
                    data=row.get("params",{}) if row.get("method")=="event" else {};payload=data.get("payload") or {};kind=data.get("type")
                    if data.get("session_id")!=session:return
                    if kind=="approval.request":
                        command=str(payload.get("command") or "")
                        approved=command in TEST_COMMANDS
                        if GUARDED and "one-operation human review" in command:
                            reason=str(payload.get("description") or "")
                            try:details=json.loads(reason.split("Requested action: ",1)[1].split("\nArguments SHA-256:",1)[0])
                            except (ValueError,IndexError):details={}
                            if command.startswith("<terminal>"):
                                approved=details.get("command") in TEST_COMMANDS|{"pwd"}
                            elif command.startswith(("<write_file>","<patch>")):
                                approved=details.get("path",details.get("file_path")) in {"/workspace/invoice.py","invoice.py"}
                        # Static fixture oracle: only this file's edits and exact test
                        # commands are allowed. No unattended approval in the product.
                        reviewed=False
                        if NATIVE_REVIEW and GUARDED and approved and not native_checked and "one-operation human review" in command:
                            native_checked=True;nonce=uuid.uuid4().hex
                            (OUT/"native-review-request.json").write_text(json.dumps({"origin":origin,"chat":stored_session,"request_id":payload.get("request_id",""),"nonce":nonce,"owner_pid":os.getpid(),"backend_pid":child.pid}),encoding="utf-8")
                            print(json.dumps({"type":"native_review_waiting","seconds":round(time.monotonic()-started,1)}),flush=True)
                            receipt=OUT/"native-review-response.json";review_deadline=time.monotonic()+60
                            while not receipt.exists() and time.monotonic()<review_deadline:time.sleep(.1)
                            result=json.loads(receipt.read_text(encoding="utf-8-sig")) if receipt.exists() else {}
                            reviewed=result.get("nonce")==nonce and result.get("passed") is True
                            report["native_review_passed"]=reviewed;report["native_review_exit_code"]=result.get("exit_code")
                        if not reviewed:send("approval.respond",{"session_id":session,"request_id":payload.get("request_id"),"choice":"once" if approved else "deny"})
                        report["events"].append({"type":kind,"allowed":approved,"command":command[:500],"allow_session":payload.get("allow_session"),"allow_permanent":payload.get("allow_permanent")})
                    elif kind in {"tool.start","tool.complete","message.complete","error","status.update"}:
                        item={"type":kind,"name":payload.get("name"),"text":str(payload.get("text") or "")[-4000:]}
                        report["events"].append(item);print(json.dumps({"type":kind,"name":payload.get("name"),"seconds":round(time.monotonic()-started,1)}),flush=True)
                def rpc(method,params):
                    rid=send(method,params);deadline=time.monotonic()+150
                    while time.monotonic()<deadline:
                        try:row=json.loads(ws.recv(timeout=30))
                        except TimeoutError:continue
                        if row.get("id")==rid:
                            if "error" in row:raise RuntimeError(method+": "+str(row["error"]))
                            return row.get("result",{})
                        event(row)
                    raise RuntimeError("Fixture RPC timed out")
                session=rpc("session.create",{"source":"dashboard","cwd":str(project),"hidden":True})["session_id"]
                report["runtime_session_id"]=session
                goal=rpc("goal.configure",{"session_id":session,"objective":"Fix invoice.py in the selected project so all nine existing invoice tests pass. Read README.md and test_invoice.py, edit invoice.py on disk and run python -m unittest -v. Work only in /workspace. Never edit tests or README, install packages or use network tools. Return concise test evidence.","max_turns":3,"contract":{"verification":"All nine original invoice tests pass in Docker and only invoice.py is changed.","boundaries":"Only the granted fixture project; edit invoice.py only."},"gates":[{"command":"python -m unittest -v","timeout_seconds":40,"max_retries":2}]})
                stored_session=next(s["session_key"] for s in rpc("session.active_list",{}).get("sessions",[]) if s["id"]==session)
                kickoff=rpc("command.dispatch",{"session_id":session,"name":"goal","arg":"resume"})
                rpc("prompt.submit",{"session_id":session,"text":kickoff["message"]})
                deadline=time.monotonic()+600;last_poll=0
                while time.monotonic()<deadline:
                    try:event(json.loads(ws.recv(timeout=3)))
                    except TimeoutError:pass
                    if time.monotonic()-last_poll>5:
                        snapshot=rpc("goal.get",{"session_id":session});last_poll=time.monotonic();report["goal"]=snapshot["state"]
                        if snapshot["state"]["status"] in {"done","paused","cleared"} and not snapshot["running"]:break
                else:rpc("command.dispatch",{"session_id":session,"name":"goal","arg":"pause"});rpc("session.interrupt",{"session_id":session});raise RuntimeError("Real project acceptance exceeded ten minutes")
                report["tests_unchanged"]=hashlib.sha256((project/"test_invoice.py").read_bytes()).hexdigest()==test_hash
                report["readme_unchanged"]=hashlib.sha256((project/"README.md").read_bytes()).hexdigest()==readme_hash
                report["only_expected_source_files"]=all(p.name in {"invoice.py","test_invoice.py","README.md"} for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
                report["code_changed"]=hashlib.sha256((project/"invoice.py").read_bytes()).hexdigest()!=baseline
                check=subprocess.run(["docker","run","--rm","--network","none","--cpus","1","--memory","768m","--cap-drop","ALL","--read-only","--mount",f"type=bind,source={project},target=/workspace,readonly","indra-documents:1","python","-B","-m","unittest","-v"],capture_output=True,text=True,timeout=60)
                report["independent_check"]={"exit_code":check.returncode,"output":(check.stdout+check.stderr)[-5000:]}
                report["passed"]=report["tests_unchanged"] and report["readme_unchanged"] and report["only_expected_source_files"] and report["code_changed"] and check.returncode==0 and report["goal"]["status"]=="done" and report["goal"]["gates"][0]["last_exit_code"]==0
                if GUARDED:
                    reviews=[e for e in report["events"] if e["type"]=="approval.request" and "one-operation human review" in e.get("command","")]
                    report["review_count"]=len(reviews)
                    report["review_scopes_restricted"]=bool(reviews) and all(e["allow_session"] is False and e["allow_permanent"] is False for e in reviews)
                    report["passed"]=report["passed"] and report["review_scopes_restricted"]
                if NATIVE_REVIEW:report["passed"]=report["passed"] and report.get("native_review_passed") is True
        except Exception as error:report["error"]=str(error)
        finally:
            report["seconds"]=round(time.monotonic()-started,2);(OUT/"acceptance.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            if child.poll() is None:child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    print(json.dumps({"passed":report["passed"],"seconds":report["seconds"],"error":report.get("error")}))
    return 0 if report["passed"] else 1

if __name__=="__main__":raise SystemExit(main())
