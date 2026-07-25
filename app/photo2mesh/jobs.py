from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from . import config


JobStatus = Literal["waiting_mask", "queued", "masking", "running", "finished", "failed"]


@dataclass
class Job:
    """1回のメッシュ生成作業を表すデータです。

    Args:
        id: ジョブを見分けるためのID。
        status: 今の状態。waiting_mask, masking, running などのどれか。
        original_name: アップロードされた元のファイル名。
        input_path: Windows上の入力画像パス。
        output_path: Windows上のPLY出力パス。
        log_path: Windows上のログファイルパス。
        mask_path: Windows上のmask画像パス。
        point_x: ユーザーがクリックした横位置。
        point_y: ユーザーがクリックした縦位置。
        created_at: ジョブを作った日時。
        updated_at: ジョブを最後に更新した日時。
        error: 失敗したときの説明。
    Returns:
        Job: dataclass が作るジョブ情報の入れ物。
    """

    id: str
    status: JobStatus
    original_name: str
    input_path: str
    output_path: str
    log_path: str
    mask_path: str
    point_x: int | None = None
    point_y: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str = ""


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def allowed_file(filename: str) -> bool:
    """アップロードされたファイル名が画像として使えるか調べます。

    Args:
        filename: ユーザーがアップロードしたファイル名。
    Returns:
        bool: 使える拡張子なら True、使えなければ False。
    """

    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def create_job(upload: FileStorage) -> Job:
    """アップロード画像を保存し、新しいジョブを作ります。

    Args:
        upload: Flask が受け取ったアップロードファイル。
    Returns:
        Job: 作成したジョブ情報。
    """

    job_id = uuid.uuid4().hex
    filename = secure_filename(upload.filename or "upload.jpg")
    job_dir = config.JOBS_DIR / job_id
    input_dir = job_dir / "input"
    mask_dir = job_dir / "masks"
    input_dir.mkdir(parents=True, exist_ok=False)
    mask_dir.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_path = input_dir / filename
    output_path = config.OUTPUT_DIR / f"{job_id}.ply"
    mask_path = mask_dir / "0.png"
    log_path = job_dir / "sam3d.log"

    # 入力画像をジョブ専用フォルダに保存します。
    upload.save(input_path)

    job = Job(
        id=job_id,
        status="waiting_mask",
        original_name=filename,
        input_path=str(input_path),
        output_path=str(output_path),
        log_path=str(log_path),
        mask_path=str(mask_path),
    )
    save_job(job)
    return job


def save_job(job: Job) -> None:
    """ジョブ情報をメモリと job.json の両方へ保存します。

    Args:
        job: 保存したいジョブ情報。
    Returns:
        None: 保存だけを行い、値は返しません。
    """

    job.updated_at = datetime.now(timezone.utc).isoformat()

    # 複数の処理が同時に触っても壊れにくいよう、鍵をかけます。
    with _lock:
        _jobs[job.id] = job
    _write_metadata(job)


def get_job(job_id: str) -> Job | None:
    """ジョブIDからジョブ情報を取り出します。

    Args:
        job_id: 探したいジョブのID。
    Returns:
        Job | None: 見つかったジョブ。なければ None。
    """

    with _lock:
        job = _jobs.get(job_id)
    if job is not None:
        return job

    # サーバ再起動後でも読めるよう、ファイルからも探します。
    metadata_path = config.JOBS_DIR / job_id / "job.json"
    if not metadata_path.exists():
        return None
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    data = _normalize_job_data(data, metadata_path.parent)
    job = Job(**data)
    with _lock:
        _jobs[job.id] = job
    return job


def list_jobs() -> list[Job]:
    """保存済みジョブを新しい順で一覧にします。

    Args:
        なし。
    Returns:
        list[Job]: 保存されているジョブの一覧。
    """

    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    loaded: list[Job] = []
    for metadata_path in sorted(config.JOBS_DIR.glob("*/job.json"), reverse=True):
        job = get_job(metadata_path.parent.name)
        if job is not None:
            loaded.append(job)
    return loaded


def mark_running(job: Job) -> None:
    """ジョブを実行中にします。

    Args:
        job: 状態を変えるジョブ。
    Returns:
        None: 状態を保存するだけで、値は返しません。
    """

    job.status = "running"
    job.error = ""
    save_job(job)


def mark_masking(job: Job, point_x: int, point_y: int) -> None:
    """ジョブをマスク作成中にし、クリック位置を保存します。

    Args:
        job: 状態を変えるジョブ。
        point_x: 画像の左から何ピクセルの場所を押したか。
        point_y: 画像の上から何ピクセルの場所を押したか。
    Returns:
        None: 状態を保存するだけで、値は返しません。
    """

    job.status = "masking"
    job.error = ""
    job.point_x = point_x
    job.point_y = point_y
    save_job(job)


def mark_queued(job: Job) -> None:
    """ジョブを SAM3D 待ち状態にします。

    Args:
        job: 状態を変えるジョブ。
    Returns:
        None: 状態を保存するだけで、値は返しません。
    """

    job.status = "queued"
    save_job(job)


def mark_finished(job: Job) -> None:
    """ジョブを完了にします。

    Args:
        job: 状態を変えるジョブ。
    Returns:
        None: 状態を保存するだけで、値は返しません。
    """

    job.status = "finished"
    save_job(job)


def mark_failed(job: Job, error: str) -> None:
    """ジョブを失敗にし、理由を保存します。

    Args:
        job: 状態を変えるジョブ。
        error: 画面やログで見るための失敗理由。
    Returns:
        None: 状態を保存するだけで、値は返しません。
    """

    job.status = "failed"
    job.error = error
    save_job(job)


def _write_metadata(job: Job) -> None:
    """ジョブ情報を job.json に書き出します。

    Args:
        job: ファイルへ保存したいジョブ情報。
    Returns:
        None: ファイルへ書くだけで、値は返しません。
    """

    metadata_path = Path(job.log_path).parent / "job.json"
    metadata_path.write_text(
        json.dumps(asdict(job), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_job_data(data: dict, job_dir: Path) -> dict:
    """古い job.json に足りない値を補います。

    Args:
        data: job.json から読んだ辞書。
        job_dir: job.json が入っているジョブフォルダ。
    Returns:
        dict: 今の Job dataclass に渡せる形の辞書。
    """

    # 以前のバージョンで作ったジョブには mask_path がないので補います。
    data.setdefault("mask_path", str(job_dir / "masks" / "0.png"))
    data.setdefault("point_x", None)
    data.setdefault("point_y", None)
    return data
