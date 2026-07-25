from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from . import config


def setup_logging() -> Path:
    """アプリのログ出力先を作り、古いログを整理します。

    Args:
        なし。
    Returns:
        Path: 今回の起動で使うログファイルのパス。
    """

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Flask と自分たちのログを、同じ app ログへ書きます。
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        encoding="utf-8",
    )
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    cleanup_logs("app_*.log", config.LOG_KEEP_COUNT)
    logging.getLogger(__name__).info("Application logging started: %s", log_path)
    return log_path


def cleanup_logs(pattern: str, keep_count: int) -> None:
    """指定した種類のログを新しい順で指定件数だけ残します。

    Args:
        pattern: 消す対象を探すためのファイル名パターン。
        keep_count: 残したい最新ログの数。
    Returns:
        None: 古いファイルを消すだけで、値は返しません。
    """

    log_files = sorted(
        config.LOGS_DIR.glob(pattern),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    # 6件目以降を消して、ログが増え続けないようにします。
    for old_log in log_files[keep_count:]:
        old_log.unlink(missing_ok=True)
