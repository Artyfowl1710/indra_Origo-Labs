import {useEffect,useState} from "react";
import {api} from "@/lib/api";
import {useProfileScope} from "@/contexts/useProfileScope";
import {IndraPanel} from "@/components/IndraSurface";

export function ParallelWorkSettings(){
  const {profile}=useProfileScope();
  return <ParallelSettings key={profile || "default"} profile={profile || undefined}/>;
}
function ParallelSettings({profile}:{profile?:string}){
  const [limit,setLimit]=useState(3),[loading,setLoading]=useState(true),[ready,setReady]=useState(false),[saving,setSaving]=useState(false),[message,setMessage]=useState("");
  useEffect(()=>{
    let active=true;
    api.getConfig(profile).then(config=>{
      if(!active)return;
      const delegation=config.delegation as {max_concurrent_children?:number}|undefined;
      setLimit(delegation?.max_concurrent_children ?? 3);
      setReady(true);
    }).catch(()=>{if(active)setMessage("Could not load parallel task settings.");})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[profile]);
  async function save(){
    setSaving(true);setMessage("");
    try{
      await api.saveConfig({delegation:{max_concurrent_children:limit}},profile);
      setMessage("Saved for new delegated tasks.");
    }catch{setMessage("Could not save. Your existing settings are unchanged.");}
    finally{setSaving(false);}
  }
  return <IndraPanel title="Parallel agent work" description="Let the agent delegate independent tasks concurrently using its existing tools.">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-2 text-sm" htmlFor="indra-parallel-limit">Maximum concurrent child agents
        <select id="indra-parallel-limit" className="rounded-lg border border-input bg-card text-card-foreground px-3 py-2" value={limit}
          disabled={loading || saving} onChange={event=>setLimit(Number(event.target.value))}>
          {[...new Set([1,2,3,4,limit])].sort((a,b)=>a-b).map(value=><option key={value} value={value}>{value}</option>)}
        </select>
      </label>
      <button type="button" className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm" disabled={loading || saving || !ready} onClick={()=>void save()}>{saving?"Saving…":"Save parallel limit"}</button>
    </div>
    <p className="mt-3 text-sm text-muted-foreground">API providers can serve independent children concurrently, subject to their rate limits and cost. The delegation toolset must be enabled; saving this limit does not start agents or grant permissions.</p>
    <p className="mt-2 text-sm text-muted-foreground">The built-in local GPU router currently queues one inference at a time to protect model switching and memory. Child agents can still overlap non-model work. GPU continuous batching needs separate memory and throughput acceptance; more slots do not guarantee lower latency.</p>
    {message && <p role="status" className="mt-2 text-sm">{message}</p>}
  </IndraPanel>;
}
