"""
Branch health check with scoring for the Student Database repo.
Run: python check_branch.py
"""

import os
import subprocess
import sys
from typing import Tuple, Optional

# Weights (sum to 100)
WEIGHTS = {
    "compile": 40,       # py_compile + import factory
    "sqlalchemy": 20,    # exactly one SQLAlchemy()
    "strays": 10,        # no models.py / routes.py
    "routes": 20,        # URL map import + health smoke
    "lint_tests": 10,    # optional ruff/pytest (if installed)
}

def run(cmd, desc=None, check=True) -> Tuple[bool, str]:
    if desc:
        print(f"\n== {desc} ==")
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=check
        )
        out = (p.stdout or "").strip()
        if out:
            print(out)
        return True, out
    except subprocess.CalledProcessError as e:
        print("Command failed:", " ".join(cmd))
        print(e.stdout or "")
        return False, e.stdout or ""

def py_compile_all() -> bool:
    ok, files = run(["git", "ls-files", "*.py"], "Gather Python files", check=False)
    py_files = (files or "").split()
    if not py_files:
        print("No Python files found.")
        return False
    ok, _ = run([sys.executable, "-m", "py_compile", *py_files], "Python compile check", check=False)
    return ok

def import_factory():
    print("\n== App factory check ==")
    try:
        # If your factory lives elsewhere, change this import:
        from app import create_app
        a = create_app()
        print("✅ create_app worked")
        return a
    except Exception as e:
        print(f"❌ create_app failed: {e}")
        return None

def sqlalchemy_count_ok() -> tuple[bool, int]:
    print("\n== SQLAlchemy instance check ==")
    # Exclude this script and common virtualenv dirs
    ok, out = run(
        ["git","grep","-n","SQLAlchemy(","--",
         ":!check_branch.py",":!.venv",":!venv",":!env",":!**/.git/*"],
        check=False
    )
    lines = (out or "").splitlines()
    count = len([line for line in lines if line.strip()])
    for line in lines:
        print(line)
    print(f"Found {count} SQLAlchemy() calls (excluding helper files)")
    return (count == 1, count)

def stray_files_ok() -> bool:
    print("\n== Stray files check ==")
    bad = False
    for fname in ["models.py", "routes.py"]:
        if os.path.exists(fname):
            bad = True
            print(f"❌ Found stray {fname}")
        else:
            print(f"✅ No {fname}")
    return not bad

def url_map_ok(app) -> bool:
    if not app:
        print("Skipping URL map: no app")
        return False
    print("\n== URL map ==")
    try:
        print(app.url_map)
        return True
    except Exception as e:
        print("❌ Failed to print URL map:", e)
        return False

def health_smoke_ok(app) -> bool:
    if not app:
        print("Skipping health checks: no app")
        return False
    print("\n== Health endpoint check ==")
    ok_all = True
    paths = ["/health", "/api/v1/health", "/auth/health"]
    with app.test_client() as c:
        for p in paths:
            try:
                r = c.get(p)
                print(p, r.status_code)
                # 200 is ideal; 404 is acceptable if route doesn't exist.
                # Mark as OK if no exception thrown.
            except Exception as e:
                ok_all = False
                print(p, "ERR", e)
    return ok_all

def ruff_unused_count() -> Optional[int]:
    print("\n== Lint (ruff) unused imports (optional) ==")
    if not shutil_which("ruff"):
        print("ruff not installed; skipping")
        return None
    ok, out = run(["ruff", "check", "--select", "F401", "."], check=False)
    # Each finding is a line; empty output = 0
    count = 0
    for line in (out or "").splitlines():
        if line.strip() and ":" in line:
            count += 1
    print(f"Unused import findings: {count}")
    return count

def pytest_ok() -> Optional[bool]:
    print("\n== Tests (pytest) (optional) ==")
    if not shutil_which("pytest"):
        print("pytest not installed; skipping")
        return None
    ok, _ = run(["pytest", "-q"], check=False)
    print("pytest:", "OK" if ok else "FAIL")
    return ok

def shutil_which(name: str) -> bool:
    from shutil import which
    return which(name) is not None

def score_section(passed: bool, weight: int) -> int:
    return weight if passed else 0

def main():
    print("=== Branch Health Check (with scoring) ===")

    # Compile + factory import
    compile_ok = py_compile_all()
    app = import_factory()
    factory_ok = app is not None
    compile_section_ok = compile_ok and factory_ok
    compile_points = score_section(compile_section_ok, WEIGHTS["compile"])

    # SQLAlchemy single instance
    sa_ok, sa_count = sqlalchemy_count_ok()
    sa_points = score_section(sa_ok, WEIGHTS["sqlalchemy"])

    # Stray files
    strays_ok = stray_files_ok()
    strays_points = score_section(strays_ok, WEIGHTS["strays"])

    # Routes: url map + health smoke
    url_ok = url_map_ok(app)
    health_ok = health_smoke_ok(app)
    routes_ok = url_ok and health_ok
    routes_points = score_section(routes_ok, WEIGHTS["routes"])

    # Optional: ruff + pytest (partial credit if either passes)
    lint_points = 0
    ruff_count = ruff_unused_count()
    tests_ok = pytest_ok()

    # Scoring rule:
    # - If pytest is present and passes => full lint_tests points
    # - else if ruff is present and reports <= 3 unused imports => full points
    # - else if ruff present with some findings => half points
    # - else (neither installed) => 0 points (not penalized, but no credit)
    if tests_ok is True:
        lint_points = WEIGHTS["lint_tests"]
    elif ruff_count is not None:
        if ruff_count <= 3:
            lint_points = WEIGHTS["lint_tests"]
        elif ruff_count <= 10:
            lint_points = WEIGHTS["lint_tests"] // 2
        else:
            lint_points = 0

    total = compile_points + sa_points + strays_points + routes_points + lint_points

    print("\n================= SCORE SUMMARY =================")
    print(f"Compile & factory  : {compile_points}/{WEIGHTS['compile']}  "
          f"({'OK' if compile_section_ok else 'FAIL'})")
    print(f"SQLAlchemy single  : {sa_points}/{WEIGHTS['sqlalchemy']}  "
          f"(found {sa_count})")
    print(f"No stray files     : {strays_points}/{WEIGHTS['strays']}  "
          f"({'OK' if strays_ok else 'FAIL'})")
    print(f"Routes & health    : {routes_points}/{WEIGHTS['routes']}  "
          f"({'OK' if routes_ok else 'FAIL'})")
    if lint_points:
        print(f"Lint/Tests (opt)   : {lint_points}/{WEIGHTS['lint_tests']}  ✅")
    else:
        print(f"Lint/Tests (opt)   : {lint_points}/{WEIGHTS['lint_tests']}  (skipped or findings)")
    print("-------------------------------------------------")
    print(f"TOTAL              : {total}/100")
    print("=================================================")

    # Helpful tip for common miss:
    if not sa_ok:
        print("\nTip: Ensure exactly one `SQLAlchemy()` exists (prefer `extensions.py`) "
              "and all models import `db` from there.")

    if not factory_ok:
        print("\nTip: Your app factory import failed. This script assumes "
              "`from app import create_app` based on your app.py.")

if __name__ == "__main__":
    main()