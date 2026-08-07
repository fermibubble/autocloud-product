"""Harness-layer envelope minting for the sandbox /run endpoint.

Attaches a signed observation envelope to every command result returned
by the sandbox execution server, giving run_command output the same
tamper-evident provenance as gcp-observe tool results. The signer is the
sandbox server process - the model only ever sees the already-sealed
envelope, so it cannot alter command output without breaking the seal.

Wire-up is 3 lines in the sandbox server (see HARNESS-MINTING.md):

    sys.path.append("/opt/rollout-reviewer/compat/gcp-harness")
    import sandbox_envelope
    ...
    resp = sandbox_envelope.attach(resp, cmd_list, workdir)

What the envelope attests: "this exact command, run in this workdir at
this time, produced these bytes." It does NOT attest that the command
was a trustworthy evidence channel - consumers judge that from
scope.command (a gcloud read under viewer credentials is a vetted
channel; a cat of an agent-writable file is not).

Env knobs: RR_ENVELOPE_PY (signer module path), OBS_MINT_MAX_BYTES
(payload clip per stream, default 256 KiB), OBS_MINT_TTL_SECONDS
(freshness horizon, default 600). The signing key itself is read by the
signer module (OBS_SIGNING_KEY) - same key as the reviewer servers.
"""

import base64
import importlib.util
import os

_ENVELOPE_PY = os.environ.get(
    "RR_ENVELOPE_PY", "/opt/rollout-reviewer/servers/gcp-observe/envelope.py")
_MAX_BYTES = int(os.environ.get("OBS_MINT_MAX_BYTES", "262144"))
_TTL = int(os.environ.get("OBS_MINT_TTL_SECONDS", "600"))

_signer_mod = None


def _signer():
    global _signer_mod
    if _signer_mod is None:
        spec = importlib.util.spec_from_file_location("rr_envelope", _ENVELOPE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _signer_mod = mod
    return _signer_mod


def _decode(b64_text):
    raw = base64.b64decode(b64_text or "")
    return raw[:_MAX_BYTES].decode("utf-8", errors="replace"), len(raw)


def attach(resp, cmd_list, workdir):
    """Add resp["observation_envelope"]; never break the /run response."""
    try:
        if "stdout" not in resp and "stderr" not in resp:
            return resp  # nothing executed - nothing to attest
        stdout, stdout_bytes = _decode(resp.get("stdout"))
        stderr, stderr_bytes = _decode(resp.get("stderr"))
        if "error" in resp:
            completeness = "INCOMPLETE"  # e.g. timeout: partial output
        elif stdout_bytes > _MAX_BYTES or stderr_bytes > _MAX_BYTES:
            completeness = "TRUNCATED"
        else:
            completeness = "COMPLETE"
        resp["observation_envelope"] = _signer().mint(
            "command_output",
            scope={"command": list(cmd_list or []), "workdir": workdir,
                   "executor": "sandbox-run"},
            payload={"returncode": resp.get("returncode"),
                     "stdout": stdout, "stderr": stderr},
            quality={"completeness": completeness,
                     "stdout_bytes": stdout_bytes,
                     "stderr_bytes": stderr_bytes},
            source="sandbox-server",
            ttl_seconds=_TTL,
        )
    except Exception as exc:  # minting must never take down /run
        resp["observation_envelope_error"] = str(exc)
    return resp
