from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from . import config
from .jobs import allowed_file, create_job, get_job, list_jobs
from .logging_utils import setup_logging
from .model_gallery import ensure_thumbnail, get_model, list_models
from .sam3d_runner import run_async


def create_app() -> Flask:
    """Flask アプリを作り、URL と処理を結び付けます。

    Args:
        なし。
    Returns:
        Flask: 起動に使う Flask アプリ本体。
    """

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging()

    @app.get("/")
    def index():
        """トップ画面を表示します。

        Args:
            なし。
        Returns:
            str: ジョブ一覧を含むHTML。
        """

        return render_template("index.html", jobs=list_jobs(), models=list_models()[:6])

    @app.post("/jobs")
    def submit_job():
        """アップロードされた写真から新しいジョブを作ります。

        Args:
            なし。
        Returns:
            str | tuple[str, int]: 成功時はジョブ画面へ移動し、失敗時はエラー付きHTMLを返します。
        """

        upload = request.files.get("photo")
        if upload is None or not upload.filename:
            return render_template("index.html", jobs=list_jobs(), models=list_models()[:6], error="写真ファイルを選択してください。"), 400
        if not allowed_file(upload.filename):
            return render_template("index.html", jobs=list_jobs(), models=list_models()[:6], error="対応形式は png, jpg, jpeg, webp, bmp, tif, tiff です。"), 400

        job = create_job(upload)
        return redirect(url_for("job_detail", job_id=job.id))

    @app.get("/jobs/<job_id>")
    def job_detail(job_id: str):
        """指定したジョブの詳細画面を表示します。

        Args:
            job_id: 表示したいジョブのID。
        Returns:
            str: ジョブ状態を含むHTML。
        """

        job = get_job(job_id)
        if job is None:
            abort(404)
        return render_template("job.html", job=job, mask_exists=Path(job.mask_path).exists())

    @app.get("/api/jobs/<job_id>")
    def job_api(job_id: str):
        """画面の自動更新用にジョブ状態を JSON で返します。

        Args:
            job_id: 状態を調べたいジョブのID。
        Returns:
            Response: ジョブ状態、エラー、リンクを含むJSONレスポンス。
        """

        job = get_job(job_id)
        if job is None:
            abort(404)
        return jsonify(
            {
                "id": job.id,
                "status": job.status,
                "error": job.error,
                "mask_url": url_for("job_mask", job_id=job.id) if Path(job.mask_path).exists() else "",
                "download_url": url_for("download_job", job_id=job.id) if Path(job.output_path).exists() else "",
                "log_url": url_for("job_log", job_id=job.id) if Path(job.log_path).exists() else "",
            }
        )

    @app.post("/api/jobs/<job_id>/mask")
    def create_mask(job_id: str):
        """クリック位置からマスク作成と SAM3D 実行を開始します。

        Args:
            job_id: 処理したいジョブのID。
        Returns:
            Response: 開始できたかどうかを示すJSONレスポンス。
        """

        job = get_job(job_id)
        if job is None:
            abort(404)
        if job.status not in {"waiting_mask", "failed"}:
            return jsonify({"error": "このジョブはすでに処理中または完了しています。"}), 409

        data = request.get_json(silent=True) or {}
        try:
            point_x = int(data["x"])
            point_y = int(data["y"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "クリック位置を正しく受け取れませんでした。"}), 400

        # クリックした点をもとに、裏側でSAMのマスク作成とSAM3Dを続けて動かします。
        run_async(job, point_x, point_y)
        return jsonify({"ok": True})

    @app.get("/jobs/<job_id>/image")
    def job_image(job_id: str):
        """アップロード画像を画面表示用に返します。

        Args:
            job_id: 画像を見たいジョブのID。
        Returns:
            Response: アップロード画像のレスポンス。
        """

        job = get_job(job_id)
        if job is None or not Path(job.input_path).exists():
            abort(404)
        return send_file(job.input_path)

    @app.get("/jobs/<job_id>/mask")
    def job_mask(job_id: str):
        """作成済みマスク画像を画面表示用に返します。

        Args:
            job_id: mask を見たいジョブのID。
        Returns:
            Response: mask 画像のレスポンス。
        """

        job = get_job(job_id)
        if job is None or not Path(job.mask_path).exists():
            abort(404)
        return send_file(job.mask_path)

    @app.get("/jobs/<job_id>/download")
    def download_job(job_id: str):
        """完成した PLY ファイルをダウンロードさせます。

        Args:
            job_id: ダウンロードしたいジョブのID。
        Returns:
            Response: PLY ファイルのダウンロードレスポンス。
        """

        job = get_job(job_id)
        if job is None or not Path(job.output_path).exists():
            abort(404)
        return send_file(job.output_path, as_attachment=True, download_name=f"{job.id}.ply")

    @app.get("/models")
    def models_index():
        """マイモデル一覧を表示します。

        Args:
            なし。
        Returns:
            str: サムネイル付きモデル一覧HTML。
        """

        return render_template("models.html", models=list_models())

    @app.get("/models/<model_id>/thumbnail")
    def model_thumbnail(model_id: str):
        """PLY から作ったサムネイル画像を返します。

        Args:
            model_id: 表示したいモデルID。
        Returns:
            Response: PNG サムネイル画像。
        """

        model = get_model(model_id)
        if model is None:
            abort(404)
        thumbnail_path = ensure_thumbnail(model)
        return send_file(thumbnail_path, mimetype="image/png")

    @app.get("/models/<model_id>/download")
    def model_download(model_id: str):
        """マイモデルから PLY をダウンロードさせます。

        Args:
            model_id: ダウンロードしたいモデルID。
        Returns:
            Response: PLY ファイルのダウンロードレスポンス。
        """

        model = get_model(model_id)
        if model is None:
            abort(404)
        return send_file(model.ply_path, as_attachment=True, download_name=f"{model.id}.ply")

    @app.get("/jobs/<job_id>/log")
    def job_log(job_id: str):
        """SAM3D 実行ログをテキストとして返します。

        Args:
            job_id: ログを見たいジョブのID。
        Returns:
            Response: ログファイルのレスポンス。
        """

        job = get_job(job_id)
        if job is None or not Path(job.log_path).exists():
            abort(404)
        return send_file(job.log_path, mimetype="text/plain; charset=utf-8")

    return app
