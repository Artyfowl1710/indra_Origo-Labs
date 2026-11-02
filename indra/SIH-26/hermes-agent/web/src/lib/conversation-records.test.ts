import {afterEach,describe,it,expect,vi} from "vitest";
import {VoiceJournal,conversationSaver,type RecordInput} from "./conversation-records";
vi.mock("./api",()=>({fetchJSON:vi.fn(async()=>({ok:true}))}));
afterEach(()=>vi.useRealTimers());
describe("voice conversation recording",()=>{
 it("coalesces fragments without losing either speaker or earlier turns",async()=>{vi.useFakeTimers();const saved:RecordInput[]=[];const save=vi.fn(async(rows:RecordInput[])=>{saved.push(...rows);});const journal=new VoiceJournal(save,"model","provider",vi.fn());journal.speech("user","Hello ");journal.speech("user","world");journal.speech("assistant","Hi");await journal.flush();expect(saved.map(r=>r.text)).toEqual(["Hello world","Hi"]);expect(saved.map(r=>r.role)).toEqual(["user","assistant"]);});
 it("preserves long utterances in separate bounded records",async()=>{vi.useFakeTimers();const saved:RecordInput[]=[];const journal=new VoiceJournal(async rows=>{saved.push(...rows);},"model","provider",vi.fn());journal.speech("user","x".repeat(20000));await journal.flush();expect(saved.map(r=>r.text).join("")).toHaveLength(20000);expect(saved.every(r=>r.text.length<=16000)).toBe(true);});
 it("keeps failed writes for retry and does not overwrite newer text",async()=>{vi.useFakeTimers();let fail=true;const saved:RecordInput[]=[];const journal=new VoiceJournal(async rows=>{if(fail)throw Error("offline");saved.push(...rows);},"model","provider",vi.fn());journal.speech("user","First");await expect(journal.flush()).rejects.toThrow();expect(journal.hasPending()).toBe(true);journal.speech("user"," updated");fail=false;await journal.flush();expect(saved[0].text).toBe("First updated");expect(journal.hasPending()).toBe(false);});
 it("persists the bound chat once, retries failed metadata, and announces saved records",async()=>{
  const {fetchJSON}=await import("./api");let fail=true;const persist=vi.fn(async()=>{if(fail)throw Error("offline");});
  const dispatch=vi.fn();vi.stubGlobal("window",{dispatchEvent:dispatch});
  try{const save=conversationSaver("original-chat","original-profile",persist);
   await expect(save([])).rejects.toThrow("offline");expect(dispatch).not.toHaveBeenCalled();fail=false;
   await save([]);await save([]);expect(persist).toHaveBeenCalledTimes(2);expect(dispatch).toHaveBeenCalledTimes(2);
   expect(vi.mocked(fetchJSON).mock.calls.at(-1)?.[0]).toContain("original-chat/records?profile=original-profile");
  }finally{vi.unstubAllGlobals();}
 });
});
