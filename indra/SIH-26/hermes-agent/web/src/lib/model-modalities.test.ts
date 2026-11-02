import { expect, it } from "vitest";
import { modalityLabels } from "./model-modalities";

it("distinguishes text only from unknown metadata", () => {
  expect(modalityLabels()).toEqual(["Capabilities unknown"]);
  expect(modalityLabels({ input_modalities: ["text"] })).toEqual(["Text only"]);
});
it("labels all media and does not call a tool-less multimodal model text-only", () => {
  expect(modalityLabels({ input_modalities: ["text", "image", "video", "audio"], tools: false })).toEqual(["Multimodal", "Image", "Video", "Audio", "No tools"]);
});
it("identifies specialist APIs", () => {
  expect(modalityLabels({ model_kind: "live", chat_compatible: false })).toContain("live");
});
