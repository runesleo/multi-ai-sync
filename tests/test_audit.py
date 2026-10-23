import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ai_sync_audit as a  # noqa: E402


def touch(path: Path, age_hours: float, now: float, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    t = now - age_hours * 3600
    os.utime(path, (t, t))


def iso(now: float, hours_ago: float) -> str:
    return (datetime.fromtimestamp(now, timezone.utc) - timedelta(hours=hours_ago)).isoformat()


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.now = time.time()

    def tearDown(self):
        self.tmp.cleanup()

    def audit(self, *agents, **top):
        return a.audit({"agents": list(agents), **top}, now=self.now)

    def test_ok_stale_missing_and_skipped(self):
        touch(self.d / "chat/a.txt", 1, self.now)
        touch(self.d / "out/p1/latest.json", 50, self.now)
        r = self.audit({"name": "bot", "chat": str(self.d / "chat/*.txt"),
                        "results": str(self.d / "out/*/latest.json"), "memory": str(self.d / "mem/bot.md")},
                       {"name": "chat-only", "chat": str(self.d / "chat/*.txt")}, max_age_hours=36)
        bot, chat_only = r["agents"]
        self.assertEqual([bot[l]["status"] for l in a.LAYERS], [a.OK, a.STALE, a.MISSING])
        self.assertEqual(bot["gaps"], ["results", "memory"])
        self.assertEqual((chat_only["results"]["status"], chat_only["gaps"]), (a.SKIPPED, []))
        self.assertFalse(r["ok"])

    def test_every_mode_reports_each_stale_file(self):
        for i in range(13):
            touch(self.d / f"out/p{i}/latest.json", 1 if i < 2 else 50, self.now)
        pattern = str(self.d / "out/*/latest.json")
        newest = self.audit({"name": "t", "results": pattern})["agents"][0]["results"]
        self.assertEqual(newest["status"], a.OK)  # newest mode hides the 11 stale ones — by design
        every = self.audit({"name": "t", "results": pattern, "results_mode": "every"})["agents"][0]
        self.assertEqual(every["results"]["status"], a.STALE)
        self.assertEqual(len(every["results"]["patterns"][0]["stale"]), 11)
        self.assertIn("11/13 file(s) older than", "\n".join(a.gap_lines(every)))

    def test_list_of_patterns_flags_one_missing(self):
        touch(self.d / "p1/latest.json", 1, self.now)
        r = self.audit({"name": "t", "results": [str(self.d / "p1/latest.json"), str(self.d / "p2/latest.json")]})
        self.assertEqual(r["agents"][0]["results"]["status"], a.MISSING)

    def test_content_timestamp_beats_fresh_mtime(self):
        p = self.d / "latest.json"
        p.write_text(json.dumps({"observed_at": "2020-01-01T00:00:00Z"}))  # just copied: mtime is now
        row = self.audit({"name": "x", "results": str(p), "results_time_field": "observed_at"})["agents"][0]
        self.assertEqual((row["results"]["status"], row["results"]["patterns"][0]["time_source"]), (a.STALE, "content"))

    def test_unusable_content_timestamp_is_a_gap_not_mtime(self):
        p = self.d / "latest.json"
        for body in ["not json", "[1, 2]", json.dumps({"other": 1}), json.dumps({"observed_at": "soon"}),
                     json.dumps({"observed_at": iso(self.now, -48)})]:  # last one: two days in the future
            p.write_text(body)
            row = self.audit({"name": "x", "results": str(p), "results_time_field": "observed_at"})["agents"][0]
            self.assertEqual(row["results"]["status"], a.UNREADABLE, body)

    def test_parse_time_formats(self):
        base = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()
        for s in ["2026-01-02T03:04:05Z", "2026-01-02T03:04:05z", "2026-01-02T03:04:05+0000",
                  "2026-01-02T11:04:05+08:00", "2026-01-02T03:04:05.123456789Z", "2026-01-02 03:04:05",
                  "2026-01-02T03:04:05"]:  # no offset → UTC, not local time
            self.assertAlmostEqual(a.parse_time(s), base, delta=1, msg=s)
        for n in [base, base * 1e3, base * 1e6, base * 1e9]:
            self.assertAlmostEqual(a.parse_time(n), base, delta=1)
        for bad in [None, True, "", "yesterday", -5]:
            self.assertIsNone(a.parse_time(bad))

    def test_age_at_limit_is_ok(self):
        touch(self.d / "m.md", 26, self.now)
        self.assertTrue(self.audit({"name": "x", "memory": str(self.d / "m.md"), "max_age_hours": 26})["ok"])

    def test_recursive_glob_includes_top_level(self):
        touch(self.d / "o/top.md", 1, self.now)
        touch(self.d / "o/deep/er/r.md", 1, self.now)
        r = self.audit({"name": "x", "results": str(self.d / "o/**/*.md")})
        self.assertEqual(r["agents"][0]["results"]["files"], 2)

    def test_bad_configs(self):
        p = str(self.d / "x")
        for cfg in [[], {"agents": []}, {"agents": None}, {"agents": [{"chat": p}]},
                    {"agents": [{"name": "x"}]}, {"agents": [{"name": "x", "chat": None}]},
                    {"agents": [{"name": "x", "chat": ["a", 3]}]}, {"max_age_hours": None, "agents": [{"name": "x", "chat": p}]},
                    {"agents": [{"name": "x", "chat": p, "chat_mode": "all"}]}]:
            with self.assertRaises(a.ConfigError, msg=cfg):
                a.audit(cfg, now=self.now)

    def test_cli_exit_codes_and_json_stdout(self):
        touch(self.d / "m.md", 1, self.now)
        cfg = self.d / "c.json"

        def run(obj=None, *args):
            if obj is not None:
                cfg.write_text(obj if isinstance(obj, str) else json.dumps(obj))
            return subprocess.run([sys.executable, str(ROOT / "ai_sync_audit.py"), "--config", str(cfg), *args],
                                  capture_output=True, text=True)

        p = run({"agents": [{"name": "x", "memory": str(self.d / "m.md")}]}, "--json")
        self.assertEqual(p.returncode, 0)
        self.assertTrue(json.loads(p.stdout)["ok"])
        p = run({"agents": [{"name": "x", "memory": str(self.d / "nope.md")}]})
        self.assertEqual(p.returncode, 1)
        self.assertIn("x / memory: MISSING", p.stdout)
        self.assertEqual(run("[]").returncode, 2)
        self.assertEqual(run("{bad json").returncode, 2)
        p = run({"agents": [{"name": "x", "chat": None}]})
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("Traceback", p.stderr)
        cfg.unlink()
        self.assertEqual(run().returncode, 2)

    def test_init_does_not_overwrite(self):
        cfg = self.d / "ai-sync.json"
        with open(os.devnull, "w") as null:
            old, sys.stdout = sys.stdout, null
            try:
                self.assertEqual(a.main(["--init", "--config", str(cfg)]), 0)
            finally:
                sys.stdout = old
        self.assertTrue(json.loads(cfg.read_text())["agents"])
        self.assertEqual(a.main(["--init", "--config", str(cfg)]), 2)


if __name__ == "__main__":
    unittest.main()
