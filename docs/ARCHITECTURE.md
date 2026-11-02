# Architecture and diagrams

This document describes the source layout and major interactions for the 1.7.2 baseline. The diagrams are Mermaid and render on GitHub.

## Component diagram

```mermaid
flowchart LR
  subgraph Client
    Desktop[Desktop browser]
    Android[Origo Remote Android WebView]
  end
  subgraph Access
    Local[Loopback HTTP]
    Tailnet[Tailscale Serve HTTPS]
    Login[Remote token login + signed cookie]
  end
  subgraph Origo[Origo FastAPI process]
    Routes[API routes]
    Agent[Agent / harness]
    Policies[Policy + permission queue]
    Rag[RAG + Knowledge Studio]
    State[SQLite store]
    Workspace[Workspace + backups]
    Web[Public web fetch/search]
    Sandbox[Docker sandbox]
    Ext[Skills / optional plugins]
  end
  Model[Configured model endpoint]
  Qdrant[Optional Qdrant]
  Desktop --> Local --> Routes
  Android --> Tailnet --> Login --> Routes
  Routes --> Agent
  Routes --> Rag
  Routes --> State
  Agent --> Policies
  Policies --> Workspace
  Agent --> Web
  Agent --> Sandbox
  Agent --> Ext
  Agent --> Model
  Rag --> State
  Rag -. optional read-only integration .-> Qdrant
```

## Desktop chat sequence

```mermaid
sequenceDiagram
  actor User
  participant UI as Browser UI
  participant API as FastAPI
  participant H as Agent harness
  participant P as Permission queue
  participant M as Model endpoint
  participant S as SQLite/state
  User->>UI: Submit prompt
  UI->>API: Chat request / stream
  API->>H: Start bounded run
  H->>S: Read conversation and policy state
  H->>M: Prompt + allowed context
  M-->>H: Text / tool proposal
  alt Tool needs approval
    H->>P: Create pending permission
    P-->>UI: Await user decision
    User->>UI: Approve or deny
    UI->>API: Permission decision
    API->>P: Resolve decision
  end
  H->>S: Persist run and event records
  H-->>UI: Stream events / final response
```

## Remote Android connection

```mermaid
sequenceDiagram
  actor User
  participant App as Android companion
  participant TS as Tailscale Serve
  participant O as Origo backend
  User->>App: Enter private https://...ts.net endpoint
  App->>TS: HTTPS request over tailnet
  TS->>O: Proxy to loopback-only service
  O-->>App: Redirect to remote login if no valid session
  User->>App: Enter Origo remote token
  App->>O: POST /remote/login
  O-->>App: Host-bound 12h Secure/HttpOnly/SameSite cookie
  App->>O: Subsequent same-origin requests
  O-->>App: Authenticated workstation UI/API
```

## RAG data flow

```mermaid
flowchart TD
  Upload[Upload or index workspace] --> Filter[Type/path/size policy]
  Filter --> Extract[Text extraction + secret scrubbing]
  Extract --> Chunk[Bounded chunks + metadata]
  Chunk --> FTS[SQLite FTS5 lexical index]
  Chunk -. optional explicit embedding endpoint .-> Embed[Dense embeddings]
  Query[User query] --> Lex[Lexical candidate search]
  Query -. optional .-> Dense[Dense candidate search]
  FTS --> Lex
  Embed --> Dense
  Lex --> Fuse[Rank fusion / reranking / dedup]
  Dense --> Fuse
  Fuse --> Cite[Source chunks + citations]
  Cite --> Inspect[User inspects evidence]
  Inspect --> Context[Explicit one-turn Copilot context]
```

## Trust boundaries

1. Model responses and retrieved document content are untrusted input.
2. Browser requests are untrusted; remote requests must satisfy the remote access gate.
3. Workspace paths are constrained, but the process still runs as the current OS user.
4. External URLs are subject to validation, but DNS rebinding/SSRF residual risk remains.
5. Docker is a defense-in-depth boundary; Docker daemon, image, kernel and host configuration remain trusted.
6. Remote access is for one trusted user, not multi-user authorization.
