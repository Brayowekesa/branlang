# run_tests.py
import os
import sys
import subprocess
from pathlib import Path

TEST_DIR = Path(__file__).parent / "tests"

def find_test_cases():
    """Finds all BranLang test files (*.bl) in the tests/ directory."""
    if not TEST_DIR.is_dir():
        print(f"Error: Test directory not found at '{TEST_DIR}'")
        sys.exit(1)
    
    test_files = sorted(TEST_DIR.glob("*.bl"))
    return [path.stem for path in test_files]

def run_single_test(test_name):
    """
    Runs a single test case and compares its output/error to expected files.
    Returns (passed: bool, details: str).
    """
    source_file = TEST_DIR / f"{test_name}.bl"
    input_file = TEST_DIR / f"{test_name}.in"
    expected_out_file = TEST_DIR / f"{test_name}.out"
    expected_err_file = TEST_DIR / f"{test_name}.err"

    stdin_payload = input_file.read_text(encoding='utf-8') if input_file.exists() else None
    
    # We use subprocess to run each test in an isolated process.
    # This prevents a crash in one test from stopping the entire suite.
    # Set PYTHONIOENCODING to 'utf-8' to prevent UnicodeEncodeError on Windows
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'

    result = subprocess.run(
        [sys.executable, 'branlang.py', str(source_file)],
        capture_output=True, text=True, encoding='utf-8', input=stdin_payload, env=env
    )

    # Normalize line endings for cross-platform compatibility
    actual_stdout = result.stdout.replace('\r\n', '\n')
    actual_stderr = result.stderr.replace('\r\n', '\n')

    # Case 1: Test is expected to fail
    if expected_err_file.exists():
        expected_stderr = expected_err_file.read_text(encoding='utf-8').replace('\r\n', '\n')
        if result.returncode == 0:
            return False, "FAILED: Expected a non-zero exit code but got 0."
        if expected_stderr not in actual_stderr:
            details = (
                f"FAILED: STDERR mismatch.\n"
                f"--- EXPECTED ---\n{expected_stderr}\n"
                f"---- ACTUAL ----\n{actual_stderr}\n"
                f"----------------"
            )
            return False, details
        return True, "PASSED (expected failure)"

    # Case 2: Test is expected to succeed
    if not expected_out_file.exists():
        return False, f"FAILED: Missing expected output file: {expected_out_file.name}"

    expected_stdout = expected_out_file.read_text(encoding='utf-8').replace('\r\n', '\n')

    if result.returncode != 0:
        return False, f"FAILED: Expected exit code 0 but got {result.returncode}.\nSTDERR:\n{actual_stderr}"

    if actual_stdout != expected_stdout:
        details = (
            f"FAILED: STDOUT mismatch.\n"
            f"--- EXPECTED ---\n{expected_stdout}\n"
            f"---- ACTUAL ----\n{actual_stdout}\n"
            f"----------------"
        )
        return False, details

    return True, "PASSED"

def run_tests():
    test_cases = find_test_cases()
    passed_count = 0
    failed_tests = []

    print("=== Running BranLang Test Suite ===")
    
    for test_name in test_cases:
        print(f"--- Running: {test_name}.bl ... ", end="")
        passed, details = run_single_test(test_name)
        print(details.split('\n')[0]) # Print just the first line of the status
        if passed:
            passed_count += 1
        else:
            if '\n' in details: # Print multi-line details for mismatches
                print(details)
            failed_tests.append(test_name)

    print("\n" + "="*30)
    print(f"Test Summary: {passed_count}/{len(test_cases)} passed.")
    if failed_tests:
        print("Failed tests:", ", ".join(failed_tests))
        sys.exit(1)
    else:
        print("All tests passed successfully! 🎉")
        sys.exit(0)

if __name__ == '__main__':
    run_tests()