"""Strict configured-entry validation. This is not OS-level client confinement.
The interpreter, repository, manifest and administrator are trusted.
"""
from __future__ import annotations
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / 'scripts/mcp_enforcement_proxy.py'


def is_enforced_server_spec(spec: dict[str, Any]) -> bool:
    if set(spec) - {'command', 'args'}:
        return False  # no environment injection, remote URL or alternate cwd
    command, args = spec.get('command'), spec.get('args')
    if not isinstance(command, str) or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return False
    executable = shutil.which(command)
    if not executable or Path(executable).resolve() != Path(sys.executable).resolve():
        return False
    if len(args) < 3:
        return False
    script = Path(args[0])
    if (script if script.is_absolute() else ROOT / script).resolve() != PROXY.resolve():
        return False
    try:
        sep = args.index('--')
    except ValueError:
        return False
    if not args[sep+1:]:
        return False
    opts = args[1:sep]
    if len(opts) % 2:
        return False
    seen = set()
    for key, value in zip(opts[::2], opts[1::2]):
        if key not in {'--policy', '--log', '--server-name', '--ask-mode'} or key in seen:
            return False
        if key == '--ask-mode' and value != 'deny':
            return False
        if not value or value.startswith('--'):
            return False
        seen.add(key)
    return True


def validate_client_mcp_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    servers = config.get('mcpServers') if isinstance(config, dict) else None
    if not isinstance(servers, dict) or not servers:
        return False, ['missing-or-empty mcpServers']
    errors = [f'{name}: unapproved launch specification' for name, spec in servers.items()
              if not isinstance(spec, dict) or not is_enforced_server_spec(spec)]
    return not errors, errors


def verify_manifest(manifest: dict) -> None:
    """Verify an administrator-provisioned manifest; never learn hashes at launch."""
    files = manifest.get('sha256')
    required = {'scripts/mcp_enforcement_proxy.py'} | {str(p.relative_to(ROOT)) for p in (ROOT/'src').glob('*.py')}
    if not isinstance(files, dict) or not required.issubset(files):
        raise ValueError('manifest omits trusted enforcement files')
    for name, digest in files.items():
        p = (ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file():
            raise ValueError('invalid manifest path')
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError(f'integrity check failed: {name}')
