"""Authenticated project, knowledge, memory and provenance endpoints for Indra."""
from pathlib import Path
import tempfile
from typing import List
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from hermes_cli.web_deps import late
from hermes_cli.origo_workspace import workspace as _workspace

def service(request):
    from hermes_cli.web_server_profiles import _profile_scope
    with _profile_scope(request.query_params.get("profile")): return _workspace()

router=APIRouter(prefix="/api/indra/workspace", tags=["indra-workspace"])
require_token=late("_require_token")

class ConversationEntry(BaseModel):
    id:str=Field(min_length=1,max_length=160)
    kind:Literal["voice","note"]="voice"
    role:Literal["user","assistant","note"]="note"
    text:str=Field(min_length=1,max_length=16000)
    model:str=Field(default="",max_length=160)
    provider:str=Field(default="",max_length=160)
class ConversationBatch(BaseModel):
    entries:List[ConversationEntry]=Field(min_length=1,max_length=50)

@router.get("/conversations/{chat}/records")
def conversation_records(chat:str,request:Request,after:int=0):
    require_token(request);current=service(request)
    from origo_runtime.conversation_records import ConversationRecords
    return {"entries":checked(ConversationRecords(current.root).list,chat,after)}

@router.post("/conversations/{chat}/records")
def save_conversation_records(chat:str,body:ConversationBatch,request:Request):
    require_token(request);current=service(request)
    from origo_runtime.conversation_records import ConversationRecords
    import hashlib,json
    entries=[entry.model_dump() for entry in body.entries]
    checked(ConversationRecords(current.root).save,chat,entries)
    current.audit.append("conversation.records_saved",{"chat":chat,"entries":len(entries),"content_hash":hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()})
    return {"saved":len(entries)}

@router.on_event("startup")
async def warm_offline_encoder():
    import logging
    try:
        _workspace()
        from origo_runtime.embeddings import encoder,status
        if status()["installed"]: await run_in_threadpool(encoder)
    except Exception as error:
        logging.getLogger(__name__).warning("Offline embedding warmup unavailable (%s)",type(error).__name__)

class Grant(BaseModel):
    name: str=Field(default="", max_length=80)
    root: str=Field(max_length=2000)
class Search(BaseModel):
    query: str=Field(min_length=1,max_length=2000)
    project: str=Field(default="library", max_length=40)
class DocumentReview(BaseModel):
    family: str=Field(max_length=120)
    version: str=Field(default="",max_length=40)
    owner: str=Field(default="",max_length=120)
    effective_date: str=Field(default="",max_length=10)
    review_due: str=Field(default="",max_length=10)
    status: Literal["unreviewed","current","superseded"]="unreviewed"
    superseded_by: str=Field(default="",max_length=32)
    revision: str=Field(pattern=r"^[a-f0-9]{64}$")
class Identity(BaseModel):
    name: str=Field(default="",max_length=80)
    instructions: str=Field(default="",max_length=2000)
    share_across_profiles: bool=False
    interests: str=Field(default="",max_length=300)
    facts: List[str]=Field(default_factory=list,max_length=20)
    use_in_requests: bool=False
    setup_complete: bool=False
    revision: str | None=Field(default=None,max_length=64)

class MemoryImportReview(BaseModel):
    id: str=Field(pattern=r"^[a-f0-9]{32}$")
    selected: List[str]=Field(min_length=1,max_length=20)
    revision: str=Field(pattern=r"^[a-f0-9]{64}$")

def checked(call, *args):
    try: return call(*args)
    except PermissionError as error: raise HTTPException(403,str(error)) from error
    except (ValueError,FileNotFoundError,NotADirectoryError) as error: raise HTTPException(400,str(error)) from error

@router.get("/projects")
def projects(request: Request):
    require_token(request); return {"projects":service(request).projects()}

@router.post("/projects")
def grant(body: Grant, request: Request):
    require_token(request); return {"id":checked(service(request).grant, body.name, body.root)}

@router.delete("/projects/{project}")
def revoke(project: str,request: Request):
    require_token(request); checked(service(request).revoke,project); return {"ok":True}

@router.get("/projects/{project}/files")
def files(project:str,request:Request):
    require_token(request); return {"files":checked(service(request).files,project),"limit":2000}

@router.post("/projects/{project}/index")
def index(project:str,request:Request):
    require_token(request); return checked(service(request).index,project)

@router.get("/projects/{project}/preview")
def project_preview(project:str,path:str,request:Request):
    require_token(request); return {"text":checked(service(request).preview,project,path)}

