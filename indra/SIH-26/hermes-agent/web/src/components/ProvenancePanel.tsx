import { useEffect,useState } from "react";
import { workspaceApi } from "@/lib/workspace-api";
export function ProvenancePanel(){
 const [data,setData]=useState<Awaited<ReturnType<typeof workspaceApi.audit>>|null>(null),[error,setError]=useState("");
 const refresh=()=>workspaceApi.audit().then(setData).catch(e=>setError(String(e)));
 useEffect(()=>{void refresh();},[]);
 async function checkpoint(){try{const value=await workspaceApi.checkpoint();const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="indra-audit-checkpoint.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(String(e));}}
 return <section className="indra-provenance"><div className="indra-panel-title"><h2>Signed activity ledger</h2><button onClick={()=>void refresh()}>Verify chain</button><button onClick={()=>void checkpoint()}>Export checkpoint</button></div><p>{data?`${data.verification.valid?"Signatures verified":"Verification failed"} · ${data.verification.count??data.verification.checked} events · SHA-256 + Ed25519`:"Loading provenance…"}</p><p>Tracks observed model, tool and approval events. Payloads are hashed; prompts and API keys are not copied into this ledger. Keep checkpoints elsewhere to detect later deletion or rewriting by the PC owner.</p>{error&&<p role="alert">{error}</p>}<div className="indra-provenance-list">{data?.events.slice(0,30).map(e=><details key={e.seq}><summary><time>{new Date(e.time).toLocaleString()}</time><strong>{e.kind}</strong><span>{[e.payload.provider,e.payload.model,e.payload.tool_name||e.payload.tool].filter(Boolean).join(" · ")}</span></summary><code>{e.hash}</code></details>)}</div></section>;
}
