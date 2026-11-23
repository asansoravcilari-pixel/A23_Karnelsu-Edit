"""Black-box checks that the ABI delta report never trusts invalid inputs."""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "explain_stock_abi_delta.py"
REFERENCE = ROOT / "references" / "a235fxxseezb1_stock_module_crc.tsv"


def exports():
    with REFERENCE.open(encoding="utf-8", newline="") as handle:
        values = {row["symbol"]: row["stock_crc"]
                  for row in csv.DictReader(handle, delimiter="\t")}
    return [f"{crc}\t{symbol}\tvmlinux\tEXPORT_SYMBOL"
            for symbol, crc in values.items()]


class DeltaInputTests(unittest.TestCase):
    def invoke(self, baseline=None, ksu=None, reference=None, missing_baseline=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stock = root / "stock.symvers"
            if not missing_baseline:
                stock.write_text("\n".join(exports() if baseline is None else baseline) + "\n")
            ksu_path = root / "ksu.symvers"
            ksu_path.write_text("\n".join(exports() if ksu is None else ksu) + "\n")
            ref = REFERENCE
            if reference is not None:
                ref = root / "reference.tsv"
                ref.write_text(reference)
            out = root / "report.txt"
            run = subprocess.run([sys.executable, str(SCRIPT), str(ref), str(stock),
                                  str(ksu_path), str(out)], text=True, capture_output=True)
            return run.returncode, out.read_text() if out.exists() else run.stderr

    def test_exact_reference_reports_static_match_only(self):
        code, report = self.invoke()
        self.assertEqual(code, 0, report)
        self.assertIn("Do not flash", report)

    def test_actual_crc_delta_is_reported_and_fails(self):
        changed = exports()
        changed[0] = changed[0].replace("0x2c75b772", "0x0000ffff")
        code, report = self.invoke(ksu=changed)
        self.assertEqual(code, 1, report)
        self.assertIn("kernelSU_changed_compatible_symbol", report)

    def test_out_of_range_crc_fails_without_truncation(self):
        changed = exports()
        changed[0] = changed[0].replace("0x2c75b772", "0x100000000")
        code, report = self.invoke(baseline=changed)
        self.assertNotEqual(code, 0)
        self.assertIn("CRC exceeds 32-bit width", report)
        self.assertIn("FAIL CLOSED", report)

    def test_duplicate_export_fails(self):
        changed = exports()
        code, report = self.invoke(ksu=changed + [changed[0]])
        self.assertNotEqual(code, 0)
        self.assertIn("duplicate exported symbol", report)

    def test_tampered_reference_fails(self):
        changed = REFERENCE.read_text().replace("0x2c75b772", "0x2c75b773", 1)
        code, report = self.invoke(reference=changed)
        self.assertNotEqual(code, 0)
        self.assertIn("OEM reference SHA-256 mismatch", report)

    def test_missing_profile_yields_failure_report(self):
        code, report = self.invoke(missing_baseline=True)
        self.assertNotEqual(code, 0)
        self.assertIn("FAIL CLOSED", report)
        self.assertIn("stock.symvers", report)


if __name__ == "__main__":
    unittest.main()
