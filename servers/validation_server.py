"""Local deterministic MCP integration fixture; no external services required."""
import json
import os
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from safe_files import read_under, write_under
base=Path(sys.argv[1]).resolve()
receipts=Path(sys.argv[2])
server=FastMCP('validation-fixture')

def receipt(name, args):
    with receipts.open('a') as f: f.write(json.dumps({'tool':name,'arguments':args})+'\n')

@server.tool()
def read_file(path: str) -> str:
    receipt('read_file', {'path':path})
    return read_under(base,path)

@server.tool()
def write_file(path: str, content: str) -> str:
    receipt('write_file', {'path':path})
    return write_under(base,path,content)

@server.tool()
def read_failure(path: str) -> str:
    receipt('read_failure', {'path':path})
    raise RuntimeError('deliberate upstream error')

@server.tool()
def read_text_file(path: str) -> str:
    receipt('read_crash', {'path':path})
    os._exit(17)

if __name__=='__main__': server.run()
