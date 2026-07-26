# photo2mesh

写真をアップロードし、WSL 内の `sam3d-blackwell` conda 環境で SAM3D を実行して PLY モデルを生成するローカル Web アプリです。

## 起動

1. `start.bat` をダブルクリックします。
2. 初回のみ `.venv` を作成し、`requirements.txt` の依存関係をインストールします。
3. ブラウザで `http://127.0.0.1:7860` を開きます。

## SAM3D コマンド設定

既定では、WSL から見たプロジェクトパスを `/mnt/e/Program/photo2mesh` として扱います。
この値は [app/photo2mesh/config.py](app/photo2mesh/config.py) の `WSL_PROJECT_ROOT` で管理しています。

写真をアップロードした後、詳細画面でメッシュ化したい物体を1クリックします。クリック座標は Meta Segment Anything に渡され、`storage/jobs/<job_id>/masks/0.png` に mask が作られます。その後、その mask を使って SAM3D が PLY を生成します。

## Segment Anything 設定

ワンクリック mask 作成には、WSL 側の `sam3d-blackwell` conda 環境で `segment_anything` が import できる必要があります。

`E:\Program\sam3D\checkpoints` は SAM3D 本体の checkpoint 置き場です。
WSL からは `/mnt/e/Program/sam3D/checkpoints` として参照します。

一方、ワンクリック mask 作成には Segment Anything 用の checkpoint も別途必要です。
既定の SAM checkpoint は次のパスです。

```bash
/mnt/e/Program/sam3D/checkpoints/sam_vit_h_4b8939.pth
```

Windows 側では、次の場所に置いてください。

```text
E:\Program\sam3D\checkpoints\sam_vit_h_4b8939.pth
```

このファイルがない場合、mask 作成は `SAM checkpoint for one-click masking was not found` で失敗します。

必要に応じて Windows 側で以下を設定してから `start.bat` を起動してください。

```bat
set SAM_CHECKPOINT=/mnt/e/Program/sam3D/checkpoints/sam_vit_h_4b8939.pth
set SAM_MODEL_TYPE=vit_h
set SAM_DEVICE=cuda
```

既定では次のコマンドを WSL 内で実行します。

```bash
python "/mnt/e/Program/photo2mesh/app/sam3d_worker/create_mask_from_click.py" --image "{input}" --output "{mask_file}" --x {point_x} --y {point_y} --checkpoint "/mnt/e/Program/sam3D/checkpoints/sam_vit_h_4b8939.pth" --model-type "vit_h" --device "cuda"
python "/mnt/e/Program/photo2mesh/app/sam3d_worker/run_sam3d_from_image.py" --image "{input}" --output "{output}" --project-root "/home/gonsgon/sam3D/sam-3d-objects" --mask-source "{mask}"
```

環境に合わせて変更したい場合は、Windows 側で以下の環境変数を設定してから `start.bat` を起動してください。

```bat
set PHOTO2MESH_WSL_PROJECT_ROOT=/mnt/e/Program/photo2mesh
set SAM_MASK_COMMAND_TEMPLATE=python "{wsl_project_root}/app/sam3d_worker/create_mask_from_click.py" --image "{input}" --output "{mask_file}" --x {point_x} --y {point_y} --checkpoint "{sam_checkpoint}" --model-type "{sam_model_type}" --device "{sam_device}"
set SAM3D_COMMAND_TEMPLATE=python "{wsl_project_root}/app/sam3d_worker/run_sam3d_from_image.py" --image "{input}" --output "{output}" --project-root "{wsl_project_root}" --mask-source "{mask}"
```

使用できるプレースホルダー:

- `{input}`: WSL 形式のアップロード画像パス
- `{output}`: WSL 形式の出力 PLY パス
- `{mask}`: WSL 形式の mask フォルダパス
- `{mask_file}`: WSL 形式の mask PNG パス
- `{point_x}`: 元画像ピクセルでのクリック横位置
- `{point_y}`: 元画像ピクセルでのクリック縦位置
- `{wsl_project_root}`: WSL 形式のプロジェクトルート。既定値は `/mnt/e/Program/photo2mesh`

