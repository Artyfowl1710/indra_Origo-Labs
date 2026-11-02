import { fetchJSON } from "./api";
const base="/api/indra/workspace";
const json=(method:string,body?:unknown):RequestInit=>({method,headers:{"Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});
export interface Project {id:string;name:string;root:string}
export interface Identity {name:string;instructions:string;share_across_profiles:boolean;interests?:string;facts?:string[];use_in_requests?:boolean;setup_complete?:boolean;revision?:string}
export interface MemoryImport {id:string;revision:string;expires:number;candidates:{id:string;text:string;blocked:boolean;reasons:string[]}[]}
const memoryPath=(path:string,profile?:string)=>base+path+(profile===undefined?"":"?profile="+encodeURIComponent(profile));
export interface Governance {family:string;version:string;owner:string;effective_date:string;review_due:string;status:"unreviewed"|"current"|"superseded";superseded_by:string;revision:string;warnings:string[]}
export interface Document {doc_id:string;filename:string;chunk_count:number;embedding_indexed:boolean;source:string;governance:Governance;safety?:{version:number;quarantined:boolean;rules:string[]}}
export interface ReviewDigest {issues:{kind:string;owner:string;warnings?:string[];documents:{doc_id:string;filename:string;governance:Governance}[]}[];scanned_documents:number;total_documents:number;bounded:boolean;method:string;delivery:string}
export interface Knowledge {status:{documents:number;chunks:number;searchable_chunks?:number;semantic_search_active:boolean;quarantined_documents?:number};documents:Document[];embedding:{model:string;offline:boolean;installed:boolean;resident:boolean;model_bytes:number}}
export interface Job {id:string;project:string;state:string;done:number;skipped:number;errors:number;total:number;details?:{file:string;error:string}[]}
export interface Evidence {context:string;citations:{id:string;filename:string;chunk:number;governance?:Governance}[];mode:string}
const collectionPath=(path:string,project:string,profile?:string)=>base+path+"?project="+encodeURIComponent(project)+(profile===undefined?"":"&profile="+encodeURIComponent(profile));
export const workspaceApi={
 artifacts:()=>fetchJSON<{entries:import("./api").ManagedFileEntry[]}>(base+"/artifacts"),
 resolveArtifact:(path:string)=>fetchJSON<{path:string}>(base+"/artifacts/resolve?path="+encodeURIComponent(path)),
 previewArtifact:(path:string)=>fetchJSON<{text:string}>(base+"/artifacts/preview?path="+encodeURIComponent(path)),
 files:(project:string)=>fetchJSON<{files:{name:string;relative:string;size:number;indexable:boolean}[];limit:number}>(base+"/projects/"+encodeURIComponent(project)+"/files"),
 preview:(project:string,path:string)=>fetchJSON<{text:string}>(base+"/projects/"+encodeURIComponent(project)+"/preview?path="+encodeURIComponent(path)),
 projects:(profile?:string)=>fetchJSON<{projects:Project[]}>(memoryPath("/projects",profile)),
 grant:(name:string,root:string)=>fetchJSON<{id:string}>(base+"/projects",json("POST",{name,root})),
 revoke:(project:string)=>fetchJSON(base+"/projects/"+encodeURIComponent(project),json("DELETE")),
 index:(project:string)=>fetchJSON<Job>(base+"/projects/"+encodeURIComponent(project)+"/index",json("POST")),
 job:(id:string)=>fetchJSON<Job>(base+"/jobs/"+encodeURIComponent(id)),
 knowledge:(project="library",profile?:string)=>fetchJSON<Knowledge>(collectionPath("/knowledge",project,profile)),
 reviewDigest:(project:string,profile:string)=>fetchJSON<ReviewDigest>(collectionPath("/knowledge/review-digest",project,profile)),
 sourcePreview:(doc:string,project:string,profile:string)=>fetchJSON<{text:string;truncated:boolean;notice:string}>(collectionPath("/knowledge/"+encodeURIComponent(doc)+"/source",project,profile)),
 reviewDocument:(doc:string,value:Governance,project:string,profile:string)=>fetchJSON<Governance>(collectionPath("/knowledge/"+encodeURIComponent(doc)+"/review",project,profile),json("PUT",value)),
 search:(query:string,project="library",profile?:string)=>fetchJSON<{results:{citation_id:string;filename:string;text:string;score:number;governance?:Governance}[];retrieval_mode:string}>(base+"/knowledge/search"+(profile===undefined?"":"?profile="+encodeURIComponent(profile)),json("POST",{query,project})),
 context:(query:string,project="library",profile?:string)=>fetchJSON<Evidence>(base+"/context"+(profile===undefined?"":"?profile="+encodeURIComponent(profile)),json("POST",{query,project})),
 upload:(files:File[],project="library",profile?:string)=>{const body=new FormData(); files.forEach(f=>body.append("files",f));body.append("project",project);return fetchJSON<{results:({name:string;error?:string;doc_id?:string;safety?:Document["safety"]})[]}>(collectionPath("/knowledge/upload",project,profile),{method:"POST",body});},
 deleteDocument:(id:string,project="library",profile?:string)=>fetchJSON(collectionPath("/knowledge/"+encodeURIComponent(id),project,profile),json("DELETE")),
 identity:(profile?:string)=>fetchJSON<Identity>(memoryPath("/identity",profile)),
 saveIdentity:(identity:Identity,profile?:string)=>fetchJSON<Identity>(memoryPath("/identity",profile),json("PUT",identity)),
 previewMemoryImport:(file:File,profile:string)=>{const body=new FormData();body.append("file",file);return fetchJSON<MemoryImport>(memoryPath("/identity/import/preview",profile),{method:"POST",body});},
 commitMemoryImport:(review:MemoryImport,selected:string[],profile:string)=>fetchJSON<Identity>(memoryPath("/identity/import/commit",profile),json("POST",{id:review.id,revision:review.revision,selected})),
 audit:()=>fetchJSON<{verification:{valid:boolean;count:number;checked?:number;head:string;public_key:string};events:{seq:number;time:string;kind:string;hash:string;payload:{model?:string;provider?:string;tool?:string;tool_name?:string;session?:string}}[];limitation:string}>(base+"/audit"),
 checkpoint:()=>fetchJSON<Record<string,unknown>>(base+"/audit/checkpoint"),
};
