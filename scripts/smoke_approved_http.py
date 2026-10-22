"""One live authorization/transport probe, retaining prior attempts.
Proxy environment is forwarded explicitly because MCP's default child env omits it.
"""
import asyncio,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from live_outcomes import classify_result
async def run():
    env={k:v for k,v in os.environ.items() if k in {'PATH','LANG','SSL_CERT_FILE','SSL_CERT_DIR','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'}}
    p=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/serve_approved_http.py'),'--manifest',str(ROOT/'configs/approved_http_route_reference.json'),'--log',str(ROOT/'results/trusted_contract_live_audit.jsonl')],env=env)
    async with stdio_client(p) as (rd,wr):
        async with ClientSession(rd,wr) as s:
            init=await s.initialize();listing=await s.list_tools()
            result=await asyncio.wait_for(s.call_tool('http_request',{'host':'docs.python.org','path':'/3/'}),30)
            report={'scope':'One positive live MCP HTTP request; not a task-completion benchmark','arguments':{'host':'docs.python.org','path':'/3/'},'outcome':classify_result(result),'initialization':init.model_dump(mode='json',by_alias=True),'tools':listing.model_dump(mode='json',by_alias=True),'receipt':result.model_dump(mode='json',by_alias=True)}
            path=ROOT/'results/trusted_contract_live_smoke.json'
            if path.exists():
                prior=json.loads(path.read_text());report['previous_attempts']=prior.pop('previous_attempts',[])+[prior]
            path.write_text(json.dumps(report,indent=2)+'\n');print(report['outcome'])
asyncio.run(run())