必要に応じて以下も変更できます。

- `SAM3D_CONDA_ENV`: conda 環境名。既定値は `sam3d-blackwell`
- `SAM3D_WORKDIR`: WSL 内でコマンド実行前に移動するディレクトリ
- `SAM3D_CODE_ROOT`: WSL 内の SAM3D コードルート。既定値は `/home/gonsgon/sam3D/sam-3d-objects`
- `SAM3D_CHECKPOINT_ROOT`: WSL 内の SAM3D checkpoint ルート。既定値は `/mnt/e/Program/sam3D/checkpoints`
- `SAM_CHECKPOINT`: Segment Anything の checkpoint パス
- `SAM_MODEL_TYPE`: Segment Anything のモデル種類。既定値は `vit_h`
- `SAM_DEVICE`: Segment Anything の実行デバイス。既定値は `cuda`
- `PHOTO2MESH_WINDOWS_PROJECT_ROOT`: Windows 側のプロジェクトルート。既定値はこのフォルダ
- `PHOTO2MESH_WSL_PROJECT_ROOT`: WSL から見たプロジェクトルート。既定値は `/mnt/e/Program/photo2mesh`
- `PHOTO2MESH_HOST`: Web サーバのホスト。既定値は `127.0.0.1`
- `PHOTO2MESH_PORT`: Web サーバのポート。既定値は `7860`

## SAM3D 実行スクリプト

[app/sam3d_worker/run_sam3d_from_image.py](app/sam3d_worker/run_sam3d_from_image.py) が、`app/demo.py` と同じ流れで SAM3D を呼び出します。

1. `notebook/inference.py` から `Inference`, `load_image`, `load_single_mask` を読み込みます。
2. `checkpoints/hf/pipeline.yaml` を使ってモデルを読み込みます。
3. Segment Anything が作成した `storage/jobs/<job_id>/masks/` を `load_single_mask(..., index=0)` に渡します。
4. `output["glb"]` を PLY として保存します。

## 生成物

アップロード画像、ログ、mask は `storage/jobs/<job_id>/` に保存されます。PLY はプロジェクト直下の `output/<job_id>.ply` に保存されます。`storage/`、`output/*.ply`、`.venv/` は Git 管理対象外です。

## マイモデル

トップ画面と `/models` では、`output/` にある PLY ファイルを「マイモデル」として一覧表示します。

各モデルのサムネイルは、PLY の頂点、色、三角面を読み取り、画面いっぱいに収まるように自動で投影して `storage/thumbnails/<model_id>.png` に保存します。トップ画面では最近のモデルを横並びで表示し、サイドメニューの「マイモデル」から `/models` に移動すると全モデルを一覧表示します。サムネイル画像をクリックすると、対応する色付きメッシュ PLY ファイルをダウンロードできます。

## ログ

コンソール出力とプログラムログは `logs/` に保存されます。

- `logs/start_*.log`: `start.bat` の起動ログと Flask のコンソール出力
- `logs/app_*.log`: Flask アプリ内のプログラムログ

ログは種類ごとに直近5件だけ残します。古いログは起動時に自動で削除されます。

## 実行状況の見える化

`start.bat` は Flask のコンソール出力を画面に表示しつつ、同じ内容を `logs/start_*.log` に UTF-8 で保存します。

写真をクリックして SAM/SAM3D を開始すると、ジョブごとに別のコンソール画面が開きます。この画面には、WSL 起動、conda activate、Segment Anything の mask 作成、SAM3D 実行の進行状況が表示されます。同じ内容は `storage/jobs/<job_id>/sam3d.log` にも保存されます。

別画面を出したくない場合は、Windows 側で以下を設定してから起動してください。

