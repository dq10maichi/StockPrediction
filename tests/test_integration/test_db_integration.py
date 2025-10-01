import pytest
import subprocess
import os

# This test performs integration testing on the database through manage_tickers.py script.
# It assumes that the database is running and accessible.

TEST_TICKER = "TEST.T"
TEST_FEATURES = "^N225,^TPX"

def run_script(command):
    """Helper function to run a script via shell and return its output."""
    # We run the script via python interpreter inside the docker container
    # This is to ensure that the script is run in the same environment as the application
    full_command = ["python", "script/manage_tickers.py"] + command
    # Pass the parent process's environment to the subprocess
    result = subprocess.run(full_command, capture_output=True, text=True, env=os.environ)
    return result

def test_manage_tickers_integration():
    """Tests the add, list, and remove commands of manage_tickers.py."""
    # 1. Initial Cleanup: Ensure the test ticker doesn't exist
    remove_result = run_script(["remove", "--ticker", TEST_TICKER])
    assert remove_result.returncode == 0
    
    # 2. List and verify it's not there
    list_result_before = run_script(["list"])
    assert list_result_before.returncode == 0
    assert TEST_TICKER not in list_result_before.stdout

    # 3. Add the ticker
    add_result = run_script(["add", "--ticker", TEST_TICKER, "--features", TEST_FEATURES])
    assert add_result.returncode == 0
    assert f"銘柄 '{TEST_TICKER}' の追加/更新が完了しました。" in add_result.stdout

    # 4. List and verify it exists
    list_result_after = run_script(["list"])
    assert list_result_after.returncode == 0
    assert TEST_TICKER in list_result_after.stdout
    assert TEST_FEATURES in list_result_after.stdout

    # 5. Remove the ticker
    remove_result_after = run_script(["remove", "--ticker", TEST_TICKER])
    assert remove_result_after.returncode == 0
    assert f"銘柄 '{TEST_TICKER}' の削除が完了しました。" in remove_result_after.stdout

    # 6. List and verify it's gone
    list_result_final = run_script(["list"])
    assert list_result_final.returncode == 0
    assert TEST_TICKER not in list_result_final.stdout
