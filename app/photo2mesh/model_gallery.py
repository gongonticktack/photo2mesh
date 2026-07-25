from __future__ import annotations

import json
import logging
import math
import random
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from . import config


LOGGER = logging.getLogger(__name__)

PLY_TYPE_SIZES = {
    "char": 1,
    "uchar": 1,
    "int8": 1,
    "uint8": 1,
    "short": 2,
    "ushort": 2,
    "int16": 2,
    "uint16": 2,
    "int": 4,
    "uint": 4,
    "float": 4,
    "float32": 4,
    "double": 8,
    "float64": 8,
}

PLY_STRUCT_TYPES = {
    "char": "b",
    "uchar": "B",
    "int8": "b",
    "uint8": "B",
    "short": "h",
    "ushort": "H",
    "int16": "h",
    "uint16": "H",
    "int": "i",
    "uint": "I",
    "float": "f",
    "float32": "f",
    "double": "d",
    "float64": "d",
}


@dataclass
class ModelAsset:
    """マイモデルに表示する1つの PLY モデルです。

    Args:
        id: モデルを見分けるID。
        name: 画面に出す名前。
        ply_path: Windows上の PLY ファイルパス。
        thumbnail_path: Windows上のサムネイル画像パス。
        created_at: 並び替えに使う更新日時。
    Returns:
        ModelAsset: モデル一覧用の情報。
    """

    id: str
    name: str
    ply_path: Path
    thumbnail_path: Path
    created_at: float


def list_models() -> list[ModelAsset]:
    """`output/` にある PLY をマイモデルとして一覧にします。

    Args:
        なし。
    Returns:
        list[ModelAsset]: 新しい順に並べたモデル一覧。
    """

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    thumbnail_dir = _thumbnail_dir()
    models: list[ModelAsset] = []

    for ply_path in config.OUTPUT_DIR.glob("*.ply"):
        model_id = ply_path.stem
        models.append(
            ModelAsset(
                id=model_id,
                name=_model_name(model_id),
                ply_path=ply_path,
                thumbnail_path=thumbnail_dir / f"{model_id}.png",
                created_at=ply_path.stat().st_mtime,
            )
        )

    return sorted(models, key=lambda model: model.created_at, reverse=True)


def get_model(model_id: str) -> ModelAsset | None:
    """モデルIDから PLY モデルを探します。

    Args:
        model_id: 探したいモデルID。
    Returns:
        ModelAsset | None: 見つかったモデル。なければ None。
    """

    safe_id = Path(model_id).stem
    ply_path = config.OUTPUT_DIR / f"{safe_id}.ply"
    if not ply_path.exists():
        return None

    return ModelAsset(
        id=safe_id,
        name=_model_name(safe_id),
        ply_path=ply_path,
        thumbnail_path=_thumbnail_dir() / f"{safe_id}.png",
        created_at=ply_path.stat().st_mtime,
    )


def ensure_thumbnail(model: ModelAsset) -> Path:
    """PLY からサムネイル PNG を作ります。

    Args:
        model: サムネイルを作りたいモデル。
    Returns:
        Path: 作成済みサムネイル画像のパス。
    """

    if model.thumbnail_path.exists() and model.thumbnail_path.stat().st_mtime >= model.ply_path.stat().st_mtime:
        return model.thumbnail_path

    try:
        points = _read_ply_points(model.ply_path)
        _render_thumbnail(points, model.thumbnail_path)
    except (OSError, KeyError, ValueError, struct.error) as exc:
        # PLY の形式が想定外でも、一覧画面が止まらないようにします。
        LOGGER.exception("Failed to render thumbnail for %s", model.ply_path)
        _render_thumbnail([], model.thumbnail_path, f"preview failed: {exc}")
    return model.thumbnail_path


def _thumbnail_dir() -> Path:
    """サムネイル保存フォルダを作って返します。

    Args:
        なし。
    Returns:
        Path: サムネイル保存フォルダ。
    """

    path = config.STORAGE_DIR / "thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _model_name(model_id: str) -> str:
    """ジョブ情報からモデル名を決めます。

    Args:
        model_id: モデルID。
    Returns:
        str: 表示用のモデル名。
    """

    metadata_path = config.JOBS_DIR / model_id / "job.json"
    if not metadata_path.exists():
        return f"{model_id}.ply"

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        return data.get("original_name") or f"{model_id}.ply"
    except json.JSONDecodeError:
        return f"{model_id}.ply"


