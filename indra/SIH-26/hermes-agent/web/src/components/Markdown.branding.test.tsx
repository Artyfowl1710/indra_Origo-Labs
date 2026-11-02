import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Markdown } from "./Markdown";

describe("conversation content survives product branding", () => {
  it("preserves executable names, paths, environment variables and provider IDs", () => {
    const html = renderToStaticMarkup(<Markdown content={'Use `hermes_cli` with `HERMES_HOME` in `~/.hermes/config.yaml`. Model: `NousResearch/Hermes-3-Llama-3.1-8B`.'} />);
    for (const value of ["hermes_cli", "HERMES_HOME", "~/.hermes/config.yaml", "NousResearch/Hermes-3-Llama-3.1-8B"]) {
      expect(html).toContain(value);
    }
  });
  it("preserves upstream links and factual references rather than changing their attribution", () => {
    const html = renderToStaticMarkup(<Markdown content="[Hermes documentation](https://hermes-agent.nousresearch.com/docs/)" />);
    expect(html).toContain('href="https://hermes-agent.nousresearch.com/docs/"');
    expect(html).toContain("Hermes documentation");
  });
});
