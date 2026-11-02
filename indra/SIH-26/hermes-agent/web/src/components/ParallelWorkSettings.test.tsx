// @vitest-environment jsdom
import {act} from "react";
import {createRoot} from "react-dom/client";
import {afterEach,expect,it,vi} from "vitest";
const mocks=vi.hoisted(()=>({getConfig:vi.fn(),saveConfig:vi.fn(),profile:"work"}));
vi.mock("@/lib/api",()=>({api:mocks}));
vi.mock("@/contexts/useProfileScope",()=>({useProfileScope:()=>({profile:mocks.profile})}));
import {ParallelWorkSettings} from "./ParallelWorkSettings";
let container:HTMLDivElement|undefined;
let root:ReturnType<typeof createRoot>|undefined;
afterEach(async()=>{if(root)await act(async()=>root!.unmount());container?.remove();vi.clearAllMocks();});
async function mount(){
  container=document.createElement("div");document.body.append(container);
  root=createRoot(container);
  await act(async()=>root!.render(<ParallelWorkSettings/>));
}
it("changes only the delegation cap in the selected profile and starts no agents",async()=>{
  mocks.getConfig.mockResolvedValue({delegation:{max_concurrent_children:2,subagent_auto_approve:false},security:{untrusted_content_guard:true}});
  mocks.saveConfig.mockResolvedValue({ok:true});
  await mount();
  const select=container!.querySelector("select")!;
  expect(select.value).toBe("2");
  await act(async()=>{select.value="4";select.dispatchEvent(new Event("change",{bubbles:true}));});
  await act(async()=>container!.querySelector("button")!.click());
  expect(mocks.saveConfig).toHaveBeenCalledWith({delegation:{max_concurrent_children:4}},"work");
  expect(container!.textContent).toContain("Saved for new delegated tasks.");
});
it("refuses saving an assumed default when settings cannot be loaded",async()=>{
  mocks.getConfig.mockRejectedValue(new Error("offline"));
  await mount();
  expect(container!.querySelector("button")!.disabled).toBe(true);
  expect(mocks.saveConfig).not.toHaveBeenCalled();
});
