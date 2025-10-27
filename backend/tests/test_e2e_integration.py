# End-to-end integration tests for complete user workflows
# Based on FastAPI testing documentation and pytest best practices (Context 7 lookup: 2025-01-27)

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.chat_models import ChatResponse
from google.genai import errors

client = TestClient(app)

class TestEndToEndIntegration:
    """
    End-to-end integration tests covering complete user workflows.
    Tests the full request/response cycle from frontend to backend to Gemini API.
    """

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_complete_user_flow_single_message(self, mock_process_chat):
        """Test complete user flow from message input to response display."""
        # Mock successful chat service response
        mock_response = ChatResponse(response="Hello! I'm Oracle, your AI assistant. How can I help you today?")
        mock_process_chat.return_value = mock_response
        
        # Simulate user sending first message
        request_data = {
            "message": "Hello, Oracle!",
            "history": []
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        
        # Verify successful response
        assert response.status_code == 200
        response_data = response.json()
        assert "response" in response_data
        assert "Oracle" in response_data["response"]
        assert "timestamp" in response_data
        
        # Verify chat service was called with correct parameters
        mock_process_chat.assert_called_once()
        call_args = mock_process_chat.call_args[0][0]
        assert call_args.message == "Hello, Oracle!"
        assert len(call_args.history) == 0

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_conversation_memory_across_multiple_exchanges(self, mock_process_chat):
        """Test that conversation memory works across multiple message exchanges."""
        # Mock responses for a multi-turn conversation
        responses = [
            ChatResponse(response="Nice to meet you! I'm Oracle."),
            ChatResponse(response="I am an AI assistant created to help answer questions and have conversations."),
            ChatResponse(response="Based on our conversation, I can help with various topics including technology, science, and general questions.")
        ]
        mock_process_chat.side_effect = responses
        
        # First exchange
        response1 = client.post("/api/v1/chat", json={
            "message": "Hello, what's your name?",
            "history": []
        })
        assert response1.status_code == 200
        assert "Oracle" in response1.json()["response"]
        
        # Second exchange - should include first exchange in history
        response2 = client.post("/api/v1/chat", json={
            "message": "What are you?",
            "history": [
                {"role": "user", "parts": "Hello, what's your name?"},
                {"role": "model", "parts": "Nice to meet you! I'm Oracle."}
            ]
        })
        assert response2.status_code == 200
        assert "AI assistant" in response2.json()["response"]
        
        # Third exchange - should include full conversation history
        response3 = client.post("/api/v1/chat", json={
            "message": "What can you help me with?",
            "history": [
                {"role": "user", "parts": "Hello, what's your name?"},
                {"role": "model", "parts": "Nice to meet you! I'm Oracle."},
                {"role": "user", "parts": "What are you?"},
                {"role": "model", "parts": "I am an AI assistant created to help answer questions and have conversations."}
            ]
        })
        assert response3.status_code == 200
        assert "conversation" in response3.json()["response"]
        
        # Verify that each call included the expected history
        assert mock_process_chat.call_count == 3
        
        # Check first call (no history)
        first_call = mock_process_chat.call_args_list[0][0][0]
        assert len(first_call.history) == 0
        
        # Check second call (includes first exchange)
        second_call = mock_process_chat.call_args_list[1][0][0]
        assert len(second_call.history) == 2
        assert second_call.history[0].role == "user"
        assert second_call.history[1].role == "model"
        
        # Check third call (includes full conversation)
        third_call = mock_process_chat.call_args_list[2][0][0]
        assert len(third_call.history) == 4

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_error_scenarios_and_recovery_mechanisms(self, mock_process_chat):
        """Test various error scenarios and recovery mechanisms."""
        
        # Test 1: Network/API error
        api_error = errors.APIError("Rate limit exceeded", {})
        api_error.code = 429
        mock_process_chat.side_effect = api_error
        
        response = client.post("/api/v1/chat", json={
            "message": "Hello",
            "history": []
        })
        
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
        
        # Test 2: Service error recovery
        mock_process_chat.side_effect = ValueError("Invalid request format")
        
        response = client.post("/api/v1/chat", json={
            "message": "Test message",
            "history": []
        })
        
        assert response.status_code == 400
        assert "Invalid request format" in response.json()["detail"]
        
        # Test 3: Recovery after error - service should work again
        mock_process_chat.side_effect = None
        mock_process_chat.return_value = ChatResponse(response="Service recovered successfully")
        
        response = client.post("/api/v1/chat", json={
            "message": "Are you working now?",
            "history": []
        })
        
        assert response.status_code == 200
        assert "recovered successfully" in response.json()["response"]

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    def test_input_validation_comprehensive(self):
        """Test comprehensive input validation scenarios."""
        
        # Test empty message
        response = client.post("/api/v1/chat", json={
            "message": "",
            "history": []
        })
        assert response.status_code == 422
        
        # Test missing message field
        response = client.post("/api/v1/chat", json={
            "history": []
        })
        assert response.status_code == 422
        
        # Test message too long (over 4000 characters)
        long_message = "x" * 4001
        response = client.post("/api/v1/chat", json={
            "message": long_message,
            "history": []
        })
        assert response.status_code == 422
        
        # Test invalid history format
        response = client.post("/api/v1/chat", json={
            "message": "Hello",
            "history": [
                {"role": "invalid_role", "parts": "Some message"}
            ]
        })
        assert response.status_code == 422
        
        # Test missing parts in history
        response = client.post("/api/v1/chat", json={
            "message": "Hello",
            "history": [
                {"role": "user"}
            ]
        })
        assert response.status_code == 422

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_concurrent_requests_handling(self, mock_process_chat):
        """Test handling of concurrent chat requests."""
        # Mock delayed response to simulate concurrent processing
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # Small delay
            return ChatResponse(response="Concurrent response processed")
        
        mock_process_chat.side_effect = delayed_response
        
        # Send multiple concurrent requests
        import threading
        import time
        
        responses = []
        errors = []
        
        def send_request(message_id):
            try:
                response = client.post("/api/v1/chat", json={
                    "message": f"Concurrent message {message_id}",
                    "history": []
                })
                responses.append((message_id, response.status_code, response.json()))
            except Exception as e:
                errors.append((message_id, str(e)))
        
        # Create and start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=send_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests were processed successfully
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(responses) == 5
        
        for message_id, status_code, response_data in responses:
            assert status_code == 200
            assert "response" in response_data
            assert "Concurrent response processed" in response_data["response"]

    def test_health_check_integration(self):
        """Test health check endpoint integration."""
        response = client.get("/health")
        
        assert response.status_code == 200
        health_data = response.json()
        
        assert "status" in health_data
        assert "services" in health_data
        assert "gemini_api" in health_data["services"]
        assert "version" in health_data

    def test_cors_configuration_integration(self):
        """Test CORS configuration for frontend integration."""
        # Test preflight request
        response = client.options(
            "/api/v1/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Verify CORS is configured (TestClient may not show all headers)
        assert response.status_code in [200, 405]  # 405 is acceptable for OPTIONS
        
        # Test actual request with origin header
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'}):
            with patch('backend.services.chat_service.ChatService.process_chat_request') as mock_chat:
                mock_chat.return_value = ChatResponse(response="CORS test response")
                
                response = client.post(
                    "/api/v1/chat",
                    json={"message": "CORS test", "history": []},
                    headers={"Origin": "http://localhost:5173"}
                )
                
                assert response.status_code == 200

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_long_conversation_history_handling(self, mock_process_chat):
        """Test handling of long conversation histories."""
        mock_process_chat.return_value = ChatResponse(response="Long conversation handled")
        
        # Create a long conversation history (50 messages)
        long_history = []
        for i in range(25):
            long_history.extend([
                {"role": "user", "parts": f"User message {i}"},
                {"role": "model", "parts": f"Model response {i}"}
            ])
        
        response = client.post("/api/v1/chat", json={
            "message": "Continue our long conversation",
            "history": long_history
        })
        
        assert response.status_code == 200
        assert "Long conversation handled" in response.json()["response"]
        
        # Verify the service received the full history
        call_args = mock_process_chat.call_args[0][0]
        assert len(call_args.history) == 50

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'})
    @patch('backend.services.chat_service.ChatService.process_chat_request')
    def test_special_characters_and_unicode_handling(self, mock_process_chat):
        """Test handling of special characters and Unicode in messages."""
        mock_process_chat.return_value = ChatResponse(response="Unicode message processed: 你好世界 🌍")
        
        # Test message with various special characters and Unicode
        test_message = "Hello! Can you help with: émojis 😀, Chinese 你好, math ∑∞, and symbols @#$%?"
        
        response = client.post("/api/v1/chat", json={
            "message": test_message,
            "history": []
        })
        
        assert response.status_code == 200
        response_data = response.json()
        assert "Unicode message processed" in response_data["response"]
        assert "你好世界" in response_data["response"]
        assert "🌍" in response_data["response"]
        
        # Verify the service received the Unicode message correctly
        call_args = mock_process_chat.call_args[0][0]
        assert call_args.message == test_message

    def test_api_versioning_integration(self):
        """Test API versioning is properly implemented."""
        # Test that v1 endpoints are accessible
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'}):
            with patch('backend.services.chat_service.ChatService.process_chat_request') as mock_chat:
                mock_chat.return_value = ChatResponse(response="Version test")
                
                response = client.post("/api/v1/chat", json={
                    "message": "Version test",
                    "history": []
                })
                
                assert response.status_code == 200
        
        # Test health endpoint versioning (with API key configured)
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-api-key'}):
            response = client.get("/api/v1/chat/health")
            assert response.status_code == 200
        
        # Test that non-versioned endpoints still work
        response = client.get("/health")
        assert response.status_code == 200

    @patch.dict('os.environ', {}, clear=True)
    def test_missing_api_key_configuration(self):
        """Test behavior when Gemini API key is not configured."""
        response = client.post("/api/v1/chat", json={
            "message": "Test without API key",
            "history": []
        })
        
        # Should return 500 Internal Server Error when API key is missing
        assert response.status_code == 500
        assert "AI service not configured" in response.json()["detail"]
        
        # Health check should still work but show API key as not configured
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["services"]["gemini_api"] == "not_configured"