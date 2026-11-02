import {useEffect, useRef, useState} from "react";
import {useProfileScope} from "@/contexts/useProfileScope";
import {workspaceApi, type Identity, type MemoryImport} from "@/lib/workspace-api";
const fingerprint=(value:Identity)=>JSON.stringify(value);

export function PersonalMemory() {
  const {profile} = useProfileScope();
  return <MemoryEditor key={profile} profile={profile}/>;
}

function MemoryEditor({profile, initial, onDone}: {profile:string; initial?:Identity; onDone?:()=>void}) {
  const [value,setValue] = useState<Identity|undefined>(initial);
  const [notice,setNotice] = useState("");
  const [busy,setBusy] = useState(false);
  const [review,setReview] = useState<MemoryImport>();
  const [selected,setSelected] = useState<string[]>([]);
  const [savedValue,setSavedValue] = useState(initial?fingerprint(initial):"");
  const dirty=!!value&&fingerprint(value)!==savedValue;
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    if (!initial) workspaceApi.identity(profile).then(result => {if(alive.current){setValue(result);setSavedValue(fingerprint(result));}}).catch(error => {if(alive.current)setNotice(String(error));});
    return () => {alive.current = false;};
  }, [profile,initial]);
  async function action(task:()=>Promise<void>) {
    setBusy(true); setNotice("");
    try {await task();} catch(error) {if(alive.current)setNotice(String(error));}
    finally {if(alive.current)setBusy(false);}
  }
  async function save(skip=false) {
    if(!value)return;
    const saved = await workspaceApi.saveIdentity({...value,setup_complete:true,...(skip?{use_in_requests:false}: {})},profile);
    if(!alive.current)return;
    setValue(saved);setSavedValue(fingerprint(saved));setReview(undefined);setNotice("Saved. Applies to future requests; existing chat history stays unchanged.");
    onDone?.();
  }
  function download() {
    if(!value)return;
    const blob=new Blob([JSON.stringify({memories:value.facts??[]},null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob),link=document.createElement("a");
    link.href=url;link.download="indra-personal-memories.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <section className="indra-personal-memory" aria-label="Personal memory">
    <h2>{onDone?"Welcome to Indra.":"Make Indra yours."}</h2>
    <p>{onDone?"A little context helps Indra work your way. Every field is optional. ":""}Stored on this PC. If you allow personal context in requests, your selected model receives it—including a cloud model. You can change this here any time.</p>
    {!value?<p role="status">{notice||"Loading personal memory…"}</p>:<fieldset disabled={busy}>
      <label>Your preferred name<input autoComplete="off" value={value.name} maxLength={80} onChange={e=>setValue({...value,name:e.target.value})}/></label>
      <label>Interests<input value={value.interests??""} maxLength={300} placeholder="Research, coding, music…" onChange={e=>setValue({...value,interests:e.target.value})}/></label>
      <label>Preferences and working style<textarea value={value.instructions} maxLength={2000} placeholder="How should Indra work with you?" onChange={e=>setValue({...value,instructions:e.target.value})}/></label>
      <label><input type="checkbox" checked={value.use_in_requests??false} onChange={e=>setValue({...value,use_in_requests:e.target.checked})}/> Include this personal context in future model requests</label>
      <label><input type="checkbox" checked={value.share_across_profiles} onChange={e=>setValue({...value,share_across_profiles:e.target.checked})}/> Sync personal details with other opted-in profiles on this PC</label>
      <p className="indra-memory-help">Sharing does not sync cloud accounts or grant file access. Request consent stays separate for each profile.</p>
      {(value.facts?.length??0)>0&&<div><h3>Reviewed memories · {value.facts!.length}/20</h3><ul>{value.facts!.map((fact,index)=><li key={index}><span>{fact}</span><button type="button" aria-label={"Remove memory "+(index+1)} onClick={()=>setValue({...value,facts:value.facts!.filter((_,i)=>i!==index)})}>Remove</button></li>)}</ul></div>}
      <div className="indra-memory-actions"><button type="button" onClick={()=>void action(()=>save())}>{busy?"Saving…":onDone?"Save and continue":"Save personal memory"}</button>
      {onDone&&<button type="button" onClick={()=>void action(()=>save(true))}>Skip for now</button>}</div>
      {!onDone&&<>
        <hr/><h3>Bring your memories with you</h3>
        <p>Choose a UTF-8 text file (one fact per line) or a JSON memories list, up to 128 KiB. Export saved memories from your other assistant first. Nothing is sent to a model during import. Save edits above before choosing a file.</p>
        <label className="indra-memory-file">Review a memory export<input type="file" disabled={dirty} accept=".txt,.md,.json,text/plain,application/json" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void action(async()=>{if(file.size>131072)throw new Error("Memory export exceeds 128 KiB");const result=await workspaceApi.previewMemoryImport(file,profile);if(alive.current){setReview(result);setSelected([]);}});}}/></label>
        <button type="button" disabled={!value.facts?.length} onClick={download}>Export reviewed memories</button>
        {review&&<div className="indra-memory-review"><h3>Review before importing</h3><p>Choose only facts you want Indra to remember. Checks are conservative heuristics, not a guarantee. Blocked entries cannot be imported. Review expires after 15 minutes.</p>
          {review.candidates.map(item=><label key={item.id}><input type="checkbox" disabled={item.blocked} checked={selected.includes(item.id)} onChange={e=>setSelected(ids=>e.target.checked?[...ids,item.id]:ids.filter(id=>id!==item.id))}/><span>{item.text}{item.blocked&&<small> Quarantined: {item.reasons.join(", ")}</small>}</span></label>)}
          <div className="indra-memory-actions"><button type="button" disabled={!selected.length||dirty} onClick={()=>void action(async()=>{const result=await workspaceApi.commitMemoryImport(review,selected,profile);if(alive.current){setValue(result);setSavedValue(fingerprint(result));setReview(undefined);setNotice("Selected memories imported. Request consent is unchanged.");}})}>Import selected ({selected.length})</button><button type="button" onClick={()=>setReview(undefined)}>Cancel review</button></div>
        </div>}
      </>}
      {notice&&<p role="status">{notice}</p>}
    </fieldset>}
  </section>;
}

export function FirstRunMemory() {
  const {profile}=useProfileScope();
  return <FirstRunForProfile key={profile} profile={profile}/>;
}

function FirstRunForProfile({profile}:{profile:string}) {
  const [initial,setInitial]=useState<Identity>();
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    let canceled=false;
    workspaceApi.identity(profile).then(value=>{
      // Existing users keep their current flow; preferences remain editable in Runtime.
      if(!canceled&&!value.setup_complete&&!value.name&&!value.instructions&&!value.facts?.length)setInitial(value);
    }).catch(()=>{});
    return()=>{canceled=true;};
  },[profile]);
  useEffect(()=>{if(initial)dialog.current?.showModal();},[initial]);
  if(!initial)return null;
  return <dialog ref={dialog} className="indra-memory-onboarding" aria-label="Welcome to Indra" onCancel={()=>setInitial(undefined)}>
    <MemoryEditor profile={profile} initial={initial} onDone={()=>{dialog.current?.close();setInitial(undefined);}}/>
  </dialog>;
}
