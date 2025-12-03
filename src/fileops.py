from pathlib import Path
import shutil

from config import GlobalConfig


def move_to_archive(original_path: Path, config: GlobalConfig, download_root: Path):
	"""Archive or delete a file based on the configured archive policy."""
	if not original_path.exists():
		return

	if not config.archive.enabled:
		original_path.unlink(missing_ok=True)
		return

	base = config.paths.archive
	base.mkdir(parents=True, exist_ok=True)

	inst_download_dir = Path(download_root)
	try:
		rel = original_path.relative_to(inst_download_dir)
	except ValueError:
		# If the file is outside download_dir, fall back to storing only its basename.
		rel = Path(original_path.name)

	dest = base / rel
	dest.parent.mkdir(parents=True, exist_ok=True)
	shutil.move(str(original_path), str(dest))
