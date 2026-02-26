"""OpenClaw Gateway HTTP client using OpenAI-compatible API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Iterator, Optional

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
    
    Supports both streaming (SSE) and non-streaming responses.
    
    Usage:
        >>> client = OpenClawHttpClient(
        ...     gateway_url="http://localhost:18789",
        ...     token="your-gateway-token",
        ...     agent_id="main"
        ... )
        >>> response = client.chat("Hello", conversation_id="test-1")
        >>> 
        >>> # Or stream chunks as they arrive:
        >>> for chunk in client.chat_stream("Hello", conversation_id="test-1"):
        ...     print(chunk, end="", flush=True)
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
        
        Uses streaming internally for better timeout handling,
        but returns the complete response as a ChatResponse.
        
        Args:
            message: User message
            conversation_id: Conversation identifier (OpenClaw uses this via 'user' field)
            system_prompt: Optional system prompt override
            debug: Enable debug mode
            
        Returns:
            ChatResponse with the agent's reply
        """
        # Use streaming internally to accumulate the response
        # This provides better timeout behavior for long responses
        chunks = []
        try:
            for chunk in self.chat_stream(
                message,
                conversation_id=conversation_id,
                system_prompt=system_prompt,
                debug=debug
            ):
                chunks.append(chunk)
        except ChatClientError:
            # Re-raise chat client errors
            raise
        
        full_text = "".join(chunks)
        
        if not full_text:
            raise ChatClientError("Empty response from OpenClaw Gateway")
        
        return ChatResponse(
            text=full_text,
            conversation_id=conversation_id,
            raw={"streaming": True, "chunks": len(chunks)},
        )

    def chat_stream(
        self, 
        message: str, 
        *, 
        conversation_id: str,
        system_prompt: Optional[str] = None,
        debug: bool = False
    ) -> Iterator[str]:
        """
        Send a message to OpenClaw Gateway and stream the response.
        
        Yields text chunks as they arrive via Server-Sent Events (SSE).
        This allows for lower latency - you can start processing/speaking
        the response before it's fully generated.
        
        Args:
            message: User message
            conversation_id: Conversation identifier (OpenClaw uses this via 'user' field)
            system_prompt: Optional system prompt override
            debug: Enable debug mode
            
        Yields:
            Text chunks as they arrive from the agent
            
        Example:
            >>> for chunk in client.chat_stream("Hello", conversation_id="test"):
            ...     print(chunk, end="", flush=True)
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
        
        payload = {
            "model": self._model,
            "messages": messages,
            "user": conversation_id,
            "stream": True,  # Enable SSE streaming
        }
        
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
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
                # Read SSE stream line by line
                for line_bytes in response:
                    line = line_bytes.decode("utf-8").strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Check for end marker
                    if line == "data: [DONE]":
                        break
                    
                    # Parse SSE data line
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        try:
                            data = json.loads(data_str)
                            
                            # Extract content delta from OpenAI format
                            if "choices" in data and data["choices"]:
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                
                                if content:
                                    yield content
                                    
                        except json.JSONDecodeError:
                            # Skip malformed JSON chunks
                            continue
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise ChatClientError(
                f"OpenClaw Gateway HTTP {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise ChatClientError(
                f"Failed to connect to OpenClaw Gateway: {e.reason}"
            ) from e
