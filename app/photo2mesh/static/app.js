const jobId = document.body.dataset.jobId;
const statusEl = document.querySelector("#job-status");
const errorEl = document.querySelector("#job-error");
const downloadLink = document.querySelector("#download-link");
const sourceImage = document.querySelector("#source-image");
const maskPreview = document.querySelector("#mask-preview");
const imageStage = document.querySelector("#image-stage");
const clickMarker = document.querySelector("#click-marker");
const maskButton = document.querySelector("#mask-button");
const photoInput = document.querySelector("#photo-input");
const photoFileName = document.querySelector("#photo-file-name");
const uploadPreviewImage = document.querySelector("#upload-preview-image");
const uploadPreviewPlaceholder = document.querySelector("#upload-preview-placeholder");
let selectedPoint = null;
let uploadPreviewUrl = null;

/**
 * 画像上で押した場所を、元画像のピクセル座標に変換します。
 *
 * Args:
 *   event: ブラウザから届くクリック情報。
 * Returns:
 *   {x: number, y: number, markerX: number, markerY: number}: SAM に渡す座標と画面上の印の座標。
 */
function getImagePoint(event) {
  const rect = sourceImage.getBoundingClientRect();
  const markerX = event.clientX - rect.left;
  const markerY = event.clientY - rect.top;
  const x = Math.round((markerX / rect.width) * sourceImage.naturalWidth);
  const y = Math.round((markerY / rect.height) * sourceImage.naturalHeight);
  return { x, y, markerX, markerY };
}

/**
 * クリック位置の印を画面に表示します。
 *
 * Args:
 *   point: `getImagePoint` が返した座標情報。
 * Returns:
 *   void: 画面を書き換えるだけで、値は返しません。
 */
function showClickMarker(point) {
  clickMarker.style.left = `${point.markerX}px`;
  clickMarker.style.top = `${point.markerY}px`;
  clickMarker.classList.remove("hidden");
}

/**
 * 選んだ写真を、生成開始前に画面へ表示します。
 *
 * Args:
 *   file: ユーザーが選んだ画像ファイル。
 * Returns:
 *   void: 画面を書き換えるだけで、値は返しません。
 */
function showUploadPreview(file) {
  if (!file || !uploadPreviewImage) return;

  // 前のプレビューURLを片付けて、ブラウザのメモリを無駄にしないようにします。
  if (uploadPreviewUrl) URL.revokeObjectURL(uploadPreviewUrl);
  uploadPreviewUrl = URL.createObjectURL(file);

  uploadPreviewImage.src = uploadPreviewUrl;
  uploadPreviewImage.alt = file.name;
  uploadPreviewImage.classList.remove("hidden");
  if (uploadPreviewPlaceholder) uploadPreviewPlaceholder.classList.add("hidden");
  if (photoFileName) photoFileName.textContent = file.name;
}

/**
 * クリック位置をサーバへ送り、マスク作成を開始します。
 *
 * Args:
 *   なし。
 * Returns:
 *   Promise<void>: サーバへの送信が終わったら解決します。
 */
async function submitMaskPoint() {
  if (!selectedPoint || !jobId) return;
  maskButton.classList.add("disabled");
  maskButton.textContent = "生成中";

  const response = await fetch(`/api/jobs/${jobId}/mask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x: selectedPoint.x, y: selectedPoint.y }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "マスク作成を開始できませんでした。" }));
    errorEl.textContent = error.error;
    errorEl.classList.remove("hidden");
    maskButton.textContent = "クリック位置で生成";
    maskButton.classList.remove("disabled");
    return;
  }

  refreshJob();
}

/**
 * ジョブの状態をサーバから取り直して、画面を書き換えます。
 *
 * Args:
 *   なし。
 * Returns:
 *   Promise<void>: 画面更新が終わったら解決します。
 */
async function refreshJob() {
  if (!jobId) return;

  // ブラウザの古い情報ではなく、毎回サーバの新しい情報を取りに行きます。
  const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) return;
  const job = await response.json();

  statusEl.textContent = job.status;
  statusEl.className = `status ${job.status}`;

  if (job.error) {
    errorEl.textContent = job.error;
    errorEl.classList.remove("hidden");
  }

  if (job.download_url) {
    downloadLink.href = job.download_url;
    downloadLink.classList.remove("disabled");
  }

  if (maskButton && (job.status === "waiting_mask" || job.status === "failed")) {
    maskButton.textContent = "クリック位置で生成";
    if (selectedPoint) maskButton.classList.remove("disabled");
  }

  if (job.mask_url && maskPreview) {
    maskPreview.src = `${job.mask_url}?t=${Date.now()}`;
    maskPreview.classList.remove("hidden");
  }

  // まだ処理中なら、少し待ってからもう一度見に行きます。
  if (job.status === "masking" || job.status === "queued" || job.status === "running") {
    window.setTimeout(refreshJob, 2500);
  }
}

if (imageStage && sourceImage) {
  imageStage.addEventListener("click", (event) => {
    if (!sourceImage.complete || !["waiting_mask", "failed"].includes(statusEl.textContent)) return;
    selectedPoint = getImagePoint(event);
    showClickMarker(selectedPoint);
    maskButton.classList.remove("disabled");
  });
}

if (maskButton) {
  maskButton.addEventListener("click", submitMaskPoint);
}

if (photoInput) {
  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    showUploadPreview(file);
  });
}

refreshJob();
