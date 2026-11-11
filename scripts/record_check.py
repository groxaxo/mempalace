"""Run a local check and retain its exact command, output, and exit status."""

import os
from pathlib import Path
import shlex
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / sys.argv[1]
    command = sys.argv[2:]
    env = dict(os.environ, TMPDIR=str(root / "test-tmp"))
    result = subprocess.run(
        command, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    report = (
        f"TMPDIR={env['TMPDIR']} {shlex.join(command)}\n"
        f"{result.stdout}\nEXIT STATUS: {result.returncode}\n"
    )
    output.write_text(report, encoding="utf-8")
    print(report, end="")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