@router.get("/jobs/{job}")
def job(job:str,request:Request):
    require_token(request); value=service(request).jobs.get(job)
    if value is None: raise HTTPException(404,"Job not found")
    return dict(value)

@router.get("/knowledge")
def knowledge(request:Request,project:str="library"):
    require_token(request)
    engine=checked(service(request).engine,project)
    from origo_runtime.embeddings import status
    return {"status":engine.status(),"documents":engine.list_documents(),"embedding":status()}

@router.post("/knowledge/search")
def search(body:Search,request:Request):
    require_token(request); return checked(service(request).engine,body.project).search(body.query)

@router.get("/knowledge/review-digest")
def knowledge_review_digest(request:Request,project:str="library"):
    require_token(request); return checked(service(request).knowledge_digest,project)

@router.put("/knowledge/{doc}/review")
def review_knowledge_document(doc:str,body:DocumentReview,request:Request,project:str="library"):
    require_token(request)
    return checked(service(request).review_document,project,doc,body.model_dump(exclude={"revision"}),body.revision)

@router.get("/knowledge/{doc}/source")
def preview_knowledge_source(doc:str,request:Request,project:str="library"):
    require_token(request)
    from app.knowledge_lifecycle import source_preview
    return checked(source_preview,checked(service(request).engine,project),doc)

@router.post("/context")
def context(body:Search,request:Request):
    require_token(request); return checked(service(request).context,body.query,body.project)

@router.delete("/knowledge/{doc}")
def delete_document(doc:str,request:Request,project:str="library"):
    require_token(request); return {"deleted":checked(service(request).engine,project).delete_document(doc)}

@router.post("/knowledge/upload")
async def upload(request:Request,files:List[UploadFile]=File(...),project:str=Form("library")):
    require_token(request)
    if not 1<=len(files)<=32: raise HTTPException(400,"Choose 1–32 files")
    engine=checked(service(request).engine,project); result=[]; total=0
    for file in files:
        raw=await file.read(7*1024*1024+1); await file.close(); total+=len(raw)
        if total>32*1024*1024: raise HTTPException(413,"Batch exceeds 32 MiB")
        if len(raw)>7*1024*1024: result.append({"name":file.filename,"error":"File exceeds 7 MiB"}); continue
        # Uploaded names are labels; never allow them to choose a host path.
        name=Path((file.filename or "document.txt").replace("\\","/")).name
        try:
            with tempfile.TemporaryDirectory(prefix="indra-ingest-",dir=service(request).root) as temporary:
                path=Path(temporary)/name; path.write_bytes(raw)
                doc=await run_in_threadpool(engine.ingest_file,path,"upload")
                result.append({"name":name,**doc})
        except Exception as error: result.append({"name":name,"error":type(error).__name__})
    service(request).audit.append("knowledge.uploaded",{"files":len(files),"succeeded":sum("doc_id" in r for r in result)})
    return {"results":result}

@router.get("/identity")
def identity(request:Request):
    require_token(request); return checked(service(request).identity)

@router.put("/identity")
def save_identity(body:Identity,request:Request):
    require_token(request)
    return checked(service(request).save_identity,body.model_dump(exclude={"revision"}),body.revision)

@router.post("/identity/import/preview")
async def preview_memory_import(request:Request,file:UploadFile=File(...)):
    require_token(request)
    from origo_runtime.personal_memory import MAX_EXPORT_BYTES
    try:
        raw=await file.read(MAX_EXPORT_BYTES+1)
    finally:
        await file.close()
    if len(raw)>MAX_EXPORT_BYTES: raise HTTPException(413,"Memory export exceeds 128 KiB")
    return await run_in_threadpool(checked,service(request).preview_memory_import,raw)

@router.post("/identity/import/commit")
def commit_memory_import(body:MemoryImportReview,request:Request):
    require_token(request)
    return checked(service(request).commit_memory_import,body.id,body.selected,body.revision)

@router.get("/audit")
def audit(request:Request):
    require_token(request); log=service(request).audit
    return {"verification":log.verify(),"events":log.recent(),"limitation":"Keep a checkpoint outside this PC to detect tail deletion or owner-level rewriting."}

@router.get("/audit/checkpoint")
def checkpoint(request:Request):
    require_token(request); return service(request).audit.verify()

