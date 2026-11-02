import { useState } from "react";
import { api } from "@/lib/api";
import { Input } from "@nous-research/ui/ui/components/input";
import { Button } from "@nous-research/ui/ui/components/button";
import {BASETEN_HACKATHON} from "@/lib/provider-presets";

export function SelfHostedEndpoint({onSaved}:{onSaved?:()=>void|Promise<void>}={}) {
  const [name, setName] = useState("My Ollama");
  const [base, setBase] = useState("http://127.0.0.1:11434/v1");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [media, setMedia] = useState<string[]>([]);
  const [activate, setActivate] = useState(false);
  const [voiceEnabled,setVoiceEnabled]=useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(save: boolean) {
    setBusy(true); setMessage("");
    const body = { name, base_url: base, model, ...(key ? { api_key: key } : {}), input_modalities: ["text", ...media], make_default: activate, voice_enabled:voiceEnabled };
    try {
      if (save) { await api.saveCustomEndpoint(body); setKey(""); setMessage(activate ? "Endpoint saved and selected. Start a new conversation to use it." : "Endpoint saved. Select it in Change model."); await onSaved?.(); }
      else { const result = await api.validateCustomEndpoint(body); setModels(result.models); if (!model && result.models[0]) setModel(result.models[0]); setMessage(result.ok ? `Connected. ${result.models.length} models discovered.` : result.message); }
    } catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  return <section className="border border-border bg-card p-4 space-y-3">
    <h2 className="font-semibold">Connect a model endpoint</h2>
    <button type="button" className="rounded border px-3 py-2 text-sm" onClick={()=>{setName(BASETEN_HACKATHON.name);setBase(BASETEN_HACKATHON.base_url);setModel(BASETEN_HACKATHON.model);setMedia(["image","video","audio"]);setVoiceEnabled(true);}}>Use Baseten · Muse Spark Open · Hackathon</button>
    <p className="text-xs text-muted-foreground">Hackathon keys require the model ending in -1026. You can enter a different model ID for another entitlement.</p>
    <p className="text-sm text-muted-foreground">Ollama: http://127.0.0.1:11434/v1 · llama.cpp: http://127.0.0.1:8080/v1. Local servers usually need no key. For a protected server, enter the key configured by its owner. Use HTTPS for remote credentials.</p>
    <div className="grid gap-3 md:grid-cols-2">
      <label>Name<Input value={name} onChange={e => setName(e.target.value)} /></label>
      <label>API base URL<Input value={base} onChange={e => setBase(e.target.value)} /></label>
      <label>Model ID<Input list="self-hosted-models" value={model} onChange={e => setModel(e.target.value)} placeholder="Test connection to discover models" /><datalist id="self-hosted-models">{models.map(m => <option key={m} value={m} />)}</datalist></label>
      <label>API key (optional)<Input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} placeholder="Leave blank for an unprotected local server" /></label>
    </div>
    <p className="text-xs text-muted-foreground">Declare only inputs the loaded model and server actually accept. This endpoint uses the OpenAI-compatible chat protocol.</p>
    <div className="flex gap-4 flex-wrap">{["image", "video", "audio"].map(m => <label key={m}><input type="checkbox" checked={media.includes(m)} onChange={e => setMedia(e.target.checked ? [...media, m] : media.filter(v => v !== m))} /> {m}</label>)}</div>
    <label className="block text-sm"><input type="checkbox" checked={activate} onChange={e => setActivate(e.target.checked)} /> Select as main model after saving</label>
    <label className="block text-sm"><input type="checkbox" checked={voiceEnabled} onChange={e=>setVoiceEnabled(e.target.checked)}/> Offer this model in Voice mode</label>
    {voiceEnabled&&<p className="text-xs text-muted-foreground">Text-response models use your connected transcription service and device speech. This does not require a native realtime-audio API.</p>}
    <div className="flex gap-2"><Button disabled={busy || !base} onClick={() => void run(false)}>Test connection</Button><Button disabled={busy || !base || !name || !model} onClick={() => void run(true)}>Save endpoint</Button></div>
    {message && <p role="status" className="text-sm">{message}</p>}
  </section>;
}
