"""Package the ARM bundle: python tests/make_zip.py [out.zip]
Skips __pycache__, the scratch mutation folder and work/ chunk copies of the robustness long-input run."""
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "academic-polish-ledger_arm_v0.1.0.zip")
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for r, ds, fs in os.walk(ROOT):
        ds[:] = [d for d in ds if d not in ("__pycache__", ".git", "_mut_tmp")]
        rel_dir = os.path.relpath(r, ROOT).replace(os.sep, "/")
        if rel_dir.startswith("tests/cases/") and ("/work" in rel_dir or "/output" in rel_dir):
            continue  # scratch runs; the evaluated runs are under execution/results/cases
        if rel_dir.startswith("execution/results/robustness/long_input/work/chunks"):
            continue
        for f in fs:
            p = os.path.join(r, f)
            z.write(p, os.path.relpath(p, ROOT).replace(os.sep, "/"))
            n += 1
with open(out, "rb") as fh:
    print(n, "files", round(os.path.getsize(out) / 1e6, 2), "MB", hashlib.sha256(fh.read()).hexdigest(), out)
