"""Synthetic-only regression tests; no proprietary source files required."""
from __future__ import annotations
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from a235f_source_provenance import inventory, main


class SourceProvenanceTest(unittest.TestCase):
    def make_archive(self, root: Path, *, duplicate=False) -> Path:
        archive = root / 'Kernel.tar.gz'
        entries = [
            ('build_kernel.sh', b'REAL_CC=toolchain/clang CROSS_COMPILE=aarch64-linux-android-4.9 CLANG_TRIPLE=aarch64-linux-gnu-'),
            ('kernel_src/Makefile', b'CC=python scripts/gcc-wrapper.py $(REAL_CC)\n'),
            ('kernel_src/include/linux/wait.h', b'struct wait_queue_head { int lock; };\n'),
            ('kernel_src/drivers/kernelsu/core.c', b'int dummy;'),
        ]
        if duplicate:
            entries.append(('build_kernel.sh', b'SECOND COPY'))
        with tarfile.open(archive, 'w:gz') as tar:
            for name, data in entries:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 1709164800
                tar.addfile(info, BytesIO(data))
        return archive

    def test_read_only_report_never_certifies_firmware(self):
        with tempfile.TemporaryDirectory() as td:
            archive = self.make_archive(Path(td))
            fingerprint = hashlib.sha256(archive.read_bytes()).hexdigest()
            x = inventory(archive, expected_sha256=fingerprint)
            self.assertEqual(x['regular_file_count'], 4)
            self.assertEqual(x['kernel_su_path_count'], 1)
            self.assertEqual(x['mtime_year_histogram_utc'], {2024: 4})
            self.assertTrue(x['selected_files']['build_kernel.sh']['build_flags_present']['REAL_CC'])
            self.assertTrue(x['selected_files']['kernel_src/Makefile']['uses_gcc_wrapper'])
            self.assertEqual(x['provenance_assessment'], 'NOT_VERIFIED_OFFICIAL_SAMSUNG_MATCH')
            self.assertFalse(x['flash_approval'])
            self.assertTrue(x['hash_matched_supplied_expected'])

    def test_digest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            archive = self.make_archive(Path(td))
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                inventory(archive, expected_sha256='0' * 64)
            self.assertEqual(main([str(archive), '--expected-sha256', '0'*64]), 2)

    def test_reject_duplicate_selected_member(self):
        with tempfile.TemporaryDirectory() as td:
            archive = self.make_archive(Path(td), duplicate=True)
            with self.assertRaisesRegex(ValueError, 'duplicate selected'):
                inventory(archive)

    def test_no_source_or_invalid_input(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'bad.tar.gz'
            p.write_bytes(b'not a gzip tar file')
            self.assertEqual(main([str(p)]), 2)
            self.assertEqual(main([str(p), '--expected-sha256', '1'*64]), 2)

    def test_json_file_output(self):
        with tempfile.TemporaryDirectory() as td:
            archive = self.make_archive(Path(td))
            report = Path(td) / 'report.json'
            self.assertEqual(main([str(archive), '--output', str(report)]), 0)
            self.assertIn('NOT_VERIFIED_OFFICIAL_SAMSUNG_MATCH', report.read_text())
            self.assertTrue(archive.is_file())


if __name__ == '__main__':
    unittest.main()
