from __future__ import annotations

import argparse
import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "backend" / "data" / "kol_crm.db"
DEFAULT_OUTPUT_DIR = ROOT / "backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_database(path: Path) -> dict[str, str | int]:
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    return {"path": str(path.resolve()), "sha256": sha256_file(path), "size": path.stat().st_size}


def create_backup(source: Path, output_dir: Path, timestamp: str | None = None) -> dict[str, str | int]:
    if not source.is_file():
        raise FileNotFoundError(f"Database not found: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    target = output_dir / f"kol_crm_backup_{stamp}.db"
    temporary = output_dir / f".{target.name}.tmp"
    if target.exists():
        raise FileExistsError(f"Backup already exists: {target}")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(source, timeout=30)) as source_db, closing(sqlite3.connect(temporary)) as target_db:
            source_db.backup(target_db)
            target_db.commit()
        result = verify_database(temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    digest = str(result["sha256"])
    checksum = target.with_suffix(target.suffix + ".sha256")
    checksum.write_text(f"{digest}  {target.name}\n", encoding="ascii")
    return {"path": str(target.resolve()), "sha256": digest, "size": target.stat().st_size, "checksum": str(checksum.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify a consistent Pangdun CRM SQLite backup")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    result = verify_database(args.verify) if args.verify else create_backup(args.source, args.output_dir)
    print("SQLite integrity: ok")
    print(f"Database: {result['path']}")
    print(f"Size: {result['size']} bytes")
    print(f"SHA-256: {result['sha256']}")
    if result.get("checksum"):
        print(f"Checksum file: {result['checksum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
