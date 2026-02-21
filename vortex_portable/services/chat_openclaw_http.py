"""OpenClaw Gateway HTTP client using OpenAI-compatible API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Optional

from ..exceptions import ChatClientError
from ..models import ChatResponse


class OpenClawHttpClient:
    """
    OpenClaw Gateway client using OpenAI-compatible HTTP API.
    
    This follows the same approach as openclaw-voice project:
    connects to OpenClaw Gateway's /v1/chat/completions endpoint
    instead of using WebSocket with device pairing.
    
    OpenClaw maintains session state server-side. By passing the
    conversation_id as the 'user' field in the request, OpenClaw
    derives a stable session key and maintains conversation history.
    
    Usage:
        >>> client = OpenClawHttpClient(
        ...     gateway_url="http://localhost:18789",
        ...     token="your-gateway-token",
        ...     agent_id="main"
        ... )
        >>> response = client.chat("Hello", conversation_id="test-1")
    """

    def __init__(
        self,
        gateway_url: str,
        token: str,
        agent_id: str = "main",
        timeout: float = 30.0,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        """
        Initialize OpenClaw HTTP client.
        
        Args:
            gateway_url: OpenClaw Gateway URL (e.g., http://localhost:18789)
            token: Gateway authentication token
            agent_id: Agent ID in OpenClaw config (default: "main")
            timeout: Request timeout in seconds
            ssl_context: Optional SSL context for HTTPS
        """
        base = gateway_url.rstrip("/")
        self._endpoint = f"{base}/v1/chat/completions"
        self._token = token
        self._model = f"openclaw:{agent_id}"
        self._timeout = timeout
        self._ssl_context = ssl_context

    def chat(
        self, 
        message: str, 
        *, 
        conversation_id: str,
        system_prompt: Optional[str] = None,
        debug: bool = False
    ) -> ChatResponse:
        """
        Send a message to OpenClaw Gateway.
        
        Args:
            message: User message
            conversation_id: Conversation identifier (OpenClaw uses this via 'user' field)
            system_prompt: Optional system prompt override
            debug: Enable debug mode
            
        Returns:
            ChatResponse with the agent's reply
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": message
        })
        
        # OpenClaw uses the 'user' field to derive a stable session key
        # This enables conversation continuity across multiple requests
        payload = {
            "model": self._model,
            "messages": messages,
            "user": conversation_id,
            "stream": False,
        }
        
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        
        try:
            request = urllib.request.Request(
                self._endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            
            with urllib.request.urlopen(
                request,
                timeout=self._timeout,
                context=self._ssl_context,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
                
            # Parse OpenAI-compatible response
            if "choices" not in data or not data["choices"]:
                raise ChatClientError("Invalid response from OpenClaw Gateway")
            
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            
            if not content:
                raise ChatClientError("Empty response from OpenClaw Gateway")
            
            return ChatResponse(
                text=content,
                conversation_id=conversation_id,
                raw=data,
            )
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise ChatClientError(
                f"OpenClaw Gateway HTTP {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise ChatClientError(
                f"Failed to connect to OpenClaw Gateway: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise ChatClientError(
                f"Invalid JSON response from OpenClaw Gateway"
            ) from e
