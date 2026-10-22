"""New opt-in contract experiment on unchanged inputs and labels.

Deployment assignment is explicit and independent of labels/domains: exact
http_request calls containing host/path at the root or under request use the
approved reference adapter. Other calls retain the default checker. This is
synthetic authorization replay, not a reconstruction of historical execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from checker import PermissionChecker
from trusted_http_contract import ApprovedHttpRouteBinding
from policy_manager import PolicyManager
from models import ToolCall, Decision
from metrics import confusion_counts, derive_rates

PROFILES=['read_only','limited_network','no_code_exec','approval_gated']
FILES=['holdout/pilot_87.json','large_dataset.jsonl','organic_holdout.json','adaptive_boundaries_v2.json','external_schema_cases.json','reviewer2_targeted_cases.json','real_mcp_workflows.json']
def assigned(name,args):
    if name!='http_request' or not isinstance(args,dict):return False
    return {'host','path'} <= args.keys() or (isinstance(args.get('request'),dict) and {'host','path'} <= args['request'].keys())

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'results/trusted_contract_study'));a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'configs/approved_http_route_reference.json').read_text())
    b=ApprovedHttpRouteBinding.load(ROOT/manifest['source'],manifest['sha256'])
    policies={n:PolicyManager().load(ROOT/'policies'/f'{n}.yaml') for n in PROFILES}
    plain=PermissionChecker();bound=PermissionChecker(trusted_http_route=b)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'New explicitly configured adapter assignment; unchanged inputs/labels; authorization replay only','assignment':'Exact http_request with host/path at root or under request; no label/domain selection','manifest':manifest,'source_hashes':{},'datasets':{}}
    for folder in ['src','servers']:
        for f in sorted((ROOT/folder).glob('*.py')):report['source_hashes'][str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
    for filename in FILES:
        path=ROOT/'datasets'/filename;data=path.read_bytes();cases=[json.loads(l) for l in data.splitlines()] if path.suffix=='.jsonl' else json.loads(data)
        labels=[];old={n:[] for n in PROFILES};new={n:[] for n in PROFILES};assigned_count=0;changes=[]
        for c in cases:
            name=c['tool_name'];args=c.get('arguments') or {};use=assigned(name,args);assigned_count+=int(use)
            labels.append(not bool(c.get('beneficial')));call=ToolCall(name=name,arguments=args)
            for n,policy in policies.items():
                before,br=plain.evaluate(call,policy)
                after,ar=bound.evaluate(call,policy) if use else (before,br)
                old[n].append(before==Decision.ALLOW);new[n].append(after==Decision.ALLOW)
                if before!=after:
                    changes.append({'id':c['id'],'beneficial':bool(c.get('beneficial')),'profile':n,'before':before.value,'after':after.value,'before_categories':sorted(br.inferred_categories),'after_categories':sorted(ar.inferred_categories)})
        item={'input_sha256':hashlib.sha256(data).hexdigest(),'calls':len(cases),'adapter_assigned_calls':assigned_count,'default':{n:derive_rates(confusion_counts(labels,old[n])) for n in PROFILES},'contract_enabled':{n:derive_rates(confusion_counts(labels,new[n])) for n in PROFILES},'decision_changes':len(changes)}
        report['datasets'][filename]=item
        (out/(path.stem+'_changes.json')).write_text(json.dumps(changes,indent=2)+'\n')
        print(filename,'assigned',assigned_count,'limited_network',item['default']['limited_network']['bcar'],'->',item['contract_enabled']['limited_network']['bcar'],flush=True)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
