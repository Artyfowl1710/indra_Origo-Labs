import { describe, expect, it } from "vitest";
import { VoiceRequestGate } from "./voice-request";

describe("voice request ownership", () => {
  it("cancels in-flight work and invalidates late results on close", () => {
    const gate = new VoiceRequestGate();
    const request = gate.begin();
    expect(request.isCurrent()).toBe(true);
    gate.cancel();
    expect(request.signal.aborted).toBe(true);
    expect(request.isCurrent()).toBe(false);
    gate.cancel();
  });
  it("accepts only the latest recording when requests overlap", async () => {
    const gate = new VoiceRequestGate();
    const first = gate.begin();
    const second = gate.begin();
    const submitted: string[] = [];
    await Promise.all([
      Promise.resolve().then(() => { if (first.isCurrent()) submitted.push("stale"); }),
      Promise.resolve().then(() => { if (second.isCurrent()) submitted.push("latest"); }),
    ]);
    expect(first.signal.aborted).toBe(true);
    expect(submitted).toEqual(["latest"]);
  });
});
