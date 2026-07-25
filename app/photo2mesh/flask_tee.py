from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Flask の出力を画面とログの両方へ流します。

    Args:
        なし。
    Returns:
        int: Flask が返した終了コード。
    """

    log_path = Path(os.environ["START_LOG"])
    host = os.environ.get("PHOTO2MESH_HOST", "127.0.0.1")
    port = os.environ.get("PHOTO2MESH_PORT", "7860")
    command = [
        sys.executable,
        "-m",
        "flask",
        "--app",
        "photo2mesh.server",
        "run",
        "--host",
        host,
        "--port",
        port,
    ]

    # 1行ずつ読みながら、同じ内容を画面とログに流します。
    with log_path.open("a", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log_file.write(line)
                log_file.flush()
        except KeyboardInterrupt:
            process.terminate()
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
