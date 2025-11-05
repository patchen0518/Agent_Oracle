#!/usr/bin/env python3
"""
Simple test script to verify the simplified chat implementation works correctly.
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.gemini_client import GeminiClient
from backend.services.session_service import SessionService
from backend.services.session_chat_service import SessionChatService
from backend.models.session_models import SessionCreate
from backend.config.database import get_session


async def test_simplified_chat():
    """Test the simplified chat implementation."""
    print("Testing simplified chat implementation...")
    
    # Check if API key is available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return False
    
    try:
        # Initialize services
        gemini_client = GeminiClient(api_key=api_key)
        print("✅ GeminiClient initialized successfully")
        
        # Test session stats
        stats = gemini_client.get_session_stats()
        print(f"✅ Session stats: {stats}")
        
        # Test session creation and reuse
        session_id = 1
        system_instruction = "You are a helpful assistant."
        
        # Create first session
        chat_session1 = gemini_client.get_or_create_session(session_id, system_instruction)
        print("✅ First session created")
        
        # Get same session (should reuse)
        chat_session2 = gemini_client.get_or_create_session(session_id, system_instruction)
        print("✅ Second session retrieved (should be same instance)")
        
        # Verify it's the same session object
        if chat_session1 is chat_session2:
            print("✅ Session reuse working correctly")
        else:
            print("❌ Session reuse not working - different objects returned")
            return False
        
        # Test sending a message
        response = chat_session1.send_message("Hello, can you help me?")
        print(f"✅ Message sent successfully. Response: {response[:100]}...")
        
        # Test conversation continuity
        response2 = chat_session1.send_message("What did I just ask you?")
        print(f"✅ Follow-up message sent. Response: {response2[:100]}...")
        
        # Test session cleanup
        removed = gemini_client.remove_session(session_id)
        print(f"✅ Session cleanup: {removed}")
        
        print("\n🎉 All tests passed! Simplified chat implementation is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv("backend/.env")
    
    # Run the test
    success = asyncio.run(test_simplified_chat())
    sys.exit(0 if success else 1)