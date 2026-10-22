import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from checker import PermissionChecker
from models import ToolCall, Decision, Policy
from policy_manager import PolicyManager
from trusted_http_contract import ApprovedHttpRouteBinding, ApprovedHttpRouteService, ContractMismatch

SOURCE=ROOT/'servers/contract_http_server.py'
PIN=json.loads((ROOT/'configs/approved_http_route_reference.json').read_text())['sha256']
POLICY=PolicyManager().load(ROOT/'policies/limited_network.yaml')
def binding():return ApprovedHttpRouteBinding.load(SOURCE,PIN)
def check(args,name='http_request',bound=True):
    return PermissionChecker(trusted_http_route=binding() if bound else None).evaluate(ToolCall(name=name,arguments=args),POLICY)

@pytest.mark.parametrize('args',[
 {'host':'api.github.com','path':'/zen'},
 {'request':{'host':'en.wikipedia.org','path':'/wiki/MCP'}},
 {'host':'docs.python.org','path':'/tmp/output.json'},
])
def test_approved_route_restores_benign_allowance(args):
    assert check(args,bound=False)[0] == Decision.DENY
    decision,record=check(args)
    assert decision == Decision.ALLOW
    assert record.inferred_categories == {'net.http'}
    assert 'administrator_pinned_route_contract' in record.inference_reasons['net.http']

@pytest.mark.parametrize('args',[
 {'host':'untrusted.example','path':'/collect'},
 {'host':'api.github.com@untrusted.example','path':'/zen'},
 {'host':'api.github.com','path':'//untrusted.example/collect'},
 {'host':'api.github.com','path':'/\\untrusted.example'},
 {'host':'api.github.com','path':'/zen\nX: y'},
 {'host':'api.github.com','path':'/zen','output_path':'/tmp/output.json'},
 {'request':{'host':'api.github.com','path':'/zen','destination':'/tmp/output.json'}},
 {'host':'api.github.com','path':'/zen','trusted_route_paths':['path']},
 {'host':'api.github.com','path':'/zen','server':'approved-http'},
 {'host':'api.github.com','path':['/zen']},
 {'host':'api.github.com','path':'/zen','url':'https://untrusted.example'},
 {'request':{'host':'api.github.com','path':'/zen'},'context':{'url':'https://docs.python.org'}},
])
def test_contract_cannot_hide_other_resources_or_change_origin(args):
    assert check(args)[0] == Decision.DENY

@pytest.mark.parametrize('name',['http_request_download','http_request_save_file','other_http_request','http_request_v2'])
def test_exact_tool_identity_required(name):
    assert check({'host':'api.github.com','path':'/tmp/output.json'},name)[0] == Decision.DENY

def test_exact_reviewer_example_still_requires_write():
    decision,record=check({'url':'https://docs.python.org/3/','path':'/tmp/output.json'},'http_request_download')
    assert decision == Decision.DENY
    assert {'fs.write','net.http'} <= record.inferred_categories

def test_bad_pin_rejected_before_loading():
    with pytest.raises(ContractMismatch):ApprovedHttpRouteBinding.load(SOURCE,'0'*64)

def test_changed_source_rejected_even_under_allow_all_policy(tmp_path):
    target=tmp_path/'adapter.py';target.write_bytes(SOURCE.read_bytes())
    bound=ApprovedHttpRouteBinding.load(target,PIN)
    target.write_text(target.read_text()+'\n# changed\n')
    c=PermissionChecker(trusted_http_route=bound)
    d,r=c.evaluate(ToolCall('http_request',{'host':'api.github.com','path':'/zen'}),Policy(name='permissive',default=Decision.ALLOW))
    assert d == Decision.DENY
    assert any('trusted_contract_mismatch' in s for s in r.inference_reasons['code.exec'])

def test_same_bound_implementation_executes_get_without_file_output(tmp_path):
    b=binding();service=ApprovedHttpRouteService(b,POLICY)
    output_path=tmp_path/'output.json';args={'host':'api.github.com','path':str(output_path)}
    opener=MagicMock();opener.open.return_value.__enter__.return_value.read.return_value=b'fixture-response'
    with patch.object(b._implementation.urllib.request,'build_opener',return_value=opener):
        d,r,result=service.call('http_request',args)
    assert d == Decision.ALLOW and result=='fixture-response'
    request=opener.open.call_args.args[0]
    assert request.full_url=='https://api.github.com'+str(output_path)
    assert request.get_method()=='GET'
    assert not output_path.exists()
    assert b._implementation.NoRedirect().redirect_request(None,None,302,'',{},'https://untrusted.example') is None

def test_denied_request_never_reaches_network():
    b=binding();service=ApprovedHttpRouteService(b,POLICY)
    with patch.object(b._implementation.urllib.request,'build_opener') as network:
        d,r,result=service.call('http_request',{'host':'untrusted.example','path':'/collect'})
    assert d == Decision.DENY and result is None
    network.assert_not_called()

def test_schema_agrees_with_supported_shapes():
    import jsonschema
    b=binding()
    for args in [{'host':'api.github.com','path':'/zen'},{'request':{'host':'api.github.com','path':'/zen'}}]:
        jsonschema.validate(args,b._implementation.INPUT_SCHEMA)
        b.route_paths('http_request',args)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'host':'api.github.com','path':'/zen','output_path':'/tmp/x'},b._implementation.INPUT_SCHEMA)

def test_mcp_endpoint_advertises_pinned_schema_and_denies_invalid_calls(tmp_path):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from live_outcomes import classify_result
    async def exercise():
        params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/serve_approved_http.py'),'--manifest',str(ROOT/'configs/approved_http_route_reference.json'),'--log',str(tmp_path/'audit.jsonl')])
        async with stdio_client(params) as (rd,wr):
            async with ClientSession(rd,wr) as session:
                await session.initialize()
                tools=await session.list_tools()
                assert [t.name for t in tools.tools]==['http_request']
                assert tools.tools[0].inputSchema==binding()._implementation.INPUT_SCHEMA
                for name,args in [('http_request_download',{'url':'https://docs.python.org/3/','path':'/tmp/output.json'}),('http_request',{'host':'untrusted.example','path':'/collect'}),('http_request',{'host':'api.github.com','path':'/zen','output_path':'/tmp/out'})]:
                    result=await session.call_tool(name,args)
                    assert classify_result(result)['authorization']=='deny'
    asyncio.run(exercise())
