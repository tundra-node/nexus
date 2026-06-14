#!/usr/bin/env python3
"""
Test script for Prism Backend API
Verifies that the backend can be imported and endpoints are defined correctly.
"""

import sys
import json

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
        import httpx
        import asyncio
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_backend_structure():
    """Test that the backend main.py has correct structure."""
    print("\nTesting backend structure...")
    try:
        with open('main.py', 'r') as f:
            content = f.read()
        
        # Check for key components
        checks = [
            ('FastAPI app', 'app = FastAPI('),
            ('Status endpoint', '/api/status'),
            ('Bandwidth endpoint', '/api/bandwidth'),
            ('Tunnels endpoint', '/api/tunnels'),
            ('Router info endpoint', '/api/router-info'),
            ('CORS middleware', 'CORSMiddleware'),
            ('i2pd RPC proxy', 'call_i2pd_rpc'),
        ]
        
        all_passed = True
        for name, pattern in checks:
            if pattern in content:
                print(f"✓ {name} found")
            else:
                print(f"✗ {name} NOT found")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error checking backend structure: {e}")
        return False

def test_pydantic_models():
    """Test that Pydantic models are correctly defined."""
    print("\nTesting Pydantic models...")
    try:
        from main import (
            StatusResponse,
            BandwidthResponse,
            TunnelInfo,
            TunnelsResponse,
            RouterInfoResponse,
        )
        
        # Test StatusResponse
        status = StatusResponse(
            uptime=3600,
            active_peers=10,
            tunnel_count=5,
            tunnels_in=2,
            tunnels_out=3,
            status="online"
        )
        print(f"✓ StatusResponse: {status.model_dump()}")
        
        # Test BandwidthResponse
        bandwidth = BandwidthResponse(
            inbound_rate=1024.5,
            outbound_rate=2048.3,
            total_inbound=1000000,
            total_outbound=2000000
        )
        print(f"✓ BandwidthResponse: {bandwidth.model_dump()}")
        
        # Test TunnelInfo and TunnelsResponse
        tunnel = TunnelInfo(
            id="tunnel123",
            state="established",
            direction="inbound",
            peers=3,
            created=1234567890
        )
        tunnels = TunnelsResponse(tunnels=[tunnel], total=1)
        print(f"✓ TunnelsResponse: {tunnels.model_dump()}")
        
        # Test RouterInfoResponse
        router_info = RouterInfoResponse(
            version="0.9.56",
            identity="router_identity_hash",
            uptime=86400,
            net_id=2
        )
        print(f"✓ RouterInfoResponse: {router_info.model_dump()}")
        
        return True
    except Exception as e:
        print(f"✗ Pydantic model test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Prism Backend - API Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Backend Structure", test_backend_structure()))
    results.append(("Pydantic Models", test_pydantic_models()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✓ All tests passed! Backend is ready to run.")
        return 0
    else:
        print("\n✗ Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
