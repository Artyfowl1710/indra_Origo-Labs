import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const driver = vi.hoisted(() => ({ render: vi.fn(), dispose: vi.fn(), release: vi.fn() }));
vi.mock("three", async (importOriginal) => ({
  ...await importOriginal<Record<string, unknown>>(),
  WebGLRenderer: class {
    setPixelRatio() {} setSize() {}
    render = driver.render; dispose = driver.dispose; forceContextLoss = driver.release;
  },
}));
import { mountCompanion } from "./origo-companion-scene.js";

describe("companion resource and motion policy", () => {
  let media: EventTarget & { matches: boolean };
  let page: EventTarget & { hidden: boolean };
  let visibility: (entries: { isIntersecting: boolean }[]) => void;
  let frames: Map<number, FrameRequestCallback>;
  let cleanup: (() => void) | undefined;
  beforeEach(() => {
    vi.clearAllMocks();
    media = Object.assign(new EventTarget(), { matches: false });
    page = Object.assign(new EventTarget(), { hidden: false });
    frames = new Map(); let sequence = 0;
    vi.stubGlobal("window", { devicePixelRatio: 3, matchMedia: () => media });
    vi.stubGlobal("document", page);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { frames.set(++sequence, callback); return sequence; });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback: typeof visibility) { visibility = callback; }
      observe() {} disconnect() {}
    });
  });
  afterEach(() => { cleanup?.(); cleanup = undefined; vi.unstubAllGlobals(); });
  function mount() { cleanup = mountCompanion(new EventTarget() as HTMLCanvasElement); }
  function tick() { const pending = [...frames.values()]; frames.clear(); pending.forEach(callback => callback(performance.now())); }
  it("renders reduced motion once and resumes when the preference changes", () => {
    media.matches = true; mount();
    expect(driver.render).toHaveBeenCalledOnce();
    expect(frames.size).toBe(0);
    media.matches = false; media.dispatchEvent(new Event("change"));
    expect(frames.size).toBe(1);
  });
  it("stops drawing while hidden or offscreen and resumes when visible", () => {
    mount(); page.hidden = true; tick();
    expect(frames.size).toBe(0);
    const count = driver.render.mock.calls.length;
    page.hidden = false; page.dispatchEvent(new Event("visibilitychange"));
    expect(driver.render.mock.calls.length).toBeGreaterThan(count);
    visibility([{ isIntersecting: false }]); tick();
    expect(frames.size).toBe(0);
    visibility([{ isIntersecting: true }]);
    expect(frames.size).toBe(1);
  });
  it("releases the renderer and scheduled work when the welcome screen unmounts", () => {
    mount(); cleanup?.(); cleanup = undefined;
    expect(frames.size).toBe(0);
    expect(driver.dispose).toHaveBeenCalledOnce();
    expect(driver.release).toHaveBeenCalledOnce();
    const count = driver.render.mock.calls.length;
    page.dispatchEvent(new Event("visibilitychange")); media.dispatchEvent(new Event("change"));
    expect(driver.render).toHaveBeenCalledTimes(count);
  });
});
