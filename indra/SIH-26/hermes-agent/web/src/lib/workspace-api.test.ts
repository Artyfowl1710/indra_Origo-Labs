import {afterEach,describe,expect,it,vi} from "vitest";
import {workspaceApi,type MemoryImport,type Governance} from "./workspace-api";
import {fetchJSON} from "./api";
vi.mock("./api",()=>({fetchJSON:vi.fn(async()=>({}))}));
afterEach(()=>vi.clearAllMocks());
describe("profile-bound personal memory requests",()=>{
 it("binds document reviews and digests to the original collection and profile",async()=>{
  const value:Governance={family:"Policy",version:"2",owner:"Fleet",effective_date:"",review_due:"",status:"current",superseded_by:"",revision:"reviewed-content-revision",warnings:[]};
  await workspaceApi.reviewDocument("document",value,"project id","original-profile");
  const [url,init]=vi.mocked(fetchJSON).mock.calls[0];
  expect(url).toBe("/api/indra/workspace/knowledge/document/review?project=project%20id&profile=original-profile");
  expect(JSON.parse(String(init?.body)).revision).toBe(value.revision);
  await workspaceApi.reviewDigest("library","");
  expect(vi.mocked(fetchJSON).mock.calls[1][0]).toBe("/api/indra/workspace/knowledge/review-digest?project=library&profile=");
 });
 it("keeps the explicitly selected profile on reads and writes",async()=>{
  await workspaceApi.identity("work & research");
  expect(vi.mocked(fetchJSON).mock.calls[0][0]).toBe("/api/indra/workspace/identity?profile=work%20%26%20research");
  await workspaceApi.saveIdentity({name:"Asha",instructions:"",share_across_profiles:false,revision:"previous-revision"},"");
  const [url,init]=vi.mocked(fetchJSON).mock.calls[1];
  expect(url).toBe("/api/indra/workspace/identity?profile=");
  expect(JSON.parse(String(init?.body)).revision).toBe("previous-revision");
 });
 it("sends only selected candidate IDs and the reviewed revision on commit",async()=>{
  const review:MemoryImport={id:"preview",revision:"reviewed-revision",expires:100,candidates:[{id:"0",text:"A private fact",blocked:false,reasons:[]}]};
  await workspaceApi.commitMemoryImport(review,["0"],"original-profile");
  const [url,init]=vi.mocked(fetchJSON).mock.calls[0];
  expect(url).toContain("?profile=original-profile");
  expect(JSON.parse(String(init?.body))).toEqual({id:"preview",selected:["0"],revision:"reviewed-revision"});
 });
});
