"""Сжатие старого сырья.

Сырьё не удаляется никогда: это единственный слой, который нельзя пересоздать.
Но и лежать целиком в несжатом виде ему незачем — читают его редко, а JSON
жмётся примерно в десять раз.

Свежие дни остаются как есть: их дочитывает сбор при повторных запусках и
загрузка. Сжимаются файлы старше RAW_COMPRESS_AFTER_DAYS дней. Читатели
разницы не замечают, её знает raw_files.py.

Запуск:  python compress_raw.py
         python compress_raw.py --days 7
         python compress_raw.py --dry-run
"""
from __future__ import annotations

import argparse
import gzip
import shutil
from datetime import date, timedelta

from config import RAW_COMPRESS_AFTER_DAYS, RAW_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сжать сырьё старше N дней")
    parser.add_argument(
        "--days",
        type=int,
        default=RAW_COMPRESS_AFTER_DAYS,
        help=f"возраст файла в днях, по умолчанию {RAW_COMPRESS_AFTER_DAYS}",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="только показать, что будет сжато"
    )
    return parser.parse_args()


def day_of(name: str) -> date | None:
    """Дата сбора из имени файла: raw_2026-09-23_gb_... → 2026-09-23."""
    parts = name.split("_")
    if len(parts) < 2:
        return None
    try:
        return date.fromisoformat(parts[1])
    except ValueError:
        return None


def main() -> int:
    args = parse_args()
    edge = date.today() - timedelta(days=args.days)

    targets = []
    for path in sorted(RAW_DIR.glob("raw_*.json")):
        day = day_of(path.name)
        if day is not None and day <= edge:
            targets.append(path)

    if not targets:
        print(f"Нечего сжимать: файлов старше {args.days} дн. нет.")
        return 0

    before = sum(path.stat().st_size for path in targets)
    print(f"Файлов старше {args.days} дн. ({edge} и раньше): {len(targets)}, "
          f"{before / 1e6:.1f} МБ")
    if args.dry_run:
        return 0

    after = 0
    for path in targets:
        target = path.with_suffix(".json.gz")
        # Сначала пишется сжатая копия, и только потом удаляется исходник:
        # обрыв посреди работы не должен оставить день без файла.
        with path.open("rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        after += target.stat().st_size
        path.unlink()

    print(f"Сжато до {after / 1e6:.1f} МБ, освобождено {(before - after) / 1e6:.1f} МБ "
          f"(в {before / after:.1f} раза).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
