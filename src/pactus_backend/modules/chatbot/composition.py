"""Composition helpers for the chatbot module."""

from .application.repositories import IConversationRepository
from .application.services import ConversationService


def build_conversation_service(repository: IConversationRepository) -> ConversationService:
    """Builds the conversation application service."""
    return ConversationService(repository=repository)
