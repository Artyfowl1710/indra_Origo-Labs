# Indra Agent Setup & Configuration Guide
*Built by Origo Labs for SIH-26*

Indra is a fully autonomous, offline, privacy-first AI agent swarm designed to run entirely locally. This version features custom branding, local configuration constraints, multi-agent delegation, and file-based RAG—without any cloud dependencies.

---

## 1. System Capabilities & Features

### Core Offline Tools (Fully Unlocked)
Indra operates seamlessly without internet access using built-in local tools:
- **Code Execution (`code_execution`)**: Writes, tests, and runs Python scripts locally.
- **Project Management (`kanban` & `todo`)**: Creates and manages markdown-based Kanban boards and task lists.
- **Background Automation (`cronjob`)**: Schedules local tasks, reminders, and scripts to run on a timer via the `indra gateway`.
- **Context & Vision (`session_search`, `clarify`, `vision`)**: Analyzes past session logs and processes images completely locally using Vision Language Models (VLMs).
- **Persistent Memory (`memory`)**: Automatically learns user preferences and stores them in a local SQLite database for cross-session recall.

### Advanced Capabilities
- **Swarm Delegation (Parallel Agents)**: Using the custom `/trick-delegate` skill, the agent can spawn autonomous parallel sub-agents to tackle multiple tasks at once.
- **Dynamic Routing**: Automatically maps tasks to the best local model. For example, `indra-auto` (Qwen) handles tool execution and logic, while `indra-writer` (Gemma) or `indra-hermes` handles creative generation.
- **Obsidian Vault Integration (Local RAG)**: Instead of a heavy vector database, Indra uses file-based retrieval. It natively navigates your `MyVault` folder, reads your markdown/PDF documents into its context window, and acts as a "Second Brain" to answer questions based strictly on your private data.

## 2. One-Click Installation (Judges/Hackathon Mode)

We have engineered a fully automated installer that will set up the entire ecosystem, download the required offline LLMs, embed the API keys, and configure the environment without any manual intervention.

1. **Extract the ZIP file** to your Desktop (or any preferred location).
2. Right-click `install-indra.ps1` and select **Run with PowerShell**.
   *(Note: This wizard will automatically download the required GGUF models directly from HuggingFace to bypass GitHub file size limits, verify their SHA-256 signatures, and create an Immutable Audit Log).*
3. Once complete, a shortcut named **INDRA Dashboard** will be placed on your Desktop.

---

## 3. Launching Indra

Simply double-click the **INDRA Dashboard** shortcut on your Desktop.

This will automatically:
1. Auto-configure the model routing matrix.
2. Spin up the backend Llama-Swap engine and AI Workbench.
3. Open the Indra Dashboard in your default web browser (`http://127.0.0.1:9119`).

*Note: The first launch may take ~10 seconds for the backend services to fully initialize.*

---

## 5. Usage & Commands

Once the backend is running, open a new terminal and launch the interactive CLI:

```powershell
.\venv\Scripts\indra.exe
```

Launch the browser frontend with:

```powershell
.\start-dashboard.ps1
```

### Useful CLI Commands:
- `/model indra-auto`: Switches the active model to Qwen (Highly recommended for tool execution and Vault operations).
- `/trick-delegate [instructions]`: Forces the model to use the `delegate_task` tool properly to spawn multiple parallel sub-agents.
- `indra gateway`: Run this in a separate terminal if you want your background `cronjob` timers to physically execute.

### Important URLs for Debugging:
- **Indra Web UI:** `http://127.0.0.1:9119`
- **AI Workbench Gateway:** `http://127.0.0.1:8000/ui`
- **Llama-Swap Engine:** `http://127.0.0.1:8100/ui/`
