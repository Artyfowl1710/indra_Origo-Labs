# Hermes Workbench demo guide

The `indra` command starts Qdrant, llama-swap, and Workbench when needed, then starts Hermes.

## After restarting the PC

1. Wait until Windows has finished starting.
2. Start Docker Desktop and wait until its engine is running when the demo needs code execution.
3. Open a new Windows PowerShell window.
4. Run `indra`.
5. Wait for the `INDRA` prompt and enter your request.

Keep the PowerShell window open. The first reply is slower while the model loads. A quick test is:

```powershell
indra chat -q "Reply DEMO_OK only" --cli
```

## Services

| Service | Address | Purpose |
|---|---|---|
| Workbench API | `http://127.0.0.1:8000/v1` | Endpoint used by Hermes |
| Workbench page | `http://127.0.0.1:8000/ui/` | Local browser interface |
| API documentation | `http://127.0.0.1:8000/docs` | Interactive API reference |
| llama-swap | `http://127.0.0.1:8100` | Loads and swaps GGUF models |
| Qdrant | Not started | The MRPL demo uses local skills and supplied files instead |

These addresses are local to this PC. Public internet access is not enabled.

## Professional model roles

| Model name | Role | Local model |
|---|---|---|
| `indra-auto` | Automatic specialist selection | Routes to one of the models below |
| `indra-general` | General agent and tool use | Qwen 3.5 4B |
| `indra-engineer` | Programming, debugging, APIs, and databases | Qwen 3.5 4B |
| `indra-analyst` | Mathematics, calculations, and logic | Qwen 3.5 4B |
| `indra-writer` | Summaries, rewriting, and concise drafting | Gemma 2 2B |
| `indra-vision` | Image understanding and OCR | Qwen2-VL OCR 2B |

The 4 GB GPU can hold only one model at a time. llama-swap changes models automatically based on the model ID in the request. Switching can take several seconds.

The `indra` launcher gives Hermes a private Docker CLI configuration at
`C:\Users\Kaivalya\AppData\Local\hermes\docker-config`. This avoids permission
problems in the normal user Docker settings while keeping Docker Desktop as the engine.

`indra-auto` is the default. It classifies the latest user request on every turn.
llama-swap unloads the previous model and loads the selected specialist into VRAM:

- Images go to `indra-vision`.
- Coding and technical implementation go to `indra-engineer`.
- Mathematics and calculations go to `indra-analyst`.
- Summaries, translation, and rewriting go to `indra-writer`.
- General and mixed tasks go to `indra-general`.

You can select a professional name explicitly:

```powershell
indra --model indra-engineer chat -q "Debug this Python function" --cli
indra --model indra-analyst chat -q "Solve 3x + 7 = 22" --cli
indra --model indra-writer chat -q "Rewrite this paragraph clearly" --cli
```

Short aliases are also available: `auto`, `general`, `coder`, `maths`, `writer`,
and `ocr`.

Select the OCR model with:

```powershell
indra --model indra-vision chat --image "C:\path\to\image.png" -q "Read all text in this image." --cli
```

The matching `mmproj-prithivmlmods.qwen2-vl-ocr-2b-instruct-vision.gguf`
projector is installed and configured on CPU to fit the 4 GB GPU. For a singular
image request, Workbench removes older image attachments and sends the newest
image to the vision model. Ask to compare “both images” or “all images” when you
want multiple attachments processed together.

## Admin API key

No user key was generated. The existing admin key is used for Hermes, Workbench commands, and API calls. It is stored in:

- `C:\Users\Kaivalya\AppData\Local\hermes\.env`
- `C:\Users\Kaivalya\AppData\Local\hermes\hermes-agent\backend\.env`

Look for `WORKBENCH_API_KEY=...`. Do not publish this value. API clients send it as:

```text
Authorization: Bearer YOUR_WORKBENCH_API_KEY
```

The admin helper reads the key automatically:

```powershell
cd C:\Users\Kaivalya\AppData\Local\hermes\hermes-agent\backend
.\workbench-admin.ps1 status
.\workbench-admin.ps1 models list
```

## Before a demo

```powershell
cd C:\Users\Kaivalya\AppData\Local\hermes\hermes-agent\backend
.\start-backend.ps1
.\workbench-admin.ps1 status
.\workbench-admin.ps1 models list
indra chat -q "Reply DEMO_OK only" --cli
```

Status should say `ok`. The model list contains the four physical model IDs plus the six professional `indra-*` names. Close GPU-heavy applications if loading fails; the active model normally uses about 3.1–3.4 GB VRAM.

## Troubleshooting

If `indra` reports a connection error, run `start-backend.ps1`, check status, and inspect:

```text
data\qdrant-start-error.log
data\llamaswap-start-error.log
data\workbench-start-error.log
data\swap-live.log
data\workbench-live-error.log
```

If switching models stalls, close the current `indra` session and retry. Avoid simultaneous model requests because the GPU is sized for one model.

Qdrant and RAG are disabled for this demonstration. ClickUp is disabled because it needs its own OAuth login. A Hermes update may overwrite the local 16K context-floor adjustment; reapply it if Hermes again reports a 64K requirement.

## MRPL Enterprise Intelligence & Reporting

The local `mrpl-report` skill reads enterprise MRPL records and creates
validated Word, PDF, PowerPoint, or Excel files utilizing sovereign enterprise knowledge.
The format libraries are installed in both the local and Docker environments.

Sample source:

```text
/workspace/MyVault/MRPL_Corporate_Master_Index.md
```

Start the workflow with the skill preloaded:

```powershell
indra chat -s mrpl-report -q "Analyze the MRPL corporate dossier using sovereign knowledge records. Generate a professional Word report and PDF in /workspace/outputs/mrpl-report, then report the verified file paths." --cli
```

Change `Word report and PDF` to `PowerPoint presentation`, `Excel workbook`, or
`Word, PDF, PowerPoint, and Excel` to generate other outputs. Generated files
appear in:

```text
outputs/mrpl-report
```

## Verified

- Qwen, Gemma, Phi, and the OCR model remain registered in Workbench.
- Automatic and professional routes use Qwen, Gemma, and Qwen2-VL. Phi is excluded from routing.
- Qwen, Gemma, and Qwen2-VL returned replies through `indra`; the vision projector is installed.
- Indra created `/root/factorial.py` in Docker, executed it, and verified `factorial(5) = 120`.
- Qwen also used its terminal tool successfully.
- Workbench accepts the admin key and rejects unauthenticated requests.
- Model discovery, chat completions, and embeddings require an admin key; no user key is used.
- Qdrant is not started; the demo does not depend on it.
- llama-swap and Workbench return HTTP 200 health responses.
