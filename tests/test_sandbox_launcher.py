import os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_sandbox_gate_refuses_when_backend_cannot_create_namespace(tmp_path):
 if shutil.which('bwrap'):
  r=subprocess.run([sys.executable,str(ROOT/'scripts/sandbox_launcher.py'),'--root',str(tmp_path),'--workdir','/workspace','--unshare-net','--','true'],capture_output=True,text=True)
  # Managed CI may expose bwrap without namespace privileges; a failed launch is fail-closed.
  assert r.returncode != 0 or r.stdout == ''
 else:
  r=subprocess.run([sys.executable,str(ROOT/'scripts/sandbox_launcher.py'),'--root',str(tmp_path),'--workdir','/workspace','--','true'],capture_output=True,text=True)
  assert r.returncode != 0 and 'SANDBOX_REQUIRED' in r.stderr
