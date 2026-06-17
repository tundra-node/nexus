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
        print("  OK - All imports successful")
        return True
    except ImportError as e:
        print(f"  FAIL - Import error: {e}")
        return False


def test_backend_structure():
    """Test that the backend modules have correct structure."""
    print("\nTesting backend structure...")
    try:
        # Check main.py (routes)
        with open('services/router/main.py', 'r') as f:
            main_content = f.read()

        # Check client.py (I2PControl + webconsole)
        with open('services/router/client.py', 'r') as f:
            client_content = f.read()

        # Check models.py (Pydantic)
        with open('services/router/models.py', 'r') as f:
            models_content = f.read()

        checks = [
            ('FastAPI app (main.py)', 'app = FastAPI(', main_content),
            ('Status endpoint (main.py)', '/api/status', main_content),
            ('Bandwidth endpoint (main.py)', '/api/bandwidth', main_content),
            ('Tunnels endpoint (main.py)', '/api/tunnels', main_content),
            ('Router info endpoint (main.py)', '/api/router-info', main_content),
            ('CORS middleware (main.py)', 'CORSMiddleware', main_content),
            ('Health endpoint (main.py)', '/health', main_content),
            ('Router health endpoint (main.py)', '/api/router-health', main_content),
            ('I2PControl session (client.py)', 'I2PControlSession', client_content),
            ('Webconsole scraper (client.py)', 'scrape_main_page', client_content),
            ('Bandwidth cache (client.py)', 'BandwidthCache', client_content),
            ('Pydantic models (models.py)', 'StatusResponse', models_content),
            ('TunnelEntry model (models.py)', 'TunnelEntry', models_content),
        ]

        all_passed = True
        for name, pattern, content in checks:
            if pattern in content:
                print(f"  OK - {name}")
            else:
                print(f"  FAIL - {name} NOT found")
                all_passed = False

        return all_passed
    except Exception as e:
        print(f"  FAIL - Error checking backend structure: {e}")
        return False


def test_pydantic_models():
    """Test that Pydantic models are correctly defined."""
    print("\nTesting Pydantic models...")
    try:
        from services.router.models import (
            StatusResponse,
            BandwidthResponse,
            TunnelEntry,
            TunnelsResponse,
            RouterInfoResponse,
            RouterDetailsResponse,
            TransportInfo,
            I2pTunnelDestination,
            SetBandwidthRequest,
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
        print(f"  OK - StatusResponse: {status.model_dump()}")

        # Test BandwidthResponse
        bandwidth = BandwidthResponse(
            inbound_rate=1024.5,
            outbound_rate=2048.3,
            total_inbound=1000000,
            total_outbound=2000000
        )
        print(f"  OK - BandwidthResponse: {bandwidth.model_dump()}")

        # Test TunnelEntry and TunnelsResponse
        tunnel = TunnelEntry(
            id="tunnel123",
            state="established",
            direction="inbound",
            latency_ms=50,
            data_kib=128.5,
        )
        tunnels = TunnelsResponse(tunnels=[tunnel], total=1)
        print(f"  OK - TunnelsResponse: {tunnels.model_dump()}")

        # Test RouterInfoResponse
        router_info = RouterInfoResponse(
            version="0.9.56",
            identity="router_identity_hash",
            uptime=86400,
            net_id=2
        )
        print(f"  OK - RouterInfoResponse: {router_info.model_dump()}")

        # Test RouterDetailsResponse
        details = RouterDetailsResponse(
            identity="test_ident",
            caps="OR",
            version="0.9.56",
            external_address="1.2.3.4 1234",
            routers=100,
            floodfills=20,
            leasesets=50,
            client_tunnels=5,
            transit_tunnels=10,
            network_status="OK",
            tunnel_success_rate=95,
            uptime="2h 30m",
            received="1.5 MB",
            sent="2.0 MB",
            transit="500 KB",
            services={"HTTP Proxy": "enabled", "SOCKS Proxy": "enabled"},
        )
        print(f"  OK - RouterDetailsResponse: {details.model_dump()}")

        # Test TransportInfo
        transport = TransportInfo(name="NTCP2", peers=15)
        print(f"  OK - TransportInfo: {transport.model_dump()}")

        # Test I2pTunnelDestination
        dest = I2pTunnelDestination(name="abyssal", b32="abc123")
        print(f"  OK - I2pTunnelDestination: {dest.model_dump()}")

        # Test SetBandwidthRequest
        req = SetBandwidthRequest(inbound=128, outbound=64)
        print(f"  OK - SetBandwidthRequest: {req.model_dump()}")

        return True
    except Exception as e:
        print(f"  FAIL - Pydantic model test failed: {e}")
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
        symbol = "OK" if passed else "FAIL"
        print(f"  {symbol} - {name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\nAll tests passed! Backend is ready to run.")
        return 0
    else:
        print("\nSome tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
