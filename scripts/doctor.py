"""Run local service diagnostics without sending an inference prompt."""
import asyncio, json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env', encoding='utf-8-sig')
from app.providers import OpenAICompatibleProvider
from app.diagnostics import diagnose
from app.tools import ensure_workspace

async def main():
    p = OpenAICompatibleProvider()
    report = await diagnose(p, ensure_workspace())
    print('INDRA ORIGO — LOCAL SERVICE DIAGNOSTICS')
    for service in report['services']:
        icon = {'online':'OK', 'reachable':'WARN', 'offline':'OFF', 'not_configured':'SKIP'}.get(service['state'],'?')
        print(f"[{icon:4}] {service['name']:18} {service['latency_ms'] if service['latency_ms'] is not None else '-':>6} ms  {service['detail']}")
    print('\nSummary:', json.dumps(report['summary']))
    kb = report.get('integrations', {}).get('knowledge_search', {})
    print(f"Knowledge retrieval: {kb.get('state', 'unknown')} — {kb.get('detail', '')}")
    print('Optional service failures do not prevent the UI from running.')
if __name__ == '__main__': asyncio.run(main())
