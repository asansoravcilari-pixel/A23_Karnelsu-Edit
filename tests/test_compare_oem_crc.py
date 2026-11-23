#!/usr/bin/env python3
"""Black-box regression tests for A235FXXSEEZB1 OEM CRC gate."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_oem_crc.py"


def reference():
    lines = ["module\tsymbol\tstock_crc"]
    for prefix, name, size in (("wifi", "qca_cld3_wlan.ko", 408), ("rdbg", "rdbg.ko", 34)):
        lines.extend(f"{name}\t{prefix}_{n:03}\t0x{n+1:08x}" for n in range(size))
    return lines


def symvers():
    lines = []
    for prefix, size in (("wifi", 408), ("rdbg", 34)):
        lines.extend(f"0x{n+1:08x}\t{prefix}_{n:03}\tvmlinux\tEXPORT_SYMBOL" for n in range(size))
    return lines


class GateTests(unittest.TestCase):
    def invoke(self, refs=None, syms=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.tsv").write_text("\n".join(reference() if refs is None else refs) + "\n")
            (root / "Module.symvers").write_text("\n".join(symvers() if syms is None else syms) + "\n")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(root / "ref.tsv"), str(root / "Module.symvers"), str(root / "report")],
                text=True, capture_output=True
            )
            report = (root / "report").read_text() if (root / "report").exists() else run.stderr
            return run.returncode, report

    def test_matching_reference_passes_static_only(self):
        code, report = self.invoke()
        self.assertEqual(code, 0, report)
        self.assertIn("DEVICE BOOT STILL UNVERIFIED", report)

    def test_empty_reference_fails(self):
        code, report = self.invoke(refs=["module\tsymbol\tstock_crc"])
        self.assertNotEqual(code, 0)
        self.assertIn("expected 408", report)

    def test_missing_wifi_fails(self):
        code, report = self.invoke(refs=reference()[:1] + reference()[409:])
        self.assertNotEqual(code, 0)
        self.assertIn("expected 408", report)

    def test_partial_reference_fails(self):
        code, report = self.invoke(refs=reference()[:-1])
        self.assertNotEqual(code, 0)
        self.assertIn("expected 34", report)

    def test_duplicate_reference_import_fails(self):
        lines = reference()
        code, report = self.invoke(refs=lines + [lines[1]])
        self.assertNotEqual(code, 0)
        self.assertIn("duplicated import", report)

    def test_unexpected_module_fails(self):
        code, report = self.invoke(refs=reference() + ["unknown.ko\ta\t0x00000001"])
        self.assertNotEqual(code, 0)
        self.assertIn("unexpected module", report)

    def test_corrupt_crc_fails(self):
        lines = reference()
        lines[1] = lines[1].replace("0x00000001", "garbage")
        code, report = self.invoke(refs=lines)
        self.assertNotEqual(code, 0)
        self.assertIn("invalid hexadecimal CRC", report)

    def test_missing_export_fails(self):
        code, report = self.invoke(syms=symvers()[1:])
        self.assertNotEqual(code, 0)
        self.assertIn("MISSING wifi_000", report)

    def test_crc_mismatch_fails(self):
        lines = symvers()
        lines[0] = lines[0].replace("0x00000001", "0x0000ffff")
        code, report = self.invoke(syms=lines)
        self.assertNotEqual(code, 0)
        self.assertIn("MISMATCH wifi_000", report)

    def test_duplicate_export_fails(self):
        lines = symvers()
        code, report = self.invoke(syms=lines + [lines[0]])
        self.assertNotEqual(code, 0)
        self.assertIn("duplicate exported symbol", report)

    def test_empty_symvers_fails(self):
        code, report = self.invoke(syms=[])
        self.assertNotEqual(code, 0)
        self.assertIn("no valid exports", report)

    def test_invalid_header_fails(self):
        lines = reference()
        lines[0] = "module\tsymbol"
        code, report = self.invoke(refs=lines)
        self.assertNotEqual(code, 0)
        self.assertIn("header must be", report)


if __name__ == "__main__":
    unittest.main()
