"""Independent-source generalization and comparator evaluation.
Extracts tool calls from AgentDojo released run traces, AgentBound manifests and
AGT policy examples. It does not use the paper's datasets or inference helpers
for the declared expected labels; labels are lexical capability annotations.
"""
from __future__ import annotations
import json,re,hashlib,glob,statistics,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'src'; sys.path.insert(0,str(SRC))
from models import ToolCall,Decision
from policy_manager import PolicyManager
from checker import PermissionChecker

def expected(name,args):
 s=(name+' '+json.dumps(args,sort_keys=True)).lower()
 cats=set()
 if any(x in s for x in ['read','get','list','search','fetch','view','restaurant','calendar']): cats.add('fs.read')
 if any(x in s for x in ['write','delete','update','send','create','add_event','save','move']): cats.add('fs.write')
 if any(x in s for x in ['http','url','web','fetch','search','restaurant']): cats.add('net.http')
 if any(x in s for x in ['shell','terminal','exec','process','run_command']): cats.add('code.exec')
 if any(x in s for x in ['env','credential','secret','token','password']): cats.add('env.read')
 return cats
rows=[]
for p in glob.glob(str(Path(__file__).resolve().parents[4]/'research_inputs/agentdojo/**/*.json'),recursive=True):
 try:d=json.loads(Path(p).read_text())
 except:continue
 for m in d.get('messages',[]):
  if not isinstance(m,dict) or m.get('role')!='assistant':continue
  content=m.get('content',''); content=content if isinstance(content,str) else json.dumps(content)
  for mname,args in re.findall(r'(?:Tool|tool|function)\s*[:=]\s*([A-Za-z_][\w-]*)[^\n]{0,180}?(?:Parameter|parameters|args|arguments)\s*[:=]\s*([^\n]+)',content):
   try:a=json.loads(args.replace("'",'"')) if args.strip().startswith(('{','[')) else {'text':args}
   except:a={'text':args}
   rows.append({'source':'AgentDojo','tool':mname,'arguments':a})
# AgentBound manifest names/descriptions
for p in [Path(__file__).resolve().parents[4]/'research_inputs/agentbound/mcp-servers/data/permission-list.json',Path(__file__).resolve().parents[4]/'research_inputs/agentbound/helpers/manifest-creator-agent/batch.json']:
 try:d=json.loads(p.read_text())
 except:continue
 items=d if isinstance(d,list) else []
 for x in items:
  if isinstance(x,dict): rows.append({'source':'AgentBound','tool':x.get('name','manifest_item'),'arguments':{'description':x.get('description',''),'permissions':x.get('permissions',[])}})
# AGT examples / policy rule expressions
for p in glob.glob(str(Path(__file__).resolve().parents[4]/'research_inputs/agt/**/*.yaml'),recursive=True)[:100]:
 txt=Path(p).read_text(errors='ignore')
 for t in re.findall(r'(?:tool|action|resource|command)\s*[:=]\s*["\']?([A-Za-z_][\w.-]*)',txt,re.I):rows.append({'source':'AGT','tool':t,'arguments':{'policy_file':p}})
rows=rows[:1000]
policy=PolicyManager();policy.load(ROOT/'policies/limited_network.yaml');checker=PermissionChecker(path_root=ROOT)
results=[]
for r in rows:
 exp=expected(r['tool'],r['arguments']); decision,rec=checker.evaluate(ToolCall(name=r['tool'],arguments=r['arguments'],server=r['source']),policy.get_current())
 results.append({'source':r['source'],'tool':r['tool'],'expected_categories':sorted(exp),'inferred_categories':sorted(rec.inferred_categories),'category_match':exp==rec.inferred_categories,'decision':decision.value})
by={}
for src in sorted(set(x['source'] for x in results)):
 q=[x for x in results if x['source']==src];by[src]={'n':len(q),'category_match':sum(x['category_match'] for x in q),'rate':sum(x['category_match'] for x in q)/len(q) if q else 0}
out={'experiment':'independent-source generalization','sources':by,'n':len(results),'rows':results,'source_sha256':{str(Path(p)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in glob.glob(str(Path(__file__).resolve().parents[4]/'research_inputs/downloads.json'))},'environment':{'platform':platform.platform()}}
(ROOT/'results/external_generalization.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
