import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IndexTests(unittest.TestCase):
    def test_find_record_after_unrelated_package_and_continuation(self):
        parser = load_module("debian_index", SRC / "parser_debian_control_file.py")
        records = parser.parse_packages(
            "Package: unrelated\nVersion: 99\n\nPackage: spotify-client\n"
            "Version: 1:1.2.3\nDescription: first\n continuation\n"
        )
        self.assertEqual(records[1]["Package"], "spotify-client")
        self.assertEqual(records[1]["Description"], "first\ncontinuation")

    def test_index_without_blank_package_separators(self):
        parser = load_module("debian_index", SRC / "parser_debian_control_file.py")
        records = parser.parse_packages("Package: one\nVersion: 1\nPackage: two\nVersion: 2\n")
        self.assertEqual([r["Package"] for r in records], ["one", "two"])


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "payload"
        self.config = self.root / "config with spaces"
        self.data.mkdir()
        for script in ("generate_bin.sh", "generate_generate_flags_file.sh", "generate_generate_envs_file.sh"):
            subprocess.run(["bash", str(SRC / script), str(self.data), "false"], check=True)
        self.binary = self.data / "spotify"
        # The generated launcher and the actual executable occupy different paths.
        self.launcher = self.root / "spotify"
        self.binary.rename(self.launcher)
        self.binary.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$CAPTURE"\nprintf "%s" "${EXAMPLE:-}" > "$ENV_CAPTURE"\necho native-output\nexit 37\n')
        self.binary.chmod(0o755)
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.config),
                        SPOTIFY_DATA_DIR=str(self.data), CAPTURE=str(self.root / "args"),
                        ENV_CAPTURE=str(self.root / "env"), SPOTIFY_DEBUG="0")

    def run_launcher(self, *args):
        return subprocess.run([str(self.launcher), *args], env=self.env, capture_output=True, text=True)

    def captured_args(self):
        return (self.root / "args").read_bytes().split(b"\0")[:-1]

    def test_empty_configs_add_no_empty_argument_and_preserve_exit(self):
        result = self.run_launcher("spotify:track:example", "argument with spaces")
        self.assertEqual(result.returncode, 37)
        self.assertEqual(self.captured_args(), [b"spotify:track:example", b"argument with spaces"])

    def test_debug_and_private_log(self):
        log = self.root / "logs with spaces" / "debug.log"
        result = self.run_launcher(f"--debug-log={log}", "spotify:album:example")
        self.assertEqual(result.returncode, 37)
        self.assertIn(b"--debug-level=4", self.captured_args())
        self.assertIn(b"--enable-logging=stderr", self.captured_args())
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        self.assertIn("native-output", log.read_text())

    def test_environment_values_are_preserved_without_shell_evaluation(self):
        folder = self.config / "spotify"
        folder.mkdir(parents=True)
        (folder / "spotify.env").write_text("# comment\nEXAMPLE=literal $(do-not-execute) value\n")
        (folder / "spotify-flags.conf").write_text("  # comment\n--example=value with spaces\n")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 37)
        self.assertEqual((self.root / "env").read_text(), "literal $(do-not-execute) value")
        self.assertEqual(self.captured_args(), [b"--example=value with spaces"])

    def test_invalid_environment_assignment_is_rejected(self):
        folder = self.config / "spotify"
        folder.mkdir(parents=True)
        (folder / "spotify.env").write_text("not an assignment\n")
        self.assertEqual(self.run_launcher().returncode, 2)
        self.assertFalse((self.root / "args").exists())


@unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb is required")
class ScanGateTests(unittest.TestCase):
    def build_with_scanner(self, update_status, scan_status):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "deb"
            (package / "DEBIAN").mkdir(parents=True)
            (package / "DEBIAN/control").write_text(
                "Package: spotify-client\nVersion: 1:1.2.3\nArchitecture: amd64\n"
                "Depends: libc6 (>= 2.39)\nMaintainer: Test <test@example.invalid>\nDescription: Test fixture\n"
            )
            executable = package / "usr/share/spotify/spotify"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/bash\nexit 0\n")
            executable.chmod(0o755)
            (package / "usr/bin").mkdir(parents=True)
            subprocess.run(["dpkg-deb", "--build", str(package), str(root / "spotify-client_1.2.3_amd64.deb")],
                           check=True, capture_output=True)
            stubs = root / "stubs"
            stubs.mkdir()
            for command, status in (("freshclam", update_status), ("clamscan", scan_status), ("rpmbuild", 0)):
                script = stubs / command
                script.write_text(f'#!/bin/bash\necho {command} >> "$EVENTS"\nexit {status}\n')
                script.chmod(0o755)
            env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}",
                       EVENTS=str(root / "events"), BUILD_DIR=str(root / "rpmbuild"),
                       SOURCES_DIR=str(root / "rpmbuild/SOURCES"), SPOTIFY_DOWNLOAD_DIR=str(root),
                       CLAMAV_DATABASE_DIR=str(root / "db"), SCAN_REPORT_DIR=str(root / "reports"),
                       BUILTIN_FFMPEG="false")
            result = subprocess.run([str(SRC / "build_SRPM.sh"), "stable", "1.2.3"],
                                    env=env, capture_output=True, text=True)
            events = (root / "events").read_text().splitlines()
            return result, events

    def test_update_failure_stops_before_scan_or_rpm(self):
        result, events = self.build_with_scanner(2, 0)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["freshclam"])

    def test_detection_stops_before_rpm(self):
        result, events = self.build_with_scanner(0, 1)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["freshclam", "clamscan"])

    def test_scan_error_stops_before_rpm(self):
        result, events = self.build_with_scanner(0, 2)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["freshclam", "clamscan"])

    def test_clean_scan_is_required_before_rpm(self):
        result, events = self.build_with_scanner(0, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["freshclam", "clamscan", "rpmbuild"])


class ReportTests(unittest.TestCase):
    def test_download_chart_includes_rpm_assets_only_and_escapes_names(self):
        report = load_module("download_stats", REPO / "tools/download_stats.py")
        page = report.render([{"tag_name": "<version>", "assets": [
            {"name": "spotify.x86_64.rpm", "download_count": 123},
            {"name": "other.zip", "download_count": 999}]}], "owner/repo")
        self.assertIn("123", page)
        self.assertNotIn("999", page)
        self.assertIn("&lt;version&gt;", page)

    def test_only_current_64_bit_targets_are_build_candidates(self):
        targets = json.loads((REPO / "packaging/targets.json").read_text())["targets"]
        self.assertTrue(any(t["status"] == "candidate" for t in targets))
        self.assertTrue(all(t["architecture"] in ("x86_64", "x86_64_v2") for t in targets if t["status"] == "candidate"))
        self.assertTrue(all(t["status"] == "unavailable" for t in targets if t["architecture"] in ("i386", "i686")))
        self.assertFalse(any(t["chroot"].endswith("-aarch64") for t in targets))


if __name__ == "__main__":
    unittest.main()
