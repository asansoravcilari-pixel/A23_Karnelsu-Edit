#!/usr/bin/env python3
"""Read-only inventory of a Samsung kernel source tarball; never certifies OEM equivalence."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

MAX_SELECTED_SIZE = 1024 * 1024
FILE_SUFFIXES = (
    'build_kernel.sh', 'Makefile', 'scripts/gcc-wrapper.py',
    'include/linux/wait.h', 'include/linux/completion.h',
    'include/linux/spinlock_types.h', 'include/asm-generic/qspinlock_types.h',
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path, *, expected_sha256: str | None = None) -> dict:
    actual_hash = _sha256(path)
    if expected_sha256 and actual_hash != expected_sha256.lower():
        raise ValueError(f'archive SHA-256 mismatch: expected {expected_sha256}, got {actual_hash}')

    years: Counter[int] = Counter()
    selected: dict[str, dict] = {}
    member_count = 0
    earliest: int | None = None
    latest: int | None = None
    ksu_path_count = 0
    seen_selected: set[str] = set()
    with tarfile.open(path, 'r|gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            member_count += 1
            stamp = int(member.mtime)
            years[datetime.fromtimestamp(stamp, timezone.utc).year] += 1
            earliest = stamp if earliest is None else min(earliest, stamp)
            latest = stamp if latest is None else max(latest, stamp)
            segments = member.name.lower().split('/')
            if any(x in {'kernelsu', 'kernelsu-next', 'susfs'} for x in segments):
                ksu_path_count += 1
            # Limited allowlist; no extraction and no executable launched.
            key = next((s for s in FILE_SUFFIXES if member.name in {s, 'kernel_src/' + s}), None)
            if key is None:
                continue
            if member.name in seen_selected:
                raise ValueError(f'duplicate selected archive member: {member.name}')
            seen_selected.add(member.name)
            info: dict = {'size': member.size}
            if 0 <= member.size <= MAX_SELECTED_SIZE:
                f = archive.extractfile(member)
                if f is None:
                    raise ValueError(f'cannot read selected member {member.name}')
                data = f.read(MAX_SELECTED_SIZE + 1)
                if len(data) != member.size:
                    raise ValueError(f'truncated selected member {member.name}')
                info['sha256'] = hashlib.sha256(data).hexdigest()
                if key == 'build_kernel.sh':
                    script = data.decode('utf-8', errors='replace')
                    info['build_flags_present'] = {
                        'REAL_CC': bool(re.search(r'\bREAL_CC\b', script)),
                        'CROSS_COMPILE': bool(re.search(r'\bCROSS_COMPILE\b', script)),
                        'CLANG_TRIPLE': bool(re.search(r'\bCLANG_TRIPLE\b', script)),
                        'LLVM_equals_1': bool(re.search(r'\bLLVM\s*=\s*1\b', script)),
                        'gcc_4_9_reference': '4.9' in script,
                    }
                elif key == 'Makefile':
                    makefile = data.decode('utf-8', errors='replace')
                    info['uses_gcc_wrapper'] = 'scripts/gcc-wrapper.py' in makefile
            else:
                info['warning'] = 'oversized selected file; contents not read'
            selected[member.name] = info

    def iso(stamp: int | None) -> str | None:
        return datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp is not None else None

    return {
        'archive': str(path), 'archive_bytes': path.stat().st_size,
        'archive_sha256': actual_hash, 'hash_matched_supplied_expected': expected_sha256 is not None,
        'regular_file_count': member_count, 'mtime_year_histogram_utc': dict(sorted(years.items())),
        'earliest_archive_mtime_utc': iso(earliest), 'latest_archive_mtime_utc': iso(latest),
        'kernel_su_path_count': ksu_path_count, 'selected_files': selected,
        'provenance_assessment': 'NOT_VERIFIED_OFFICIAL_SAMSUNG_MATCH',
        'notice': 'File modification times and names do not prove firmware/source equivalence; compare an official Samsung release identifier/checksum and the target firmware.',
        'flash_approval': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='a local source.tar.gz or Kernel.tar.gz')
    parser.add_argument('--expected-sha256', help='optional expected digest; pin is not proof of Samsung origin')
    parser.add_argument('--output', type=Path, help='write JSON report to this path')
    args = parser.parse_args(argv)
    if args.expected_sha256 and not re.fullmatch(r'[0-9a-fA-F]{64}', args.expected_sha256):
        parser.error('expected SHA-256 must be 64 hexadecimal characters')
    try:
        data = inventory(args.archive, expected_sha256=args.expected_sha256)
        report = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + '\n'
        if args.output:
            args.output.write_text(report, encoding='utf-8')
        else:
            sys.stdout.write(report)
    except (OSError, tarfile.TarError, ValueError, OverflowError) as exc:
        print(f'FAIL CLOSED (source inventory): {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
