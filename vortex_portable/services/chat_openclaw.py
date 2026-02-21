"""OpenClaw Gateway client for agent communication via WebSocket."""

from __future__ import annotations

import json
import logging
import ssl
import time
import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import websocket as websocket_module
else:
    websocket_module = None  # type: ignore[assignment]

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore[assignment]

from ..exceptions import ChatClientError
from ..models import ChatResponse
from ..device_identity import DeviceIdentity

logger = logging.getLogger(__name__)


class OpenClawChatClient:
    """
    WebSocket client that connects to OpenClaw Gateway and sends chat requests.

    OpenClaw Gateway is a self-hosted gateway for AI agents that uses WebSocket
    with a JSON-RPC-like protocol. This client implements the protocol to send
    chat messages and receive responses.

    Protocol:
        1. Connect with WebSocket
        2. Send connect request with authentication
        3. Receive hello-ok response
        4. Send chat.send requests with the user message
        5. Receive chat events with streaming responses
        6. Poll for completion or error

    Usage:
        >>> client = OpenClawChatClient(
        ...     gateway_url="ws://localhost:18789",
        ...     token="your-gateway-token"
        ... )
        >>> response = client.chat("Hello", conversation_id="test-1")
        >>> response.text
        'Hi there!'
    """

    def __init__(
        self,
        gateway_url: str,
        *,
        token: Optional[str] = None,
        password: Optional[str] = None,
        device_token: Optional[str] = None,
        timeout: float = 60.0,
        ssl_context: Optional[ssl.SSLContext] = None,
        device_id: Optional[str] = None,
        client_id: Optional[str] = "vortex-portable",
        client_version: Optional[str] = "1.0.0",
    ) -> None:
        """
        Initialize the OpenClaw Gateway client.

        Args:
            gateway_url: WebSocket URL of the OpenClaw Gateway (e.g., ws://localhost:18789)
            token: Gateway authentication token (preferred)
            password: Gateway authentication password (alternative to token)
            device_token: Pre-authorized device token (if device is already paired)
            timeout: Timeout in seconds for responses
            ssl_context: Optional SSL context for wss:// connections
            device_id: Optional stable device identifier
            client_id: Client identifier sent in connect handshake
            client_version: Client version sent in connect handshake
        """
        if websocket is None:
            raise ImportError(
                "websocket-client is required for OpenClaw integration. "
                "Install it with: pip install websocket-client"
            )

        self._gateway_url = gateway_url.rstrip("/")
        self._token = token
        self._password = password
        self._device_token = device_token
        self._timeout = timeout
        self._ssl_context = ssl_context
        self._device_id = device_id or f"vortex-{uuid.uuid4().hex[:12]}"
        self._client_id = client_id
        self._client_version = client_version
        self._ws: Optional[Any] = None  # websocket.WebSocket when connected
        self._protocol_version = 3
        self._session_key = "main"  # Default session key for OpenClaw
        
        # Initialize device identity manager (handles persistent Ed25519 keypair)
        self._device_identity = DeviceIdentity(self._device_id)

    def _connect_gateway(self) -> None:
        """Establish WebSocket connection and perform handshake."""
        if self._ws and self._ws.connected:
            return

        logger.info(f"Connecting to OpenClaw Gateway at {self._gateway_url}...")

        # Create WebSocket connection
        self._ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE} if self._ssl_context else None)
        self._ws.connect(self._gateway_url, timeout=self._timeout)

        # Wait for potential connect.challenge event
        challenge_nonce = None
        try:
            self._ws.settimeout(1.0)  # Short timeout for challenge
            frame = self._ws.recv()
            if frame:
                msg = json.loads(frame)
                if msg.get("type") == "event" and msg.get("event") == "connect.challenge":
                    challenge_nonce = msg.get("payload", {}).get("nonce")
                    logger.debug(f"Received connect challenge with nonce: {challenge_nonce}")
        except Exception:
            # No challenge received or timeout, continue without it
            pass
        finally:
            self._ws.settimeout(self._timeout)

        # Send connect request
        connect_request = self._build_connect_request(challenge_nonce)
        
        # Debug: Log what we're sending (sanitize sensitive data)
        debug_request = connect_request.copy()
        if "params" in debug_request and "auth" in debug_request["params"]:
            debug_request["params"]["auth"] = {"token": "***"}
        logger.debug(f"Sending connect request: {json.dumps(debug_request, indent=2)}")
        
        self._send_request(connect_request)

        # Wait for hello-ok response
        response = self._receive_response(connect_request["id"])
        if not response.get("ok"):
            error = response.get("error", {})
            error_msg = error.get("message", "Unknown error")
            error_code = error.get("code", "unknown")
            
            # Log full error for debugging
            logger.error(f"OpenClaw connection error: {error_msg} (code: {error_code})")
            logger.debug(f"Full error response: {json.dumps(error, indent=2)}")
            
            # Check if it's a pairing/device issue
            if "device" in error_msg.lower() or "pairing" in error_msg.lower() or "identity" in error_msg.lower():
                # Enhanced error message with pairing instructions
                pairing_help = (
                    f"\n\n"
                    f"Device pairing required!\n"
                    f"Device ID: {self._device_id}\n\n"
                    f"To approve this device:\n"
                    f"1. List pending approvals: openclaw devices list\n"
                    f"2. Approve: openclaw devices approve <requestId>\n\n"
                    f"Or save this device ID to .env to persist:\n"
                    f"VORTEX_OPENCLAW_DEVICE_ID={self._device_id}\n\n"
                    f"Note: ws://127.0.0.1:18789 connections should auto-approve.\n"
                    f"If you're still seeing this, check OpenClaw logs: openclaw logs --follow"
                )
                raise ChatClientError(f"Gateway connection failed: {error_msg}{pairing_help}")
            
            raise ChatClientError(f"Gateway connection failed: {error_msg}")

        # Check if gateway issued a device token (for future connections)
        payload = response.get("payload", {})
        if isinstance(payload, dict):
            auth_info = payload.get("auth")
            if isinstance(auth_info, dict):
                issued_device_token = auth_info.get("deviceToken")
                if issued_device_token:
                    logger.info(f"Received device token from gateway (save for future use)")
                    print(f"\n✓ Gateway issued device token (save this to .env):")
                    print(f"  VORTEX_OPENCLAW_DEVICE_TOKEN={issued_device_token}\n")
                    self._device_token = issued_device_token

        logger.info("Successfully connected to OpenClaw Gateway")

    def _build_connect_request(self, challenge_nonce: Optional[str] = None) -> Dict[str, Any]:
        """Build the connect handshake request."""
        auth: Dict[str, str] = {}
        # Only use gateway token or password, NOT device token
        # Device tokens are received after connecting, not sent during connect
        if self._token:
            auth["token"] = self._token
        elif self._password:
            auth["password"] = self._password

        # Build device identity using persistent Ed25519 keypair
        current_time = int(time.time() * 1000)
        device = self._device_identity.get_device_identity(current_time, challenge_nonce)
        
        if self._device_token:
            logger.debug(f"Building connect request with device token for: {self._device_id}")
        else:
            logger.debug(f"Building connect request - Initial pairing for device: {self._device_id}")

        return {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "connect",
            "params": {
                "minProtocol": self._protocol_version,
                "maxProtocol": self._protocol_version,
                "client": {
                    "id": "cli",
                    "version": self._client_version,
                    "platform": "macos",
                    "mode": "cli",
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": auth,
                "locale": "en-US",
                "userAgent": f"openclaw-cli/{self._client_version}",
                "device": device,
            },
        }

    def _send_request(self, request: Dict[str, Any]) -> None:
        """Send a request frame to the gateway."""
        if not self._ws or not self._ws.connected:
            raise ChatClientError("WebSocket is not connected")
        
        payload = json.dumps(request)
        logger.debug(f"Sending request: {request['method']}")
        self._ws.send(payload)

    def _receive_response(self, request_id: str) -> Dict[str, Any]:
        """Wait for a response with the matching request ID."""
        if not self._ws:
            raise ChatClientError("WebSocket is not connected")

        start_time = time.time()
        while time.time() - start_time < self._timeout:
            try:
                frame = self._ws.recv()
                if not frame:
                    continue

                msg = json.loads(frame)
                
                # Handle events (log them but continue waiting for response)
                if msg.get("type") == "event":
                    event_name = msg.get("event")
                    logger.debug(f"Received event: {event_name}")
                    continue

                # Handle responses
                if msg.get("type") == "res" and msg.get("id") == request_id:
                    return msg

            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                raise ChatClientError(f"Error receiving response: {exc}") from exc

        raise ChatClientError(f"Timeout waiting for response to request {request_id}")

    def _receive_chat_events(self, run_id: str) -> str:
        """Receive and accumulate chat events until completion."""
        if not self._ws:
            raise ChatClientError("WebSocket is not connected")

        accumulated_text = ""
        start_time = time.time()

        while time.time() - start_time < self._timeout:
            try:
                frame = self._ws.recv()
                if not frame:
                    continue

                msg = json.loads(frame)
                
                # Handle chat events
                if msg.get("type") == "event" and msg.get("event") == "chat":
                    payload = msg.get("payload", {})
                    
                    # Check if this is for our run
                    if payload.get("runId") != run_id:
                        continue
                    
                    # Extract text chunks
                    delta = payload.get("delta", {})
                    if "text" in delta:
                        accumulated_text += delta["text"]
                        logger.debug(f"Received text chunk: {delta['text'][:50]}...")
                    
                    # Check for completion
                    status = payload.get("status")
                    if status in ("done", "completed", "ok"):
                        logger.info(f"Chat completed with {len(accumulated_text)} characters")
                        return accumulated_text
                    elif status == "error":
                        error_msg = payload.get("error", {}).get("message", "Unknown error")
                        raise ChatClientError(f"Chat failed: {error_msg}")
                
                # Handle agent events (may contain final text)
                elif msg.get("type") == "event" and msg.get("event") == "agent":
                    payload = msg.get("payload", {})
                    
                    if payload.get("runId") != run_id:
                        continue
                    
                    # Extract text from agent completion
                    if payload.get("status") in ("done", "completed", "ok"):
                        text = payload.get("text") or payload.get("content")
                        if text and not accumulated_text:
                            accumulated_text = text
                        logger.info(f"Agent run completed")
                        return accumulated_text

            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                if accumulated_text:
                    # Return partial text if we have it
                    logger.warning(f"Error during chat event stream, returning partial: {exc}")
                    return accumulated_text
                raise ChatClientError(f"Error receiving chat events: {exc}") from exc

        # Timeout - return what we have
        if accumulated_text:
            logger.warning(f"Timeout receiving chat events, returning partial text")
            return accumulated_text
        
        raise ChatClientError("Timeout waiting for chat completion")

    def chat(self, message: str, *, conversation_id: str, debug: bool = False) -> ChatResponse:
        """
        Send a chat message to the OpenClaw Gateway agent.

        Args:
            message: User message text
            conversation_id: Conversation/session identifier (mapped to OpenClaw sessionKey)
            debug: Enable debug mode (affects agent verbosity)

        Returns:
            ChatResponse with the assistant's reply
        """
        # Ensure we're connected
        self._connect_gateway()

        # Build chat.send request
        run_id = str(uuid.uuid4())
        chat_request = {
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "chat.send",
            "params": {
                "sessionKey": self._session_key,
                "text": message,
                "runId": run_id,
                "idempotencyKey": str(uuid.uuid4()),
                "thinking": debug,  # Enable thinking mode if debug
                "verbose": debug,
            },
        }

        print(f"[openclaw] Sending message to agent...")
        self._send_request(chat_request)

        # Wait for acknowledgment response
        ack_response = self._receive_response(chat_request["id"])
        if not ack_response.get("ok"):
            error = ack_response.get("error", {})
            raise ChatClientError(f"Chat request failed: {error.get('message', 'Unknown error')}")

        payload = ack_response.get("payload", {})
        actual_run_id = payload.get("runId", run_id)
        status = payload.get("status")
        
        if status == "error":
            raise ChatClientError(f"Chat request rejected: {payload.get('error', {}).get('message', 'Unknown')}")

        print(f"[openclaw] Receiving response stream...")
        
        # Receive chat events and accumulate response
        response_text = self._receive_chat_events(actual_run_id)

        if not response_text:
            raise ChatClientError("Empty response from agent")

        return ChatResponse(
            text=response_text,
            conversation_id=conversation_id,  # Keep the original for continuity
            raw={"runId": actual_run_id, "sessionKey": self._session_key},
        )

    def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws and self._ws.connected:
            try:
                self._ws.close()
                logger.info("Closed OpenClaw Gateway connection")
            except Exception as exc:
                logger.warning(f"Error closing WebSocket: {exc}")
        self._ws = None

    def __del__(self) -> None:
        """Ensure connection is closed on cleanup."""
        self.close()
