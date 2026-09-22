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


def _prepare_chat_text(
    container,
    field_name: str,
    text: str,
    processor: PiiProcessor,
    system_id: str,
) -> PreparedRequest:
    prepared = processor.prepare_request(
        system_id,
        text,
    )
    container[field_name] = prepared.masked_text
    return prepared


def _prepare_chat_message(
    message: dict,
    processor: PiiProcessor,
    system_id: str,
) -> list[PreparedRequest]:
    content = message.get("content")

    if isinstance(content, str):
        return [
            _prepare_chat_text(
                message,
                "content",
                content,
                processor,
                system_id,
            )
        ]

    if not isinstance(content, list):
        return []

    prepared_requests: list[PreparedRequest] = []

    for part in content:
        if not isinstance(part, dict):
            continue

        text = part.get("text")

        if not isinstance(text, str):
            continue

        prepared_requests.append(
            _prepare_chat_text(
                part,
                "text",
                text,
                processor,
                system_id,
            )
        )

    return prepared_requests


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

        prepared_requests.extend(
            _prepare_chat_message(
                message,
                processor,
                system_id,
            )
        )

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

    if isinstance(choices, list):
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
