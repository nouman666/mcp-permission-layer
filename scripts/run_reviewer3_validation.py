#!/usr/bin/env python3
"""Reviewer 3 validation suite.

Separates capability-inference validity from policy-profile outcomes.
Produces machine-readable raw decisions plus a compact Markdown summary.
"""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from inference import infer_categories
from checker import PermissionChecker
from policy_manager import PolicyManager
from models import ToolCall
from proxy import EnforcementProxy

# Review Part C is implemented (Reviewer 3 Comments 1-3):
# policy-independent inference validation, a policy-faithfulness matrix,
# routed-gate accounting, and an external-provenance MCPTox challenge.

def loadj(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def inference_metrics(cases, label_key, exact_labels=True):
    rows=[]; tp=fp=fn=0; exact=covered=0
    for c in cases:
        expected=set(c[label_key]); r=infer_categories(c['tool_name'],c.get('arguments') or {})
        got=set(r.categories)
        inter=len(expected & got); tp+=inter; fn+=len(expected-got); fp+=len(got-expected)
        exact += got==expected
        covered += expected <= got
        rows.append({**c,'inferred_categories':sorted(got),'covered':expected<=got,'exact':got==expected,'high_risk':r.high_risk,'reasons':r.reasons})
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    return rows, {
        'n':len(cases), 'case_required_coverage':covered/len(cases) if cases else 0.0,
        'exact_set_accuracy':exact/len(cases) if exact_labels and cases else None,
        'micro_precision':precision if exact_labels else None,
        'micro_recall':recall,
        'micro_f1':f1 if exact_labels else None,
        'required_labels':tp+fn, 'missed_required_labels':fn,
        'extra_inferred_labels':fp,
    }

def policy_faithfulness():
    canonical={
      'fs.read':('read_file',{'path':'workspace/README.md'}),
      'fs.write':('write_file',{'path':'workspace/out.txt','content':'x'}),
      'net.http':('fetch',{'url':'https://docs.python.org/3/library/os.html'}),
      'code.exec':('execute_command',{'command':'echo ok'}),
      'env.read':('get-env',{}),
      'process':('kill_process',{'pid':123}),
    }
    expected={
      'read_only': {'fs.read':'allow','fs.write':'deny','net.http':'deny','code.exec':'deny','env.read':'deny','process':'deny'},
      'limited_network': {'fs.read':'allow','fs.write':'deny','net.http':'allow','code.exec':'deny','env.read':'deny','process':'deny'},
      'no_code_exec': {'fs.read':'allow','fs.write':'allow','net.http':'allow','code.exec':'deny','env.read':'deny','process':'deny'},
      'approval_gated': {'fs.read':'allow','fs.write':'ask','net.http':'allow','code.exec':'ask','env.read':'ask','process':'deny'},
    }
    rows=[]; checker=PermissionChecker()
    for prof,matrix in expected.items():
        pm=PolicyManager(); pm.load(str(ROOT/'policies'/f'{prof}.yaml')); p=pm.get_current()
        for cat,(name,args) in canonical.items():
            decision,rec=checker.evaluate(ToolCall(name,args),p)
            rows.append({'id':f'{prof}:{cat}','profile':prof,'case':cat,'expected':matrix[cat],'observed':decision.value,'match':decision.value==matrix[cat],'inferred_categories':sorted(rec.inferred_categories)})
    restrictions=[
      ('limited_network','untrusted-domain','fetch',{'url':'https://untrusted.example/x'},'deny'),
      ('limited_network','sensitive-path','read_file',{'path':'~/.ssh/id_rsa'},'deny'),
      ('limited_network','unresolved-network','http_request',{'payload':'x'},'deny'),
    ]
    for prof,cid,name,args,exp in restrictions:
        pm=PolicyManager(); pm.load(str(ROOT/'policies'/f'{prof}.yaml')); d,rec=checker.evaluate(ToolCall(name,args),pm.get_current())
        rows.append({'id':f'{prof}:{cid}','profile':prof,'case':cid,'expected':exp,'observed':d.value,'match':d.value==exp,'inferred_categories':sorted(rec.inferred_categories)})
    return rows, {'n':len(rows),'matches':sum(x['match'] for x in rows),'agreement':sum(x['match'] for x in rows)/len(rows)}


def declared_capability_oracle_agreement(official_cases):
    """Compare B4 with an idealized declared-capability/ACL oracle.

    The oracle does not infer categories: it receives the independently specified
    documented category set, then applies the SAME policy/restriction functions.
    It is a narrow comparator for inference-vs-declaration, not a reimplementation
    of AgentBound, AGT, or any full server sandbox.
    """
    checker=PermissionChecker(); rows=[]
    for prof in ('read_only','limited_network','no_code_exec','approval_gated'):
        pm=PolicyManager(); pm.load(str(ROOT/'policies'/f'{prof}.yaml')); policy=pm.get_current()
        for c in official_cases:
            tc=ToolCall(c['tool_name'],c.get('arguments') or {})
            b4,_=checker.evaluate(tc,policy)
            cat_decisions={}
            for cat in set(c['expected_categories']):
                rule=checker._lookup(policy,cat)
                cat_decisions[cat]=checker._evaluate_rule(tc,rule,cat)
            oracle=checker._aggregate(cat_decisions)
            rows.append({'id':f"{prof}:{c['id']}",'profile':prof,'case_id':c['id'],'b4':b4.value,'declared_capability_oracle':oracle.value,'match':b4==oracle})
    matches=sum(x['match'] for x in rows)
    return rows, {'n':len(rows),'matches':matches,'agreement':matches/len(rows)}

def routed_gate_accounting():
    calls=[
      ('read_file',{'path':'workspace/a.txt'}),('write_file',{'path':'workspace/b.txt','content':'x'}),
      ('fetch',{'url':'https://docs.python.org/3/library/os.html'}),('fetch',{'url':'https://untrusted.example/x'}),
      ('execute_command',{'command':'echo ok'}),('get-env',{}),('kill_process',{'pid':7}),
      ('read_file',{'path':'~/.ssh/id_rsa'}),('list_directory',{'path':'workspace'}),
      ('git_status',{'repo_path':'workspace/repo'}),('git_add',{'repo_path':'workspace/repo','files':['a.py']}),
      ('mystery_tool',{'value':'x'}),
    ]
    with tempfile.TemporaryDirectory() as td:
        log=Path(td)/'audit.jsonl'
        proxy=EnforcementProxy(str(ROOT/'policies'/'limited_network.yaml'),str(log))
        rows=[]
        for name,args in calls:
            d,r=proxy.handle_tool_call(name,args,server='routing-audit')
            rows.append({'tool_name':name,'decision':d.value,'categories':sorted(r.inferred_categories)})
        logs=proxy.get_audit_records()
    return rows, {'routed_calls':len(calls),'audit_records':len(logs),'accounted_fraction':len(logs)/len(calls),'scope_note':'This verifies accounting only for calls presented to the configured proxy. Direct or alternative upstream routes bypass this enforcement boundary by construction and are not claimed to be intercepted.'}

def main():
    official=loadj(ROOT/'datasets'/'reviewer3_official_mechanism_audit.json')
    external=loadj(ROOT/'datasets'/'reviewer3_mcptox_external_challenge.json')
    off_rows,off_m=inference_metrics(official,'expected_categories',exact_labels=True)
    ext_rows,ext_m=inference_metrics(external,'required_categories',exact_labels=False)
    policy_rows,policy_m=policy_faithfulness()
    oracle_rows,oracle_m=declared_capability_oracle_agreement(official)
    route_rows,route_m=routed_gate_accounting()
    report={'official_mechanism_audit':off_m,'mcptox_external_provenance':ext_m,'policy_faithfulness':policy_m,'declared_capability_oracle':oracle_m,'routed_gate_accounting':route_m,
            'caveats':[
              'The official reference-server audit is a review-driven mechanism audit and was used to correct documented tool semantics; it is not a blind hold-out.',
              'The MCPTox set has external provenance but is not blinded: the authors had access to MCPTox during revision. Its labels specify minimum required capabilities, so additional conservative categories are not counted as false positives.',
              'No claim of complete interception across unconfigured alternative call paths is made.',
              'No full end-to-end LLM-agent task-completion benchmark is added; utility claims remain call-level and multi-step workflow allowance is reported separately.'
            ]}
    raw={'official':off_rows,'mcptox_external':ext_rows,'policy_faithfulness':policy_rows,'declared_capability_oracle':oracle_rows,'routed_gate':route_rows,'summary':report}
    out=ROOT/'results'; out.mkdir(exist_ok=True)
    (out/'reviewer3_validation_raw.json').write_text(json.dumps(raw,indent=2),encoding='utf-8')
    (out/'reviewer3_validation_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pct=lambda x:f'{100*x:.2f}%'
    md=f'''# Reviewer 3 mechanism-validation summary\n\n- Official reference-server mechanism audit: **{off_m['n']} cases**, exact-set accuracy **{pct(off_m['exact_set_accuracy'])}**, required-capability coverage **{pct(off_m['case_required_coverage'])}**, micro precision/recall/F1 **{pct(off_m['micro_precision'])} / {pct(off_m['micro_recall'])} / {pct(off_m['micro_f1'])}**.\n- MCPTox external-provenance challenge: **{ext_m['n']} cases**, minimum-required-capability case coverage **{pct(ext_m['case_required_coverage'])}**, required-label micro recall **{pct(ext_m['micro_recall'])}**; {ext_m['extra_inferred_labels']} additional conservative labels were inferred.\n- Policy-faithfulness matrix: **{policy_m['matches']}/{policy_m['n']}** expected category/profile or restriction decisions matched (**{pct(policy_m['agreement'])}**).\n- Declared-capability/ACL oracle comparator: B4 agrees on **{oracle_m['matches']}/{oracle_m['n']}** official-case/profile decisions (**{pct(oracle_m['agreement'])}**). This is an idealized declaration comparator, not an AgentBound/AGT reimplementation.\n- Routed-gate accounting: **{route_m['audit_records']}/{route_m['routed_calls']}** calls presented to the configured proxy produced audit records (**{pct(route_m['accounted_fraction'])}**). This is not a claim that alternate routes cannot bypass the proxy.\n\n## Interpretation boundaries\n\n1. The official audit is review-driven and not a blind hold-out.\n2. MCPTox is external-provenance but not blinded because the authors had access to the benchmark during revision.\n3. MCPTox labels here are minimum required capabilities; over-approximate extra categories are not treated as errors.\n4. The study does not claim complete interception of calls that are not routed through the configured proxy.\n5. The study still does not measure full LLM-agent task completion; BCAR remains a call-level utility metric.\n'''
    (out/'REVIEWER3_VALIDATION_SUMMARY.md').write_text(md,encoding='utf-8')
    print(md)

if __name__=='__main__': main()
