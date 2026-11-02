# Architecture and trust boundaries


```text
Native desktop shell (Electron, isolated renderer)
  └─ owned loopback backend (Python)
      ├─ project grants / approvals / goals
      ├─ knowledge extraction → compact local embedding/index
      ├─ agent orchestration → configured API or local model endpoint
      ├─ tools → scoped files / approved execution / optional connectors
      └─ artifacts + conversation state + provenance ledger
Phone clients → authenticated messaging gateway / private dashboard path
```

The desktop owns backend startup and cleanup. Packaged runtime paths are separate from per-user profile paths. It does not require the judge to open a web page or start two servers manually. The renderer uses isolated context, disabled Node integration and a constrained native folder-picker bridge.

The model is not a trusted operating-system principal. Tool calls still pass through configured approvals and scopes. Retrieved content is data, not policy. Provider calls cross a network trust boundary; private phone sharing has its own authentication boundary. Optional local inference moves model execution to a local server but does not eliminate tool risk.

Main code areas: `origo-desktop`, `origo_runtime`, and the imported agent/workbench under `indra/SIH-26/hermes-agent`. Internal compatibility identifiers are retained intentionally. See [development](development.md) for running and testing the source.
