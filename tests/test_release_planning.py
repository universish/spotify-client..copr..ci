import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("plan_release", REPO / "tools/plan_release.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


def release(version, number, **kwargs):
    return {"tag_name": f"v{version}-{number}", "draft": False, "prerelease": False,
            "assets": [{"name": f"spotify-{version}-{number}.x86_64.rpm"},
                       {"name": f"spotify-{version}-{number}.src.rpm"}], **kwargs}


def build(version, number, state="succeeded", name="spotify"):
    return {"source_package": {"name": name, "version": f"{version}-{number}"}, "state": state}


class PlanningTests(unittest.TestCase):
    def test_same_version_schedule_exits_before_work(self):
        result = planner.plan("1.2.3", [release("1.2.3", 3)], [], [])
        self.assertFalse(result["needed"])
        self.assertNotIn("release", result)

    def test_manual_always_increments_even_without_new_deb(self):
        result = planner.plan("1.2.3", [release("1.2.3", 3)], [], [], manual=True)
        self.assertEqual((result["needed"], result["release"], result["tag"]), (True, 4, "v1.2.3-4"))

    def test_new_version_resets_to_one(self):
        result = planner.plan("1.2.4", [release("1.2.3", 99)],
                              [{"ref": "refs/tags/v1.2.3-100"}], [build("1.2.3", 101)])
        self.assertEqual(result["release"], 1)

    def test_copr_history_can_be_ahead_of_github(self):
        result = planner.plan("1.2.3", [release("1.2.3", 3)], [], [build("1.2.3", 9)], manual=True)
        self.assertEqual(result["release"], 10)

    def test_copr_success_stops_scheduled_rebuild_without_github_release(self):
        self.assertFalse(planner.plan("1.2.3", [], [], [build("1.2.3", 1)])["needed"])

    def test_reserved_failed_attempt_is_never_reused(self):
        result = planner.plan("1.2.3", [], [{"ref": "refs/tags/v1.2.3-4"}], [build("1.2.3", 5, "failed")])
        self.assertTrue(result["needed"])
        self.assertEqual(result["release"], 6)

    def test_draft_or_prerelease_does_not_mark_stable_version_delivered(self):
        for options in ({"draft": True}, {"prerelease": True}):
            result = planner.plan("1.2.3", [release("1.2.3", 2, **options)], [], [])
            self.assertEqual(result["release"], 3)

    def test_mixed_or_incomplete_assets_do_not_count_as_complete_release(self):
        record = release("1.2.3", 2)
        record["assets"][0]["name"] = "spotify-1.2.3-1.x86_64.rpm"
        self.assertTrue(planner.plan("1.2.3", [record], [], [])["needed"])

    def test_version_prefix_does_not_match_another_version(self):
        result = planner.plan("1.2.3", [release("1.2.30", 50)], [], [])
        self.assertEqual(result["release"], 1)

    def test_legacy_distribution_suffix_is_counted(self):
        result = planner.plan("1.2.3", [], [], [build("1.2.3", "8.el10")], manual=True)
        self.assertEqual(result["release"], 9)
        self.assertEqual(planner.revision_from_rpm("1.2.3", "spotify-1.2.3-12.fc44.x86_64.rpm"), 12)

    def test_unrelated_copr_package_does_not_consume_counter(self):
        self.assertEqual(planner.plan("1.2.3", [], [], [build("1.2.3", 8, name="other")])["release"], 1)


class ReservationTests(unittest.TestCase):
    def test_collision_gets_next_number_without_moving_old_tag(self):
        class API:
            def __init__(self):
                self.calls = []

            def call(self, path, data=None):
                self.calls.append((path, data))
                if data and data["ref"].endswith("-4"):
                    raise HTTPError("https://api.github.com", 422, "exists", {}, io.BytesIO())
                return {}

        api = API()
        self.assertEqual(planner.reserve(api, "1.2.3", 4, "a" * 40), (5, "v1.2.3-5"))
        self.assertEqual([c[0] for c in api.calls], ["/git/refs", "/git/ref/tags/v1.2.3-4", "/git/refs"])
        self.assertEqual(api.calls[-1][1]["sha"], "a" * 40)

    def test_permission_failure_is_not_mistaken_for_a_collision(self):
        class API:
            def call(self, path, data=None):
                raise HTTPError("https://api.github.com", 403, "forbidden", {}, io.BytesIO())

        with self.assertRaises(HTTPError):
            planner.reserve(API(), "1.2.3", 1, "a" * 40)

    def test_secret_errors_do_not_echo_secret_contents(self):
        with self.assertRaises(ValueError) as raised:
            planner.require_copr_config("highly-private-malformed-secret")
        self.assertNotIn("highly-private", str(raised.exception))


class SpecReleaseTests(unittest.TestCase):
    def test_reserved_number_is_used_in_rpm_metadata_and_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "spotify.spec"
            subprocess.run(["bash", str(REPO / "src/generate_spec.sh"), str(output), "1.2.3"],
                           env=dict(os.environ, BUILTIN_FFMPEG="false", SPOTIFY_RELEASE="7"), check=True)
            text = output.read_text()
            self.assertIn("Release:        7%{?dist}", text)
            self.assertIn("1.2.3-7\n", text)

    def test_invalid_release_number_is_rejected(self):
        for number in ("0", "-1", "1.2", "1\nName: injected"):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "spotify.spec"
                result = subprocess.run(["bash", str(REPO / "src/generate_spec.sh"), str(output), "1.2.3"],
                                        env=dict(os.environ, BUILTIN_FFMPEG="false", SPOTIFY_RELEASE=number), capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
