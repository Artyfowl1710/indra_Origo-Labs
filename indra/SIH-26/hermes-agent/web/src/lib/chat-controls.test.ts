import {describe,it,expect,vi} from "vitest";
import {chatControl} from "./chat-controls";
import {BASETEN_HACKATHON} from "./provider-presets";
describe("chat control forwarding",()=>{
 it("preserves goal contracts and returns only the backend's kickoff request",async()=>{
  const request=vi.fn().mockResolvedValue({type:"send",notice:"Goal set",message:"Build the fixture"});
  const text="/goal Build the fixture\nverify: test suite passes\nboundaries: project only";
  expect(await chatControl({request},"live-chat",text)).toEqual({notice:"Goal set",message:"Build the fixture"});
  expect(request).toHaveBeenCalledWith("command.dispatch",{session_id:"live-chat",name:"goal",arg:text.slice(6)});
 });
 it("does not turn ordinary prose into a command and keeps status display-only",async()=>{
  const request=vi.fn().mockResolvedValue({type:"exec",output:"Paused"});
  expect(await chatControl({request},"chat","Explain /goal to me")).toBeNull();expect(request).not.toHaveBeenCalled();
  expect(await chatControl({request},"chat","/goal status")).toEqual({notice:"Paused"});
 });
 it("uses the exact hackathon model entitlement",()=>{expect(BASETEN_HACKATHON.model).toBe("meta-models/muse-spark-open-1026");expect(new URL(BASETEN_HACKATHON.base_url).hostname).toBe("inference.baseten.co");});
});
