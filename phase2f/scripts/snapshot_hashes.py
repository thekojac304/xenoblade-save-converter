"""Record SHA-256 of the frozen Phase 2E snapshot and check the release-candidate copy equals the live 2E RC."""
import hashlib
import json
import os

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
S = os.path.join(P2F, "snapshot_2E")


def h(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


out = {}
for dp, _, fs in os.walk(S):
    for f in fs:
        p = os.path.join(dp, f)
        out[os.path.relpath(p, S).replace(os.sep, "/")] = h(p)
json.dump(out, open(os.path.join(P2F, "manifests", "snapshot_2E_sha256.json"), "w"), indent=1, sort_keys=True)
pre = "release_candidate_copy/"
bad = [k for k in out if k.startswith(pre) and h(os.path.join(ROOT, "release_candidate", k[len(pre):])) != out[k]]
print(len(out), "files snapshotted; RC copy mismatches:", bad)
