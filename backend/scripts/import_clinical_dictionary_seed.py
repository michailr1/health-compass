"""Validate or explicitly import a Clinical Dictionaries v2 seed manifest.

Default mode is dry-run validation. Database writes require ``--apply`` and use
``DATABASE_MIGRATOR_URL`` so the runtime application role is never elevated.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.clinical_dictionary_seed import load_seed_manifest, upsert_seed_manifest

DEFAULT_SEED = Path(__file__).parents[1] / "data" / "clinical_dictionary" / "ru-RU-pilot-v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or import a clinical dictionary seed")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_SEED)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write validated concepts and aliases using DATABASE_MIGRATOR_URL",
    )
    return parser.parse_args()


async def run(path: Path, *, apply: bool) -> int:
    manifest = load_seed_manifest(path)
    alias_count = sum(len(concept.aliases) for concept in manifest.concepts)
    print(
        f"VALID version={manifest.version} concepts={len(manifest.concepts)} aliases={alias_count}"
    )

    if not apply:
        print("DRY_RUN no database changes applied")
        return 0

    if not settings.database_migrator_url:
        raise RuntimeError("DATABASE_MIGRATOR_URL is required with --apply")

    engine = create_async_engine(settings.database_migrator_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                result = await upsert_seed_manifest(session, manifest)
        print(
            f"APPLIED version={manifest.version} concepts={result['concepts']} aliases={result['aliases']}"
        )
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args.path, apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
