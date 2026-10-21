"""Regression coverage for resource-specific uncertainty and destination mixtures."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pytest
from checker import PermissionChecker
from inference import infer_categories
from models import ToolCall, Decision
from policy_manager import PolicyManager

POLICY = PolicyManager().load(Path(__file__).resolve().parents[1] / 'policies/limited_network.yaml')
ALLOWED = 'https://docs.python.org/3/'

def decision(name, arguments):
    return PermissionChecker().evaluate(ToolCall(name=name, arguments=arguments), POLICY)[0]

@pytest.mark.parametrize('name', ['download', 'fetch', 'web_fetch', 'http_request', 'upload', 'notify'])
def test_network_name_cannot_resolve_local_operation(name):
    args = {'url': ALLOWED, 'path': 'project/settings.json'}
    inferred = infer_categories(name, args)
    assert decision(name, args) == Decision.DENY
    if name == 'download':
        assert 'fs.write' in inferred.categories
    else:
        assert inferred.high_risk and 'code.exec' in inferred.categories

@pytest.mark.parametrize('value', ['//untrusted.example/collect', '/collect', 'https://', '', None, 'https://bad host/'])
@pytest.mark.parametrize('shape', ['nested', 'list', 'reverse_list'])
def test_allowed_destination_never_masks_other_destination(value, shape):
    bad = {'url': value}
    good = {'url': ALLOWED}
    args = {'request': bad, 'context': good} if shape == 'nested' else {'requests': [bad, good] if shape == 'list' else [good, bad]}
    assert decision('http_request', args) == Decision.DENY

@pytest.mark.parametrize('args', [
    {'url': '//docs.python.org/3/'},
    {'requests': [{'url': ALLOWED}, {'url': 'https://api.github.com/'}]},
    {'request': {'host': 'docs.python.org', 'request_path': '/3/library/os.html'}},
    {'requests': [{'base_url': ALLOWED, 'route': '/3/'}]},
])
def test_supported_allowed_destinations_and_routes(args):
    assert decision('http_request', args) == Decision.ALLOW
    assert 'fs.read' not in infer_categories('http_request', args).categories

def test_mixed_resolution_status_is_retained():
    items = PermissionChecker()._extract_domain_resources({'requests': [{'url': '/collect'}, {'url': ALLOWED}]})
    assert items == [(('requests', '[0]', 'url'), None), (('requests', '[1]', 'url'), 'docs.python.org')]

@pytest.mark.parametrize('name', ['http_request_download', 'http_request_save_file'])
@pytest.mark.parametrize('shape', ['flat', 'nested', 'list'])
def test_http_local_output_requires_write(name, shape):
    request = {'url': ALLOWED, 'path': '/tmp/output.json'}
    args = request if shape == 'flat' else {'request': request} if shape == 'nested' else {'requests': [request]}
    inferred = infer_categories(name, args)
    assert {'net.http', 'fs.write'} <= inferred.categories
    assert decision(name, args) == Decision.DENY

@pytest.mark.parametrize('destination', [{'url': ALLOWED}, {'host': 'api.github.com'}])
@pytest.mark.parametrize('path', ['/tmp/output.json', '/zen'])
def test_generic_absolute_http_path_remains_unresolved(destination, path):
    args = {**destination, 'path': path}
    inferred = infer_categories('http_request', args)
    assert inferred.high_risk
    assert 'ambiguous_resource_intent_fail_closed' in inferred.reasons['code.exec']
    assert decision('http_request', args) == Decision.DENY

@pytest.mark.parametrize('key', ['route', 'request_path'])
def test_download_signal_overrides_route_hint(key):
    args = {'url': ALLOWED, key: '/tmp/output.json'}
    assert 'fs.write' in infer_categories('http_request_download', args).categories
    assert decision('http_request_download', args) == Decision.DENY

@pytest.mark.parametrize('shape', ['flat', 'nested', 'list'])
def test_explicit_route_does_not_mask_separate_local_output(shape):
    request = {'url': ALLOWED, 'request_path': '/3/', 'output_path': '/tmp/output.json'}
    args = request if shape == 'flat' else {'request': request} if shape == 'nested' else {'requests': [request]}
    assert 'fs.write' in infer_categories('http_request', args).categories
    assert decision('http_request', args) == Decision.DENY

@pytest.mark.parametrize('key', ['route', 'request_path'])
def test_route_context_must_be_in_same_object(key):
    args = {'request': {key: '/tmp/output.json'}, 'context': {'url': ALLOWED}}
    assert infer_categories('http_request', args).high_risk
    assert decision('http_request', args) == Decision.DENY

@pytest.mark.parametrize('key', ['route', 'request_path'])
def test_allowed_route_does_not_hide_unresolved_generic_path(key):
    args = {'url': ALLOWED, key: '/3/', 'path': '/tmp/output.json'}
    inferred = infer_categories('http_request', args)
    assert inferred.high_risk
    assert 'ambiguous_resource_intent_fail_closed' in inferred.reasons['code.exec']
    assert decision('http_request', args) == Decision.DENY
