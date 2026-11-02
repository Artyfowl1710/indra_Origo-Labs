import {useEffect,useRef,useState} from "react";
import {loadRecords,type ConversationRecord} from "@/lib/conversation-records";
export function ConversationRecordPanel({chat,profile,active,messages}:{chat:string;profile:string;active:boolean;messages:{role:string;text:string}[]}){
 const [rows,setRows]=useState<ConversationRecord[]>([]),[error,setError]=useState("");const cursor=useRef(0),entries=useRef(new Map<string,ConversationRecord>());
 useEffect(()=>{setRows([]);entries.current.clear();cursor.current=0;if(!chat||!active)return;let canceled=false,busy=false;
  const pull=async()=>{if(busy)return;busy=true;try{for(let page=0;page<20;page++){const result=await loadRecords(chat,profile,cursor.current);if(canceled)return;for(const row of result.entries){entries.current.set(row.id,row);cursor.current=Math.max(cursor.current,row.seq);}if(result.entries.length<200)break;}setRows([...entries.current.values()].sort((a,b)=>a.created.localeCompare(b.created)));setError("");}catch(e){if(!canceled)setError(String(e));}finally{busy=false;}};
  void pull();const timer=setInterval(()=>void pull(),2000);return()=>{canceled=true;clearInterval(timer);};
 },[chat,profile,active]);
 async function download(){
  try{
   // Read a fresh snapshot so the latest saved turn is included between polls.
   const snapshot=new Map<string,ConversationRecord>();let after=0,complete=false;
   for(let page=0;page<1000;page++){
    const result=await loadRecords(chat,profile,after);
    for(const row of result.entries){snapshot.set(row.id,row);after=Math.max(after,row.seq);}
    if(result.entries.length<200){complete=true;break;}
   }
   if(!complete)throw new Error("This record is too large for a browser export.");
   const saved=[...snapshot.values()].sort((a,b)=>a.created.localeCompare(b.created));
   const lines=["# Indra conversation record",`Chat: ${chat}`,"","## Chat messages",...messages.flatMap(row=>[`### ${row.role}`,row.text,""]),"## Voice transcript and action notes",...saved.flatMap(row=>[`### ${row.created} · ${row.kind} · ${row.role}`,`${row.model}${row.provider?` · ${row.provider}`:""} · ${row.source}`,row.text,""])];const blob=new Blob([lines.join("\n\n")],{type:"text/markdown;charset=utf-8"}),url=URL.createObjectURL(blob),anchor=document.createElement("a");anchor.href=url;anchor.download="indra-conversation.md";anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setError("");
  }catch(e){setError(String(e));}
 }
 if(!chat)return null;
 return <details open className="indra-conversation-record"><summary>Conversation record · {rows.length} voice/action entries</summary><p>Saved locally with this chat. Voice transcripts are captured text, not raw audio. Runtime entries record tool and approval activity.</p><button type="button" onClick={download}>Export conversation as Markdown</button>{error&&<p role="alert">{error}</p>}<div className="indra-record-entries">{rows.slice(-100).map(row=><article key={row.id}><p>{new Date(row.created).toLocaleTimeString()} · {row.kind} · {row.model}</p><strong>{row.role==="user"?"You":row.role==="assistant"?"Indra":"Activity"}</strong><p className="indra-record-text" translate="no">{row.text}</p></article>)}</div></details>;
}
