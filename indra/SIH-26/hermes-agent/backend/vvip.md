Yes. Here are the exact Hermes-side steps your friend should follow. Assume Hermes is already installed and they're using PowerShell.

1. Go to Hermes
cd "$env:LOCALAPPDATA\hermes\hermes-agent"

Activate the venv if they have one:

.\venv\Scripts\Activate.ps1
2. Set the local terminal backend
hermes config set terminal.backend local

Verify:

hermes config get terminal.backend

It should show:

local
3. Configure Workbench as the model provider

Run:

hermes config set model.default qwen3.5-4b
hermes config set model.provider workbench
hermes config set model.base_url http://127.0.0.1:8000/v1
hermes config set model.api_mode chat_completions

Verify:

hermes config get model

Expected:

default: qwen3.5-4b
provider: workbench
base_url: http://127.0.0.1:8000/v1
api_mode: chat_completions
4. Configure the Workbench provider

The provider should have:

workbench:
  base_url: http://127.0.0.1:8000/v1
  key_env: OPENAI_API_KEY
  model: qwen3.5-4b
  api_mode: chat_completions
  extra_body:
    chat_template_kwargs:
      enable_thinking: false

If they're editing config.yaml, put that under providers:.

5. Set their Workbench API key

They need their own key, not yours:

$env:OPENAI_API_KEY="THEIR_WORKBENCH_KEY"

If they want it permanently:

[Environment]::SetEnvironmentVariable(
    "OPENAI_API_KEY",
    "THEIR_WORKBENCH_KEY",
    "User"
)

Then open a new PowerShell window.

6. Start Hermes
hermes

Test:

who are you?

Then test the important part:

Create test.py that prints the first 10 Fibonacci numbers and run it.

They should see Hermes:

write_file
   ↓
terminal
   ↓
python test.py
   ↓
result
7. One important thing

They do not need to modify Hermes source code.

Your fixes are on the Workbench side:

Hermes
   ↓
your modified Workbench
   ↓
llama-swap
   ↓
llama-server

So the friend's Hermes installation should remain stock.

Only the Hermes configuration above needs changing.

The 131.1K context display can be ignored for the demo; your actual llama-server is currently 28,416.
