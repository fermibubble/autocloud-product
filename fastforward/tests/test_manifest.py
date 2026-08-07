"""Table-driven tests for manifest canonicalization, digest, and traits."""

from rollout_fastforward import manifest

LEAK = {"items": [{"kind": "dependency", "name": "pg-pool", "from": "2.1.0", "to": "3.0.0"}]}
RETRY = {"items": [{"kind": "config", "name": "retry_max", "from": 1, "to": 4}]}
CRED = {"items": [{"kind": "dependency", "name": "auth-client", "from": "5.2", "to": "6.0"}]}
BENIGN = {"items": [{"kind": "code", "name": "render", "paths": ["handlers/render.py"]}]}


def test_digest_is_order_insensitive():
    a = {"items": [LEAK["items"][0], RETRY["items"][0], CRED["items"][0]]}
    b = {"items": [CRED["items"][0], LEAK["items"][0], RETRY["items"][0]]}
    assert manifest.digest(a) == manifest.digest(b)


def test_digest_is_path_order_insensitive():
    a = {"items": [{"kind": "code", "name": "x", "paths": ["b.py", "a.py"]}]}
    b = {"items": [{"kind": "code", "name": "x", "paths": ["a.py", "b.py"]}]}
    assert manifest.digest(a) == manifest.digest(b)


def test_digest_changes_on_semantic_change():
    bumped = {"items": [{"kind": "dependency", "name": "pg-pool", "from": "2.1.0", "to": "3.1.0"}]}
    assert manifest.digest(LEAK) != manifest.digest(bumped)


def test_canonicalize_accepts_deploy_event():
    event = {"to_revision": "r2", "change_manifest": LEAK}
    assert manifest.canonicalize(event) == manifest.canonicalize(LEAK)
    assert manifest.digest(event) == manifest.digest(LEAK)


def test_dependency_features():
    feats = manifest.features(LEAK)
    assert "dep:pg-pool" in feats
    assert "dep-class:pool" in feats
    assert "dep-class:db" in feats  # "pg" keyword


def test_config_features():
    assert manifest.features(RETRY) == ["cfg-class:retry", "cfg:retry_max"]


def test_auth_dependency_features():
    feats = manifest.features(CRED)
    assert "dep:auth-client" in feats
    assert "dep-class:auth" in feats
    assert "dep-class:http" in feats  # "client" keyword


def test_code_features_from_paths():
    m = {"items": [{"kind": "code", "name": "conn", "paths": ["src/db/connection.py"]}]}
    assert manifest.features(m) == ["code-touch:connection"]
    m = {"items": [{"kind": "code", "name": "jobs", "paths": ["jobs/cron_runner.py"]}]}
    assert manifest.features(m) == ["code-touch:schedule"]


def test_flag_and_schema_features():
    m = {"items": [{"kind": "flag", "name": "enable-agent-memory", "from": False, "to": True},
                   {"kind": "schema", "name": "orders", "from": "v3", "to": "v4"}]}
    feats = manifest.features(m)
    assert "flag:enable-agent-memory" in feats
    assert "schema:orders" in feats
    assert "kind:schema" in feats


def test_benign_code_item_has_no_features():
    assert manifest.features(BENIGN) == []
