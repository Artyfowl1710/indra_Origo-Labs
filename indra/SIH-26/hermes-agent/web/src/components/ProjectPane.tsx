import { useEffect,useState } from "react";
import { FolderOpen,Plus,RefreshCw,X } from "lucide-react";
import { workspaceApi,type Project,type Job } from "@/lib/workspace-api";
import {canPickFolder,pickProjectFolder} from "@/lib/desktop-workspace";

export function ProjectPane({selected,onSelect}:{selected:string;onSelect:(project:Project|null)=>void}) {
 const [files,setFiles]=useState<{name:string;relative:string;size:number;indexable:boolean}[]>([]),[preview,setPreview]=useState("");
 const [projects,setProjects]=useState<Project[]>([]),[path,setPath]=useState(""),[adding,setAdding]=useState(false),[error,setError]=useState(""),[job,setJob]=useState<Job|null>(null);
 const load=()=>workspaceApi.projects().then(r=>setProjects(r.projects)).catch(e=>setError(String(e)));
 useEffect(()=>{void load();},[]);
 useEffect(()=>{setPreview("");if(selected==="library"||!selected){setFiles([]);return;}workspaceApi.files(selected).then(r=>setFiles(r.files)).catch(e=>setError(String(e)));},[selected,job?.state]);
 useEffect(()=>{if(selected==="library"||!selected)return;const timer=setInterval(()=>{workspaceApi.index(selected).then(setJob).catch(e=>setError(String(e)));},60000);return()=>clearInterval(timer);},[selected]);
 useEffect(()=>{if(!job||!["queued","indexing"].includes(job.state))return;const timer=setInterval(()=>{workspaceApi.job(job.id).then(setJob).catch(e=>setError(String(e)));},1500);return()=>clearInterval(timer);},[job]);
 async function grant(){try{setError("");const value=await workspaceApi.grant("",path);await load();setAdding(false);setPath("");setJob(await workspaceApi.index(value.id));}catch(e){setError(String(e));}}
 return <section className="indra-project-pane">
  <div className="indra-panel-title"><strong><FolderOpen size={15}/> Projects</strong><button type="button" aria-label="Grant project folder access" onClick={()=>{setAdding(true);if(canPickFolder())void pickProjectFolder().then(value=>{if(value)setPath(value);}).catch(e=>setError(String(e)));}}><Plus size={16}/></button></div>
  <p>Choose a project for folder context and local knowledge. Switching starts a new chat.</p>
  <button className={!selected||selected==="library"?"selected":""} onClick={()=>onSelect(null)}>Personal library</button>
  {projects.map(p=><div className="indra-project-row" key={p.id}><button className={selected===p.id?"selected":""} title={p.root} onClick={()=>onSelect(p)}>{p.name}</button><button title="Index new and changed documents" aria-label={`Index ${p.name}`} onClick={()=>workspaceApi.index(p.id).then(setJob).catch(e=>setError(String(e)))}><RefreshCw size={13}/></button><button aria-label={`Revoke ${p.name}`} onClick={()=>{workspaceApi.revoke(p.id).then(()=>{void load();if(selected===p.id)onSelect(null);}).catch(e=>setError(String(e)));}}><X size={13}/></button></div>)}
  {adding&&<div className="indra-project-grant">{canPickFolder()&&<button type="button" onClick={()=>pickProjectFolder().then(value=>{if(value)setPath(value);}).catch(e=>setError(String(e)))}><FolderOpen size={16}/> Choose folder…</button>}<label>Selected folder<input aria-label="Project folder path" value={path} onChange={e=>setPath(e.target.value)} placeholder="Choose a folder or enter its path"/></label><p>Grants read access to this folder for indexing and selects it as the working folder for new chats. Tool actions keep their existing approvals. Credentials and build folders are excluded from indexing.</p><button disabled={!path.trim()} onClick={()=>void grant()}>Grant & index documents</button></div>}
  {job&&<p role="status">{job.state} · {job.done} indexed · {job.skipped} unchanged/unsupported · {job.errors} errors</p>}
  {files.length>0&&<details className="indra-project-files"><summary>{files.length}{files.length===2000?"+":""} project files</summary><div>{files.map(f=><button key={f.relative} title={f.relative} onClick={()=>workspaceApi.preview(selected,f.relative).then(r=>setPreview(r.text)).catch(e=>setError(String(e)))}>{f.relative}<small>{f.indexable?"Knowledge":"File"}</small></button>)}</div></details>}
  {preview&&<details open className="indra-project-preview"><summary>File preview <button onClick={()=>setPreview("")}>Close</button></summary><pre>{preview}</pre></details>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
