"""Pinned live Table 8 rerun. Preserves the 25 published requests unchanged.
Install results/final_environment_freeze.txt and npm ci in configs/table8_npm first.
B0 is a conceptual allow-all comparator, never executed against upstream servers.
"""
import argparse, asyncio, hashlib, importlib.metadata, json, os, platform, shutil, subprocess, sys, tempfile, time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from checker import PermissionChecker
from models import ToolCall, Decision
from policy_manager import PolicyManager
from live_outcomes import classify_result
from metrics import confusion_counts, derive_rates
PROFILES=['limited_network','read_only','no_code_exec','approval_gated']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
async def run(args):
 out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
 npm=Path(args.npm_root).resolve()
 entry=npm/'node_modules/@modelcontextprotocol/server-filesystem/dist/index.js'
 package=json.loads((entry.parent.parent/'package.json').read_text())
 assert package['version']=='2026.8.31'
 cases=json.loads((ROOT/'datasets/real_mcp_workflows.json').read_text())
 report={'experiment':'Complete pinned live stdio rerun of Table 8','started_utc':datetime.now(timezone.utc).isoformat(),'n_distinct_calls':len(cases),'executions_per_call_per_profile':1,'b0_note':'Conceptual allow-all; no upstream execution or measured latency','timing':'session.call_tool only; excludes server startup and tool discovery; includes transport, proxy decision and upstream response or denial','environment':{'python':sys.version,'platform':platform.platform(),'mcp':importlib.metadata.version('mcp'),'pydantic':importlib.metadata.version('pydantic'),'node':subprocess.check_output(['node','--version'],text=True).strip(),'npm':subprocess.check_output(['npm','--version'],text=True).strip(),'filesystem_version':package['version'],'filesystem_entry_sha256':sha(entry),'npm_lock_sha256':sha(npm/'package-lock.json')},'source_hashes':{},'profiles':{}}
 for folder in ['src','servers','policies']:
  for p in sorted((ROOT/folder).glob('*')):
   if p.is_file():report['source_hashes'][str(p.relative_to(ROOT))]=sha(p)
 report['source_hashes']['datasets/real_mcp_workflows.json']=sha(ROOT/'datasets/real_mcp_workflows.json')
 report['source_hashes']['scripts/mcp_enforcement_proxy.py']=sha(ROOT/'scripts/mcp_enforcement_proxy.py')
 subprocess.run([sys.executable,'-m','pip','check'],stdout=(out/'pip_check.txt').open('w'),check=True)
 (out/'python_environment.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
 def save(): (out/'report.json').write_text(json.dumps(report,indent=2))
 save()
 for profile in PROFILES:
  # Isolated disposable working copy; no real credentials passed to child servers.
  with tempfile.TemporaryDirectory(prefix='mcp-table8-') as tmp:
   work=Path(tmp)/'workspace'
   shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('.git','results','logs','artifacts','__pycache__','node_modules','.venv*'))
   policy=PolicyManager().load(work/'policies'/f'{profile}.yaml')
   check=PermissionChecker(path_root=work)
   for case in cases:
    if case['server'] in ['terminal','process','env']:
     decision,_=check.evaluate(ToolCall(name=case['tool_name'],arguments=case['arguments']),policy)
     assert decision!=Decision.ALLOW,('Unsafe preflight',profile,case['id'])
   home=Path(tmp)/'home';home.mkdir()
   env={k:v for k,v in os.environ.items() if k in ['PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy']}
   env.update({'HOME':str(home),'PYTHONUNBUFFERED':'1'})
   scripts={'fetch':'real_fetch_server.py','git':'real_git_server.py','terminal':'real_shell_server.py','env':'real_shell_server.py','process':'real_shell_server.py'}
   rows=[];starts={}
   stderr=(out/f'{profile}_stderr.log').open('w')
   async with AsyncExitStack() as stack:
    sessions={}
    for server in ['filesystem',*scripts]:
     upstream=[shutil.which('node'),str(entry),str(work)] if server=='filesystem' else [sys.executable,str(work/'servers'/scripts[server])]
     params=StdioServerParameters(command=sys.executable,args=[str(work/'scripts/mcp_enforcement_proxy.py'),'--policy',str(work/'policies'/f'{profile}.yaml'),'--server-name',server,'--log',str(out/f'{profile}_{server}_audit.jsonl'),'--',*upstream],cwd=str(work),env=env)
     rd,wr=await stack.enter_async_context(stdio_client(params,errlog=stderr))
     session=await stack.enter_async_context(ClientSession(rd,wr))
     init=await asyncio.wait_for(session.initialize(),30)
     tools=await asyncio.wait_for(session.list_tools(),30)
     starts[server]={'initialization':init.model_dump(mode='json',by_alias=True),'tools':[t.name for t in tools.tools]}
     sessions[server]=session
     print(profile,'connected',server,flush=True)
    for case in cases:
     name=case['tool_name']
     if case['server']=='filesystem':name={'list_dir':'list_directory','view_file':'read_file'}.get(name,name)
     start=time.perf_counter()
     try:
      result=await asyncio.wait_for(sessions[case['server']].call_tool(name,case['arguments']),35)
      latency=(time.perf_counter()-start)*1000
      outcome=classify_result(result);receipt=result.model_dump(mode='json',by_alias=True)
     except Exception as exc:
      latency=(time.perf_counter()-start)*1000
      outcome={'authorization':'unknown','execution':'transport_error','error_type':type(exc).__name__};receipt={'error':str(exc)}
     rows.append({'id':case['id'],'server':case['server'],'tool':name,'arguments':case['arguments'],'beneficial':case['beneficial'],'latency_ms':latency,'outcome':outcome,'receipt':receipt})
     print(profile,case['id'],outcome,flush=True)
   stderr.close()
   known=[r for r in rows if r['outcome']['authorization']!='unknown']
   rates=derive_rates(confusion_counts([not r['beneficial'] for r in known],[r['outcome']['authorization']=='allow' for r in known]))
   report['profiles'][profile]={'rates':rates,'known_authorization':len(known),'unknown_outcomes':len(rows)-len(known),'benign_protocol_success':sum(r['beneficial'] and r['outcome']['execution']=='upstream_ok' for r in rows),'latency_mean_ms':sum(r['latency_ms'] for r in rows)/len(rows),'initializations':starts,'details':rows}
   save()
 report['completed_utc']=datetime.now(timezone.utc).isoformat()
 report['complete']=all(p['known_authorization']==25 for p in report['profiles'].values()) and len(report['profiles'])==4
 save()
 if not report['complete']:raise SystemExit('Incomplete authorization coverage; do not substitute into Table 8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--npm-root',default=str(ROOT/'configs/table8_npm'));p.add_argument('--output',default=str(ROOT/'results/table8_pinned_rerun'))
 asyncio.run(run(p.parse_args()))
