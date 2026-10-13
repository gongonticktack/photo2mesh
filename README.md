# photo2mesh

## 概要

写真をアップロードして対象物のマスクを作成し、SAM 3D Objectsで3Dメッシュを生成するローカルWebアプリです。WindowsのFlask画面からWSL内のSAM・SAM3Dを実行し、PLYモデルを保存します。

## 主な機能

- 画像アップロードとジョブ管理。
- 画像内のクリック位置からSAMによる対象マスクを作成。
- SAM3Dによる3Dモデル生成とPLYダウンロード。
- 生成済みモデルの一覧・サムネイル表示。
- ジョブごとの実行ログ表示。

## 推奨要件

| 項目 | 環境 |
| --- | --- |
| OS | WindowsとWSL2 |
| Windows側 | Python 3.11を推奨、現行ブラウザ |
| WSL側 | conda、SAM・SAM 3D Objectsの実行環境 |
| GPU | WSLから利用できるNVIDIA CUDA対応GPU・ドライバー |
| モデル | SAMのチェックポイント、SAM3Dコードと必要な重み |

既定のWSL conda環境名は`sam3d-blackwell`です。GPUメモリの最低値は本リポジトリで定義していません。SAM3Dの環境・重みはWindows用起動スクリプトだけでは導入できません。

## 必要なライブラリ

Windows側は`requirements.txt`で固定しています。

| ライブラリ | バージョン | 用途 |
| --- | --- | --- |
| Flask | 3.0.3 | Web画面 |
| Werkzeug | 3.0.3 | Web処理 |
| Pillow | 10.4.0 | 画像処理 |

WSL側はSAM・SAM3D公式実装のPyTorch、CUDA、画像・メッシュ処理依存関係を別途導入してください。

## 使い方

### 環境準備

1. WSL2でGPUが利用できることを確認します。
2. [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects)とSAMの環境・重みを準備します。
3. 次の環境変数を実際の配置先に合わせます。コードには既存PC向けのパスが含まれるため、他PCへ移す場合は変更が必要です。

| 環境変数 | 内容 |
| --- | --- |
| `SAM3D_CONDA_ENV` | WSLのconda環境。既定`sam3d-blackwell` |
| `PHOTO2MESH_WSL_PROJECT_ROOT` | WSLから見たこのプロジェクトのパス |
| `PHOTO2MESH_WINDOWS_PROJECT_ROOT` | Windows側のプロジェクトパス |
| `SAM3D_CODE_ROOT` | WSL側のSAM 3D Objectsコード |
| `SAM3D_CHECKPOINT_ROOT` | SAM・SAM3Dの重み配置先 |
| `SAM_CHECKPOINT` | SAMの重みファイル |
| `SAM_MODEL_TYPE` | SAMモデル種別。既定`vit_h` |
| `SAM_DEVICE` | SAMの実行デバイス。既定`cuda` |

### 起動・モデル生成

1. ルートの`start.bat`をダブルクリックします。Windows側の仮想環境と依存関係を準備します。
2. `http://127.0.0.1:7860/`を開きます。
3. 写真をアップロードし、対象物をクリックしてマスクを作成します。
4. マスクを確認して3D生成を実行します。
5. ジョブ画面からPLYをダウンロードします。生成済みモデルは「マイモデル」からも確認できます。

既定の画像上限は100 MBです。PNG・JPEG・WebP・BMP・TIFFに対応します。停止するときは起動コンソールで`Ctrl+C`を押します。

## 追加設定・保存先

| 項目 | 内容 |
| --- | --- |
| `PHOTO2MESH_HOST / PHOTO2MESH_PORT` | 待受先。既定`127.0.0.1:7860` |
| `PHOTO2MESH_MAX_UPLOAD_MB` | 画像サイズ上限。既定100 |
| `PHOTO2MESH_STORAGE_DIR` | 入力・ジョブ保存先 |
| `PHOTO2MESH_OUTPUT_DIR` | PLY保存先 |
| `PHOTO2MESH_LOGS_DIR` | ログ保存先 |
| `PHOTO2MESH_LOG_KEEP_COUNT` | 種類ごとのログ保持件数。既定5 |
| `SAM_MASK_COMMAND_TEMPLATE` | マスク生成コマンドのカスタマイズ |
| `SAM3D_COMMAND_TEMPLATE` | 3D生成コマンドのカスタマイズ |

標準の保存先は`storage/jobs/<job_id>/`、`output/`、`logs/`です。

## フォルダ構成

| 相対パス | 役割 |
| --- | --- |
| `app/photo2mesh/` | Webサーバー、設定、ジョブ、WSL呼出し、モデル一覧 |
| `app/photo2mesh/templates/` | HTML画面 |
| `app/photo2mesh/static/` | CSS・JavaScript |
| `app/sam3d_worker/` | WSL側で実行するマスク・3D生成処理 |
| `app/demo.py` | SAM3D推論の参考スクリプト |
| `output/` | 生成したPLY |
| `logs/` | 起動・アプリログ |
| `storage/jobs/` | 実行時に生成する入力画像・マスク・ジョブログ |
| `requirements.txt` | Windows側依存関係 |
| `start.bat` | Windows起動入口 |

## 仕組み

Windows画面で受け取った画像とクリック位置をWSLへ渡します。SAMが対象範囲を切り出し、SAM3Dが画像とマスクから形状を推定します。生成モデルをPLYとして保存し、画面へ結果とログを返します。

## 確認・トラブル対処

- 起動確認は画像アップロード→マスク→生成→PLYダウンロードの順で行います。
- WSL処理が失敗：conda環境名、WSLのプロジェクト・コード・重みパスを確認します。
- マスク生成失敗：SAMチェックポイント、モデル種別とGPUを確認します。
- 原因調査：ジョブ画面のログと`logs/`を確認します。
- 7860番が使用中：`PHOTO2MESH_PORT`を変更します。Music Stationも既定で同じポートを使用します。
