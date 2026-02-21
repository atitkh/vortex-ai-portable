#!/usr/bin/env python3
"""
Simple test script for OpenClaw integration.

This script tests the OpenClaw WebSocket client without requiring
the full VortexAI pipeline (no audio/wake word dependencies).

Usage:
    python test_openclaw.py

Environment variables required:
    VORTEX_OPENCLAW_GATEWAY_URL (default: ws://localhost:18789)
    VORTEX_OPENCLAW_TOKEN (required if gateway has auth)
"""

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
    print("⚠️  python-dotenv not installed - .env file won't be loaded")
    print("   Install with: pip install python-dotenv")
    print()

try:
    from vortex_portable.services.chat_openclaw_http import OpenClawHttpClient
    from vortex_portable.exceptions import ChatClientError
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure you've installed the dependencies:")
    print("  pip install python-dotenv")
    sys.exit(1)


def main():
    """Test OpenClaw Gateway connection and chat."""
    # Get configuration from environment
    gateway_url = os.environ.get("VORTEX_OPENCLAW_GATEWAY_URL", "http://localhost:18789")
    token = os.environ.get("VORTEX_OPENCLAW_TOKEN")
    agent_id = os.environ.get("VORTEX_OPENCLAW_AGENT_ID", "main")
    
    print("=" * 60)
    print("OpenClaw Gateway HTTP Test")
    print("=" * 60)
    print(f"Gateway URL: {gateway_url}")
    print(f"Auth Token: {'✓ Set' if token else '✗ Not set'}")
    print(f"Agent ID: {agent_id}")
    print()
    
    if not token:
        print("⚠️  Warning: No authentication configured.")
        print("Set VORTEX_OPENCLAW_TOKEN for gateway auth")
        print()
    
    # Create client
    try:
        print("Creating OpenClaw HTTP client...")
        client = OpenClawHttpClient(
            gateway_url=gateway_url,
            token=token,
            agent_id=agent_id,
            timeout=60.0,
        )
        print("✓ Client created successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        sys.exit(1)
    
    # Test connection and chat
    test_message = "Hello! Can you introduce yourself?"
    conversation_id = "test-session-001"
    
    try:
        print(f"Sending test message: '{test_message}'")
        print(f"Conversation ID: {conversation_id}")
        print()
        print("-" * 60)
        
        response = client.chat(
            test_message,
            conversation_id=conversation_id,
            debug=False,
        )
        
        print("-" * 60)
        print()
        print("✓ Response received successfully!")
        print()
        print("Response:")
        print(f"  Text: {response.text[:200]}{'...' if len(response.text) > 200 else ''}")
        print(f"  Length: {len(response.text)} characters")
        print(f"  Conversation ID: {response.conversation_id}")
        print()
        
        # Test second message to verify session continuity
        print("Testing session continuity with second message...")
        second_message = "What did I just ask you?"
        
        response2 = client.chat(
            second_message,
            conversation_id=conversation_id,
            debug=False,
        )
        
        print("✓ Second response received!")
        print()
        print("Response:")
        print(f"  Text: {response2.text[:200]}{'...' if len(response2.text) > 200 else ''}")
        print(f"  Length: {len(response2.text)} characters")
        print()
        
    except ChatClientError as e:
        print(f"❌ Chat error: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Verify OpenClaw Gateway is running:")
        print("     openclaw status")
        print("  2. Check the gateway URL is correct")
        print("  3. Verify authentication token matches gateway config")
        print("  4. Check OpenClaw logs:")
        print("     openclaw logs --follow")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    
    print()
    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run VortexAI Portable in console mode:")
    print("     VORTEX_CHAT_MODE=openclaw python -m vortex_portable")
    print()
    print("  2. Run in audio mode (requires audio setup):")
    print("     VORTEX_CHAT_MODE=openclaw python -m vortex_portable --mode audio")
    print()
    print("  3. Check the OpenClaw dashboard:")
    print("     http://localhost:18789")
    print()


if __name__ == "__main__":
    main()