```bat
set SAM_VISIBLE_CONSOLE=0
```

## Codex 向けルール

Codex 向けの永続指示は、プロジェクト直下の `AGENTS.md` に置いています。

- 更新のたびに、この `README.md` へ変更内容を追記または更新します。
- コード内コメントは、中学生でも処理の目的が分かるくらいの言葉で書きます。
- 関数には docstring を付け、`Args` と `Returns` を必ず記載します。

## 更新履歴

- 2026-07-26: 写真選択時に生成開始前のプレビューを表示するようにし、ジョブ画面ではマスク作成ボタンが画面外に切れないよう調整。
- 2026-07-26: トップ画面の手順説明を、参照デザインに合わせて3枚のカード表示へ変更。
- 2026-07-25: UI 上で SAM と SAM3D を使っていることが分かるよう、ブランド表記、生成パネル、ジョブ画面、マイモデル画面の文言を更新。
- 2026-07-25: トップ画面に、写真アップロードから PLY 出力までの手順表示をコンパクトな形で再追加。
- 2026-07-25: マイモデルのサムネイル生成を点群描画から、PLY の三角面を使った色付きメッシュ描画へ変更。
- 2026-07-25: デスクトップ表示で画面全体が縦スクロールしにくいようにレイアウトを圧縮し、サイドメニューを「ホーム」「マイモデル」に整理。
- 2026-07-25: 参照デザインに合わせ、左サイドバー付きのダッシュボード構成へ変更し、マイモデルを横並びギャラリー表示に更新。
- 2026-07-25: `output/` の PLY を「マイモデル」として一覧表示し、PLY からサムネイル PNG を自動生成してクリックでダウンロードできるように更新。
- 2026-07-25: Web UI をさらにモダンなダークテーマへ調整し、ナビゲーション、モデルギャラリー、ジョブ履歴の見た目を統一。
- 2026-07-25: Web UI をダークモードのモダンなデザインへ更新し、状態表示やアップロード領域を見やすく調整。
- 2026-07-25: `start.bat` と SAM/SAM3D ジョブの進行状況をコンソールに表示し、WSL/conda/SAM/SAM3D のステップを見える化。
- 2026-07-25: spconv の実行時ビルドで `cublasLt.h` / `nvcc` が見つからない問題に対応するため、WSL 実行時に CUDA bin/include/library パスを明示設定。
- 2026-07-25: SAM3D のコードルートを `/home/gonsgon/sam3D/sam-3d-objects`、checkpoint ルートを `/mnt/e/Program/sam3D/checkpoints` に合わせて設定。
- 2026-07-25: SAM/SAM3D 失敗時にログ末尾を画面へ出すようにし、conda 初期化の探索先を追加。
- 2026-07-25: `wslpath` 変換エラーを避けるため、既知の Windows/WSL プロジェクトルートから WSL パスを組み立てる方式に変更。
- 2026-07-25: `AGENTS.md` を日本語化し、補助メモ用の `ai/README.md` を削除。
- 2026-07-25: Codex の公式仕様に合わせ、プロジェクト直下に `AGENTS.md` を追加。
- 2026-07-25: `logs/` フォルダへコンソール出力とプログラムログを保存し、直近5件だけ残す仕組みを追加。
- 2026-07-25: `start.bat` が日本語コメントの文字コードで閉じる問題を避けるため、ASCII のみの内容に変更し、`start.log` を出力するように更新。
- 2026-07-25: Web画面で画像を1クリックし、Meta Segment Anything で object mask を作成してから SAM3D を実行する流れを追加。
- 2026-07-25: `sam3d.run` の仮コマンドをやめ、`demo.py` 参考の `run_sam3d_from_image.py` を追加。WSL プロジェクトパス設定と `output/` 出力に対応。
- 2026-07-25: Codex 向けルールを追加し、Web アプリ本体へコメントと docstring を追加。
