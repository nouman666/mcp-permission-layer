import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from inference import infer_categories
from checker import PermissionChecker
from policy_manager import PolicyManager
from models import ToolCall
from proxy import EnforcementProxy

# Review Part C is implemented (Reviewer 3 Comments 1-3):
# tests directly validate inference labels, policy faithfulness, and routed audit accounting.

def test_official_reference_server_mechanism_audit_exact_sets():
    cases=json.loads((ROOT/'datasets'/'reviewer3_official_mechanism_audit.json').read_text())
    assert len(cases)==27
    for c in cases:
        got=infer_categories(c['tool_name'],c.get('arguments') or {}).categories
        assert got==set(c['expected_categories']), (c['id'],got,c['expected_categories'])

def test_policy_profile_faithfulness_matrix_and_restrictions():
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
    checker=PermissionChecker()
    for profile,matrix in expected.items():
        pm=PolicyManager(); pm.load(str(ROOT/'policies'/f'{profile}.yaml'))
        for cat,(name,args) in canonical.items():
            d,_=checker.evaluate(ToolCall(name,args),pm.get_current())
            assert d.value==matrix[cat], (profile,cat,d.value,matrix[cat])
    pm=PolicyManager(); pm.load(str(ROOT/'policies'/'limited_network.yaml')); p=pm.get_current()
    for name,args in [('fetch',{'url':'https://untrusted.example/x'}),('read_file',{'path':'~/.ssh/id_rsa'}),('http_request',{'payload':'x'})]:
        d,_=checker.evaluate(ToolCall(name,args),p); assert d.value=='deny'

def test_routed_proxy_calls_all_create_audit_records(tmp_path):
    proxy=EnforcementProxy(str(ROOT/'policies'/'limited_network.yaml'),str(tmp_path/'audit.jsonl'))
    calls=[('read_file',{'path':'workspace/a.txt'}),('write_file',{'path':'workspace/b.txt','content':'x'}),('fetch',{'url':'https://docs.python.org/3/library/os.html'}),('execute_command',{'command':'echo ok'})]
    for n,a in calls: proxy.handle_tool_call(n,a,server='test')
    assert len(proxy.get_audit_records())==len(calls)


def test_declared_capability_oracle_agrees_with_b4_on_official_audit():
    cases=json.loads((ROOT/'datasets'/'reviewer3_official_mechanism_audit.json').read_text())
    checker=PermissionChecker()
    total=matches=0
    for profile in ('read_only','limited_network','no_code_exec','approval_gated'):
        pm=PolicyManager(); pm.load(str(ROOT/'policies'/f'{profile}.yaml')); policy=pm.get_current()
        for c in cases:
            tc=ToolCall(c['tool_name'],c.get('arguments') or {})
            b4,_=checker.evaluate(tc,policy)
            cds={}
            for cat in set(c['expected_categories']):
                cds[cat]=checker._evaluate_rule(tc,checker._lookup(policy,cat),cat)
            oracle=checker._aggregate(cds)
            total += 1; matches += (b4==oracle)
    assert total==108 and matches==108

# Review Part C2 is implemented (Reviewer 3 Comment 2):
# configured-path bypass rejection and task-level/comparator experiments.
def test_deployment_guard_rejects_raw_upstream_entries():
    sys.path.insert(0,str(ROOT/'src'))
    from deployment_guard import validate_client_mcp_config
    good={'mcpServers':{'enforced-x':{'command':'python','args':['scripts/mcp_enforcement_proxy.py','--','python','server.py']}}}
    ok,errors=validate_client_mcp_config(good); assert ok and not errors
    bad={'mcpServers':dict(good['mcpServers'])}
    bad['mcpServers']['raw-x']={'command':'python','args':['server.py']}
    ok,errors=validate_client_mcp_config(bad); assert not ok and errors

def test_reviewer3_comment2_validation_script_outputs_complete_results():
    import importlib.util
    p=ROOT/'scripts'/'run_reviewer3_comment2_validation.py'
    spec=importlib.util.spec_from_file_location('r3c2',p); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    i=mod.interception_completeness(); assert i['sealed_config_valid']; assert i['bypass_variants_rejected']==4; assert i['audit_records']==i['routed_calls']==12
    pf=mod.policy_faithfulness(); assert pf['matches']==pf['n']==27
    ac=mod.acl_comparison(); assert set(ac)=={'read_only','limited_network','no_code_exec','approval_gated'}
    wf=mod.workflow_completion(); assert all(v['benign_tasks']==12 and v['malicious_tasks']==8 for v in wf.values())
