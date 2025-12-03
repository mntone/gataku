[English](./README.md) | 日本語

# gataku (画拓)

gataku は「画像」と「魚拓」を組み合わせた造語で、フェディバースの
ブックマークメディアをアーカイブするためのツールです。名前は日本語の
語感を大切にしつつ、グローバルでも扱いやすいようにアルファベット表記
を採用しています。

> **利用のお願い**  
> gataku は常識の範囲内で利用し、著作権や各インスタンスの利用規約を
> 尊重してください。非公開コンテンツの無断保存や配布、利用規約に反する
> 行為などには絶対に使わないでください。

AI の支援を受けながらわずか 2 日でプロトタイプを作成し、今後も実際の
フィードバックをもとに継続的に進化させていきます。

## ✨ 特徴

- Mastodon 互換 API を用いたブックマーク収集と自動ダウンロード
- 柔軟なファイル名テンプレートとログファイル出力
- ハッシュ DB による重複検知とアーカイブポリシー管理
- `download.useragent` などの設定を含む YAML ベースの構成ファイル
- `prune_downloads.py` による不要ファイルとハッシュ DB のクリーンアップ


## 🚀 セットアップ

```bash
python -m venv .venv
pip install -r requirements.txt
```

OS に応じて仮想環境を有効化してください。

- **macOS / Linux / WSL**
  ```bash
  source .venv/bin/activate
  ```
- **Windows (PowerShell)**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt)**
  ```bat
  .\.venv\Scripts\activate.bat
  ```


## 🖱️ 使い方

1. `config.sample.yaml` を `config.yaml` にコピーし、自分の環境に合わせて
   編集します。`instances` セクションにアクセストークンを設定してください。
2. 必要に応じて `download.useragent` を編集し、ダウンロード時に送信する
   User-Agent を明示的に指定できます。未設定の場合は既定値が使われます。
3. 以下のようにメインスクリプトを実行します。

```bash
python -m src.main [--config config.yaml]
```

CLI には `--limit`, `--dry-run`, `--dump-bookmarks` などのオプションが
あります。詳細は `python -m src.main --help` を参照してください。

### 設定における注意事項
- `download.filename_pattern` で保存パスをテンプレート化できます。
- `download.rate` と `download.retry` でレート制御とリトライ間隔を調整できます。
- `logging` セクションを使ってログの出力先や頻度を制御します。
- `archive.policy` により既存ファイルとの衝突時の動作を選択できます。
- `filename_pattern` では下記プレースホルダーを組み合わせて柔軟なフォルダ構成を作れます。

### メンテナンス
- `python -m src.prune_downloads [--config config.yaml] <path...>` で指定した
  ファイルを削除し、ハッシュ DB からも同時に削除できます。
- ハッシュ DB (`JsonlHashDB`) は JSONL 形式で保存されるため、必要に応じて
  バックアップを取ってください。
- Pull Request を送る際は `python3 -m pytest` を実行し、テストが通ることを確認してください。

## ❓ よくある質問
- **対応している Python のバージョンは？**  
  現在は Python 3.13 系で開発・テストしており、公式サポートは 3.11 以降
  （推奨は 3.13）とします。それより古いバージョンは対象外です。

- **途中で停止しても再開できますか？**  
  はい。ハッシュ DB でダウンロード済みのファイルを把握しているため、再実行すると
  重複をスキップします（アーカイブポリシーを変更しない限り）。

- **`download.useragent` はいつ変更すべきですか？**  
  インスタンス管理者から特定の User-Agent を求められる場合や、自分の
  連絡先を明示したい場合に設定してください。未設定の場合は既定値が使われます。

- **重複や不要ファイルの片付け方法は？**  
  `python -m src.prune_downloads [--config config.yaml] <path...>` を利用すると、
  ファイルの削除とハッシュ DB からの削除を同時に行えます。

- **テンプレートに使える変数は？**  
  | プレースホルダー | 説明 |
  | --- | --- |
  | `{origin_host}`, `{origin_group}` | メディアの配信元ホストと分類（例: `misskey`）。 |
  | `{account_host}`, `{account_group}` | 投稿アカウントのホストと分類。 |
  | `{sha256}` / `{sha256:8}` | ハッシュ全文または先頭 N 文字。 |
  | `{screenname}` | 投稿者のユーザー名/ハンドル。 |
  | `{index}` | ステータス内のメディア番号。 |
  | `{ext}` | メディアの拡張子。 |
  | `_date_vars` 由来: `{year}`, `{yearmonth}`, `{date}`, `{month}`, `{week}`, `{yearweek}`, `{yearquarter}`, `{datetime}`。 |

  これらは `download.filename_pattern` と `logging.filename_pattern` の両方で使用できます。


## 📜 ライセンス

このプロジェクトは GNU General Public License v3.0（GPLv3）の下で配布されています。
詳細は [`LICENSE`](./LICENSE)（英語）を参照してください。

GPL の条件を守る限り、ソフトウェアを利用・改変・再配布できます。
派生物を公開する場合は、同じライセンスで提供する必要があります。


## 🤝 貢献

Issue や Pull Request は歓迎します。責任ある利用を前提に、改善案や
バグ報告をお待ちしています。


## 👤 問い合わせ先

gataku は *mntone* が開発・保守しています。

- GitHub: https://github.com/mntone
- Mastodon: https://mstdn.jp/@mntone
- X: https://x.com/mntone
