from quads.web.auth_helpers import is_cloud_owner


def test_owner_match():
    assert is_cloud_owner("alice", "alice", [])


def test_ccuser_match_and_email_localpart():
    assert is_cloud_owner("bob", "eve", ["bob"])
    assert is_cloud_owner("carol", "eve", ["carol@example.com"])


def test_owner_match_case_insensitive():
    assert is_cloud_owner("ALICE", "alice", [])
    assert is_cloud_owner("alice", "ALICE", [])


def test_non_member_denied():
    assert not is_cloud_owner("mallory", "alice", ["bob"])


def test_anonymous_denied():
    assert not is_cloud_owner(None, "alice", [])


def test_admin_bypass():
    assert is_cloud_owner("zed", "alice", [], roles=["admin"])


def test_string_ccuser_treated_as_single_entry():
    assert is_cloud_owner("alice,bob", "eve", "alice,bob")
    assert not is_cloud_owner("a", "eve", "alice,bob")
    assert not is_cloud_owner("alice", "eve", "alice,bob")


def test_non_string_and_falsy_ccuser_safe():
    assert not is_cloud_owner("mallory", "alice", [None])
    assert not is_cloud_owner("mallory", "alice", None)
    assert not is_cloud_owner("mallory", "alice", "")
