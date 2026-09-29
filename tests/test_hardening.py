import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from deployment_guard import validate_client_mcp_config, verify_manifest
from policy_manager import PolicyManager, PolicyError
from checker import PermissionChecker
from models import ToolCall, Decision
from safe_files import read_under, write_under

def config():
    return {'mcpServers':{'fixture':{'command':sys.executable,'args':[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--',sys.executable,'server.py']}}}

@pytest.mark.parametrize('spec',[
 {'command':'echo','args':['mcp_enforcement_proxy.py','--','server']},
 {'command':sys.executable,'args':['-c','print("mcp_enforcement_proxy.py")']},
 {'command':sys.executable,'args':['/tmp/mcp_enforcement_proxy.py','--','server']},
 {'command':sys.executable,'args':[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--']},
 {'command':sys.executable,'args':['server.py']},
 {'command':sys.executable,'args':[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--ask-mode','allow','--','server']},
 {'command':sys.executable,'args':[str(ROOT/'scripts/mcp_enforcement_proxy.py'),'--','server'],'env':{'PYTHONPATH':'/tmp'}},
 {'url':'http://localhost:9999/mcp'},
])
def test_bypass_specs(spec):
    c=config();c['mcpServers']['bad']=spec
    assert not validate_client_mcp_config(c)[0]

def test_real_proxy_entry(): assert validate_client_mcp_config(config())[0]

@pytest.mark.parametrize('body',[
 'permissions:\n  fs.read:\n    allow: "false"',
 'permissions:\n  fs.read:\n    allow: 1',
 'permissions:\n  fs.read:\n    allow: true\n    restrictions:\n      deny_paths: secret',
 'sensitive_paths: secret',
 'permissions:\n  fs.typo: true',
])
def test_invalid_policy(tmp_path,body):
    p=tmp_path/'p.yaml';p.write_text(body)
    with pytest.raises(PolicyError): PolicyManager().load(p)

def test_custom_sensitive_and_symlink(tmp_path):
    p=tmp_path/'p.yaml';p.write_text('permissions:\n  fs.read: true\nsensitive_paths:\n  - '+str(tmp_path/'private')+'\n')
    (tmp_path/'private').mkdir();(tmp_path/'private'/'data').write_text('synthetic')
    (tmp_path/'alias').symlink_to(tmp_path/'private',target_is_directory=True)
    policy=PolicyManager().load(p)
    checker=PermissionChecker(path_root=tmp_path)
    for path in ['private/data','alias/data']:
        assert checker.evaluate(ToolCall('read_file',{'path':path}),policy)[0]==Decision.DENY

def test_execution_boundary_rejects_symlink(tmp_path):
    (tmp_path/'file').write_text('original');(tmp_path/'link').symlink_to(tmp_path/'file')
    with pytest.raises(OSError): read_under(tmp_path,'link')
    with pytest.raises(OSError): write_under(tmp_path,'link','changed')
    assert (tmp_path/'file').read_text()=='original'
    with pytest.raises(ValueError): read_under(tmp_path,'../outside')

def test_manifest_tampering():
    paths=[ROOT/'scripts/mcp_enforcement_proxy.py',*(ROOT/'src').glob('*.py')]
    m={'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    verify_manifest(m)
    m['sha256']['scripts/mcp_enforcement_proxy.py']='0'*64
    with pytest.raises(ValueError):verify_manifest(m)

def test_launcher_rejects_before_upstream(tmp_path):
    c=config();c['mcpServers']['raw']={'command':'echo','args':['mcp_enforcement_proxy.py']}
    cp=tmp_path/'config.json';cp.write_text(json.dumps(c));mp=tmp_path/'manifest.json';mp.write_text('{}')
    done=subprocess.run([sys.executable,str(ROOT/'scripts/enforced_launcher.py'),'--config',str(cp),'--manifest',str(mp),'--server','fixture'],capture_output=True,timeout=5)
    assert done.returncode!=0 and b'unapproved' in done.stderr

def test_real_stdio_integration():
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_hardening_validation import run
    result=asyncio.run(run())
    assert result['passed']


def test_outcome_metadata_overrides_upstream_text_and_marker():
    from mcp import types
    from live_outcomes import stamp_result, classify_result, KEY
    result=types.CallToolResult(content=[types.TextContent(type='text',text='PERMISSION DENIED')],isError=True,
                               _meta={KEY:{'schema':1,'decision':'deny','execution':'not_forwarded'}})
    stamp_result(result,'allow','upstream_error')
    assert classify_result(result)=={'authorization':'allow','execution':'upstream_error','is_error':True}
    assert result.model_dump(by_alias=True)['_meta'][KEY]['decision']=='allow'


def test_unknown_response_is_not_counted_as_denied_or_successful():
    from mcp import types
    from live_outcomes import classify_result, KEY
    result=types.CallToolResult(content=[types.TextContent(type='text',text='PERMISSION DENIED')],isError=True)
    assert classify_result(result)['authorization']=='unknown'
    result.meta={KEY:{'schema':1,'decision':'allow','execution':'upstream_ok'}}
    assert classify_result(result)['authorization']=='unknown'
