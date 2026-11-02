import {fetchJSON} from "./api";
export function transcribeVoice(dataUrl:string,mime:string,profile="",signal?:AbortSignal,connection?:{provider:string;model:string}){return fetchJSON<{ok:boolean;transcript:string;provider?:string}>(`/api/indra/voice/transcribe?profile=${encodeURIComponent(profile)}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({data_url:dataUrl,mime_type:mime,...connection}),signal});}
/** Dictation uses recorded audio, not browser speech-recognition services. */
export class AudioDictation {
 private recorder?:MediaRecorder;private stream?:MediaStream;private chunks:Blob[]=[];private size=0;private canceled=false;private timer?:ReturnType<typeof setTimeout>;private request=new AbortController();
 private profile:string;private done:(text:string)=>void;private status:(value:boolean)=>void;private error:(message:string)=>void;
 constructor(profile:string,done:(text:string)=>void,status:(value:boolean)=>void,error:(message:string)=>void){this.profile=profile;this.done=done;this.status=status;this.error=error;}
 isRecording(){return this.recorder?.state==="recording";}
 async start(){try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});if(this.canceled){stream.getTracks().forEach(t=>t.stop());return;}this.stream=stream;
  const mime=["audio/webm;codecs=opus","audio/webm","audio/mp4"].find(value=>MediaRecorder.isTypeSupported(value));
  this.recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);
  this.recorder.ondataavailable=e=>{this.size+=e.data.size;if(this.size>8*1024*1024){this.cancel();this.error("Voice recording exceeds 8 MiB. Try a shorter recording.");}else if(e.data.size)this.chunks.push(e.data);};
  this.recorder.onstop=()=>{this.release();if(!this.canceled)void this.finish();};
  this.recorder.onerror=()=>{this.cancel();this.error("Microphone recording failed. Check device permissions.");};
  this.recorder.start(250);this.status(true);this.timer=setTimeout(()=>this.stop(),60000);
 }catch(error){this.cancel();this.error(error instanceof Error?error.message:"Microphone unavailable.");}}
 stop(){if(this.recorder?.state==="recording")this.recorder.stop();}
 private release(){clearTimeout(this.timer);const stream=this.stream;this.stream=undefined;stream?.getTracks().forEach(t=>t.stop());this.status(false);}
 private async finish(){try{const blob=new Blob(this.chunks,{type:this.recorder?.mimeType||"audio/webm"});if(blob.size<100)return;const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsDataURL(blob);});if(this.canceled)return;const response=await transcribeVoice(data,blob.type.split(";")[0],this.profile,this.request.signal);if(!this.canceled&&response.transcript?.trim())this.done(response.transcript.trim());}catch(error){if(!this.canceled)this.error(error instanceof Error?error.message:"Voice transcription failed.");}}
 cancel(){this.canceled=true;this.request.abort();this.stop();this.release();this.chunks=[];}
}
