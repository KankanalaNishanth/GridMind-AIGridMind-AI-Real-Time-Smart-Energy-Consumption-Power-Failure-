"""Test all endpoints against live uvicorn server"""
import time
import requests
import uvicorn
import multiprocessing

def run_test():
    # Wait for server to start
    base = "http://127.0.0.1:8000"
    for _ in range(30):
        try:
            r = requests.get(f"{base}/api/v1/health")
            if r.status_code == 200:
                print("Server is up and healthy!")
                break
        except Exception:
            time.sleep(0.5)

    print("\n1. Testing Root (Frontend Index.html)...")
    r = requests.get(f"{base}/")
    assert r.status_code == 200
    assert "GridMind AI" in r.text
    print(f"   [OK] Status: {r.status_code}, Length: {len(r.text)} bytes")

    print("\n2. Testing Static CSS...")
    r = requests.get(f"{base}/css/style.css")
    assert r.status_code == 200
    assert "bg-primary" in r.text
    print(f"   [OK] Status: {r.status_code}, Length: {len(r.text)} bytes")

    print("\n3. Testing Static JS...")
    r = requests.get(f"{base}/js/app.js")
    assert r.status_code == 200
    print(f"   [OK] Status: {r.status_code}, Length: {len(r.text)} bytes")

    print("\n4. Testing Dashboard Summary...")
    r = requests.get(f"{base}/api/v1/dashboard/summary")
    assert r.status_code == 200
    print(f"   [OK] Summary: {r.json()}")

    print("\n5. Testing Clusters Endpoint...")
    r = requests.get(f"{base}/api/v1/dashboard/clusters")
    assert r.status_code == 200
    print(f"   [OK] Circles count: {len(r.json())}")

    print("\n6. Testing Disruption Prediction Endpoint...")
    payload = {
        "circle": "HANUMAKONDA",
        "tot_services": 750,
        "billed_services": 680,
        "load": 320.0,
        "units": 54000.0,
        "month_num": 6
    }
    r = requests.post(f"{base}/api/v1/predict/disruption", json=payload)
    assert r.status_code == 200
    print(f"   [OK] Disruption response: {r.json()}")

    print("\n7. Testing Smart Meter Anomaly Endpoint...")
    payload_anom = {
        "circle": "PEDDAPALLY",
        "tot_services": 500,
        "billed_services": 0,
        "load": 600.0,
        "units": 0.0,
        "month_num": 12
    }
    r = requests.post(f"{base}/api/v1/predict/anomaly", json=payload_anom)
    assert r.status_code == 200
    print(f"   [OK] Anomaly response: {r.json()}")

    print("\n8. Testing SARIMA Demand Forecast Endpoint...")
    r = requests.get(f"{base}/api/v1/predict/forecast?steps=6")
    assert r.status_code == 200
    print(f"   [OK] Forecast points: {len(r.json()['forecast'])}")

    print("\n9. Testing Authentication & RBAC Login for Admins...")
    login_admin = requests.post(f"{base}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_admin.status_code == 200, f"Admin login failed: {login_admin.text}"
    admin_token = login_admin.json()["access_token"]
    print(f"   [OK] Super Admin logged in: {login_admin.json()['user']['name']}")

    login_sec1 = requests.post(f"{base}/api/v1/auth/login", json={"username": "sec_admin1", "password": "secadmin1"})
    assert login_sec1.status_code == 200, f"Sec Admin 1 login failed: {login_sec1.text}"
    print(f"   [OK] Security Admin 1 logged in: {login_sec1.json()['user']['name']}")

    login_sec2 = requests.post(f"{base}/api/v1/auth/login", json={"username": "sec_admin2", "password": "secadmin2"})
    assert login_sec2.status_code == 200, f"Sec Admin 2 login failed: {login_sec2.text}"
    print(f"   [OK] Security Admin 2 logged in: {login_sec2.json()['user']['name']}")

    print("\n10. Testing Kafka Stream Simulation Endpoint with Bearer Token...")
    # Verify unauthenticated request is blocked
    r_unauth = requests.post(f"{base}/api/v1/stream/simulate?n=5")
    assert r_unauth.status_code == 401, f"Expected 401 unauthenticated, got {r_unauth.status_code}"
    print("   [OK] Unauthenticated stream attempt correctly blocked (401)")

    # Authenticated call
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.post(f"{base}/api/v1/stream/simulate?n=5", headers=headers)
    assert r.status_code == 200
    data = r.json()
    print(f"   [OK] Stream processed: {data['messages_processed']}, alerts: {data['alerts_generated']}")

    print("\n11. Testing Security Audit Logs Endpoint...")
    r_audit = requests.get(f"{base}/api/v1/auth/audit-logs", headers=headers)
    assert r_audit.status_code == 200
    print(f"   [OK] Retrieved {r_audit.json()['count']} audit records.")

    print("\n12. Testing Model Evaluation Summary...")
    r = requests.get(f"{base}/api/v1/evaluate/summary")
    assert r.status_code == 200
    print(f"   [OK] Evaluation keys: {list(r.json().keys())}")

    print("\n" + "=" * 50)
    print(" >>> ALL 12 TESTS VERIFIED SUCCESSFULLY! <<<")
    print("=" * 50)

if __name__ == "__main__":
    import threading
    # Start server in background thread if not already running
    try:
        r = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=0.8)
    except Exception:
        threading.Thread(
            target=lambda: uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning"),
            daemon=True
        ).start()
    run_test()
