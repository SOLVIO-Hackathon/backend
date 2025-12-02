"""
Quick test script to verify ReAct Agent implementation

This script tests the agent endpoint with a simple conversation flow.
Run this after starting the server with: uvicorn main:app --reload
"""

import httpx
import asyncio


async def test_agent_chat():
    """Test the agent chat endpoint"""
    base_url = "http://localhost:8000"

    # First, you need a valid JWT token from /auth/login
    # For this test, you'll need to:
    # 1. Register a CITIZEN user
    # 2. Login to get a token
    # 3. Replace 'YOUR_JWT_TOKEN' below with the actual token

    token = "YOUR_JWT_TOKEN"  # Replace with actual token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Start conversation
        print("Test 1: Starting conversation with agent...")
        response = await client.post(
            f"{base_url}/agent/chat",
            json={
                "message": "Hello! Can you help me report some waste?"
            },
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data['response']}")
        print(f"Workflow Stage: {data['workflow_stage']}")
        print(f"Session ID: {data['session_id']}")
        session_id = data['session_id']
        print()

        # Test 2: Ask about quests
        print("Test 2: Asking about my quests...")
        response = await client.post(
            f"{base_url}/agent/chat",
            json={
                "message": "Show me my quests",
                "session_id": session_id
            },
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data['response']}")
        print()

        # Test 3: Ask for statistics
        print("Test 3: Asking for statistics...")
        response = await client.post(
            f"{base_url}/agent/chat",
            json={
                "message": "What are my quest statistics?",
                "session_id": session_id
            },
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data['response']}")
        print()

        # Test 4: Search for information
        print("Test 4: Searching for waste management info...")
        response = await client.post(
            f"{base_url}/agent/chat",
            json={
                "message": "How should I dispose of plastic waste?",
                "session_id": session_id
            },
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data['response']}")
        print()


if __name__ == "__main__":
    print("=" * 80)
    print("ReAct Agent Test Script")
    print("=" * 80)
    print()
    print("PREREQUISITES:")
    print("1. Server must be running: uvicorn main:app --reload")
    print("2. You need a valid JWT token from /auth/login")
    print("3. User must be CITIZEN type")
    print()
    print("To get a token:")
    print("1. POST to /auth/register with CITIZEN user_type")
    print("2. POST to /auth/login to get access_token")
    print("3. Replace 'YOUR_JWT_TOKEN' in this script with the token")
    print()
    print("=" * 80)
    print()

    # Uncomment to run tests (after adding valid token)
    # asyncio.run(test_agent_chat())

    print("Update the token in this script, then uncomment the asyncio.run line to test!")
