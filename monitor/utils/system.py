import subprocess
import shlex


def run_cmd(cmd, timeout=30):
    """Run a shell command and return stdout. Returns empty string on error."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Command failed: {cmd} -> {e}")
        return ""


def run_kubectl(args, timeout=30):
    """Run a kubectl command."""
    return run_cmd(f"kubectl {args}", timeout=timeout)
