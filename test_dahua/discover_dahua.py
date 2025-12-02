#!/usr/bin/env python3
"""
Dahua Camera Discovery Tool
Sends UDP broadcast to discover Dahua cameras on the network
"""
import socket
import struct
import time

# Dahua discovery ports
DISCOVERY_PORT = 37810
BROADCAST_IP = "255.255.255.255"

# Dahua discovery magic packet
DHIP_HEADER = bytes([
    0x44, 0x48, 0x49, 0x50,  # DHIP magic
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
])

def discover_cameras(timeout=5):
    """Discover Dahua cameras on the network."""
    print(f"Searching for Dahua cameras (waiting {timeout}s)...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1)
    
    # Bind to receive responses
    sock.bind(('', DISCOVERY_PORT))
    
    # Send discovery broadcast
    try:
        sock.sendto(DHIP_HEADER, (BROADCAST_IP, DISCOVERY_PORT))
        print("Discovery broadcast sent...")
    except Exception as e:
        print(f"Broadcast error: {e}")
    
    # Listen for responses
    cameras = []
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            data, addr = sock.recvfrom(4096)
            if addr[0] not in [c[0] for c in cameras]:
                cameras.append((addr[0], data))
                print(f"  Found camera at: {addr[0]}")
        except socket.timeout:
            continue
        except Exception as e:
            pass
    
    sock.close()
    return cameras

if __name__ == "__main__":
    cameras = discover_cameras(timeout=5)
    
    if cameras:
        print(f"\n=== Found {len(cameras)} Dahua camera(s) ===")
        for ip, data in cameras:
            print(f"  - {ip}")
    else:
        print("\nNo Dahua cameras found on the network.")
        print("\nPossible reasons:")
        print("  1. Camera not powered on")
        print("  2. Camera not connected to network")
        print("  3. Camera on different subnet")
        print("  4. Camera has discovery disabled")
