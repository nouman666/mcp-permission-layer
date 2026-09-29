"""Independent declared-capability policy comparator, not a deployed server ACL.
Shares data types and policy input only; does not call inference/checker helpers.
Scope: lexical resources and documented scalar keys in this controlled benchmark.
"""
import fnmatch
import posixpath
import re
from urllib.parse import urlparse
from models import Decision

def scalars(value, key=''):
    if isinstance(value, dict):
        for k,v in value.items(): yield from scalars(v,str(k).lower())
    elif isinstance(value, list):
        for v in value: yield from scalars(v,key)
    else: yield key,value

def norm(p):
    return posixpath.normpath(p.replace('\\','/')).lower()

def matches(p, pattern):
    p,pattern=norm(p),norm(pattern)
    if not any(x in pattern for x in '*?['):
        if p==pattern or p.startswith(pattern.rstrip('/')+'/'): return True
        if pattern.startswith('~/'):
            suffix=pattern[1:]
            if p.endswith(suffix) or suffix+'/' in '/'+p.lstrip('/'): return True
    return fnmatch.fnmatchcase(p,pattern.replace('**','*')) or fnmatch.fnmatchcase(p.lstrip('/'),pattern.replace('**','*'))

def domain_match(host, pattern):
    pattern=pattern.lower().strip().rstrip('.')
    return pattern=='*' or host==pattern or (pattern.startswith('*.') and (host==pattern[2:] or host.endswith(pattern[1:])))

class ServerSideACL:
    def evaluate(self, call, declared_categories, policy):
        if not declared_categories: return Decision.DENY
        paths=[]; hosts=[]
        for key,val in scalars(call.arguments):
            if not isinstance(val,str): continue
            if '://' in val:
                host=urlparse(val).hostname
                if host: hosts.append(host.lower().rstrip('.'))
            elif key in {'host','hostname','domain','domain_name','server_host'}:
                hosts.append(val.lower().split(':')[0].rstrip('.'))
            elif any(x in key for x in ('path','file','dir','folder','root')) or val.startswith(('/', './', '../', '~/', 'workspace/')) or re.match(r'^[a-zA-Z]:[\\/]',val):
                paths.append(val)
        decisions=[]
        for cat in declared_categories:
            rule=policy.permissions.get(cat)
            if rule is None:
                decisions.append(policy.default); continue
            if not rule.allow:
                return Decision.DENY
            if cat in {'fs.read','fs.write','env.read'}:
                denies=list(rule.deny_paths)+list(policy.sensitive_paths)
                if (denies or rule.allow_paths) and not paths: return Decision.DENY
                for path in paths:
                    if any(matches(path,p) for p in denies): return Decision.DENY
                    if rule.allow_paths and not any(matches(path,p) for p in rule.allow_paths): return Decision.DENY
            if cat=='net.http':
                if (rule.allow_domains or rule.deny_domains) and not hosts: return Decision.DENY
                for host in hosts:
                    if any(domain_match(host,p) for p in rule.deny_domains if p.strip()!='*'): return Decision.DENY
                    if rule.allow_domains:
                        if not any(domain_match(host,p) for p in rule.allow_domains): return Decision.DENY
                    elif any(domain_match(host,p) for p in rule.deny_domains): return Decision.DENY
            decisions.append(rule.mode)
        return Decision.DENY if Decision.DENY in decisions else Decision.ASK if Decision.ASK in decisions else Decision.ALLOW
