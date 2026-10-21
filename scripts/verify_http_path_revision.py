"""Compare authorization and inference against the pre-route-fix source.
No network or upstream tool execution. Baseline source is supplied explicitly.
"""
import argparse, hashlib, json, sys, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import checker
from inference import infer_categories
from metrics import confusion_counts, derive_rates
from models import ToolCall
from policy_manager import PolicyManager
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--output',required=True);args=p.parse_args()
b=Path(args.baseline).read_text();mod=types.ModuleType('baseline_inference');sys.modules[mod.__name__]=mod;exec(compile(b,args.baseline,'exec'),mod.__dict__)
policies={n:PolicyManager().load(ROOT/'policies'/f'{n}.yaml') for n in ['read_only','limited_network','no_code_exec','approval_gated']}
files=['holdout/pilot_87.json','large_dataset.jsonl','organic_holdout.json','adaptive_boundaries_v2.json','external_schema_cases.json','reviewer2_targeted_cases.json','real_mcp_workflows.json']
report={'baseline_sha256':hashlib.sha256(b.encode()).hexdigest(),'corrected_sha256':hashlib.sha256((ROOT/'src/inference.py').read_bytes()).hexdigest(),'scope':'Deterministic inference and authorization replay; not fresh live latency or task completion','datasets':{}}
for filename in files:
 path=ROOT/'datasets'/filename;cases=[json.loads(x) for x in path.read_text().splitlines()] if path.suffix=='.jsonl' else json.loads(path.read_text())
 changes=[];inference_changes=[]
 actual=[];allowed={n:[] for n in policies}
 for c in cases:
  actual.append(not bool(c.get('beneficial')))
  name=c['tool_name'];a=c.get('arguments') or {};old=mod.infer_categories(name,a);new=infer_categories(name,a)
  if (old.categories,old.high_risk)!=(new.categories,new.high_risk):inference_changes.append(c['id'])
  for profile,policy in policies.items():
   call=ToolCall(name=name,arguments=a)
   checker.infer_categories=mod.infer_categories;before=checker.PermissionChecker().evaluate(call,policy)[0].value
   checker.infer_categories=infer_categories;after=checker.PermissionChecker().evaluate(call,policy)[0].value
   allowed[profile].append(after == 'allow')
   if before!=after:changes.append({'id':c['id'],'profile':profile,'before':before,'after':after})
 report['datasets'][filename]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cases':len(cases),'profile_comparisons':len(cases)*4,'inference_changes':inference_changes,'decision_changes':changes,'rates':{n:derive_rates(confusion_counts(actual,values)) for n,values in allowed.items()}}
 print(filename,len(cases),'inference changes',len(inference_changes),'decision changes',len(changes),flush=True)
Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