def _read_ply_points(ply_path: Path, max_points: int = 120_000) -> list[tuple[float, float, float, tuple[int, int, int]]]:
    """PLY からサムネイルに使う頂点を読みます。

    Args:
        ply_path: 読みたい PLY ファイル。
        max_points: 読み込む頂点の最大数。
    Returns:
        list[tuple[float, float, float, tuple[int, int, int]]]: 座標と色の一覧。
    """

    with ply_path.open("rb") as file:
        header_lines: list[str] = []
        while True:
            line = file.readline()
            if not line:
                raise ValueError("PLY header was not found.")
            text = line.decode("ascii", errors="replace").strip()
            header_lines.append(text)
            if text == "end_header":
                break
        data_start = file.tell()

    info = _parse_ply_header(header_lines)
    if info["format"] == "ascii":
        return _read_ascii_vertices(ply_path, len(header_lines), info, max_points)
    if info["format"] == "binary_little_endian":
        return _read_binary_vertices(ply_path, data_start, info, max_points)
    raise ValueError(f"Unsupported PLY format: {info['format']}")


def _parse_ply_header(header_lines: list[str]) -> dict:
    """PLY ヘッダーから頂点の読み方を調べます。

    Args:
        header_lines: PLY のヘッダー行。
    Returns:
        dict: format, vertex_count, vertex_properties を持つ辞書。
    """

    ply_format = ""
    vertex_count = 0
    vertex_properties: list[tuple[str, str]] = []
    current_element = ""

    for line in header_lines:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "format":
            ply_format = parts[1]
        elif parts[0] == "element":
            current_element = parts[1]
            if current_element == "vertex":
                vertex_count = int(parts[2])
        elif parts[0] == "property" and current_element == "vertex" and parts[1] != "list":
            vertex_properties.append((parts[1], parts[2]))

    return {
        "format": ply_format,
        "vertex_count": vertex_count,
        "vertex_properties": vertex_properties,
    }


def _read_binary_vertices(
    ply_path: Path,
    data_start: int,
    info: dict,
    max_points: int,
) -> list[tuple[float, float, float, tuple[int, int, int]]]:
    """binary_little_endian PLY の頂点を読みます。

    Args:
        ply_path: 読みたい PLY ファイル。
        data_start: 頂点データが始まるバイト位置。
        info: PLY ヘッダーから作った情報。
        max_points: 読み込む頂点の最大数。
    Returns:
        list[tuple[float, float, float, tuple[int, int, int]]]: 座標と色の一覧。
    """

    properties = info["vertex_properties"]
    record_size = sum(PLY_TYPE_SIZES[property_type] for property_type, _ in properties)
    offsets = _property_offsets(properties)
    stride = max(1, math.ceil(info["vertex_count"] / max_points))
    points = []

    with ply_path.open("rb") as file:
        for index in range(0, info["vertex_count"], stride):
            file.seek(data_start + index * record_size)
            record = file.read(record_size)
            if len(record) < record_size:
                break
            points.append(_decode_binary_vertex(record, properties, offsets))

    return points


def _read_ascii_vertices(
    ply_path: Path,
    header_line_count: int,
    info: dict,
    max_points: int,
) -> list[tuple[float, float, float, tuple[int, int, int]]]:
    """ASCII PLY の頂点を読みます。

    Args:
        ply_path: 読みたい PLY ファイル。
        header_line_count: ヘッダーの行数。
        info: PLY ヘッダーから作った情報。
        max_points: 読み込む頂点の最大数。
    Returns:
        list[tuple[float, float, float, tuple[int, int, int]]]: 座標と色の一覧。
    """

    stride = max(1, math.ceil(info["vertex_count"] / max_points))
    property_names = [name for _, name in info["vertex_properties"]]
    points = []

    with ply_path.open("r", encoding="ascii", errors="replace") as file:
        for _ in range(header_line_count):
            next(file)
        for index in range(info["vertex_count"]):
            line = file.readline()
            if not line:
                break
            if index % stride != 0:
                continue
            values = line.split()
            value_map = dict(zip(property_names, values))
            points.append(
                (
                    float(value_map["x"]),
                    float(value_map["y"]),
                    float(value_map["z"]),
                    _vertex_color(value_map),
                )
            )

    return points


def _property_offsets(properties: list[tuple[str, str]]) -> dict[str, int]:
    """binary PLY の各 property が何バイト目にあるか調べます。

    Args:
        properties: PLY ヘッダーに書かれていた頂点 property。
    Returns:
        dict[str, int]: property 名からバイト位置への対応。
    """

    offsets = {}
    offset = 0
    for property_type, name in properties:
        offsets[name] = offset
        offset += PLY_TYPE_SIZES[property_type]
    return offsets


