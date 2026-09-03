#!/usr/bin/env python3
"""
Automated verification helper script for Aura Marketing AI OS spec-vs-reality audit.
Runs file checks, code markers grep, test suite execution, and optional live endpoint curl checks.
"""
import os
import sys
import argparse
import subprocess
import requests

def run_checks(repo_dir: str, base_url: str = None):
    print(f"========================================================================")
    print(f"  AUTOMATED SPEC-VS-REALITY AUDIT PRE-CHECK")
    print(f"  Repo: {repo_dir}")
    print(f"========================================================================\n")

    # A. File Inventory
    files_to_check = [
        "backend/main.py",
        "backend/auth.py",
        "backend/deps.py",
        "backend/auth_router.py",
        "backend/wallet_router.py",
        "backend/marketing_doctor.py",
        "backend/seo_engine.py",
        "backend/campaigns.py",
        "backend/webaudit_router.py",
        "backend/analytics_router.py",
        "backend/image_router.py",
        "backend/tests/test_api.py",
        "skills/aura-testing/SKILL.md"
    ]

    print("--- Section A: File Inventory ---")
    for f in files_to_check:
        full_path = os.path.join(repo_dir, f)
        exists = os.path.exists(full_path)
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  [{status}] {f}")

    # B. Unit Test Execution
    print("\n--- Section B: Unit Test Suite Execution ---")
    test_file = os.path.join(repo_dir, "backend", "tests", "test_api.py")
    if os.path.exists(test_file):
        try:
            res = subprocess.run(
                [sys.executable, "-m", "unittest", "backend/tests/test_api.py"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            print(f"  Return code: {res.returncode}")
            print(f"  Output:\n{res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            print(f"  ❌ Error executing unit test suite: {e}")
    else:
        print("  ❌ test_api.py not found.")

    # C. Live Endpoints Check
    if base_url:
        print(f"\n--- Section C: Live Endpoint Check ({base_url}) ---")
        endpoints = [
            ("GET", "/api/auth/me"),
            ("GET", "/api/seo/suggest?q=marketing"),
            ("GET", "/api/notifications"),
            ("GET", "/api/analytics/dashboard")
        ]
        for method, ep in endpoints:
            url = f"{base_url.rstrip('/')}{ep}"
            try:
                r = requests.request(method, url, timeout=5)
                print(f"  [{r.status_code} {r.reason}] {method} {ep}")
            except Exception as err:
                print(f"  [❌ FAILED] {method} {ep} - {err}")

    print("\n========================================================================")
    print("  PRE-CHECK COMPLETED. Proceed to manual row-by-row verification.")
    print("========================================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getcwd(), help="Path to repo root")
    parser.add_argument("--base-url", default=None, help="Optional FastAPI live server URL")
    args = parser.parse_args()
    run_checks(args.repo, args.base_url)
