from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    """コマンドラインから画像、クリック位置、SAM設定を受け取ります。

    Args:
        なし。
    Returns:
        argparse.Namespace: mask 作成に必要な設定を入れた値。
    """

    parser = argparse.ArgumentParser(description="Create a one-click object mask with Segment Anything.")
    parser.add_argument("--image", required=True, help="WSL から見える入力画像パス。")
    parser.add_argument("--output", required=True, help="WSL から見える mask PNG 出力パス。")
    parser.add_argument("--x", required=True, type=int, help="画像の左から数えたクリック位置。")
    parser.add_argument("--y", required=True, type=int, help="画像の上から数えたクリック位置。")
    parser.add_argument("--checkpoint", required=True, help="SAM の checkpoint ファイルパス。")
    parser.add_argument("--model-type", default="vit_h", help="SAM のモデル種類。例: vit_h, vit_l, vit_b。")
    parser.add_argument("--device", default="cuda", help="cuda または cpu。")
    return parser.parse_args()


def choose_device(requested_device: str) -> str:
    """使う計算デバイスを決めます。

    Args:
        requested_device: 設定で指定された `cuda` または `cpu`。
    Returns:
        str: 実際に使うデバイス名。
    """

    import torch

    # GPU が使えないPCでも止まらないよう、cuda がなければ cpu にします。
    if requested_device == "cuda" and not torch.cuda.is_available():
        return "cpu"
    return requested_device


def load_rgb_image(image_path: Path) -> np.ndarray:
    """画像を SAM が読める RGB 配列に変換します。

    Args:
        image_path: WSL から見える入力画像パス。
    Returns:
        np.ndarray: RGB の画像データ。
    """

    image = Image.open(image_path).convert("RGB")
    return np.array(image)


def create_mask(
    image_path: Path,
    output_path: Path,
    point_x: int,
    point_y: int,
    checkpoint: Path,
    model_type: str,
    device: str,
) -> None:
    """クリックした点を含む物体の mask PNG を作ります。

    Args:
        image_path: WSL から見える入力画像パス。
        output_path: WSL から見える mask PNG 出力パス。
        point_x: 画像の左から何ピクセルの場所を押したか。
        point_y: 画像の上から何ピクセルの場所を押したか。
        checkpoint: SAM の checkpoint ファイルパス。
        model_type: SAM のモデル種類。
        device: 実際に使う計算デバイス。
    Returns:
        None: mask PNG を保存するだけで、値は返しません。
    """

    from segment_anything import SamPredictor, sam_model_registry

    image = load_rgb_image(image_path)
    model = sam_model_registry[model_type](checkpoint=str(checkpoint))
    model.to(device=device)

    predictor = SamPredictor(model)
    predictor.set_image(image)

    # クリックした点を「この物体に含めたい点」として SAM に渡します。
    point_coords = np.array([[point_x, point_y]])
    point_labels = np.array([1])
    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    # 複数候補のうち、SAM が一番自信を持っている mask を使います。
    best_index = int(np.argmax(scores))
    mask = masks[best_index].astype(np.uint8) * 255

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, mode="L").save(output_path)


def main() -> int:
    """スクリプトの入口として、引数確認から mask 保存まで行います。

    Args:
        なし。
    Returns:
        int: 成功したら 0、失敗したら 1。
    """

    args = parse_args()
    image_path = Path(args.image)
    output_path = Path(args.output)
    checkpoint = Path(args.checkpoint)

    if not image_path.exists():
        print(f"Input image was not found: {image_path}", file=sys.stderr)
        return 1
    if not checkpoint.exists():
        print(
            "SAM checkpoint for one-click masking was not found: "
            f"{checkpoint}. This is different from SAM3D object checkpoints.",
            file=sys.stderr,
        )
        return 1

    device = choose_device(args.device)
    create_mask(
        image_path=image_path,
        output_path=output_path,
        point_x=args.x,
        point_y=args.y,
        checkpoint=checkpoint,
        model_type=args.model_type,
        device=device,
    )
    print(f"Mask has been saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
