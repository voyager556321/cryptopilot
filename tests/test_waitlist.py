"""Waitlist store (marketing landing) — isolated from portfolio logic."""

from src.web.waitlist import WaitlistStore


def test_waitlist_add_and_dedupe(tmp_path):
    store = WaitlistStore(tmp_path)
    a = store.add("You@Email.com", source="landing")
    assert a["ok"] and not a["duplicate"]
    assert a["email"] == "you@email.com"
    b = store.add("you@email.com")
    assert b["duplicate"] is True
    data = (tmp_path / "waitlist.json").read_text(encoding="utf-8")
    assert data.count("you@email.com") == 1


def test_waitlist_rejects_bad_email(tmp_path):
    store = WaitlistStore(tmp_path)
    try:
        store.add("not-an-email")
        assert False, "expected ValueError"
    except ValueError:
        pass
