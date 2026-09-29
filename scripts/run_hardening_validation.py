"""Live stdio output/side-effect validation; controlled fixture, not an LLM benchmark."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from live_outcomes import classify_result

@asynccontextmanager
async def session(base, profile, tag):
    audit=base/f'{tag}_audit.jsonl'; receipts=base/f'{tag}_receipts.jsonl'
    spec={'command':sys.executable,'args':[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--policy',str(ROOT/'policies'/f'{profile}.yaml'),'--log',str(audit),'--server-name','validation','--',sys.executable,str(ROOT/'servers/validation_server.py'),str(base),str(receipts)]}
    c={'mcpServers':{'validation':spec}}
    files=[ROOT/'scripts/mcp_enforcement_proxy.py',*(ROOT/'src').glob('*.py'),ROOT/'policies'/f'{profile}.yaml',ROOT/'servers/validation_server.py',ROOT/'scripts/enforced_launcher.py']
    m={'interpreter_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),'approved_config':c,'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    # Fixture provisioning only; production manifest is administrator-provisioned.
    cp=base/f'{tag}.json';cp.write_text(json.dumps(c));mp=base/f'{tag}_manifest.json';mp.write_text(json.dumps(m))
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/enforced_launcher.py'),'--config',str(cp),'--manifest',str(mp),'--server','validation'],cwd=str(ROOT))
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as client:
            await client.initialize()
            yield client,audit,receipts

def rows(path): return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
def body(result): return ''.join(getattr(x,'text','') for x in result.content)

async def run():
    checks=[];artifacts={}
    def check(name, ok):
        checks.append({'check':name,'passed':bool(ok)})
        if not ok: raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='mcp-hardening-') as td:
        base=Path(td);(base/'a.txt').write_text('alpha');(base/'b.txt').write_text('beta')
        async with session(base,'limited_network','limited') as (c,a,r):
            check('tool discovery over actual MCP transport',len((await c.list_tools()).tools)==4)
            x=await c.call_tool('read_file',{'path':str(base/'a.txt')})
            y=await c.call_tool('read_file',{'path':str(base/'b.txt')})
            check('benign two-read workflow final output',not x.isError and not y.isError and body(x)+'|'+body(y)=='alpha|beta')
            x=await c.call_tool('write_file',{'path':str(base/'out.txt'),'content':'blocked'})
            check('denial uses protocol isError and proxy metadata',x.isError and classify_result(x)['authorization']=='deny' and classify_result(x)['execution']=='not_forwarded')
            check('denied write has no side effect',not (base/'out.txt').exists())
            check('denied write has no upstream receipt',len(rows(r))==2)
            x=await c.call_tool('read_file',{'path':str(base/'missing.txt')})
            check('upstream error preserved and distinguished from denial',x.isError and 'No such file' in body(x) and classify_result(x)['authorization']=='allow' and classify_result(x)['execution']=='upstream_error')
            check('all four routed calls audited',len(rows(a))==4)
            check('only three allowed calls received upstream',len(rows(r))==3)
        artifacts['limited_network']={'audit':rows(a),'upstream_receipts':rows(r)}
        async with session(base,'no_code_exec','write') as (c,a,r):
            x=await c.call_tool('write_file',{'path':str(base/'out.txt'),'content':'verified output'})
            y=await c.call_tool('read_file',{'path':str(base/'out.txt')})
            check('benign write-read workflow output and disk content',not x.isError and not y.isError and body(y)=='verified output' and (base/'out.txt').read_text()=='verified output')
            (base/'link.txt').symlink_to(base/'a.txt')
            x=await c.call_tool('write_file',{'path':str(base/'link.txt'),'content':'modified'})
            check('execution boundary blocks symlink write',x.isError and (base/'a.txt').read_text()=='alpha')
        artifacts['no_code_exec']={'audit':rows(a),'upstream_receipts':rows(r)}
        async with session(base,'approval_gated','ask') as (c,a,r):
            x=await c.call_tool('write_file',{'path':str(base/'ask.txt'),'content':'blocked'})
            check('ASK defaults to denial without upstream execution',x.isError and not (base/'ask.txt').exists() and not rows(r))
        artifacts['approval_gated']={'audit':rows(a),'upstream_receipts':rows(r)}
        crash_failed=False
        try:
            async with session(base,'read_only','crash') as (c,a,r):
                await c.list_tools()
                result=await asyncio.wait_for(c.call_tool('read_text_file',{'path':str(base/'a.txt')}),5)
                crash_failed=result.isError
        except Exception:
            crash_failed=True
        check('upstream crash produces failure, no successful response',crash_failed and any(x['tool']=='read_crash' for x in rows(base/'crash_receipts.jsonl')))
        artifacts['crash']={'audit':rows(base/'crash_audit.jsonl'),'upstream_receipts':rows(base/'crash_receipts.jsonl')}
    return {'passed':all(x['passed'] for x in checks),'checks':checks,'artifacts':artifacts,'scope':'Controlled local stdio fixture; two benign executed workflows, denial/error/symlink/crash checks; no OS confinement or autonomous-agent benchmark.', 'environment':{'python':sys.version,'platform':platform.platform(),'mcp':importlib.metadata.version('mcp'),'anyio':importlib.metadata.version('anyio')}}

if __name__=='__main__':
    result=asyncio.run(run())
    out=ROOT/'results/hardening_validation.json';out.write_text(json.dumps(result,indent=2))
    print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'output':str(out)},indent=2))
