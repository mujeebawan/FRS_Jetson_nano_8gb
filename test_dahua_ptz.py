#!/usr/bin/env python3
"""Test script for Dahua RPC-based PTZ control."""

import asyncio
import hashlib
import random
import httpx

# Camera configuration
CAMERA_IP = "10.1.1.68"
USERNAME = "admin"
PASSWORD = "HDZQ12300618"

# Character set for random string generation (matches Dahua's JS implementation)
RANDOM_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

def sha256(text: str) -> str:
    """Calculate SHA256 hash."""
    return hashlib.sha256(text.encode()).hexdigest()

def generate_random() -> str:
    """Generate random string matching Dahua's format."""
    return ''.join(random.choice(RANDOM_CHARS) for _ in range(6))

def hash_password(password: str, random_str: str) -> str:
    """Hash password using Dahua's algorithm."""
    first_hash = sha256(password)
    return sha256(first_hash + random_str)

async def test_rpc_login():
    """Test RPC login to camera."""
    print("Testing Dahua RPC login...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"http://{CAMERA_IP}/SDK/UNIV_API"

        random_str = generate_random()
        hashed_password = hash_password(PASSWORD, random_str)

        print(f"Random: {random_str}")
        print(f"Hashed password: {hashed_password}")

        login_data = {
            "session": 0,
            "id": 1,
            "call": {"service": "rpc", "method": "login"},
            "params": {
                "userName": USERNAME,
                "password": hashed_password,
                "random": random_str,
                "encryptType": 1,
            }
        }

        print(f"\nSending login request to {url}")
        print(f"Data: {login_data}")

        response = await client.post(url, json=login_data)
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get("result"):
                session_id = result.get("session")
                print(f"\nLogin successful! Session ID: {session_id}")
                return session_id
            else:
                print(f"\nLogin failed: {result.get('error')}")

        return None

async def test_ptz_command(session_id: int):
    """Test PTZ command with session."""
    print(f"\nTesting PTZ zoom with session {session_id}...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"http://{CAMERA_IP}/SDK/UNIV_API"

        # Test zoom in
        ptz_data = {
            "session": session_id,
            "id": 2,
            "call": {"service": "ptz", "method": "setPTZCmd"},
            "params": {
                "channel": 0,
                "code": "ZoomTele",
                "arg1": 0,
                "arg2": 5,
                "arg3": 0,
            }
        }

        cookies = {"WebSessionID": str(session_id)}

        print(f"Sending PTZ command: {ptz_data}")
        response = await client.post(url, json=ptz_data, cookies=cookies)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get("result"):
                print("PTZ command successful!")

                # Wait a bit then stop
                await asyncio.sleep(1)

                stop_data = {
                    "session": session_id,
                    "id": 3,
                    "call": {"service": "ptz", "method": "setPTZCmd"},
                    "params": {
                        "channel": 0,
                        "code": "Stop",
                        "arg1": 0,
                        "arg2": 0,
                        "arg3": 0,
                    }
                }

                print("\nSending stop command...")
                stop_response = await client.post(url, json=stop_data, cookies=cookies)
                print(f"Stop response: {stop_response.text}")

                return True
            else:
                print(f"PTZ command failed: {result.get('error')}")

        return False

async def test_get_capabilities(session_id: int):
    """Test getting PTZ capabilities."""
    print(f"\nTesting getPTZCapa with session {session_id}...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"http://{CAMERA_IP}/SDK/UNIV_API"

        data = {
            "session": session_id,
            "id": 4,
            "call": {"service": "ptz", "method": "getPTZCapa"},
            "params": {"channel": 0}
        }

        cookies = {"WebSessionID": str(session_id)}

        response = await client.post(url, json=data, cookies=cookies)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

async def main():
    print("=" * 60)
    print("Dahua RPC PTZ Test")
    print("=" * 60)

    # Test login
    session_id = await test_rpc_login()

    if session_id:
        # Test getting capabilities
        await test_get_capabilities(session_id)

        # Test PTZ command
        await test_ptz_command(session_id)
    else:
        print("\nLogin failed, cannot test PTZ commands")

if __name__ == "__main__":
    asyncio.run(main())
