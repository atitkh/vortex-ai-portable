"""HTTP client for the Vortex `/chat` endpoint."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Dict, Iterable, Optional

from ..exceptions import ChatClientError
from ..models import ChatResponse


class HttpChatClient:
    """
    Minimal HTTP client that talks to the Vortex chat endpoint.

    Usage:
        >>> client = HttpChatClient("http://localhost:8000", api_key=None)
        >>> response = client.chat("Hello", conversation_id="test-1")
        >>> response.text
        'Hi there!'
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/chat"
        self._api_key = api_key
        self._timeout = timeout
        self._ssl_context = ssl_context

    def chat(self, message: str, *, conversation_id: str, debug: bool = False) -> ChatResponse:
        """Send a single message to Vortex and validate the reply shape."""
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "debug": debug,
        }
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        print(f"[chat] Sending to {self._endpoint}...")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=self._ssl_context) as response:  # type: ignore[arg-type]
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
                print(f"[chat] Received response ({len(body)} bytes)")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ChatClientError(f"Chat request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise ChatClientError(f"Chat request could not reach the server: {exc.reason}") from exc

        if "application/json" not in content_type:
            raise ChatClientError(f"Unexpected content type: {content_type}")

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ChatClientError("Chat response was not valid JSON") from exc

        text = _extract_assistant_text(payload)
        conversation_id = _extract_conversation_id(payload)
        return ChatResponse(text=text, conversation_id=conversation_id, raw=payload)

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers


def _extract_assistant_text(payload: Dict[str, object]) -> str:
    """
    Normalize multiple plausible response shapes to a string.

    Accepted shapes (first match wins):
        {"data": {"response": "text"}}
        {"reply": "text"}
        {"message": {"role": "assistant", "content": "text"}}
        {"choices": [{"message": {"role": "assistant", "content": "text"}}]}
    """

    data = payload.get("data")
    if isinstance(data, dict):
        response = data.get("response")
        if isinstance(response, str):
            return response

    if isinstance(payload.get("reply"), str):
        return payload["reply"]  # type: ignore[return-value]

    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    choices = payload.get("choices")
    if isinstance(choices, Iterable):
        for choice in choices:
            if isinstance(choice, dict):
                msg = choice.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str):
                        return content

    raise ChatClientError("Chat response did not contain assistant content")


def _extract_conversation_id(payload: Dict[str, object]) -> Optional[str]:
    data = payload.get("data")
    if isinstance(data, dict):
        conv = data.get("conversation_id")
        if isinstance(conv, str):
            return conv
    message = payload.get("message")
    if isinstance(message, dict):
        conv = message.get("conversation_id")
        if isinstance(conv, str):
            return conv
    return None
