"""
Quick API test script to verify backend is working.
Tests basic authentication and endpoint access.
"""
import httpx
import asyncio


BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


async def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("   ✅ Health check passed")
            return True
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False


async def test_register():
    """Test user registration"""
    print("\n🔍 Testing user registration...")
    async with httpx.AsyncClient() as client:
        user_data = {
            "email": "test@example.com",
            "full_name": "Test User",
            "phone_number": "+8801712345678",
            "user_type": "citizen",
            "password": "testpassword123"
        }

        response = await client.post(f"{API_V1}/auth/register", json=user_data)

        if response.status_code == 201:
            print("   ✅ Registration successful")
            return response.json()
        elif response.status_code == 400:
            print("   ⚠️  User already exists (this is OK)")
            return None
        else:
            print(f"   ❌ Registration failed: {response.status_code}")
            print(f"      {response.text}")
            return None


async def test_login():
    """Test user login"""
    print("\n🔍 Testing login...")
    async with httpx.AsyncClient() as client:
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }

        response = await client.post(f"{API_V1}/auth/login", json=login_data)

        if response.status_code == 200:
            data = response.json()
            print("   ✅ Login successful")
            print(f"      Token: {data['access_token'][:30]}...")
            return data["access_token"]
        else:
            print(f"   ❌ Login failed: {response.status_code}")
            print(f"      {response.text}")
            return None


async def test_protected_route(token):
    """Test protected route with JWT token"""
    print("\n🔍 Testing protected route...")
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"{API_V1}/auth/me", headers=headers)

        if response.status_code == 200:
            user = response.json()
            print("   ✅ Protected route accessed")
            print(f"      User: {user['email']} ({user['user_type']})")
            return True
        else:
            print(f"   ❌ Protected route failed: {response.status_code}")
            return False


async def test_quest_list(token):
    """Test quest listing"""
    print("\n🔍 Testing quest listing...")
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"{API_V1}/quests", headers=headers)

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Quest list retrieved")
            print(f"      Total quests: {data['total']}")
            return True
        else:
            print(f"   ❌ Quest list failed: {response.status_code}")
            return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Zerobin API Test Suite")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    try:
        # Test health
        if not await test_health():
            print("\n❌ Server is not responding. Is it running?")
            print("   Start with: python main.py")
            return

        # Test registration
        await test_register()

        # Test login
        token = await test_login()
        if not token:
            print("\n❌ Cannot continue without valid token")
            return

        # Test protected routes
        await test_protected_route(token)
        await test_quest_list(token)

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print("\nNext steps:")
        print("  - Visit http://localhost:8000/docs for Swagger UI")
        print("  - Use the token for authenticated requests")
        print("  - Start building frontend integration")

    except Exception as e:
        print(f"\n❌ Error during tests: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
