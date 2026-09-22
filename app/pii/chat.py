from copy import deepcopy
from dataclasses import dataclass

from app.pii.processor import PiiProcessor, PreparedRequest


@dataclass(frozen=True, slots=True)
class PreparedChatPayload:
    payload: dict
    prepared_requests: tuple[PreparedRequest, ...]

    @property
    def contains_pii(self) -> bool:
        return any(
            prepared.entity_count > 0
            for prepared in self.prepared_requests
        )


def prepare_chat_payload(
    payload: dict,
    processor: PiiProcessor,
    system_id: str,
) -> PreparedChatPayload:
    masked_payload = deepcopy(payload)
    prepared_requests: list[PreparedRequest] = []

    messages = masked_payload.get("messages")

    if not isinstance(messages, list):
        return PreparedChatPayload(
            payload=masked_payload,
            prepared_requests=(),
        )

    for message in messages:
        if not isinstance(message, dict):
            continue

        content = message.get("content")

        if isinstance(content, str):
            prepared = processor.prepare_request(
                system_id,
                content,
            )
            message["content"] = prepared.masked_text
            prepared_requests.append(prepared)
            continue

        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue

            text = part.get("text")

            if not isinstance(text, str):
                continue

            prepared = processor.prepare_request(
                system_id,
                text,
            )
            part["text"] = prepared.masked_text
            prepared_requests.append(prepared)

    return PreparedChatPayload(
        payload=masked_payload,
        prepared_requests=tuple(prepared_requests),
    )


def _demask_text(
    text: str,
    processor: PiiProcessor,
    prepared_requests: tuple[PreparedRequest, ...],
) -> str:
    result = text

    for prepared in prepared_requests:
        result = processor.finalize_response(
            prepared,
            result,
        )

    return result


def finalize_chat_response(
    response_payload: dict,
    processor: PiiProcessor,
    prepared_requests: tuple[PreparedRequest, ...],
) -> dict:
    restored = deepcopy(response_payload)
    choices = restored.get("choices")

    if not isinstance(choices, list):
        return restored

    for choice in choices:
        if not isinstance(choice, dict):
            continue

        message = choice.get("message")

        if isinstance(message, dict):
            content = message.get("content")

            if isinstance(content, str):
                message["content"] = _demask_text(
                    content,
                    processor,
                    prepared_requests,
                )

    return restored
