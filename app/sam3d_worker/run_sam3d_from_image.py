from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """コマンドラインから入力画像や出力先を受け取ります。

    Args:
        なし。
    Returns:
        argparse.Namespace: `image`, `output`, `project_root`, `mask_source`, `mask_index`, `seed` を持つ設定。
    """

    parser = argparse.ArgumentParser(description="Run SAM3D from one uploaded image.")
    parser.add_argument("--image", required=True, help="WSL から見える入力画像パス。")
    parser.add_argument("--output", required=True, help="WSL から見える PLY 出力パス。")
    parser.add_argument("--project-root", required=True, help="WSL から見える photo2mesh のルートパス。")
    parser.add_argument("--mask-source", default="", help="mask ファイルまたは mask フォルダのパス。")
    parser.add_argument("--mask-index", type=int, default=0, help="mask が複数あるときに使う番号。")
    parser.add_argument("--seed", type=int, default=42, help="同じ結果に近づけるための乱数の種。")
    return parser.parse_args()


def prepare_import_path(project_root: Path) -> None:
    """SAM3D の inference.py を import できるようにします。

    Args:
        project_root: WSL から見える photo2mesh のルートパス。
    Returns:
        None: Python の import 探索先を増やすだけで、値は返しません。
    """

    # demo.py と同じように notebook フォルダを import 対象にします。
    notebook_dir = project_root / "notebook"
    sys.path.insert(0, str(notebook_dir))


def load_mask(load_single_mask, image_path: Path, mask_source: Path | None, mask_index: int):
    """SAM3D に渡す mask を読み込みます。

    Args:
        load_single_mask: SAM3D 側が用意している mask 読み込み関数。
        image_path: WSL から見える入力画像パス。
        mask_source: mask ファイルまたは mask フォルダ。なければ自動で候補を試します。
        mask_index: `load_single_mask` に渡す mask 番号。
    Returns:
        object: SAM3D の `inference(image, mask)` に渡せる mask。
    """

    # 指定があればそれを優先し、ファイル指定なら親フォルダも試します。
    if mask_source is not None and mask_source.is_file():
        candidates = [mask_source, mask_source.parent]
    elif mask_source is not None:
        candidates = [mask_source]
    else:
        candidates = [image_path.parent, image_path]
    last_error: Exception | None = None

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return load_single_mask(str(candidate), index=mask_index)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        "SAM3D mask could not be loaded. "
        "Use an RGBA image supported by your SAM3D setup, or pass --mask-source."
    ) from last_error


def run_sam3d(
    image_path: Path,
    output_path: Path,
    project_root: Path,
    mask_source: Path | None,
    mask_index: int,
    seed: int,
) -> None:
    """SAM3D を実行して、メッシュを PLY として保存します。

    Args:
        image_path: WSL から見える入力画像パス。
        output_path: WSL から見える PLY 出力パス。
        project_root: WSL から見える photo2mesh のルートパス。
        mask_source: mask ファイルまたは mask フォルダ。なければ自動候補を使う。
        mask_index: `load_single_mask` に渡す mask 番号。
        seed: SAM3D に渡す乱数の種。
    Returns:
        None: PLY ファイルを保存するだけで、値は返しません。
    """

    prepare_import_path(project_root)

    # SAM3D 側の関数は demo.py と同じ名前で読み込みます。
    from inference import Inference, load_image, load_single_mask

    config_path = project_root / "checkpoints" / "hf" / "pipeline.yaml"
    inference = Inference(str(config_path), compile=False)

    # demo.py と同じく、画像と mask を読み込んでから推論します。
    image = load_image(str(image_path))
    mask = load_mask(load_single_mask, image_path, mask_source, mask_index)
    output = inference(image, mask, seed=seed)

    # demo.py では output["glb"] を trimesh object として PLY に出しています。
    mesh = output["glb"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))


def main() -> int:
    """スクリプトの入口として、引数確認から SAM3D 実行まで行います。

    Args:
        なし。
    Returns:
        int: 成功したら 0、入力ミスなどなら 1。
    """

    args = parse_args()
    image_path = Path(args.image)
    output_path = Path(args.output)
    project_root = Path(args.project_root)
    mask_source = Path(args.mask_source) if args.mask_source else None

    if not image_path.exists():
        print(f"Input image was not found: {image_path}", file=sys.stderr)
        return 1
    if not project_root.exists():
        print(f"Project root was not found: {project_root}", file=sys.stderr)
        return 1

    run_sam3d(
        image_path=image_path,
        output_path=output_path,
        project_root=project_root,
        mask_source=mask_source,
        mask_index=args.mask_index,
        seed=args.seed,
    )
    print(f"Your reconstruction has been saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
