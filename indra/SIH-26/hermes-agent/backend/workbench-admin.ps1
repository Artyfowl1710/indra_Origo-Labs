$backendRoot = $PSScriptRoot
Push-Location $backendRoot
try {
    & "$backendRoot\venv\Scripts\python.exe" -c 'from dotenv import load_dotenv; load_dotenv(override=True); from server.cli.main import app; app()' @args
} finally { Pop-Location }
