"""Tests para entidades del dominio de chatbot."""

import pytest

from contractai_backend.modules.chatbot.domain.entities import ConversationTable, Message


def _make_conv(**kwargs) -> ConversationTable:
    defaults = {"organization_id": 1, "user_id": 1, "title": "Mi conversación"}
    defaults.update(kwargs)
    return ConversationTable(**defaults)


class TestConversationTable:
    def test_creates_valid_conversation(self):
        conv = _make_conv()
        assert conv.title == "Mi conversación"
        assert conv.content == []

    def test_positive_ids_accepted(self):
        conv = _make_conv(organization_id=5, user_id=10)
        assert conv.organization_id == 5
        assert conv.user_id == 10


class TestMessage:
    def test_creates_message_with_defaults(self):
        msg = Message(role="user", content="Hola")
        assert msg.role == "user"
        assert msg.content == "Hola"
        assert msg.timestamp is not None

    def test_message_roles(self):
        for role in ("user", "bot", "system"):
            msg = Message(role=role, content="test")
            assert msg.role == role
