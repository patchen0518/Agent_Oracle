#!/usr/bin/env python3
"""
Test script to verify that conversation memory is properly maintained
across sessions and server restarts.
"""

import asyncio
import sys
import os
import requests
import json
import time

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.gemini_client import GeminiClient
from backend.services.session_service import SessionService
from backend.services.session_chat_service import SessionChatService
from backend.models.session_models import SessionCreate, MessageCreate
from backend.config.database import get_session


async def test_memory_with_services():
    """Test memory using the service layer directly."""
    print("🧪 Testing conversation memory with service layer...")
    
    # Check if API key is available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return False
    
    try:
        # Initialize services
        gemini_client = GeminiClient(api_key=api_key)
        
        # Get database session
        db_session = next(get_session())
        session_service = SessionService(db_session)
        session_chat_service = SessionChatService(db_session, gemini_client)
        
        # Create a new session
        session_data = SessionCreate(title="Memory Test Session")
        session = await session_service.create_session(session_data)
        session_id = session.id
        print(f"✅ Created session {session_id}")
        
        # Send first message
        response1 = await session_chat_service.send_message(session_id, "My name is Alice and I love pizza.")
        print(f"✅ First message sent. Response: {response1.assistant_message.content[:100]}...")
        
        # Send second message
        response2 = await session_chat_service.send_message(session_id, "What's my favorite food?")
        print(f"✅ Second message sent. Response: {response2.assistant_message.content[:100]}...")
        
        # Clear the Gemini client's session cache to simulate server restart
        gemini_client.active_sessions.clear()
        print("🔄 Cleared session cache (simulating server restart)")
        
        # Send third message - this should still remember the context
        response3 = await session_chat_service.send_message(session_id, "And what's my name again?")
        print(f"✅ Third message after cache clear. Response: {response3.assistant_message.content[:100]}...")
        
        # Check if the responses show memory
        remembers_food = "pizza" in response2.assistant_message.content.lower()
        remembers_name = "alice" in response3.assistant_message.content.lower()
        
        print(f"\n📊 Memory Test Results:")
        print(f"   Remembers favorite food (pizza): {'✅' if remembers_food else '❌'}")
        print(f"   Remembers name (Alice): {'✅' if remembers_name else '❌'}")
        
        # Clean up
        await session_service.delete_session(session_id)
        print(f"🧹 Cleaned up session {session_id}")
        
        success = remembers_food and remembers_name
        if success:
            print("\n🎉 Memory test PASSED! Conversation context is maintained across cache clears.")
        else:
            print("\n❌ Memory test FAILED! Conversation context is not properly maintained.")
        
        return success
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_with_api():
    """Test memory using the REST API."""
    print("\n🌐 Testing conversation memory with REST API...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Check if server is running
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not running or not healthy")
            return False
        
        print("✅ Server is running")
        
        # Create a new session
        session_data = {"title": "API Memory Test Session"}
        response = requests.post(f"{base_url}/api/v1/sessions/", json=session_data)
        if response.status_code != 201:
            print(f"❌ Failed to create session: {response.status_code}")
            return False
        
        session = response.json()
        session_id = session["id"]
        print(f"✅ Created session {session_id}")
        
        # Send first message
        message1 = {"message": "My name is Bob and I'm a software engineer."}
        response = requests.post(f"{base_url}/api/v1/sessions/{session_id}/chat", json=message1)
        if response.status_code != 200:
            print(f"❌ Failed to send first message: {response.status_code}")
            return False
        
        response1_data = response.json()
        print(f"✅ First message sent. Response: {response1_data['assistant_message']['content'][:100]}...")
        
        # Send second message
        message2 = {"message": "What's my profession?"}
        response = requests.post(f"{base_url}/api/v1/sessions/{session_id}/chat", json=message2)
        if response.status_code != 200:
            print(f"❌ Failed to send second message: {response.status_code}")
            return False
        
        response2_data = response.json()
        print(f"✅ Second message sent. Response: {response2_data['assistant_message']['content'][:100]}...")
        
        # Wait a moment, then send third message
        time.sleep(1)
        message3 = {"message": "What's my name?"}
        response = requests.post(f"{base_url}/api/v1/sessions/{session_id}/chat", json=message3)
        if response.status_code != 200:
            print(f"❌ Failed to send third message: {response.status_code}")
            return False
        
        response3_data = response.json()
        print(f"✅ Third message sent. Response: {response3_data['assistant_message']['content'][:100]}...")
        
        # Check if the responses show memory
        remembers_profession = "engineer" in response2_data['assistant_message']['content'].lower()
        remembers_name = "bob" in response3_data['assistant_message']['content'].lower()
        
        print(f"\n📊 API Memory Test Results:")
        print(f"   Remembers profession (engineer): {'✅' if remembers_profession else '❌'}")
        print(f"   Remembers name (Bob): {'✅' if remembers_name else '❌'}")
        
        # Clean up
        requests.delete(f"{base_url}/api/v1/sessions/{session_id}")
        print(f"🧹 Cleaned up session {session_id}")
        
        success = remembers_profession and remembers_name
        if success:
            print("\n🎉 API memory test PASSED! Conversation context is maintained.")
        else:
            print("\n❌ API memory test FAILED! Conversation context is not properly maintained.")
        
        return success
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ API test failed with error: {str(e)}")
        return False


async def main():
    """Run all memory tests."""
    print("🔍 Testing conversation memory fixes...\n")
    
    # Test 1: Service layer test
    service_success = await test_memory_with_services()
    
    # Test 2: API test (optional, only if server is running)
    api_success = test_memory_with_api()
    
    print(f"\n📋 Final Results:")
    print(f"   Service Layer Test: {'✅ PASSED' if service_success else '❌ FAILED'}")
    print(f"   REST API Test: {'✅ PASSED' if api_success else '❌ FAILED (or server not running)'}")
    
    overall_success = service_success  # API test is optional
    if overall_success:
        print(f"\n🎉 Overall: MEMORY FIX SUCCESSFUL!")
    else:
        print(f"\n❌ Overall: MEMORY FIX NEEDS MORE WORK")
    
    return overall_success


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv("backend/.env")
    
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)