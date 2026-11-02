import {it,expect} from "vitest";
import {renderToStaticMarkup} from "react-dom/server";
import {AuditEvent} from "./AuditEvent";

it("normalizes the owned legacy label in the summary without rewriting authenticated history",()=>{
  const line="2026-11-02 12:00:00 WARNING linked SQLite is vulnerable to WAL-reset; Hermes-managed installs: `hermes update`; See `hermes doctor` [AUTH-SHA256:abc123]";
  const html=renderToStaticMarkup(<AuditEvent line={line}/>);
  const summary=html.split("</summary>")[0];
  expect(summary).toContain("Indra-managed installs");
  expect(summary).not.toContain("Hermes-managed installs");
  expect(html).toContain("<pre>"+line+"</pre>");
  expect(html).toContain("original authenticated log entry");
});
it("preserves model names, source paths and other diagnostic content",()=>{
  const html=renderToStaticMarkup(<AuditEvent line="INFO model NousResearch/Hermes-3 loaded from /source/hermes-agent"/>);
  expect(html).toContain("NousResearch/Hermes-3");
  expect(html).toContain("/source/hermes-agent");
});
