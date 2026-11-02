import { describe, expect, it } from "vitest";
import { chooseDeviceVoice } from "./device-voice";

describe("device speech selection", () => {
  const remote = { name: "Network voice", localService: false };
  const first = { name: "Installed one", localService: true };
  const second = { name: "Installed two", localService: true };
  it("honors an installed voice selection", () => {
    expect(chooseDeviceVoice([remote, first, second], second.name)).toBe(second);
  });
  it("falls back to installed speech when a saved voice is missing or remote", () => {
    expect(chooseDeviceVoice([remote, first], remote.name)).toBe(first);
    expect(chooseDeviceVoice([remote, first], "Removed voice")).toBe(first);
  });
  it("reports unavailable instead of implicitly selecting network speech", () => {
    expect(chooseDeviceVoice([remote], remote.name)).toBeUndefined();
    expect(chooseDeviceVoice([], "")).toBeUndefined();
  });
});
