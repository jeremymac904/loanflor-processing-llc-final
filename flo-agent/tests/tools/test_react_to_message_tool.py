"""Ownership tests for desktop message reactions."""

from unittest.mock import MagicMock

from tools import react_to_message_tool as reactions


def test_reaction_database_closes_when_write_fails(monkeypatch):
    db = MagicMock()
    db.latest_message_row_id.return_value = 42
    db.set_message_reaction.side_effect = RuntimeError("write failed")
    monkeypatch.setattr(reactions, "_open_session_db", lambda: db)
    monkeypatch.setattr(
        reactions,
        "get_session_env",
        lambda _name, _default="": "session-1",
    )

    result = reactions.react_to_message_tool("👍")

    assert "write failed" in result
    db.close.assert_called_once()


def test_agent_profile_identity_reaches_persisted_reaction(monkeypatch):
    db = MagicMock()
    db.latest_message_row_id.return_value = 42
    db.set_message_reaction.return_value = [{"emoji": "💚", "author": "agent", "agent_id": "flo", "at": 1}]
    emitted = MagicMock()
    monkeypatch.setattr(reactions.desktop_ui, "emit", emitted)

    result = reactions._react_to_message_with_db("💚", db=db, session_key="chat-1", agent_id="flo")

    assert '"agent_id": "flo"' in result
    db.set_message_reaction.assert_called_once_with("chat-1", 42, "💚", author="agent", agent_id="flo")
    assert emitted.call_args.args[0] == "message.reaction"
