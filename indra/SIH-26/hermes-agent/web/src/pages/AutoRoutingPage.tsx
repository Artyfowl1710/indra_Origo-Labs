import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, RefreshCw, Route } from "lucide-react";
import { Link } from "react-router";
import { api, type AuxiliaryModelsResponse, type ModelInfoResponse } from "@/lib/api";
import { IndraMetric, IndraPanel, IndraState } from "@/components/IndraSurface";
import {ParallelWorkSettings} from "@/components/ParallelWorkSettings";

export default function AutoRoutingPage() {
  const [assignments, setAssignments] = useState<AuxiliaryModelsResponse | null>(null);
  const [model, setModel] = useState<ModelInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [routing, setRouting] = useState<Awaited<ReturnType<typeof api.getMediaRouting>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    api.getMediaRouting().then(setRouting).catch(() => setRouting(null));
    const [assigned, current] = await Promise.allSettled([api.getAuxiliaryModels(), api.getModelInfo()]);
    if (assigned.status === "fulfilled") setAssignments(assigned.value);
    if (current.status === "fulfilled") setModel(current.value);
    if (assigned.status === "rejected" && current.status === "rejected") setError("Model routing information is unavailable.");
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return <main className="stitch-page indra-product-page">
    <div className="indra-page-heading"><div><span>AUTO ROUTING</span><h1>The right model for the work.</h1><p>See the active model and specialist assignments used by INDRA. Selection for an individual request appears in its live session.</p></div><button type="button" className="indra-icon-action" onClick={() => void refresh()} disabled={loading} aria-label="Refresh routing"><RefreshCw size={18} /></button></div>
    {loading && !assignments && !model && <IndraState title="Loading model assignments…" />}
    {error && <IndraState title="Routing unavailable" description={error} tone="error" action={<button type="button" onClick={() => void refresh()}>Try again</button>} />}
    <ParallelWorkSettings />
    {(assignments || model) && <>
      <div className="indra-metric-grid">
        <IndraPanel title="Current model" description="The configured primary model for this profile."><IndraMetric label="MODEL" value={model?.model || assignments?.main.model || "Unavailable"} hint={model?.provider || assignments?.main.provider || undefined} /></IndraPanel>
        <IndraPanel title="Context" description="The effective context reported by the model endpoint."><IndraMetric label="TOKENS" value={model?.effective_context_length ? model.effective_context_length.toLocaleString() : "Unavailable"} /></IndraPanel>
      </div>
      <IndraPanel title="Specialist assignments" description="Configured roles from the live model assignments endpoint." action={<Link className="indra-text-link" to="/models">Manage models <ArrowUpRight size={16} /></Link>}>
        {assignments?.tasks.length ? <div className="indra-assignment-list">{assignments.tasks.map(task => <div key={task.task} className="indra-assignment-row"><span className="indra-assignment-icon"><Route size={18} /></span><div><strong>{task.task.replaceAll("_", " ")}</strong><small>{task.provider || "Provider unavailable"}</small></div><span>{task.model || "Not assigned"}</span></div>)}</div> : <IndraState title="No specialist assignments available" description="Assign specialist models from the Model Registry." />}
      </IndraPanel>
      <IndraPanel title="Media routing preview" description={routing?.policy || "Keep a capable main model; otherwise use a configured reader or the cheapest compatible model with known pricing on the same provider."}>
        <p className="text-sm text-muted-foreground">This preview does not make a generation request or verify quota. Cost comparisons estimate 1,000 input and 300 output tokens; media charges and actual usage can differ. Live and specialist APIs require their own integration.</p>
        {routing?.routes.map(route => <div className="indra-assignment-row" key={route.modality}><strong>{route.modality}</strong><span>{route.available ? `${route.provider} / ${route.model}` : "No automatic route"}</span><small>{route.reason}</small></div>)}
      </IndraPanel>
    </>}
  </main>;
}
