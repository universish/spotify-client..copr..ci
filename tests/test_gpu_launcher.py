import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]


class GPULauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.capture = self.root / "capture"
        self.capture.mkdir()
        self.sysfs = self.root / "sys"
        for script in ("generate_bin.sh", "generate_generate_flags_file.sh", "generate_generate_envs_file.sh"):
            subprocess.run(["bash", str(REPO / "src" / script), str(self.data), "false"], check=True)
        self.launcher = self.root / "spotify"
        (self.data / "spotify").rename(self.launcher)
        shutil.copy(REPO / "src/spotify-gpu.sh", self.data / "spotify-gpu.sh")
        native = self.data / "spotify"
        native.write_text('''#!/bin/bash
count=0
[[ ! -f "$CAPTURE/count" ]] || read -r count < "$CAPTURE/count"
count=$((count+1))
echo "$count" > "$CAPTURE/count"
echo "$$" > "$CAPTURE/pid"
printf '%s\\0' "$@" > "$CAPTURE/args-$count"
printf '%s|%s' "${__NV_PRIME_RENDER_OFFLOAD-unset}" "${__GLX_VENDOR_LIBRARY_NAME-unset}" > "$CAPTURE/env-$count"
case ${FAKE_FAILURE:-none} in
  always) echo 'Requested GL implementation not found' >&2; exit 1 ;;
  gpu) if [[ " $* " != *' --disable-gpu '* ]]; then echo 'ERR Display.cpp:1128 EGL_NOT_INITIALIZED' >&2; exit 1; fi ;;
  desktop) if [[ " $* " == *' --use-gl=desktop '* ]]; then echo 'Requested GL implementation not found' >&2; exit 1; fi ;;
  warning) echo 'ERR Display.cpp:1128' >&2 ;;
  sleep) exec sleep 30 ;;
esac
exit "${FAKE_EXIT_STATUS:-0}"
''')
        native.chmod(0o755)
        probe = self.bin / "glxinfo"
        probe.write_text('#!/bin/bash\nprintf "%s\\n" "${GLX_RENDERER:-}"\n')
        probe.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        SPOTIFY_DATA_DIR=str(self.data), SPOTIFY_SYSFS_ROOT=str(self.sysfs),
                        XDG_CONFIG_HOME=str(self.root / "config"), XDG_SESSION_TYPE="x11", DISPLAY=":test",
                        CAPTURE=str(self.capture), SPOTIFY_DEBUG="0")
        for key in ("__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME", "SPOTIFY_GPU_MODE", "GLX_RENDERER", "WAYLAND_DISPLAY"):
            self.env.pop(key, None)

    def gpu(self, index, vendor, driver, version=None):
        folder = self.sysfs / f"class/drm/card{index}/device"
        folder.mkdir(parents=True)
        (folder / "vendor").write_text(vendor + "\n")
        (folder / "driver").symlink_to(self.sysfs / "drivers" / driver)
        if version:
            module = self.sysfs / "module/nvidia"
            module.mkdir(parents=True, exist_ok=True)
            (module / "version").write_text(version + "\n")

    def run_launcher(self, *args):
        return subprocess.run([str(self.launcher), *args], env=self.env, capture_output=True, text=True, timeout=10)

    def args(self, attempt=1):
        return (self.capture / f"args-{attempt}").read_bytes().split(b"\0")[:-1]

    def test_intel_mesa_never_injects_nvidia_environment(self):
        self.gpu(0, "0x8086", "i915")
        result = self.run_launcher("spotify:track:example")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / "env-1").read_text(), "unset|unset")
        self.assertIn(b"--use-angle=gl", self.args())
        self.assertNotIn(b"--ignore-gpu-blocklist", self.args())
        self.assertEqual(self.args()[-1], b"spotify:track:example")

    def test_amd_wayland_preserves_native_display_selection(self):
        self.gpu(0, "0x1002", "amdgpu")
        self.env["XDG_SESSION_TYPE"] = "wayland"
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertFalse(any(arg.startswith(b"--ozone-platform=") for arg in self.args()))
        self.assertEqual((self.capture / "env-1").read_text(), "unset|unset")

    def test_hybrid_nvidia_x11_gets_prime_and_desktop_gl(self):
        self.gpu(0, "0x8086", "xe")
        self.gpu(1, "0x10de", "nvidia", "570.86.16")
        result = self.run_launcher("--debug")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / "env-1").read_text(), "1|nvidia")
        self.assertIn(b"--use-gl=desktop", self.args())
        self.assertIn(b"--ignore-gpu-blocklist", self.args())
        self.assertIn("hybrid=1", result.stderr)

    def test_nvidia_wayland_uses_working_lpf_desktop_gl_and_prime(self):
        self.gpu(0, "0x1002", "amdgpu")
        self.gpu(1, "0x10de", "nvidia", "570.86.16")
        self.env["XDG_SESSION_TYPE"] = "wayland"
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertIn(b"--use-gl=desktop", self.args())
        self.assertFalse(any(arg.startswith(b"--ozone-platform=") for arg in self.args()))
        self.assertEqual((self.capture / "env-1").read_text(), "1|nvidia")

    def test_nouveau_is_mesa_not_proprietary_nvidia(self):
        self.gpu(0, "0x10de", "nouveau")
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertNotIn(b"--ignore-gpu-blocklist", self.args())
        self.assertEqual((self.capture / "env-1").read_text(), "unset|unset")

    def test_legacy_hybrid_driver_does_not_get_unsupported_prime(self):
        self.gpu(0, "0x8086", "i915")
        self.gpu(1, "0x10de", "nvidia", "390.157")
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertEqual((self.capture / "env-1").read_text(), "unset|unset")

    def test_unsupported_desktop_gl_retries_with_angle(self):
        self.gpu(0, "0x10de", "nvidia", "570.86.16")
        self.env["FAKE_FAILURE"] = "desktop"
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / "count").read_text().strip(), "2")
        self.assertIn(b"--use-angle=gl", self.args(2))

    def test_repeated_gpu_failure_falls_back_once_to_software(self):
        self.gpu(0, "0x8086", "i915")
        self.gpu(1, "0x10de", "nvidia", "570.86.16")
        self.env["FAKE_FAILURE"] = "gpu"
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / "count").read_text().strip(), "3")
        self.assertIn(b"--disable-gpu", self.args(3))
        self.assertEqual((self.capture / "env-3").read_text(), "unset|unset")

    def test_warning_with_success_does_not_restart(self):
        self.env["FAKE_FAILURE"] = "warning"
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertEqual((self.capture / "count").read_text().strip(), "1")

    def test_safe_mode_clears_inherited_prime_and_preserves_uri(self):
        self.env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
        self.env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        self.assertEqual(self.run_launcher("--safe-mode", "spotify:album:example").returncode, 0)
        self.assertIn(b"--disable-gpu", self.args())
        self.assertIn(b"spotify:album:example", self.args())
        self.assertEqual((self.capture / "env-1").read_text(), "unset|unset")

    def test_unrelated_exit_code_is_preserved_without_retry(self):
        self.env["FAKE_EXIT_STATUS"] = "37"
        self.assertEqual(self.run_launcher().returncode, 37)
        self.assertEqual((self.capture / "count").read_text().strip(), "1")

    def test_safe_mode_removes_persistent_conflicting_gpu_flags(self):
        folder = Path(self.env["XDG_CONFIG_HOME"]) / "spotify"
        folder.mkdir(parents=True)
        (folder / "spotify-flags.conf").write_text("--use-gl=desktop\n--use-angle=vulkan\n--enable-zero-copy\n")
        self.assertEqual(self.run_launcher("--safe-mode", "spotify:album:example").returncode, 0)
        self.assertNotIn(b"--use-gl=desktop", self.args())
        self.assertNotIn(b"--use-angle=vulkan", self.args())
        self.assertIn(b"--disable-gpu", self.args())

    def test_user_gpu_flags_are_preserved_without_automatic_retry(self):
        self.gpu(0, "0x10de", "nvidia", "570.86.16")
        self.env["FAKE_FAILURE"] = "gpu"
        result = self.run_launcher("--use-gl=egl")
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.capture / "count").read_text().strip(), "1")
        self.assertEqual(self.args(), [b"--use-gl=egl"])

    def test_explicit_prime_disable_is_respected(self):
        self.gpu(0, "0x8086", "i915")
        self.gpu(1, "0x10de", "nvidia", "570.86.16")
        self.env["__NV_PRIME_RENDER_OFFLOAD"] = "0"
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertEqual((self.capture / "env-1").read_text(), "0|unset")

    def test_software_failure_is_not_retried_forever(self):
        self.gpu(0, "0x10de", "nvidia", "570.86.16")
        self.env["FAKE_FAILURE"] = "always"
        self.assertEqual(self.run_launcher().returncode, 1)
        self.assertEqual((self.capture / "count").read_text().strip(), "3")

    def test_gpu_mode_in_user_config_and_cli_precedence(self):
        folder = Path(self.env["XDG_CONFIG_HOME"]) / "spotify"
        folder.mkdir(parents=True)
        (folder / "spotify.env").write_text("SPOTIFY_GPU_MODE=software\n")
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertIn(b"--disable-gpu", self.args())
        self.assertEqual(self.run_launcher("--gpu-mode=native").returncode, 0)
        self.assertNotIn(b"--disable-gpu", self.args(2))

    def test_sigterm_is_forwarded_without_retry(self):
        self.env["FAKE_FAILURE"] = "sleep"
        process = subprocess.Popen([str(self.launcher)], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.capture / "pid").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.capture / "pid").exists())
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 143)
            self.assertEqual((self.capture / "count").read_text().strip(), "1")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
