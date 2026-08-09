"""
Build hold-out split:
  - Dev/stress: template-expanded large_dataset.jsonl
  - Test: original hand-written pilot + unseen tool-name variants

Never tune on test.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets"
OUT = DATA / "holdout"

# Tool-name remaps that keep semantics but are unseen in NAME_RULES exact lists
UNSEEN_NAME_MAP = {
    "read_file": "load_document_bytes",
    "read_file_content": "ingest_text_blob",
    "view_file": "preview_resource",
    "open_file": "open_workspace_resource",
    "list_dir": "enumerate_folder_entries",
    "write_file": "persist_document_bytes",
    "http_request": "invoke_remote_endpoint",
    "run_terminal": "invoke_local_runtime",
    "get_env": "lookup_process_setting",
    "start_process": "launch_background_worker",
}


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(seed: int = 7) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pilot = load_json(DATA / "attack_dataset.json")
    rng = random.Random(seed)

    # Paper-style pilot_87: all 61 malicious + 26 benign (sampled)
    malicious = [c for c in pilot if not c["beneficial"]]
    benign = [c for c in pilot if c["beneficial"]]
    rng.shuffle(benign)
    pilot_87 = malicious + benign[:26]
    # stable order by id
    pilot_87.sort(key=lambda c: c["id"])

    # Unseen test: remap tool names on a copy of pilot cases
    unseen = []
    for c in pilot_87:
        nc = dict(c)
        old = c["tool_name"]
        nc["tool_name"] = UNSEEN_NAME_MAP.get(old, f"custom_{old}")
        nc["id"] = f"UN-{c['id']}"
        nc["notes"] = f"unseen remapped from {old}"
        unseen.append(nc)

    # Dev pointer: stress corpus stays as large_dataset.jsonl (not copied — too big)
    manifest = {
        "seed": seed,
        "dev_stress": "datasets/large_dataset.jsonl",
        "dev_stress_note": "template-expanded; use for stress only, not claim of diversity",
        "pilot_full": "datasets/attack_dataset.json",
        "pilot_87": "datasets/holdout/pilot_87.json",
        "unseen_test": "datasets/holdout/unseen_test.json",
        "counts": {
            "pilot_full": len(pilot),
            "pilot_87": len(pilot_87),
            "pilot_87_malicious": len(malicious),
            "pilot_87_benign": 26,
            "unseen_test": len(unseen),
        },
    }

    with open(OUT / "pilot_87.json", "w", encoding="utf-8") as f:
        json.dump(pilot_87, f, indent=2)
    with open(OUT / "unseen_test.json", "w", encoding="utf-8") as f:
        json.dump(unseen, f, indent=2)
    with open(OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Hold-out written to", OUT)
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