def _decode_binary_vertex(
    record: bytes,
    properties: list[tuple[str, str]],
    offsets: dict[str, int],
) -> tuple[float, float, float, tuple[int, int, int]]:
    """binary PLY の1頂点を座標と色に変換します。

    Args:
        record: 1頂点ぶんのバイト列。
        properties: PLY ヘッダーに書かれていた頂点 property。
        offsets: property 名からバイト位置への対応。
    Returns:
        tuple[float, float, float, tuple[int, int, int]]: 座標とRGB色。
    """

    property_types = {name: property_type for property_type, name in properties}
    x = _unpack(record, offsets["x"], property_types["x"])
    y = _unpack(record, offsets["y"], property_types["y"])
    z = _unpack(record, offsets["z"], property_types["z"])

    if {"red", "green", "blue"}.issubset(offsets):
        color = (
            int(_unpack(record, offsets["red"], property_types["red"])),
            int(_unpack(record, offsets["green"], property_types["green"])),
            int(_unpack(record, offsets["blue"], property_types["blue"])),
        )
    else:
        color = (88, 230, 213)

    return float(x), float(y), float(z), color


def _unpack(record: bytes, offset: int, property_type: str) -> float | int:
    """PLY のバイト列から1つの値を取り出します。

    Args:
        record: 1頂点ぶんのバイト列。
        offset: 値が始まる位置。
        property_type: PLY の型名。
    Returns:
        float | int: 読み取った値。
    """

    return struct.unpack_from("<" + PLY_STRUCT_TYPES[property_type], record, offset)[0]


def _vertex_color(value_map: dict[str, str]) -> tuple[int, int, int]:
    """ASCII PLY の色を取り出します。

    Args:
        value_map: property 名と文字列値の対応。
    Returns:
        tuple[int, int, int]: RGB色。
    """

    if {"red", "green", "blue"}.issubset(value_map):
        return int(value_map["red"]), int(value_map["green"]), int(value_map["blue"])
    return 88, 230, 213


def _render_thumbnail(
    points: list[tuple[float, float, float, tuple[int, int, int]]],
    output_path: Path,
    message: str = "",
) -> None:
    """頂点を画面いっぱいに入るサムネイルへ描きます。

    Args:
        points: PLY から読んだ座標と色。
        output_path: PNG の保存先。
        message: 点を描けない時に画像へ入れる短い文。
    Returns:
        None: PNG を保存するだけで、値は返しません。
    """

    width, height = 960, 680
    image = _thumbnail_background(width, height)
    draw = ImageDraw.Draw(image, "RGBA")

    if not points:
        if message:
            draw.text((28, height - 52), message[:90], fill=(255, 184, 107, 220))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return

    projected = _project_points(points, width, height)
    for x, y, depth, color in sorted(projected, key=lambda item: item[2]):
        alpha = 155 + int(80 * depth)
        radius = 1 if len(projected) > 60_000 else 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _thumbnail_background(width: int, height: int) -> Image.Image:
    """サムネイル用の暗い背景を作ります。

    Args:
        width: 画像の幅。
        height: 画像の高さ。
    Returns:
        Image.Image: 背景画像。
    """

    image = Image.new("RGB", (width, height), (6, 9, 11))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(0, height, 34):
        draw.line((0, y, width, y), fill=(57, 215, 200, 18))
    for x in range(0, width, 34):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 9))
    draw.rectangle((0, 0, width - 1, height - 1), outline=(57, 215, 200, 52))
    return image


def _project_points(
    points: list[tuple[float, float, float, tuple[int, int, int]]],
    width: int,
    height: int,
) -> list[tuple[float, float, float, tuple[int, int, int]]]:
    """3D 頂点をサムネイル上の2D位置に変換します。

    Args:
        points: PLY から読んだ座標と色。
        width: サムネイル幅。
        height: サムネイル高さ。
    Returns:
        list[tuple[float, float, float, tuple[int, int, int]]]: 画面座標、奥行き、色。
    """

    sampled = points if len(points) <= 120_000 else random.sample(points, 120_000)
    xs = [point[0] for point in sampled]
    ys = [point[1] for point in sampled]
    zs = [point[2] for point in sampled]
    center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)

    rotated = []
    for x, y, z, color in sampled:
        x -= center[0]
        y -= center[1]
        z -= center[2]
        rx = 0.82 * x - 0.57 * z
        rz = 0.57 * x + 0.82 * z
        ry = 0.28 * rz + 0.96 * y
        depth = 0.96 * rz - 0.28 * y
        rotated.append((rx, ry, depth, color))

    min_x = min(point[0] for point in rotated)
    max_x = max(point[0] for point in rotated)
    min_y = min(point[1] for point in rotated)
    max_y = max(point[1] for point in rotated)
    min_depth = min(point[2] for point in rotated)
    max_depth = max(point[2] for point in rotated)
    scale = min((width * 0.82) / max(max_x - min_x, 1e-6), (height * 0.82) / max(max_y - min_y, 1e-6))
    depth_range = max(max_depth - min_depth, 1e-6)

    return [
        (
            width / 2 + (x - (min_x + max_x) / 2) * scale,
            height / 2 - (y - (min_y + max_y) / 2) * scale,
            (depth - min_depth) / depth_range,
            color,
        )
        for x, y, depth, color in rotated
    ]
