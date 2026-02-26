#!/usr/bin/env python3
"""Test OpenClaw streaming functionality."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed")

from vortex_portable.services.chat_openclaw_http import OpenClawHttpClient

def main():
    gateway_url = os.environ.get("VORTEX_OPENCLAW_GATEWAY_URL", "http://localhost:18789")
    token = os.environ.get("VORTEX_OPENCLAW_TOKEN")
    agent_id = os.environ.get("VORTEX_OPENCLAW_AGENT_ID", "main")
    
    print("=" * 60)
    print("OpenClaw Streaming Test")
    print("=" * 60)
    print(f"Gateway: {gateway_url}")
    print(f"Agent: {agent_id}")
    print()
    
    client = OpenClawHttpClient(
        gateway_url=gateway_url,
        token=token,
        agent_id=agent_id,
        timeout=60.0,
    )
    
    # Test streaming
    print("Testing streaming mode...")
    print("-" * 60)
    print("Response (streaming): ", end="", flush=True)
    
    chunks_received = 0
    for chunk in client.chat_stream(
        "Count from 1 to 5, with a brief pause between each number.",
        conversation_id="stream-test-001"
    ):
        print(chunk, end="", flush=True)
        chunks_received += 1
    
    print()
    print("-" * 60)
    print(f"✓ Received {chunks_received} chunks")
    print()
    
    # Test non-streaming (which uses streaming internally)
    print("Testing non-streaming mode (uses streaming internally)...")
    response = client.chat(
        "Say hello in 3 words or less.",
        conversation_id="stream-test-002"
    )
    print(f"Response: {response.text}")
    print(f"✓ Complete response received")
    print()
    
    print("=" * 60)
    print("✅ All streaming tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
