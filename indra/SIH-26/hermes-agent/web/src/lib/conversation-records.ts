import {fetchJSON} from "./api";
export interface RecordInput {id:string;kind:"voice"|"note";role:"user"|"assistant"|"note";text:string;model:string;provider:string}
export interface ConversationRecord extends Omit<RecordInput,"kind"> {kind:"voice"|"note"|"action";seq:number;source:"client"|"runtime";created:string}
const path=(chat:string,profile:string)=>`/api/indra/workspace/conversations/${encodeURIComponent(chat)}/records?profile=${encodeURIComponent(profile)}`;
export const loadRecords=(chat:string,profile:string,after=0)=>fetchJSON<{entries:ConversationRecord[]}>(path(chat,profile)+`&after=${after}`);
export const saveRecords=(chat:string,profile:string,entries:RecordInput[])=>fetchJSON(path(chat,profile),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({entries})});

/** Bind writes to the chat that opened voice, even if navigation changes later. */
export function conversationSaver(chat:string,profile:string,persistChat:()=>Promise<void>){
 let persisted=false,persisting:Promise<void>|undefined;
 return async(entries:RecordInput[])=>{
  await saveRecords(chat,profile,entries);
  if(!persisted){
   persisting??=persistChat().then(()=>{persisted=true;}).finally(()=>{persisting=undefined;});
   await persisting;
  }
  window.dispatchEvent(new Event("indra:conversation-recorded"));
 };
}

/** Coalesce transcription fragments into durable turns without losing older turns. */
export class VoiceJournal {
 private pending=new Map<string,RecordInput>();private turn?:RecordInput;private timer?:ReturnType<typeof setTimeout>;private sending?:Promise<void>;
 private save:(entries:RecordInput[])=>Promise<unknown>;private failure:(message:string)=>void;private model:string;private provider:string;
 constructor(save:(entries:RecordInput[])=>Promise<unknown>,model:string,provider:string,failure:(message:string)=>void){this.save=save;this.model=model;this.provider=provider;this.failure=failure;}
 speech(role:"user"|"assistant",text:string){
  if(!text)return;
  if(this.turn?.role!==role)this.turn={id:crypto.randomUUID(),kind:"voice",role,text:"",model:this.model,provider:this.provider};
  let remaining=this.turn!.text+text;
  while(remaining.length>16000){this.queue({...this.turn!,text:remaining.slice(0,16000)});remaining=remaining.slice(16000);this.turn={...this.turn!,id:crypto.randomUUID(),text:""};}
  this.turn!.text=remaining;this.queue({...this.turn!});
 }
 note(text:string){this.queue({id:crypto.randomUUID(),kind:"note",role:"note",text:text.slice(0,16000),model:this.model,provider:this.provider});}
 private queue(entry:RecordInput){this.pending.set(entry.id,entry);clearTimeout(this.timer);this.timer=setTimeout(()=>{void this.flush().catch(()=>{});},400);}
 hasPending(){return this.pending.size>0;}
 async flush():Promise<void>{
  clearTimeout(this.timer);
  if(this.sending){await this.sending;return this.flush();}
  if(!this.pending.size)return;
  const batch=[...this.pending.values()].slice(0,50);for(const entry of batch)this.pending.delete(entry.id);
  this.sending=(async()=>{try{await this.save(batch);}catch(error){for(const entry of batch)if(!this.pending.has(entry.id))this.pending.set(entry.id,entry);this.failure("Conversation record could not be saved. Retry saving before closing voice.");throw error;}finally{this.sending=undefined;}})();
  await this.sending;
  if(this.pending.size)await this.flush();
 }
}
