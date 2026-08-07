#!/usr/bin/env python3
"""Prove harness-layer minting end to end, without the harness.

1. Simulate a sandbox /run response and attach an envelope.
2. Verify it with rollout-intel's OWN envelope twin (the consumer).
3. Tamper with payload and scope -> verification must fail.
4. Oversized / timeout output -> quality marked honestly, still sealed.

Run: python3 test-sandbox-minting.py   (stdlib only, no services needed)
"""
import base64
import copy
import importlib.util
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # export/rollout-reviewer
os.environ.setdefault("RR_ENVELOPE_PY",
                      str(ROOT / "servers/gcp-observe/envelope.py"))

sys.path.insert(0, str(HERE))
import sandbox_envelope  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


intel_envelope = load(ROOT / "servers/rollout-intel/rollout_intel/envelope.py",
                      "intel_envelope")

fails = 0


def check(name, ok):
    global fails
    print(("PASS" if ok else "FAIL"), "-", name)
    fails += 0 if ok else 1


# 1. Mint over a simulated /run response (their exact response shape).
cmd = ["gcloud", "logging", "read", "severity>=ERROR", "--format=json"]
resp = {"returncode": 0,
        "stdout": base64.b64encode(
            b'[{"severity": "ERROR", "textPayload": "boom"}]').decode(),
        "stderr": base64.b64encode(b"").decode()}
resp = sandbox_envelope.attach(resp, cmd, "/workspace")
env = resp.get("observation_envelope")
check("envelope attached with obs- id",
      bool(env) and env["observation_id"].startswith("obs-"))
check("scope binds the exact command", env and env["scope"]["command"] == cmd)
check("original /run fields untouched",
      resp["returncode"] == 0 and "stdout" in resp and "stderr" in resp)

# 2. Consumer-side verification via rollout-intel's twin.
ok, reason = intel_envelope.verify(env)
check(f"rollout-intel twin verifies it ({reason})", ok)

# 3. Tampering breaks the seal.
bad = copy.deepcopy(env)
bad["payload"]["stdout"] = bad["payload"]["stdout"].replace("ERROR", "INFO")
ok, reason = intel_envelope.verify(bad)
check(f"tampered stdout rejected ({reason})", not ok)

bad2 = copy.deepcopy(env)
bad2["scope"]["command"] = ["echo", "innocent"]
ok, reason = intel_envelope.verify(bad2)
check(f"tampered command scope rejected ({reason})", not ok)

# 4. Oversized output: clipped payload, marked TRUNCATED, still sealed.
big = {"returncode": 0,
       "stdout": base64.b64encode(
           b"x" * (sandbox_envelope._MAX_BYTES + 1000)).decode(),
       "stderr": base64.b64encode(b"").decode()}
big = sandbox_envelope.attach(big, ["kubectl", "get", "pods", "-A"],
                              "/workspace")
q = big["observation_envelope"]["quality"]
ok, _ = intel_envelope.verify(big["observation_envelope"])
check("oversized output marked TRUNCATED and still verifiable",
      q["completeness"] == "TRUNCATED" and ok)

# 5. Timeout partial output marked INCOMPLETE (their 408 shape).
to = {"error": "TimeoutExpired",
      "stdout": base64.b64encode(b"partial").decode(),
      "stderr": base64.b64encode(b"").decode()}
to = sandbox_envelope.attach(to, ["gcloud", "run", "services", "list"],
                             "/workspace")
check("timeout output marked INCOMPLETE",
      to["observation_envelope"]["quality"]["completeness"] == "INCOMPLETE")

# 6. Error-only response (500 path): no output, no envelope, no crash.
err = sandbox_envelope.attach({"error": "boom"}, ["true"], "/workspace")
check("error-only response left unmodified",
      "observation_envelope" not in err)

print()
print("all checks passed" if fails == 0 else f"{fails} check(s) FAILED")
sys.exit(1 if fails else 0)
