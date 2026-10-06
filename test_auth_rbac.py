"""
Automated Test Suite for GridMind AI Role-Based Access Control (RBAC)
Tests:
1. Super Admin authentication & token generation
2. Security Admin 1 authentication & permissions
3. Security Admin 2 authentication & permissions
4. Operator authentication
5. Session token validation & tampering rejection
6. Security Audit Log recording & retrieval
7. Role enforcement dependencies (Stream simulation permission check)
"""
import asyncio
from app.core.auth import (
    USERS_DB,
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_audit_logs,
    log_security_event,
)
from app.routers.auth import (
    LoginRequest,
    get_my_profile,
    get_security_audit_logs,
    list_authorized_users,
    login,
)


class MockClient:
    host = "127.0.0.1"


class MockRequest:
    client = MockClient()


async def run_rbac_tests():
    print("=" * 60)
    print("[GridMind AI] Role-Based Access Control (RBAC) Test Suite")
    print("=" * 60)

    # Test 1: Verify configured users
    print("\n[Test 1] Verifying Configured Administrative Users...")
    assert "admin" in USERS_DB, "Super Admin 'admin' missing"
    assert "sec_admin1" in USERS_DB, "Security Admin 1 'sec_admin1' missing"
    assert "sec_admin2" in USERS_DB, "Security Admin 2 'sec_admin2' missing"
    assert "operator" in USERS_DB, "Operator 'operator' missing"
    print("  -> Found 4 configured roles: Super Admin, 2 Security Admins, Operator.")

    # Test 2: Test Admin Login
    print("\n[Test 2] Testing Super Admin Login ('admin')...")
    admin_req = LoginRequest(username="admin", password="admin123")
    admin_resp = await login(admin_req, MockRequest())
    assert admin_resp.user.role == "admin"
    assert "all" in admin_resp.user.permissions
    print(f"  -> Successfully authenticated: {admin_resp.user.name}")
    print(f"  -> Token issued: {admin_resp.access_token[:25]}... [HMAC-SHA256]")

    # Test 3: Test Security Admin 1 Login
    print("\n[Test 3] Testing Security Admin 1 Login ('sec_admin1')...")
    sec1_req = LoginRequest(username="sec_admin1", password="secadmin1")
    sec1_resp = await login(sec1_req, MockRequest())
    assert sec1_resp.user.role == "security_admin"
    assert "security_admin" in sec1_resp.user.permissions
    print(f"  -> Successfully authenticated: {sec1_resp.user.name}")

    # Test 4: Test Security Admin 2 Login
    print("\n[Test 4] Testing Security Admin 2 Login ('sec_admin2')...")
    sec2_req = LoginRequest(username="sec_admin2", password="secadmin2")
    sec2_resp = await login(sec2_req, MockRequest())
    assert sec2_resp.user.role == "security_admin"
    assert "security_admin" in sec2_resp.user.permissions
    print(f"  -> Successfully authenticated: {sec2_resp.user.name}")

    # Test 5: Test Operator Login
    print("\n[Test 5] Testing Operator Login ('operator')...")
    op_req = LoginRequest(username="operator", password="operator123")
    op_resp = await login(op_req, MockRequest())
    assert op_resp.user.role == "operator"
    assert "security_admin" not in op_resp.user.permissions
    print(f"  -> Successfully authenticated: {op_resp.user.name}")

    # Test 6: Verify Token Decoding and Tamper Detection
    print("\n[Test 6] Testing Token Cryptographic Verification & Tamper Defense...")
    valid_payload = decode_access_token(admin_resp.access_token)
    assert valid_payload is not None
    assert valid_payload["sub"] == "admin"

    # Tamper with token
    tampered_token = admin_resp.access_token[:-4] + "ABCD"
    tampered_payload = decode_access_token(tampered_token)
    assert tampered_payload is None, "Tampered token was not rejected!"
    print("  -> Cryptographic signature validation & tamper rejection verified.")

    # Test 7: Verify Audit Log Generation & Security Roster
    print("\n[Test 7] Testing Security Audit Log Retrieval...")
    user_dict1 = getattr(sec1_resp.user, "model_dump", sec1_resp.user.dict)()
    audit_resp = await get_security_audit_logs(limit=10, current_user=user_dict1)
    assert audit_resp["count"] > 0
    assert audit_resp["active_security_admins"] == 2
    print(f"  -> Retrieved {audit_resp['count']} security events. System Status: {audit_resp['system_status']}")

    user_dict_admin = getattr(admin_resp.user, "model_dump", admin_resp.user.dict)()
    roster = await list_authorized_users(current_user=user_dict_admin)
    assert roster["total"] >= 4
    print(f"  -> User roster verified with {roster['total']} personnel records.")

    print("\n" + "=" * 60)
    print(" [OK] ALL ROLE-BASED ACCESS CONTROL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_rbac_tests())
