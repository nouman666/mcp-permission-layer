"""POSIX execution-boundary access to a trusted root, refusing every symlink.
The root directory and its ancestry must be administrator controlled. This
protects these file operations, not arbitrary malicious server code.
"""
import os
from pathlib import Path

def open_under(root: Path, path: str, flags: int):
    root = root.resolve()
    p = Path(path)
    if p.is_absolute():
        p = p.relative_to(root)
    if not p.parts or '..' in p.parts:
        raise ValueError('invalid path')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in p.parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        return os.open(p.parts[-1], flags | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    finally:
        os.close(fd)

def read_under(root: Path, path: str) -> str:
    with os.fdopen(open_under(root, path, os.O_RDONLY), 'r', encoding='utf-8') as f:
        return f.read(8000)

def write_under(root: Path, path: str, content: str) -> str:
    with os.fdopen(open_under(root, path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC), 'w', encoding='utf-8') as f:
        f.write(content)
    return 'written'
