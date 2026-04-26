from uuid import UUID, uuid4

from ai_support_copilot.domain.models import Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self) -> None:
        self._conversations: dict[UUID, Conversation] = {}

    async def get_or_create(self, tenant_id: str, conversation_id: UUID | None) -> Conversation:
        if conversation_id and conversation_id in self._conversations:
            conversation = self._conversations[conversation_id]
            if conversation.tenant_id != tenant_id:
                raise PermissionError("conversation belongs to another tenant")
            return conversation
        conversation = Conversation(id=conversation_id or uuid4(), tenant_id=tenant_id)
        self._conversations[conversation.id] = conversation
        return conversation

    async def append(self, message: ConversationMessage) -> None:
        conversation = await self.get_or_create(message.tenant_id, message.conversation_id)
        conversation.messages.append(message)

    async def get(self, tenant_id: str, conversation_id: UUID) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        if not conversation or conversation.tenant_id != tenant_id:
            return None
        return conversation


conversation_repository = ConversationRepository()
