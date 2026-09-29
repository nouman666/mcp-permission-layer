"""Mandatory sandbox launch gate for supported deployments.
Refuses to launch an upstream server unless an OS sandbox backend is available.
The verified path uses bubblewrap; callers must choose explicit read-only root,
working directory and network namespace settings.
"""
from __future__ import annotations
import argparse,os,shutil,subprocess,sys

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--workdir',required=True);p.add_argument('--unshare-net',action='store_true');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args(argv)
 if not a.command or a.command[0]=='--':a.command=a.command[1:]
 b=shutil.which('bwrap')
 if not b:raise SystemExit('SANDBOX_REQUIRED: bubblewrap is unavailable; refusing unconfined launch')
 cmd=[b,'--die-with-parent','--new-session','--ro-bind',os.path.abspath(a.root),'/workspace','--chdir','/workspace','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
 if a.unshare_net:cmd += ['--unshare-net']
 cmd += ['--']+a.command
 raise SystemExit(subprocess.call(cmd))
if __name__=='__main__':main()
