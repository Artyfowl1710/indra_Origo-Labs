import {describe,it,expect} from "vitest";
import {pcm16,liveSetup,liveToolResponse} from "./live-voice";
describe("Live audio transport",()=>{
 it("uses sequential tools for 3.1 and omits unsupported response scheduling",()=>{const call={id:"1",name:"search_knowledge"};expect(liveSetup("gemini-3.1-flash-live-preview").setup.tools[0].functionDeclarations[0]).not.toHaveProperty("behavior");for(const model of ["gemini-3.1-flash-live-preview","gemini-3.8-live-extended-thinking"])expect(liveToolResponse(model,call,{}).toolResponse.functionResponses[0]).not.toHaveProperty("scheduling");expect(liveToolResponse("gemini-2.5-flash-native-audio-preview-12-2025",call,{}).toolResponse.functionResponses[0].scheduling).toBe("INTERRUPT");});
 it("downsamples to mono PCM16 at 16 kHz with clamping and little endian",()=>{const bytes=pcm16(new Float32Array([1,1,1,-1,-1,-1]),48000);expect([...bytes]).toEqual([255,127,0,128]);});
 it("preserves the resumption handle and enables thinking only for thinking models",()=>{const thinking=liveSetup("gemini-3.8-live-extended-thinking","resume-1");expect(thinking.setup.sessionResumption).toEqual({handle:"resume-1"});expect(thinking.setup.generationConfig.thinkingConfig).toEqual({thinkingLevel:"MEDIUM"});expect(liveSetup("gemini-3.8-live").setup.generationConfig).not.toHaveProperty("thinkingConfig");});
 it("advertises read-only Knowledge without granting computer actions",()=>{expect(liveSetup("gemini-3.8-live").setup.tools[0].functionDeclarations.map(v=>v.name)).toEqual(["search_knowledge"]);});
});
