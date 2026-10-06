"""
GridMind AI — Seed Initial Users
==================================
Creates DE and AE demo users in MongoDB with pre-set demo passwords.

DEFAULT DEMO CREDENTIALS:
    DE:  username=de001   password=GridDE@2026!
    AE1: username=ae001   password=GridAE@2026!
    AE2: username=ae002   password=GridAE@2026!

Usage:
    python scripts/seed_users.py                   # uses default demo passwords
    python scripts/seed_users.py --reset           # delete existing users and re-seed
    python scripts/seed_users.py --de-password X --ae-password Y  # custom passwords
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# ---------------------------------------------------------------
# DEFAULT DEMO PASSWORDS (change in production via CLI args / env)
# ---------------------------------------------------------------
DEFAULT_DE_PASSWORD = "GridDE@2026!"
DEFAULT_AE_PASSWORD = "GridAE@2026!"


def main():
    parser = argparse.ArgumentParser(description="Seed GridMind AI demo users")
    parser.add_argument("--de-password", default=None, help="Password for de001 (default: GridDE@2026!)")
    parser.add_argument("--ae-password", default=None, help="Password for ae001/ae002 (default: GridAE@2026!)")
    parser.add_argument("--mongo-uri",   default=os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--db-name",     default=os.getenv("MONGO_DB_NAME", "gridmind_ai"))
    parser.add_argument("--reset",       action="store_true", help="Delete existing seeded users and re-create them")
    args = parser.parse_args()

    # Resolve passwords
    de_pw  = args.de_password  or os.getenv("DE_PASSWORD",  DEFAULT_DE_PASSWORD)
    ae_pw  = args.ae_password  or os.getenv("AE_PASSWORD",  DEFAULT_AE_PASSWORD)

    # Hash passwords with bcrypt
    try:
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    except ImportError:
        print("ERROR: passlib not installed. Run: pip install passlib[bcrypt]")
        sys.exit(1)

    def h(p: str) -> str:
        return pwd_ctx.hash(p)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB at {args.mongo_uri} ...")
    try:
        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[args.db_name]
        print(f"  Connected — database: {args.db_name}\n")
    except ConnectionFailure as exc:
        print(f"  ERROR: Cannot connect to MongoDB: {exc}")
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()

    users_to_seed = [
        {
            "username":      "de001",
            "email":         "de001@gridmind.local",
            "password_hash": h(de_pw),
            "role":          "DE",
            "name":          "Divisional Engineer 001",
            "division_id":   None,          # DE manages ALL divisions
            "is_active":     True,
            "created_at":    now,
        },
        {
            "username":      "ae001",
            "email":         "ae001@gridmind.local",
            "password_hash": h(ae_pw),
            "role":          "AE",
            "name":          "Assistant Engineer 001",
            "division_id":   "DIV001",
            "is_active":     True,
            "created_at":    now,
        },
        {
            "username":      "ae002",
            "email":         "ae002@gridmind.local",
            "password_hash": h(ae_pw),
            "role":          "AE",
            "name":          "Assistant Engineer 002",
            "division_id":   "DIV002",
            "is_active":     True,
            "created_at":    now,
        },
    ]

    # Optional reset
    if args.reset:
        usernames = [u["username"] for u in users_to_seed]
        result = db.users.delete_many({"username": {"$in": usernames}})
        print(f"  RESET: removed {result.deleted_count} existing user(s).\n")

    created = 0
    skipped = 0

    print("Seeding users...")
    for user in users_to_seed:
        if db.users.find_one({"username": user["username"]}):
            print(f"  SKIP    {user['username']}  (already exists — use --reset to recreate)")
            skipped += 1
        else:
            db.users.insert_one(dict(user))
            print(f"  CREATED {user['username']}  role={user['role']}  division={user.get('division_id') or 'ALL'}")
            created += 1

    # Seed sample divisions
    divisions = [
        {"division_id": "DIV001", "name": "Northern Division", "is_active": True},
        {"division_id": "DIV002", "name": "Southern Division", "is_active": True},
        {"division_id": "DIV003", "name": "Eastern Division",  "is_active": True},
        {"division_id": "DIV004", "name": "Western Division",  "is_active": True},
    ]
    print("\nSeeding divisions...")
    for div in divisions:
        if not db.divisions.find_one({"division_id": div["division_id"]}):
            db.divisions.insert_one(div)
            print(f"  CREATED {div['division_id']} — {div['name']}")
        else:
            print(f"  SKIP    {div['division_id']} (already exists)")

    # ---------------------------------------------------------------
    # Final summary — show credentials clearly
    # ---------------------------------------------------------------
    print(f"\n{'='*55}")
    print("  SEED COMPLETE")
    print(f"  {created} user(s) created,  {skipped} skipped.")
    print(f"{'='*55}")
    print()
    print("  ROLE       USERNAME   PASSWORD")
    print("  ---------  ---------  ----------------")
    print(f"  DE         de001      {de_pw}")
    print(f"  AE (DIV001) ae001     {ae_pw}")
    print(f"  AE (DIV002) ae002     {ae_pw}")
    print()
    print("  Login endpoint:")
    print("    POST /api/v1/auth/login")
    print("    Body (form): username=de001&password=<password>")
    print()
    print("  Swagger UI:  http://localhost:8000/docs")
    print("  Login page:  http://localhost:8000/static/login.html")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
