import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import symtypes_intersect as si  # noqa: E402

SYMTYPES = """\
s#list_head struct list_head { s#list_head * next , * prev ; }
s#spin struct spin { int l ; }
s#wq struct wq { s#spin lock ; s#list_head head ; }
s#completion struct completion { unsigned int done ; s#wq wait ; }
s#mutex struct mutex { s#spin wait_lock ; s#list_head wait_list ; }
mutex_lock void mutex_lock ( s#mutex * )
__wake_up void __wake_up ( s#wq * , unsigned int )
complete void complete ( s#completion * )
"""


class SymtypesIntersect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.symtypes").write_text(SYMTYPES)
        self.defs = si.load_symtypes(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_closure_follows_nested_types(self):
        got = si.closure(self.defs, "complete", {})
        self.assertIn("s#wq", got)
        self.assertIn("s#list_head", got)

    def test_names_the_only_differing_type(self):
        symbols = {"mutex_lock", "__wake_up", "complete"}
        cand, deepest, uncovered, unknown = si.analyse(self.defs, symbols, {"__wake_up", "complete"})
        # spin and list_head are shared with the matching mutex_lock: cleared.
        self.assertEqual(deepest, ["s#wq"])
        self.assertIn("s#completion", cand)
        self.assertEqual(uncovered, [])
        self.assertEqual(unknown, [])

    def test_no_candidate_when_everything_shared(self):
        symbols = {"mutex_lock", "__wake_up"}
        cand, deepest, _, _ = si.analyse(self.defs, symbols, {"__wake_up"})
        # s#wq is only reached by __wake_up here, so it is still the suspect.
        self.assertEqual(deepest, ["s#wq"])
        cand, deepest, uncovered, _ = si.analyse(self.defs, {"mutex_lock"}, {"mutex_lock"})
        self.assertTrue(deepest)  # mutex types reach only mismatching symbols

    def test_unknown_symbol_is_reported_not_guessed(self):
        _, _, _, unknown = si.analyse(self.defs, {"nope"}, {"nope"})
        self.assertEqual(unknown, ["nope"])

    def test_empty_inputs_fail_closed(self):
        empty = self.root / "empty.tsv"
        empty.write_text("module\tsymbol\tstock_crc\n")
        with self.assertRaises(SystemExit):
            si.load_reference_symbols(empty)
        rep = self.root / "r.txt"
        rep.write_text("no mismatches here\n")
        with self.assertRaises(SystemExit):
            si.load_mismatches(rep)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(si.load_symtypes(Path(d)), {})

    def test_mismatch_parser(self):
        rep = self.root / "r.txt"
        rep.write_text("  MISMATCH __wake_up: OEM=0x1 rebuilt=0x2\n  MISMATCH complete: OEM=0x3 rebuilt=0x4\n")
        self.assertEqual(si.load_mismatches(rep), {"__wake_up", "complete"})


if __name__ == "__main__":
    unittest.main()
