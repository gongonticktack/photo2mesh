from __future__ import annotations

import os
from pathlib import Path


# このファイルでは、アプリ全体で使う設定を一か所に集めます。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(os.environ.get("PHOTO2MESH_STORAGE_DIR", PROJECT_ROOT / "storage"))
JOBS_DIR = STORAGE_DIR / "jobs"
OUTPUT_DIR = Path(os.environ.get("PHOTO2MESH_OUTPUT_DIR", PROJECT_ROOT / "output"))
LOGS_DIR = Path(os.environ.get("PHOTO2MESH_LOGS_DIR", PROJECT_ROOT / "logs"))
LOG_KEEP_COUNT = int(os.environ.get("PHOTO2MESH_LOG_KEEP_COUNT", "5"))

# アップロードできる最大サイズと画像形式です。
MAX_UPLOAD_MB = int(os.environ.get("PHOTO2MESH_MAX_UPLOAD_MB", "100"))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}

# WSL の中で SAM3D を動かすための設定です。
SAM3D_CONDA_ENV = os.environ.get("SAM3D_CONDA_ENV", "sam3d-blackwell")
WINDOWS_PROJECT_ROOT = Path(os.environ.get("PHOTO2MESH_WINDOWS_PROJECT_ROOT", PROJECT_ROOT))
WSL_PROJECT_ROOT = os.environ.get("PHOTO2MESH_WSL_PROJECT_ROOT", "/mnt/e/Program/photo2mesh")
SAM3D_WORKDIR = os.environ.get("SAM3D_WORKDIR", WSL_PROJECT_ROOT)
SAM3D_CODE_ROOT = os.environ.get("SAM3D_CODE_ROOT", "/home/gonsgon/sam3D/sam-3d-objects")
SAM3D_CHECKPOINT_ROOT = os.environ.get("SAM3D_CHECKPOINT_ROOT", "/mnt/e/Program/sam3D/checkpoints")
SAM_VISIBLE_CONSOLE = os.environ.get("SAM_VISIBLE_CONSOLE", "1") != "0"
SAM_CHECKPOINT = os.environ.get(
    "SAM_CHECKPOINT",
    f"{SAM3D_CHECKPOINT_ROOT}/sam_vit_h_4b8939.pth",
)
SAM_MODEL_TYPE = os.environ.get("SAM_MODEL_TYPE", "vit_h")
SAM_DEVICE = os.environ.get("SAM_DEVICE", "cuda")
SAM_MASK_COMMAND_TEMPLATE = os.environ.get(
    "SAM_MASK_COMMAND_TEMPLATE",
    'python "{wsl_project_root}/app/sam3d_worker/create_mask_from_click.py" --image "{input}" --output "{mask_file}" --x {point_x} --y {point_y} --checkpoint "{sam_checkpoint}" --model-type "{sam_model_type}" --device "{sam_device}"',
)
SAM3D_COMMAND_TEMPLATE = os.environ.get(
    "SAM3D_COMMAND_TEMPLATE",
    'python "{wsl_project_root}/app/sam3d_worker/run_sam3d_from_image.py" --image "{input}" --output "{output}" --project-root "{sam3d_code_root}" --mask-source "{mask}"',
)
