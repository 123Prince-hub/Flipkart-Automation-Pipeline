import sys
import os
import subprocess
from pathlib import Path

# Terminal encoding fix for Unicode (₹, checkmarks, etc.)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
REQ_FILE = BASE_DIR / "requirements.txt"
MAIN_FILE = BASE_DIR / "main.py"



def get_venv_executables():
    """Returns platform-specific paths for Python and Pip in venv."""
    if os.name == "nt":
        python_bin = VENV_DIR / "Scripts" / "python.exe"
        pip_bin = VENV_DIR / "Scripts" / "pip.exe"
    else:
        python_bin = VENV_DIR / "bin" / "python"
        pip_bin = VENV_DIR / "bin" / "pip"
    return python_bin, pip_bin



def are_dependencies_installed(python_bin):
    """Checks if the required packages are already installed in the virtual environment."""
    test_cmd = [
        str(python_bin),
        "-c",
        "import selenium, requests, webdriver_manager"
    ]
    result = subprocess.run(test_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0



def run_automation():
    python_bin, pip_bin = get_venv_executables()

    # 1. Re-use existing venv if already present, otherwise create it
    if not python_bin.exists():
        print(f"[RUNNER] Virtual environment not found. Creating at: {VENV_DIR}...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        print("[RUNNER] Virtual environment created successfully.")
    else:
        print("[RUNNER] Virtual environment already exists. Reusing it.")

    # 2. Skip pip install if dependencies are already installed
    if not are_dependencies_installed(python_bin):
        if REQ_FILE.exists():
            print("[RUNNER] Required packages missing. Installing from requirements.txt...")
            subprocess.run(
                [str(pip_bin), "install", "--disable-pip-version-check", "-q", "-r", str(REQ_FILE)],
                check=True
            )
            print("[RUNNER] Packages installed successfully.")
    else:
        print("[RUNNER] Dependencies already satisfied. Skipping re-installation.")

    # 3. Forward CLI arguments to main.py
    cli_args = sys.argv[1:]
    print(f"\n[RUNNER] Launching Flipkart Multithreaded Pipeline (Args: {cli_args if cli_args else 'Default Execution'}) \n")

    # 4. Execute main.py within the virtual environment
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = [str(python_bin), str(MAIN_FILE)] + cli_args
        subprocess.run(cmd, check=True, env=env)
    except KeyboardInterrupt:
        print("\n[INFO] Automation stopped by user.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    run_automation()
