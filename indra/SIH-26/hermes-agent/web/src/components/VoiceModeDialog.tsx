import {useEffect,useRef,useState} from "react";
import {createPortal} from "react-dom";
import {Mic,MicOff,Square,X,VolumeX} from "lucide-react";
import {ConversationModeModal} from "./ConversationModeModal";
import {LiveVoice,voiceStatus,type VoiceStatus,type VoiceOption} from "@/lib/live-voice";
import {workspaceApi} from "@/lib/workspace-api";
import {fetchJSON} from "@/lib/api";
import {VoiceJournal,type RecordInput} from "@/lib/conversation-records";

type Props={isOpen:boolean;onClose:()=>void;onSendMessage:(text:string)=>Promise<void>;lastAssistantMessage?:string;isModelBusy:boolean;profile?:string;project?:string;onRecord?:(entries:RecordInput[])=>Promise<unknown>};
export function VoiceModeDialog(props:Props){
 const {isOpen,profile="",project="library"}=props;
 const [exportNotice,setExportNotice]=useState(false);
 useEffect(()=>{if(isOpen){try{setExportNotice(localStorage.getItem(`indra-voice-export-notice-v1:${profile}`)!=="seen");}catch{setExportNotice(true);}}},[isOpen,profile]);
 const [view,setView]=useState<"selector"|"harness"|"custom">("selector"),[settings,setSettings]=useState<VoiceStatus>(),[selection,setSelection]=useState(""),[error,setError]=useState(""),[status,setStatus]=useState("Ready"),[active,setActive]=useState(false),[muted,setMuted]=useState(false),[transcript,setTranscript]=useState<{role:"user"|"assistant";text:string}[]>([]),[recording,setRecording]=useState(true),[reply,setReply]=useState(""),[replyBusy,setReplyBusy]=useState(false);
 const client=useRef<LiveVoice|null>(null),dialog=useRef<HTMLDivElement>(null),lastRequest=useRef(""),journal=useRef<VoiceJournal|null>(null),recordEnabled=useRef(true),history=useRef<{role:string;text:string}[]>([]),turnRequest=useRef<AbortController|null>(null);
 const options:VoiceOption[]=settings?.options??(settings?.models??[]).map(model=>({id:"google:"+model,provider:"google",model,label:model,transport:"gemini-live",configured:settings?.configured??false}));
 const selected=options.find(option=>option.id===selection)??options.find(option=>option.configured)??options[0];
 const note=(text:string)=>{if(recordEnabled.current)journal.current?.note(text);};
 const flush=()=>{void journal.current?.flush().catch(()=>{});};
 const stop=()=>{if(client.current)note("Voice call ended");client.current?.stop();client.current=null;turnRequest.current?.abort();setActive(false);setMuted(false);setStatus("Stopped");flush();};
 const close=()=>{stop();void(async()=>{try{await journal.current?.flush();props.onClose();}catch{/* Keep unsaved entries and the retry control visible. */}})();};
 const codingVoice=async()=>{stop();try{await journal.current?.flush();}catch{return;}if(props.onRecord)journal.current=new VoiceJournal(props.onRecord,"coding agent","harness",setError);setView("harness");};
 useEffect(()=>{if(!isOpen){setView("selector");return;}let canceled=false;setError("");setSettings(undefined);void voiceStatus(profile).then(value=>{if(!canceled)setSettings(value);}).catch(e=>{if(!canceled)setError(String(e));});return()=>{canceled=true;client.current?.stop();client.current=null;turnRequest.current?.abort();flush();setActive(false);};},[isOpen,profile,project]);
 useEffect(()=>{if(!isOpen||view!=="selector")return;const previous=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;document.body.style.overflow="hidden";const frame=requestAnimationFrame(()=>dialog.current?.querySelector<HTMLButtonElement>("button")?.focus());
  const key=(event:KeyboardEvent)=>{if(event.key==="Escape")close();if(event.key!=="Tab")return;const nodes=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),select,a[href],input')??[]);if(!nodes.length)return;if(!dialog.current?.contains(document.activeElement)){event.preventDefault();nodes[0].focus();}else if(event.shiftKey&&document.activeElement===nodes[0]){event.preventDefault();nodes.at(-1)?.focus();}else if(!event.shiftKey&&document.activeElement===nodes.at(-1)){event.preventDefault();nodes[0].focus();}};
  const hidden=()=>{if(document.hidden&&client.current){client.current.mute(true);setMuted(true);note("Microphone muted while app was in the background");}};
  document.addEventListener("keydown",key);document.addEventListener("visibilitychange",hidden);return()=>{cancelAnimationFrame(frame);document.body.style.overflow=overflow;document.removeEventListener("keydown",key);document.removeEventListener("visibilitychange",hidden);previous?.focus();};},[isOpen,view,props.onClose]);
 function speech(role:"user"|"assistant",text:string){if(recordEnabled.current)journal.current?.speech(role,text);setTranscript(rows=>{const last=rows.at(-1);const next=last?.role===role?[...rows.slice(0,-1),{role,text:(last.text+text).slice(-16000)}]:[...rows,{role,text}];if(role==="user")lastRequest.current=next.at(-1)!.text;return next.slice(-20);});}
 async function start(){
  if(!selected)return;
  try{await journal.current?.flush();}catch{return;}
  if(props.onRecord)journal.current=new VoiceJournal(props.onRecord,selected.model,selected.provider,setError);
  note("Voice session started");setError("");setTranscript([]);history.current=[];lastRequest.current="";setReply("");
  if(selected.transport==="chat-speech"){setView("custom");return;}
  setActive(true);const voice=new LiveVoice(selected.model,profile,{status:setStatus,error:message=>{setError(message);setActive(false);note("Voice connection reported an error");flush();},search:query=>workspaceApi.context(query,project,profile),transcript:speech,event:note});client.current=voice;
  try{await voice.start();}catch(e){setError(e instanceof Error?e.message:String(e));setActive(false);flush();}
 }
 async function customTurn(text:string){
  if(!selected)return;speech("user",text);setReplyBusy(true);const request=new AbortController();turnRequest.current=request;
  try{const result=await fetchJSON<{text:string}>(`/api/indra/voice/turn?profile=${encodeURIComponent(profile)}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider:selected.provider,model:selected.model,text,project,history:history.current.slice(-20)}),signal:request.signal});if(request.signal.aborted)return;history.current.push({role:"user",text},{role:"assistant",text:result.text});speech("assistant",result.text);setReply(result.text);note("Voice response completed");flush();}finally{if(!request.signal.aborted)setReplyBusy(false);}
 }
 if(!isOpen)return null;
 if(view!=="selector")return <ConversationModeModal {...props} onClose={close} profile={profile} voiceConnection={view==="custom"&&selected?{provider:selected.provider,model:selected.model}:undefined} onBack={()=>{stop();setView("selector");}} onSendMessage={view==="custom"?customTurn:async text=>{speech("user",text);note("Request sent to coding agent");flush();await props.onSendMessage(text);}} lastAssistantMessage={view==="custom"?reply:props.lastAssistantMessage} isModelBusy={view==="custom"?replyBusy:props.isModelBusy}/>;
 return createPortal(<div ref={dialog} className="indra-voice-dialog fixed inset-0 z-[150] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" role="dialog" aria-modal="true" aria-label="Indra voice conversation"><div className="indra-live-panel">
  <header className="indra-live-head"><div><p>INDRA · ORIGO LABS</p><h2>Voice conversation</h2></div><button aria-label="Close voice mode" onClick={close}><X/></button></header>
  <p className="indra-live-intro">A little less typing. More room to think.</p>
  <div className="indra-live-columns">
   <section className={`indra-live-stage${active&&!muted?" is-active":""}${muted?" is-muted":""}`} aria-label="Voice connection status">
    <div className="indra-live-orb" aria-hidden="true"><span/>{muted?<MicOff/>:<Mic/>}</div>
    <div role="status" aria-live="polite" className="indra-live-status">{status}</div>
    <p>{active?(muted?"Your microphone is paused.":"End call to disconnect."):"Start when you’re ready."}</p>
   </section>
   <section className="indra-live-settings" aria-label="Voice settings">
    <label>Model<select aria-label="Voice model" value={selected?.id??""} disabled={active} onChange={e=>setSelection(e.target.value)}>{options.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
    <p>{settings?.quota_notice??"The selected connection's quotas and session limits apply."}</p>
    {selected&&!selected.configured&&<p role="alert">Configure a voice connection in <a className="underline" href="/system">Runtime</a>.</p>}
    <label className="indra-live-record"><input type="checkbox" checked={recording} onChange={e=>{recordEnabled.current=e.target.checked;setRecording(e.target.checked);flush();}}/> Save transcript and activity to this chat</label>
    <p>Audio goes to your selected speech connection after you start. End call stops capture and playback.</p>
   </section>
  </div>
  <div className="indra-live-controls">{!active?<button className="indra-live-primary" disabled={!selected?.configured} onClick={()=>void start()}><Mic/>Start voice</button>:<><button onClick={()=>{client.current?.mute(!muted);setMuted(!muted);note(muted?"Microphone unmuted":"Microphone muted");}}>{muted?<MicOff/>:<Mic/>}{muted?"Unmute":"Mute"}</button><button onClick={()=>{client.current?.interrupt();note("Voice playback interrupted");}}><VolumeX/>Stop playback</button><button onClick={stop}><Square/>End call</button></>}</div>
  {exportNotice&&<aside className="indra-voice-export-notice indra-live-notice"><p>Find transcripts and activity in Chat → Settings → Conversation &amp; export. You choose whether new voice entries are saved.</p><button type="button" onClick={()=>{try{localStorage.setItem(`indra-voice-export-notice-v1:${profile}`,"seen");}catch{}setExportNotice(false);}}>Got it</button></aside>}
  {error&&<p role="alert" className="indra-live-error">{error}{journal.current?.hasPending()&&<button onClick={flush}>Retry saving</button>}</p>}
  <div className="indra-live-transcript" aria-label="Live voice transcript">{transcript.map((row,index)=><p key={index}><strong>{row.role==="user"?"You":"Indra"}</strong><span>{row.text}</span></p>)}</div>
  <footer className="indra-live-footer"><button disabled={active||!lastRequest.current||props.isModelBusy} onClick={()=>{note("Request sent to coding agent");flush();void props.onSendMessage(lastRequest.current).catch(e=>setError(String(e)));}}>Send last request to coding agent</button><button disabled={active} onClick={()=>void codingVoice()}>Use coding agent voice instead</button></footer>
  <p className="indra-live-privacy">Records stay local without raw audio. Computer actions use the coding agent and its approvals.</p>
 </div></div>,document.body);
}
