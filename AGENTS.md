# AGENTS.md

## プロジェクト指示

- このプロジェクトを変更する前に、このファイルを確認する。
- プロジェクト直下は散らかさない。直下に置くファイルは、原則として `README.md`、`requirements.txt`、`.gitignore`、`start.bat`、`AGENTS.md` などのプロジェクト全体に関わるものだけにする。
- 実装ファイルは、機能ごとにフォルダへ分けて置く。
- 動作、セットアップ、コマンド、生成物、運用ルールを変えたら、必ず `README.md` も更新する。
- ユーザーが作った可能性のあるファイルは、ユーザーが明示的に依頼しない限り、削除や巻き戻しをしない。

## コードの書き方

- コード内コメントは、中学生でも目的が分かるくらいの短い日本語で書く。
- 新しく作る、または変更する Python 関数には docstring を付ける。
- 関数の docstring には、必ず `Args` と `Returns` を書く。
- コメントは、単にコードを読み上げるのではなく、その処理がなぜ必要かを短く説明する。
- `.bat` ファイルは Windows `cmd.exe` の文字化けを避けるため、ASCII 文字だけで書く。

## 確認方法

- Python を変更した後、`.venv` がある場合は `.\\.venv\\Scripts\\python.exe -m compileall app` を実行する。
- Flask のルートを変更した後、`.venv` がある場合は `$env:PYTHONPATH='E:\\Program\\photo2mesh\\app'; .\\.venv\\Scripts\\python.exe -m flask --app photo2mesh.server routes` を実行する。
- 確認を実行できなかった場合は、最後の報告で理由を伝える。

## 実行環境メモ

- WSL から見たプロジェクトパスは `/mnt/e/Program/photo2mesh`。
- 既定の WSL conda 環境は `sam3d-blackwell`。
- SAM と SAM3D は、Windows 側から `wsl.exe` 経由で実行する。
- 生成された PLY は `output/` に保存する。
- アップロード画像、mask、ジョブごとの SAM ログは `storage/jobs/<job_id>/` に保存する。
- コンソールログとアプリログは `logs/` に保存し、種類ごとに直近5件だけ残す。
