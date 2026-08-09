"""session_db - a per-session episode store in GCS, mounted safely.

Event-driven harnesses run ONE agent turn per checkpoint and may lose
local disk between turns (Cloud Tasks re-dispatches deferred checks to
any instance), so intel.db is mounted from object storage before the
turn and persisted after it. This module is the reference
implementation of that cycle with its four failure modes closed:

1. STALE-WAL CORRUPTION - a warm instance may still hold intel.db-wal
   from an earlier turn; downloading intel.db next to it makes SQLite
   replay the OLD wal over the NEW file. mount() clears db/-wal/-shm
   before downloading.
2. SILENT HISTORY FORK - a download failure that "warns and continues"
   starts a fresh DB, then uploads it over the real history at the end
   of the turn. mount() is fail-CLOSED: a download error raises.
3. WAL LOSS ON UPLOAD - checkpointing while the connection pool still
   holds the file reports busy and leaves this turn's writes in
   intel.db-wal, which is never uploaded. persist() flushes through
   Intel.flush()/Db.flush() (dispose the pool first, TRUNCATE second,
   refuse on busy) so the .db file alone is the complete store.
4. LAST-WRITER-WINS - two deferred checks for one session on different
   instances upload concurrently; the loser's checkpoint vanishes
   silently. mount() records the blob generation and persist() uploads
   with if_generation_match: the stale writer gets a 412 and raises
   loudly instead of overwriting.

Rebinding: point the SERVICE at the mounted path with
`intel.rebind(path)` (or construct Intel with it). Assigning
`intel.db = Db(path)` is NOT enough - the DossierStore and identity
catalog stay bound to the previous store.

Wiring (in-process Intel, one agent turn):

    store = SessionStore(session_id)
    intel.rebind(store.mount())
    try:
        ...run the prompt (begin_review / checks / record)...
    finally:
        store.persist(intel)

Subprocess mode (run-stack.sh): mount() before starting rollout-intel
with INTEL_DB=<mounted path>; at end of turn POST /intel/flush (merges
the WAL, refuses on busy), then store.persist(None).

Requires google-cloud-storage - a harness-side dependency; the servers
themselves never import this module.
"""

from __future__ import annotations

import os
import re

# Session ids name a local directory AND a GCS object path: dot-only
# names ('.', '..') or exotic characters would escape /tmp/sessions or
# produce un-normalized object names ('sessions/../intel.db'), so the
# charset is a strict allowlist starting with an alphanumeric.
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class SessionStore:
    def __init__(self, session_id: str, *, bucket: str | None = None,
                 project: str | None = None,
                 local_root: str = "/tmp/sessions"):
        if (not _SESSION_ID_RE.fullmatch(session_id or "")
                or session_id in (".", "..")):
            raise ValueError(f"invalid session_id {session_id!r}: must match "
                             f"{_SESSION_ID_RE.pattern}")
        self.session_id = session_id
        self.project = project or os.environ.get("AUTOCLOUD_PROJECT_ID", "")
        self.bucket_name = bucket or os.environ["AUTOCLOUD_STATE_BUCKET"]
        self.local_dir = os.path.join(local_root, session_id)
        self.db_path = os.path.join(self.local_dir, "intel.db")
        self.blob_name = f"sessions/{session_id}/intel.db"
        # The GCS generation we mounted; persist() writes only if it is
        # still current. 0 = blob did not exist ("create only").
        self.generation: int | None = None

    def _blob(self):
        from google.cloud import storage
        client = (storage.Client(project=self.project) if self.project
                  else storage.Client())
        return client.bucket(self.bucket_name).blob(self.blob_name)

    def mount(self) -> str:
        """Download the session store (or start empty if none exists yet)
        and return the local path for INTEL_DB / Intel(...). Fail-closed:
        an unreadable existing blob raises rather than forking history."""
        os.makedirs(self.local_dir, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            leftover = self.db_path + suffix
            if os.path.exists(leftover):
                os.remove(leftover)
        blob = self._blob()
        if blob.exists():
            blob.reload()
            self.generation = blob.generation
            # Pinned to the generation we observed: a concurrent writer
            # between reload and download surfaces as an error here, not
            # as a torn mount.
            blob.download_to_filename(self.db_path,
                                      if_generation_match=self.generation)
        else:
            self.generation = 0
        return self.db_path

    def persist(self, intel_or_db=None) -> int:
        """Flush and upload. Pass the Intel service (preferred) or the Db;
        pass None only if the store is already quiesced (subprocess mode
        after POST /intel/flush). Returns the new blob generation."""
        if intel_or_db is not None:
            intel_or_db.flush()  # Intel.flush drains requests; Db.flush
            #                      disposes the pool; both TRUNCATE the WAL
            #                      and raise rather than lose it.
        if self.generation is None:
            raise RuntimeError("persist() before mount(): the generation "
                               "guard has nothing to compare against")
        blob = self._blob()
        try:
            blob.upload_from_filename(self.db_path,
                                      content_type="application/x-sqlite3",
                                      if_generation_match=self.generation)
        except Exception as exc:
            if type(exc).__name__ == "PreconditionFailed":
                raise RuntimeError(
                    f"session {self.session_id}: another writer persisted "
                    "this store after we mounted it (generation moved). This "
                    "turn's writes are NOT uploaded. Re-mount and replay the "
                    "turn - begin_review and the recorder are idempotent, so "
                    "a replay lands cleanly on the merged store.") from exc
            raise
        blob.reload()
        self.generation = blob.generation
        return self.generation
