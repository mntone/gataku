English | [日本語](./README.ja.md)

# gataku (also written as “画拓”)

gataku is a playful portmanteau of “image” and the Japanese word for
archiving (“gyotaku”). It’s a Fediverse-friendly tool for collecting the
media you’ve bookmarked on Mastodon-compatible servers. The name nods to
its Japanese roots while remaining easy to say internationally.

> **Please use responsibly**  
> Always respect copyright laws and local instance policies. Do **not** use
> gataku to archive private posts, redistribute content without permission,
> or engage in any activity that violates terms of service.

gataku was prototyped in just two days with the help of AI-assisted tooling,
and will continue to evolve based on real-world feedback.


## ✨ Features

- Fetches bookmarks via Mastodon-compatible APIs and downloads media automatically
- Flexible filename templates and log outputs (JSONL)
- Duplicate detection with hash-based storage and customizable archive policies
- YAML-based configuration, including a configurable `download.useragent`
- `prune_downloads.py` cleans up files and removes matching entries from the hash DB


## 🚀 Setup

```bash
python -m venv .venv
pip install -r requirements.txt
```

Activate the virtual environment with the command that matches your OS:

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


## 🖱️ Usage

1. Copy `config.sample.yaml` to `config.yaml` and adjust it for your environment.
   Add each instance in the `instances` section with access tokens.
2. (Optional) Set `download.useragent` to customize the User-Agent header used
   when downloading media. The default value is the same as previous releases.
3. Run the main entry point:

```bash
python -m src.main [--config config.yaml]
```

Useful CLI switches: `--limit`, `--dry-run`, `--dump-bookmarks`, and more—see
`python -m src.main --help` for the full list.

### Configuration tips
- `download.filename_pattern` controls where files are stored.
- `download.rate` and `download.retry` manage pacing and retry behavior.
- `logging` controls log destination, frequency, and what gets recorded.
- `archive.policy` instructs gataku how to handle existing duplicates.
- `filename_pattern` can use placeholders listed below to build descriptive paths.

### Maintenance
- `python -m src.prune_downloads [--config config.yaml] <path...>` removes files
  and their corresponding hash entries in one go.
- The hash database (`JsonlHashDB`) is stored as JSON Lines; back it up as needed.
- Run `python3 -m pytest` before opening pull requests to ensure all unit tests pass.

## ❓ FAQ
- **Which Python versions are supported?**  
  gataku is developed and tested on Python 3.13, with official support promised
  for Python 3.11 and newer (3.13 recommended). Older versions are not supported.

- **Can I continue after an interruption?**  
  Yes. gataku keeps track of processed hashes, so re-running the fetcher simply
  skips already-downloaded media (unless you change the archive policy).

- **When should I change `download.useragent`?**  
  Some instances ask clients to present a specific User-Agent header. You can set
  this field to your own contact information or to match the requirements of the
  server you’re accessing.

- **How do I clean up duplicates or removed files?**  
  Use `python -m src.prune_downloads [--config config.yaml] <path...>` to delete
  files and automatically remove their entries from the hash DB.

- **Which placeholders can I use in templates?**  
  | Placeholder | Description |
  | --- | --- |
  | `{origin_host}`, `{origin_group}` | Media host and normalized group (e.g., `misskey`). |
  | `{account_host}`, `{account_group}` | Source account host and group classification. |
  | `{sha256}` / `{sha256:8}` | Full hash or first N characters. |
  | `{screenname}` | Username/handle from the status. |
  | `{index}` | Media index within the status (0-based in code, typically +1 in templates). |
  | `{ext}` | File extension derived from the media. |

  Date/time placeholders from `_date_vars` expand using the timestamp attached to each status.  
  Examples below assume the initial commit timestamp `2025-12-04 00:19:59` (local server time):
  | Placeholder     | Description                     | Example          |
  | --------------- | ------------------------------- | ---------------- |
  | `{year}`        | 4-digit year                    | `2025`           |
  | `{yearmonth}`   | Compact year+month (`%Y%m`)     | `202512`         |
  | `{date}`        | ISO date (`%Y-%m-%d`)           | `2025-12-04`     |
  | `{month}`       | Month number (`01-12`)          | `12`             |
  | `{week}`        | ISO week number (00-53)         | `49`             |
  | `{quarter}`     | Quarter of the year (1-4)       | `4`              |
  | `{half}`        | Half of the year (1-2)          | `2`              |
  | `{yearweek}`    | ISO year/week (`%YW%V`)         | `2025W49`        |
  | `{yearquarter}` | Year + quarter                  | `2025Q4`         |
  | `{yearhalf}`    | Year + half                     | `2025H2`         |
  | `{datetime}`    | Full timestamp (`%Y%m%d%H%M%S`) | `20251204001959` |

  These placeholders can be used in both `download.filename_pattern` and `logging.filename_pattern`.


## 📜 License

This project is licensed under the terms of the GNU General Public License v3.0 (GPLv3).
See the [`LICENSE`](./LICENSE) file for full details.

You are free to use, modify, and distribute this software under the terms of the GPL,
provided that any derivative work is also distributed under the same license.


## 🤝 Contributing

Issues and pull requests are welcome—just remember the emphasis on responsible use.


## 👤 Contact

gataku is developed and maintained by *mntone*.

- GitHub: https://github.com/mntone
- Mastodon: https://mstdn.jp/@mntone
- X: https://x.com/mntone
