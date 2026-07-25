from __future__ import annotations

import shlex
import subprocess
import threading
from pathlib import Path

from . import config
from .jobs import Job, mark_failed, mark_finished, mark_masking, mark_queued, mark_running


def run_async(job: Job, point_x: int, point_y: int) -> None:
    """SAM3D の実行を別スレッドで始めます。

    Args:
        job: 実行したいジョブ。
        point_x: 画像上でユーザーが押した横位置。
        point_y: 画像上でユーザーが押した縦位置。
    Returns:
        None: 処理を開始するだけで、値は返しません。
    """

    # Web画面を待たせないため、重い処理は裏で動かします。
    thread = threading.Thread(target=run_job, args=(job, point_x, point_y), daemon=True)
    thread.start()


def run_job(job: Job, point_x: int, point_y: int) -> None:
    """WSL の中で SAM のマスク作成と SAM3D の PLY 作成を行います。

    Args:
        job: 入力画像や出力先を持つジョブ。
        point_x: 画像上でユーザーが押した横位置。
        point_y: 画像上でユーザーが押した縦位置。
    Returns:
        None: 結果はジョブ状態とファイルとして保存します。
    """

    mark_masking(job, point_x, point_y)
    log_path = Path(job.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Windows のパスを WSL から見える Linux 風のパスに変えます。
        input_wsl = _to_wsl_path(Path(job.input_path))
        output_wsl = _to_wsl_path(Path(job.output_path))
        mask_wsl = _to_wsl_path(Path(job.mask_path))
        mask_dir_wsl = _to_wsl_path(Path(job.mask_path).parent)
        job_dir_wsl = _to_wsl_path(log_path.parent)
        workdir_wsl = config.SAM3D_WORKDIR or job_dir_wsl

        mask_command = config.SAM_MASK_COMMAND_TEMPLATE.format(
            input=input_wsl,
            mask=mask_dir_wsl,
            mask_file=mask_wsl,
            point_x=point_x,
            point_y=point_y,
            wsl_project_root=config.WSL_PROJECT_ROOT,
            sam_checkpoint=config.SAM_CHECKPOINT,
            sam_model_type=config.SAM_MODEL_TYPE,
            sam_device=config.SAM_DEVICE,
        )
        sam3d_command = config.SAM3D_COMMAND_TEMPLATE.format(
            input=input_wsl,
            mask=mask_dir_wsl,
            mask_file=mask_wsl,
            output=output_wsl,
            job_dir=job_dir_wsl,
            wsl_project_root=config.WSL_PROJECT_ROOT,
            sam3d_code_root=config.SAM3D_CODE_ROOT,
            sam3d_checkpoint_root=config.SAM3D_CHECKPOINT_ROOT,
        )
        shell_script = _build_shell_script(workdir_wsl, mask_command, sam3d_command, job.id)

        _write_visible_runner(log_path, shell_script)
        mark_queued(job)
        mark_running(job)
        process = _run_shell_script(log_path)

        if process.returncode != 0:
            log_tail = _read_log_tail(log_path)
            mark_failed(job, f"SAM/SAM3D exited with code {process.returncode}. {log_tail}")
            return

        # 成功してもファイルがなければ、ユーザーが困るので失敗扱いにします。
        if not Path(job.output_path).exists():
            mark_failed(job, f"SAM3D completed, but {Path(job.output_path).name} was not created.")
            return

        mark_finished(job)
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n[photo2mesh] {type(exc).__name__}: {exc}\n")
        mark_failed(job, str(exc))


def _to_wsl_path(path: Path) -> str:
    """Windows のパスを WSL 用のパスへ変換します。

    Args:
        path: Windows 上のファイルまたはフォルダのパス。
    Returns:
        str: WSL で使える `/mnt/...` 形式のパス。
    """

    resolved_path = path.resolve()
    project_root = config.WINDOWS_PROJECT_ROOT.resolve()

    try:
        # このプロジェクト内なら、既知の WSL ルートから安全に組み立てます。
        relative_path = resolved_path.relative_to(project_root)
        relative_wsl_path = "/".join(part.replace("\\", "/") for part in relative_path.parts)
        return f"{config.WSL_PROJECT_ROOT.rstrip('/')}/{relative_wsl_path}"
    except ValueError:
        pass

    result = subprocess.run(
        ["wsl.exe", "wslpath", "-a", str(resolved_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "wslpath failed without message."
        raise RuntimeError(f"Failed to convert Windows path to WSL path: {resolved_path}. {message}")
    return result.stdout.strip()


def _build_shell_script(workdir_wsl: str, mask_command: str, sam3d_command: str, job_id: str) -> str:
    """WSL で実行する bash コマンドを組み立てます。

    Args:
        workdir_wsl: WSL 内で移動する作業フォルダ。
        mask_command: conda を有効化した後に実行する SAM マスク作成コマンド。
        sam3d_command: mask 作成後に実行する SAM3D コマンド。
        job_id: 表示用のジョブID。
    Returns:
        str: `bash -lc` に渡す1本のコマンド文字列。
    """

    conda_env = shlex.quote(config.SAM3D_CONDA_ENV)
    workdir = shlex.quote(workdir_wsl)

    # 何をしているかが画面で分かるよう、各ステップで echo を出します。
    return " && ".join(
        [
            "set -e",
            f"echo '[photo2mesh] Job: {shlex.quote(job_id)}'",
            "echo '[photo2mesh] WSL started.'",
            _build_conda_setup(conda_env),
            f"echo '[photo2mesh] Conda activated: {conda_env}'",
            _build_cuda_env(),
            "echo '[photo2mesh] CUDA environment prepared.'",
            f"mkdir -p {workdir}",
            f"cd {workdir}",
            "echo '[photo2mesh] Creating one-click mask with Segment Anything...'",
            mask_command,
            "echo '[photo2mesh] Mask created.'",
            "echo '[photo2mesh] Running SAM3D reconstruction...'",
            sam3d_command,
            "echo '[photo2mesh] SAM3D finished.'",
        ]
    )


def _write_visible_runner(log_path: Path, shell_script: str) -> None:
    """WSL で動かす shell script と、表示用 bat を作ります。

    Args:
        log_path: ジョブのログファイル。
        shell_script: WSL の bash で実行する処理。
    Returns:
        None: 実行用ファイルを作るだけで、値は返しません。
    """

    job_dir = log_path.parent
    shell_path = job_dir / "run_sam3d.sh"
    batch_path = job_dir / "run_visible.bat"
    shell_log_path = _to_wsl_path(log_path)
    shell_path_wsl = _to_wsl_path(shell_path)

    # tee を使うと、WSL の画面表示とログ保存を同時にできます。
    shell_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"exec > >(tee -a {shlex.quote(shell_log_path)}) 2>&1",
                "echo '[photo2mesh] ===== SAM/SAM3D job started ====='",
                shell_script,
                "echo '[photo2mesh] ===== SAM/SAM3D job completed ====='",
                "",
            ]
        ),
        encoding="utf-8",
    )
    batch_path.write_text(
        "\n".join(
            [
                "@echo off",
                "title photo2mesh SAM/SAM3D job",
                "echo Starting visible WSL SAM/SAM3D job...",
                f"echo Log file: {log_path}",
                f"wsl.exe bash {shell_path_wsl}",
                "set EXIT_CODE=%ERRORLEVEL%",
                "echo.",
                "echo SAM/SAM3D window finished with exit code %EXIT_CODE%.",
                "echo This window will close in 15 seconds.",
                "timeout /t 15",
                "exit /b %EXIT_CODE%",
                "",
            ]
        ),
        encoding="ascii",
    )
    log_path.write_text(
        "\n".join(
            [
                "[photo2mesh] Prepared visible SAM/SAM3D runner.",
                f"[photo2mesh] Windows runner: {batch_path}",
                f"[photo2mesh] WSL runner: {shell_path_wsl}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _run_shell_script(log_path: Path) -> subprocess.CompletedProcess:
    """SAM/SAM3D の shell script を実行します。

    Args:
        log_path: ジョブのログファイル。
    Returns:
        subprocess.CompletedProcess: 実行結果。
    """

    batch_path = log_path.parent / "run_visible.bat"
    if config.SAM_VISIBLE_CONSOLE:
        # start /wait で別ウィンドウを出しつつ、Python 側は終了まで待ちます。
        return subprocess.run(
            ["cmd.exe", "/c", "start", "photo2mesh SAM/SAM3D", "/wait", str(batch_path)],
            text=True,
            check=False,
        )

    return subprocess.run(["cmd.exe", "/c", str(batch_path)], text=True, check=False)


def _build_cuda_env() -> str:
    """CUDA のヘッダーとライブラリを見つけやすくします。

    Args:
        なし。
    Returns:
        str: bash で実行する CUDA 用の環境変数設定。
    """

    # spconv の実行時ビルドで cublasLt.h が見つからないため、全コンパイルへ include パスを渡します。
    return (
        "export CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}; "
        "export PATH=\"$CUDA_HOME/bin:${PATH:-}\"; "
        "export CPATH=\"$CUDA_HOME/include:$CUDA_HOME/targets/x86_64-linux/include:${CPATH:-}\"; "
        "export CPLUS_INCLUDE_PATH=\"$CUDA_HOME/include:$CUDA_HOME/targets/x86_64-linux/include:${CPLUS_INCLUDE_PATH:-}\"; "
        "export LIBRARY_PATH=\"$CUDA_HOME/lib64:$CUDA_HOME/targets/x86_64-linux/lib:${LIBRARY_PATH:-}\"; "
        "export LD_LIBRARY_PATH=\"$CUDA_HOME/lib64:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}\""
    )


def _build_conda_setup(conda_env: str) -> str:
    """WSL 内で conda 環境を有効化するコマンドを作ります。

    Args:
        conda_env: 有効化したい conda 環境名。
    Returns:
        str: bash で実行する conda 初期化コマンド。
    """

    # よくある conda の置き場所を先に source して、activate を確実に使えるようにします。
    return (
        "if [ -f \"$HOME/miniforge3/etc/profile.d/conda.sh\" ]; then . \"$HOME/miniforge3/etc/profile.d/conda.sh\"; "
        "elif [ -f \"$HOME/mambaforge/etc/profile.d/conda.sh\" ]; then . \"$HOME/mambaforge/etc/profile.d/conda.sh\"; "
        "elif [ -f \"$HOME/miniconda3/etc/profile.d/conda.sh\" ]; then . \"$HOME/miniconda3/etc/profile.d/conda.sh\"; "
        "elif [ -f \"$HOME/anaconda3/etc/profile.d/conda.sh\" ]; then . \"$HOME/anaconda3/etc/profile.d/conda.sh\"; "
        "elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then . /opt/conda/etc/profile.d/conda.sh; "
        "elif command -v conda >/dev/null 2>&1; then eval \"$(conda shell.bash hook)\"; "
        "else echo 'conda command was not found. Set SAM3D_WORKDIR or install/source conda in WSL.' >&2; exit 127; fi; "
        f"conda activate {conda_env}"
    )


def _read_log_tail(log_path: Path, max_lines: int = 8) -> str:
    """ジョブログの末尾を短く読みます。

    Args:
        log_path: 読みたいログファイル。
        max_lines: 何行まで読むか。
    Returns:
        str: 画面に出しやすい短いログ本文。
    """

    if not log_path.exists():
        return "See log for details."

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    error_words = ("fatal error:", "error:", "FAILED:", "Traceback", "RuntimeError", "No such file")
    priority_lines = [
        line.strip()
        for line in lines
        if line.strip() and any(word in line for word in error_words)
    ]
    useful_lines = priority_lines[-max_lines:] or [
        line.strip() for line in lines[-max_lines:] if line.strip() and not line.startswith("$ ")
    ]
    if not useful_lines:
        return "See log for details."
    return " ".join(useful_lines)
