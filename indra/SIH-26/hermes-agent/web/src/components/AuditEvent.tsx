import { classifyLine } from "@/lib/log-classify";

const STRUCTURED_LINE = /^\s*(\d{4}-\d{2}-\d{2}[ T][\d:,.]+)\s+(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s+(.*)$/;

export function AuditEvent({ line }: { line: string }) {
  const match = STRUCTURED_LINE.exec(line);
  const level = classifyLine(line);
  const message = match?.[3] || line;
  // Normalize only the owned legacy runtime-repair hint. The original entry
  // and its authentication hash remain verbatim in the expanded record.
  const displayMessage = message.includes("linked SQLite") && message.includes("WAL-reset")
    ? message.replace("Hermes-managed installs", "Indra-managed installs")
        .replaceAll("`hermes update`", "`indra update`")
        .replaceAll("`hermes doctor`", "`indra doctor`")
    : message;
  return <details className={`indra-audit-event indra-audit-event--${level}`}>
    <summary>
      <span className="indra-audit-event__time">{match?.[1] || "—"}</span>
      <span className="indra-audit-event__level">{match?.[2] || level}</span>
      <span className="indra-audit-event__message" translate="no">{displayMessage}</span>
    </summary>
    {displayMessage!==message && <p className="text-xs text-muted-foreground">Product label normalized in the summary. The original authenticated log entry is preserved below.</p>}
    <pre>{line}</pre>
  </details>;
}