def artifact_entries(request,limit=150):
    import os
    from hermes_cli.config import load_config
    from hermes_cli.web_server_files import _managed_files_policy
    from hermes_cli.web_routers.files import _is_sensitive_path
    from app.rag import _is_blocked_filename
    current=service(request)
    product=Path(__file__).resolve().parents[5]
    roots={current.home/"outputs",product/"workspace/outputs",product/"outputs",product/"indra/SIH-26/hermes-agent/outputs"}
    from hermes_cli.web_server_profiles import _profile_scope
    with _profile_scope(request.query_params.get("profile")):
        cwd=load_config().get("terminal",{}).get("cwd")
    if cwd: roots.add(Path(cwd)/"outputs")
    roots.update(Path(p["root"])/"outputs" for p in current.projects())
    policy=_managed_files_policy(request,create_root=False); found={}; seen=0
    for root in roots:
        if not root.is_dir() or root.is_symlink() or root.is_junction(): continue
        for directory,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if not d.startswith(".") and not (Path(directory)/d).is_symlink() and not (Path(directory)/d).is_junction()]
            for name in files:
                seen+=1
                if seen>5000: break
                path=Path(directory)/name
                if path.is_symlink() or path.is_junction() or _is_sensitive_path(path) or _is_blocked_filename(name): continue
                try:
                    real=path.resolve(strict=True); stat=real.stat()
                    if not real.is_relative_to(root.resolve()): continue
                    if policy.locked_root and not real.is_relative_to(policy.locked_root): continue
                    found[str(real)]={"name":name,"path":str(real),"is_directory":False,"size":stat.st_size,"mtime":stat.st_mtime}
                except OSError: continue
            if seen>5000: break
        if seen>5000: break
    # Earlier agent runs saved office deliverables directly in the profile
    # home. Include only those top-level document types, never its private
    # subdirectories, configuration or credential stores.
    for path in current.home.iterdir():
        if path.suffix.lower() not in {".pptx",".ppt",".pdf",".docx",".xlsx",".csv"}:
            continue
        if not path.is_file() or path.is_symlink() or path.is_junction() or _is_sensitive_path(path) or _is_blocked_filename(path.name):
            continue
        try:
            real=path.resolve(strict=True)
            if real.parent!=current.home.resolve(): continue
            if policy.locked_root and not real.is_relative_to(policy.locked_root): continue
            stat=real.stat()
            found[str(real)]={"name":path.name,"path":str(real),"is_directory":False,"size":stat.st_size,"mtime":stat.st_mtime}
        except OSError:
            continue
    return sorted(found.values(),key=lambda e:e["mtime"],reverse=True)[:limit]

@router.get("/artifacts")
def artifacts(request:Request):
    require_token(request); return {"entries":artifact_entries(request)}

@router.get("/artifacts/resolve")
def resolve_artifact(request:Request,path:str):
    require_token(request)
    import os,re
    normalized=path.replace("\\","/").removeprefix("./")
    if normalized.startswith("MEDIA:"): normalized=normalized[6:]
    if os.name=="nt" and re.match(r"^/[A-Za-z]/",normalized):
        normalized=normalized[1]+":"+normalized[2:]
    if len(normalized)>4096 or normalized.startswith("//") or ".." in normalized.split("/") or any(ord(c)<32 for c in normalized):
        raise HTTPException(400,"Invalid artifact path")
    compare=(lambda value:value.casefold()) if os.name=="nt" else (lambda value:value)
    entries=artifact_entries(request,limit=5000)
    wanted=compare(normalized)
    exact=[e for e in entries if compare(e["path"].replace("\\","/"))==wanted or compare(e["path"].replace("\\","/")).endswith("/"+wanted)]
    absolute=bool(re.match(r"^(?:[A-Za-z]:/|/)",normalized))
    if not exact and not absolute:
        exact=[e for e in entries if compare(e["name"])==compare(normalized.rsplit("/",1)[-1])]
    if not exact:
        raise HTTPException(404,"This artifact is unavailable. It may not have been created, or generation may have failed or awaited approval.")
    if len(exact)>1:
        raise HTTPException(409,"More than one artifact has this name. Choose its full path from Artifacts.")
    return {"path":exact[0]["path"]}

@router.get("/artifacts/preview")
def preview_artifact(request:Request,path:str):
    require_token(request)
    source=Path(resolve_artifact(request,path)["path"])
    if source.suffix.lower() not in {".docx",".xlsx"}: raise HTTPException(400,"No document text preview for this type")
    import subprocess,sys,os,json
    worker=Path(__file__).resolve().parents[5]/"origo_runtime/document_extract.py"
    try:
        result=subprocess.run([sys.executable,"-I",str(worker),str(source)],capture_output=True,text=True,encoding="utf-8",timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        data=json.loads(result.stdout)
        if result.returncode or data.get("error"): raise ValueError("Document could not be extracted")
        return {"text":data["text"][:100000]}
    except (ValueError,subprocess.TimeoutExpired) as error: raise HTTPException(422,"Document preview was unavailable") from error
