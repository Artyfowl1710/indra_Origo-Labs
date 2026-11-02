/**
 * Central brand configuration for the INDRA dashboard.
 *
 * All user-visible product name, tagline, descriptor, organisation, and
 * renamed navigation labels are sourced from here.  Change values in this
 * file to update the visible branding across the entire dashboard.
 *
 * IMPORTANT: Do NOT hardcode "INDRA", the tagline, or "Origo Labs" in
 * component files.  Import BRAND / BRAND_LABELS from this module instead.
 *
 * Internal/technical identifiers (API paths, localStorage keys, env vars,
 * import names, package names, backend references) remain "hermes" — only
 * user-facing text is controlled here.
 */

export const BRAND = {
  name: "Indra",
  fullName: "Indra by Origo Labs",
  descriptor: "Sovereign Intelligence Workbench",
  tagline: "Intelligence Within Your Perimeter.",
  organisation: "Origo Labs",
  browserTitle: "Indra · Origo Labs",
  browserDescription:
    "Indra by Origo Labs is a local-first AI workspace with your choice of models.",
} as const;

export const BRAND_LABELS = {
  commandCenter: "Command Center",
  operations: "Operations",
  knowledgeVault: "Knowledge Vault",
  modelRegistry: "Model Registry",
  auditTrail: "Audit Trail",
  automation: "Automation",
  capabilities: "Capabilities",
  extensions: "Extensions",
  toolConnectors: "Tool Connectors",
  integrations: "Integrations",
  eventHooks: "Event Hooks",
  restartRuntime: "Restart Runtime",
  runtimeStatus: "Runtime Status",
  updateProduct: "Update Indra",
  runtimeConsole: "Origo Console",
} as const;
