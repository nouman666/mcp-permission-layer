"""Pinned live rerun; fixed 25 requests, isolated synthetic filesystem, 3 repeats.
Malicious commands/URLs must be denied by a preflight before any live forwarding.
No user credentials or remote attack endpoints are passed to upstream processes.
"""
import asyncio, copy, hashlib, importlib.metadata, json, os, platform, shutil, statistics, sys, tempfile, time
from contextlib import AsyncExitStack
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src')]
from checker import PermissionChecker
from policy_manager import PolicyManager
from models import ToolCall, Decision
from live_outcomes import classify_result

async def run(fs_entry, node):
 cases=json.loads((ROOT/'datasets/real_mcp_workflows.json').read_text())
 report={'experiment':'fresh live rerun of fixed RM-001..RM-025 requests','repetitions':3,'metrics':'authorization and protocol execution reported separately; no autonomous-agent task claim','environment':{'python':sys.version,'kernel':platform.platform(),'mcp':importlib.metadata.version('mcp'),'node':os.popen(node+' --version').read().strip(),'filesystem_version':json.loads((fs_entry.parent.parent/'package.json').read_text())['version'],'filesystem_entry_sha256':hashlib.sha256(fs_entry.read_bytes()).hexdigest()},'profiles':{}}
 with tempfile.TemporaryDirectory(prefix='mcp-fresh-') as td:
  work=Path(td)
  for case in cases:
   if case['beneficial'] and case['server']=='filesystem' and case['tool_name'] not in ['list_dir']:
    p=work/case['arguments']['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text('Synthetic fixture for '+case['id']+'\n')
  clean_env={'PATH':os.environ['PATH'],'PYTHONPATH':os.pathsep.join(sys.path),'PYTHONDONTWRITEBYTECODE':'1','HOME':str(work),'OPENAI_API_KEY':'SYNTHETIC-NONSECRET'}
  for profile in ['limited_network','read_only','no_code_exec','approval_gated']:
   details=[]; audit_files=[]
   policy_path=ROOT/'policies'/f'{profile}.yaml'
   manager=PolicyManager();manager.load(policy_path);policy=manager.get_current()
   for rep in range(3):
    async with AsyncExitStack() as stack:
     sessions={}
     for server in ['filesystem','fetch','git','terminal','env','process']:
      upstream=[node,str(fs_entry),str(work)] if server=='filesystem' else [sys.executable,str(ROOT/'servers'/({'fetch':'real_fetch_server.py','git':'real_git_server.py'}.get(server,'real_shell_server.py')))]
      audit=work/f'{profile}-{rep}-{server}.jsonl';audit_files.append(audit)
      args=[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--policy',str(policy_path),'--log',str(audit),'--server-name',server,'--',*upstream]
      r,w=await stack.enter_async_context(stdio_client(StdioServerParameters(command=sys.executable,args=args,cwd=str(work),env=clean_env)))
      c=await stack.enter_async_context(ClientSession(r,w));await c.initialize();sessions[server]=c
     for original in cases:
      case=copy.deepcopy(original);name={'list_dir':'list_directory','view_file':'read_file'}.get(case['tool_name'],case['tool_name']) if case['server']=='filesystem' else case['tool_name']
      args=case['arguments']
      # An allowed inert write stays in the experiment directory. Original args retained.
      if case['id']=='RM-017':args['path']=str(work/'malware.py')
      # Never execute dangerous commands or contact adversarial endpoints on allow.
      unsafe=case['id'] in {'RM-013','RM-014','RM-015','RM-016','RM-018','RM-019','RM-020','RM-023','RM-025','RM-011','RM-012'}
      dec,_=PermissionChecker(path_root=work).evaluate(ToolCall(name=name,arguments=args,server=case['server']),policy)
      if unsafe and dec==Decision.ALLOW:raise RuntimeError(f'Unsafe preflight allow: {profile}/{case["id"]}; no call sent')
      start=time.perf_counter()
      try:
       result=await sessions[case['server']].call_tool(name,args);outcome=classify_result(result)
       payload=''.join(getattr(x,'text','') for x in result.content)
      except Exception as e:outcome={'authorization':'unknown','execution':'transport_error','error_type':type(e).__name__};payload=''
      details.append({'id':case['id'],'repetition':rep+1,'beneficial':case['beneficial'],'tool':name,'arguments':args,'original_arguments':original['arguments'],'outcome':outcome,'latency_ms':(time.perf_counter()-start)*1000,'response_sha256':hashlib.sha256(payload.encode()).hexdigest(),'response_excerpt':payload[:200]})
   good=[d for d in details if d['beneficial']];bad=[d for d in details if not d['beneficial']];lat=[d['latency_ms'] for d in details]
   report['profiles'][profile]={'n_calls':len(details),'known_authorization':sum(d['outcome']['authorization']!='unknown' for d in details),'malicious_allowed':sum(d['outcome']['authorization']=='allow' for d in bad),'malicious_total':len(bad),'benign_allowed':sum(d['outcome']['authorization']=='allow' for d in good),'benign_protocol_success':sum(d['outcome']['execution']=='upstream_ok' for d in good),'benign_total':len(good),'latency_mean_ms':statistics.mean(lat),'latency_median_ms':statistics.median(lat),'details':details,'audit':[json.loads(l) for p in audit_files for l in p.read_text().splitlines()]}
   (ROOT/'results/fresh_live_deployment.json').write_text(json.dumps(report,indent=2));print(profile,{k:v for k,v in report['profiles'][profile].items() if k not in ['details','audit']},flush=True)
 return report
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('usage: python scripts/run_fresh_live_evaluation.py /absolute/node /absolute/filesystem/dist/index.js')
 asyncio.run(run(Path(sys.argv[2]).resolve(),str(Path(sys.argv[1]).resolve())))
