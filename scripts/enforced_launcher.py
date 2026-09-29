"""Launch one approved entry after validating ALL entries and trusted hashes.
Administrator must protect this launcher, interpreter, config, manifest and code
against modification. Does not block independent processes or network clients.
"""
import hashlib
import argparse
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from deployment_guard import validate_client_mcp_config, verify_manifest

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--server', required=True)
    a = p.parse_args()
    config = json.loads(Path(a.config).read_text())
    manifest = json.loads(Path(a.manifest).read_text())
    valid, errors = validate_client_mcp_config(config)
    if not valid:
        raise SystemExit('; '.join(errors))
    if config != manifest.get('approved_config'):
        raise SystemExit('configuration differs from administrator-approved manifest')
    if manifest.get("interpreter_sha256") != hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest():
        raise SystemExit("unapproved interpreter hash")
    policies = []
    for entry in config["mcpServers"].values():
        argv = entry["args"]
        policy = argv[argv.index("--policy")+1] if "--policy" in argv[:argv.index("--")] else "policies/limited_network.yaml"
        pp = (ROOT/policy).resolve()
        if not pp.is_relative_to(ROOT) or str(pp.relative_to(ROOT)) not in manifest.get("sha256", {}):
            raise SystemExit("policy missing from trusted manifest")
    verify_manifest(manifest)
    spec = config['mcpServers'][a.server]
    os.chdir(ROOT)
    # Do not inherit Python startup/module overrides from the caller.
    env = {k:v for k,v in os.environ.items() if not k.startswith('PYTHON') and k not in {'LD_PRELOAD','LD_LIBRARY_PATH'}}
    os.execve(sys.executable, [sys.executable, *spec['args']], env)

if __name__ == '__main__':
    main()
