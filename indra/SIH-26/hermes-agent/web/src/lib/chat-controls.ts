export type ControlResult={notice:string;message?:string};
type Gateway={request<T>(method:string,params:Record<string,unknown>):Promise<T>};
/** Route explicit controls before attachment/RAG assembly; never send them as prose. */
export async function chatControl(gateway:Gateway,session:string,text:string):Promise<ControlResult|null>{
 const match=/^\/(goal|title)(?:\s+([\s\S]*))?$/i.exec(text.trim());
 if(!match)return null;
 const arg=match[2]?.trim()??"";
 if(match[1].toLowerCase()==="title"){
  const result=await gateway.request<{title?:string;pending?:boolean}>("session.title",{session_id:session,...(arg?{title:arg}:{})});
  if(result.pending)throw Error("Chat title is not yet saved");
  window.dispatchEvent(new Event("indra:conversation-recorded"));
  return {notice:result.title?`Chat: ${result.title}`:"This chat has no title yet."};
 }
 const result=await gateway.request<{type?:string;notice?:string;output?:string;message?:string}>("command.dispatch",{session_id:session,name:"goal",arg});
 if(result.type==="send"){
  if(!result.message)throw Error("Goal kickoff did not include a request");
  return {notice:result.notice??"Continuing toward your goal",message:result.message};
 }
 return {notice:result.output??result.notice??"Goal updated"};
}
