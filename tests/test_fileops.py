from config import GlobalConfig, PathConfig, ArchivePolicyConfig
from fileops import move_to_archive


def test_move_to_archive_deletes_when_disabled(tmp_path):
	download = tmp_path / "download"
	download.mkdir()
	file_path = download / "sample.txt"
	file_path.write_text("data")

	cfg = GlobalConfig(
		paths=PathConfig(download=download, archive=tmp_path / "archive"),
		archive=ArchivePolicyConfig(enabled=False),
	)

	move_to_archive(file_path, cfg, cfg.paths.download)
	assert not file_path.exists()


def test_move_to_archive_moves_into_archive(tmp_path):
	download = tmp_path / "dl"
	archive = tmp_path / "arch"
	download.mkdir()
	(download / "nested").mkdir()
	file_path = download / "nested" / "file.bin"
	file_path.write_text("old")

	cfg = GlobalConfig(
		paths=PathConfig(download=download, archive=archive),
		archive=ArchivePolicyConfig(enabled=True),
	)

	move_to_archive(file_path, cfg, cfg.paths.download)

	dest = archive / "nested" / "file.bin"
	assert dest.exists()
	assert not file_path.exists()
