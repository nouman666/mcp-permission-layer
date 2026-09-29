"""Reviewer-1 revision evaluation with raw per-case provenance.

Implements reviewer comments 1, 3, 5, 6, 7, and 8 by rerunning the corrected
implementation on the design set, regenerated 20k stress corpus, organic holdout,
expanded reviewer-boundary set, public-schema-shaped set, and real-MCP-style set;
repeating baselines/ablations on an untouched holdout; using BCAR; applying a
class-stratified bootstrap; separating checker-only from proxy+logging latency;
and writing raw machine-readable decisions.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]
from baselines.defenses import B0NoDefense,B1StaticAllowlist,B2DefinitionScanning,B3GatewayFilter
from checker import PermissionChecker
from inference import InferenceConfig
from metrics import confusion_counts,derive_rates,bootstrap_ci,percentile,zero_event_upper_bound,wilson_interval
from models import ToolCall,Decision
from policy_manager import PolicyManager
from proxy import EnforcementProxy,always_deny_ask_handler

DATA=ROOT/'datasets'; POL=ROOT/'policies'; RES=ROOT/'results'; RAW=RES/'raw'
PROFILES=['read_only','limited_network','no_code_exec','approval_gated']


def load_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def load_jsonl(p):
    with Path(p).open(encoding='utf-8') as f: return [json.loads(x) for x in f if x.strip()]


def make_proxy(profile, **kwargs):
    return EnforcementProxy(str(POL/f'{profile}.yaml'), os.path.join(tempfile.gettempdir(),f'r1_{profile}_{id(kwargs)}.jsonl'), ask_handler=always_deny_ask_handler, **kwargs)


def eval_proxy(cases, profile='limited_network', proxy=None, raw_name=None):
    proxy=proxy or make_proxy(profile)
    rows=[]
    for c in cases:
        t0=time.perf_counter(); d,rec=proxy.handle_tool_call(c['tool_name'],c.get('arguments') or {}); elapsed=(time.perf_counter()-t0)*1000
        rows.append({
            'id':c['id'],'beneficial':bool(c.get('beneficial')),'tool_name':c['tool_name'],'arguments':c.get('arguments') or {},
            'decision':d.value,'allowed':d==Decision.ALLOW,'categories':sorted(rec.inferred_categories),'high_risk':rec.high_risk,
            'checker_record_latency_ms':rec.latency_ms,'proxy_plus_logging_latency_ms':elapsed,
        })
    rates=derive_rates(confusion_counts([not r['beneficial'] for r in rows],[r['allowed'] for r in rows]))
    if raw_name:
        RAW.mkdir(parents=True,exist_ok=True)
        with (RAW/raw_name).open('w',encoding='utf-8',newline='\n') as f:
            for r in rows: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
    return rates, rows


def eval_defense(cases, defense):
    rows=[]
    for c in cases:
        out=defense.decide(c['tool_name'],c.get('arguments') or {},c.get('poisoned_description') or c.get('description'))
        rows.append((not c.get('beneficial',False),out=='allow'))
    return derive_rates(confusion_counts([a for a,_ in rows],[b for _,b in rows]))


def sha256(path):
    h=hashlib.sha256(); h.update(Path(path).read_bytes()); return h.hexdigest()


def checker_latency(cases, repeats=5):
    pm=PolicyManager(); policy=pm.load(POL/'limited_network.yaml'); checker=PermissionChecker()
    vals=[]
    for _ in range(repeats):
        for c in cases:
            tc=ToolCall(name=c['tool_name'],arguments=c.get('arguments') or {})
            t0=time.perf_counter(); checker.evaluate(tc,policy); vals.append((time.perf_counter()-t0)*1000)
    return {'mean_ms':sum(vals)/len(vals),'median_ms':percentile(vals,50),'p95_ms':percentile(vals,95),'p99_ms':percentile(vals,99),'n':len(vals)}


def proxy_latency(cases, repeats=3):
    proxy=make_proxy('limited_network'); vals=[]
    for _ in range(repeats):
        for c in cases:
            t0=time.perf_counter(); proxy.handle_tool_call(c['tool_name'],c.get('arguments') or {}); vals.append((time.perf_counter()-t0)*1000)
    return {'mean_ms':sum(vals)/len(vals),'median_ms':percentile(vals,50),'p95_ms':percentile(vals,95),'p99_ms':percentile(vals,99),'n':len(vals)}


def _host_details():
    # Review Part B is implemented (Reviewer 2 Comment 6): record the exact host
    # allocation and timing protocol used for the revised latency figures.
    import subprocess
    def cmd(args):
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return ''
    cpu=''
    try:
        for line in cmd(['lscpu']).splitlines():
            if line.lower().startswith('model name:'):
                cpu=line.split(':',1)[1].strip(); break
    except Exception:
        pass
    mem_kib=None
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                mem_kib=int(line.split()[1]); break
    except Exception:
        pass
    return {
        'os': platform.platform(), 'python': platform.python_version(),
        'cpu_model': cpu or platform.processor() or platform.machine(),
        'allocated_logical_cpus': os.cpu_count(),
        'memory_gib': round(mem_kib/1024/1024,2) if mem_kib else None,
    }


def main():
    # Review Part B is implemented (Reviewer 2 Comments 2, 3, 5, 6):
    # add a targeted renamed-write regression, retain frozen organic baseline
    # comparison, enumerate the three live benign profile differences, and
    # report latency hardware/repetition/operation boundaries explicitly.
    RES.mkdir(exist_ok=True); RAW.mkdir(exist_ok=True)
    # Comment 8: reconstruct stress corpus before evaluation.
    import subprocess
    subprocess.run([sys.executable,str(ROOT/'scripts'/'generate_stress_dataset.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts'/'build_reviewer_boundary_sets.py')],check=True)

    pilot=load_json(DATA/'holdout'/'pilot_87.json')
    stress=load_jsonl(DATA/'large_dataset.jsonl')
    organic=load_json(DATA/'organic_holdout.json')
    adaptive_v2=load_json(DATA/'adaptive_boundaries_v2.json')
    external=load_json(DATA/'external_schema_cases.json')
    targeted_r2=load_json(DATA/'reviewer2_targeted_cases.json')
    real=load_json(DATA/'real_mcp_workflows.json')

    splits={'pilot_design':pilot,'stress_20k':stress,'organic_holdout':organic,'adaptive_boundaries_v2':adaptive_v2,'external_schema':external,'reviewer2_targeted':targeted_r2,'real_mcp_style':real}
    report={'artifact_revision':'v1.2-r2','splits':{},'baselines':{},'ablations':{},'uncertainty':{},'latency':{},'freeze':{}}

    for split,cases in splits.items():
        report['splits'][split]={}
        for profile in PROFILES:
            rates,_=eval_proxy(cases,profile,raw_name=f'{split}__{profile}.jsonl')
            report['splits'][split][profile]=rates

    # Comment 6: controlled baselines are reported descriptively and repeated on untouched organic holdout.
    for split,cases in {'pilot_design':pilot,'organic_holdout':organic}.items():
        report['baselines'][split]={}
        for d in [B0NoDefense(),B1StaticAllowlist(),B2DefinitionScanning(),B3GatewayFilter()]:
            report['baselines'][split][d.name]=eval_defense(cases,d)
        report['baselines'][split]['B4_full_layer']=eval_proxy(cases,'limited_network')[0]

    # Reviewer 2 Comment 5: identify benign live/workflow definitions that
    # limited-network allows but read-only blocks. Both deny fs.write; the
    # difference comes from allow-listed net.http calls.
    _, ln_rows = eval_proxy(real, 'limited_network')
    _, ro_rows = eval_proxy(real, 'read_only')
    ro_by_id={r['id']:r for r in ro_rows}
    report['live_benign_profile_difference']=[
        {
            'id': r['id'], 'tool_name': r['tool_name'], 'arguments': r['arguments'],
            'limited_network': r['decision'], 'read_only': ro_by_id[r['id']]['decision'],
            'reason': 'allow-listed net.http is permitted by limited-network and denied by read-only'
        }
        for r in ln_rows if r['beneficial'] and r['decision']=='allow' and ro_by_id[r['id']]['decision']=='deny'
    ]

    # Comment 6: repeat component knockouts on organic holdout after final logic freeze.
    configs={
        'full':{},
        'no_argument_inspection':{'inference_config':InferenceConfig(use_argument_inspection=False)},
        'no_sensitive_path_elevation':{'inference_config':InferenceConfig(use_sensitive_path_elevation=False)},
        'no_domain_allowlist':{'use_domain_allow_list':False},
        'no_name_heuristics':{'inference_config':InferenceConfig(use_name_heuristics=False)},
    }
    for split,cases in {'pilot_design':pilot,'organic_holdout':organic}.items():
        report['ablations'][split]={}
        for name,kwargs in configs.items():
            report['ablations'][split][name]=eval_proxy(cases,proxy=make_proxy('limited_network',**kwargs))[0]

    # Comment 7: stratified bootstrap + direct zero-event bounds.
    _,rows=eval_proxy(pilot,'limited_network')
    yt=[not r['beneficial'] for r in rows]; yp=[r['allowed'] for r in rows]
    report['uncertainty']['pilot_stratified_bootstrap']={m:bootstrap_ci(yt,yp,m,n_boot=2000,seed=42) for m in ('asr','bcar','f1')}
    for split,cases in {'organic_holdout':organic,'adaptive_boundaries_v2':adaptive_v2,'real_mcp_style':real}.items():
        rates,_=eval_proxy(cases,'limited_network')
        n=rates['n_attack']; fn=rates['fn']
        entry={'observed_asr_pct':rates['asr'],'n_malicious':n,'successful_malicious_calls':fn}
        if fn==0: entry['one_sided_95pct_upper_asr_pct']=zero_event_upper_bound(n)
        else: entry['asr_wilson_95pct']=wilson_interval(fn,n)
        report['uncertainty'][split]=entry

    # Comment 8: distinct timing boundaries.
    latency_sample=pilot
    report['latency']['checker_only_no_logging']=checker_latency(latency_sample)
    report['latency']['local_proxy_including_sync_logging']=proxy_latency(latency_sample)
    report['latency']['live_end_to_end']='reported separately by scripts/run_live_mcp_eval.py; includes transport/proxy/upstream'
    report['environment']=_host_details()
    report['latency']['checker_only_no_logging']['repetitions']=5
    report['latency']['checker_only_no_logging']['operations_per_repetition']=len(latency_sample)
    report['latency']['checker_only_no_logging']['timed_operation']='PermissionChecker.evaluate only; excludes audit logging, proxy framing, transport, and upstream execution'
    report['latency']['local_proxy_including_sync_logging']['repetitions']=3
    report['latency']['local_proxy_including_sync_logging']['operations_per_repetition']=len(latency_sample)
    report['latency']['local_proxy_including_sync_logging']['timed_operation']='EnforcementProxy.handle_tool_call including synchronous JSONL logging; excludes MCP stdio transport and upstream execution'

    # Frozen implementation provenance / local immutable content hashes.
    freeze_files=[ROOT/'src'/'inference.py',ROOT/'src'/'checker.py',ROOT/'scripts'/'metrics.py',ROOT/'policies'/'limited_network.yaml']
    report['freeze']={str(p.relative_to(ROOT)):sha256(p) for p in freeze_files}
    report['freeze']['note']='Boundary/external-schema evaluations were run against these fixed file hashes; no heuristic edits occurred between split runs.'

    (RES/'reviewer2_revision_evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Human-readable summary.
    lines=['# Reviewer 2 revision evaluation','', 'Metric **BCAR** = benign-call allow rate; it is not task success.','']
    for split in splits:
        r=report['splits'][split]['limited_network']
        lines += [f"## {split}",f"Limited-network: ASR {r['asr']:.2f}% ({r['fn']}/{r['n_attack']} allowed attacks), BCAR {r['bcar']:.2f}% ({r['tn']}/{r['n_benign']} benign calls allowed), F1 {r['f1']:.2f}%.",""]
    lines += ['## Uncertainty']
    for k,v in report['uncertainty'].items(): lines.append(f'- {k}: `{json.dumps(v)}`')
    tr=report['splits']['reviewer2_targeted']['limited_network']
    lines += ['', '## Reviewer-2 renamed-write regression', f"Targeted case: decision security metrics ASR {tr['asr']:.2f}% (0% means the renamed write was blocked).", '', '## Live profile utility difference', f"Benign calls allowed by limited-network but denied by read-only: {[x['id'] for x in report['live_benign_profile_difference']]}", '', '## Latency boundaries', f"- Checker only, no logging: {report['latency']['checker_only_no_logging']}", f"- Local proxy including synchronous logging: {report['latency']['local_proxy_including_sync_logging']}"]
    (RES/'REVIEWER2_REVISION_SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print((RES/'REVIEWER2_REVISION_SUMMARY.md').read_text())

if __name__=='__main__': main()
