import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('onboarding', REPO / 'bootstrap/onboarding.py')
onboarding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboarding)


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = {'Bootstrap': {'Version': '26.10.31', 'Release': 1},
                     'stable': {'RPMVersion': '1.2.3'}, 'unstable': {'RPMVersion': '2.3.4'}}
        (self.root / 'source.json').write_text(json.dumps(self.data))
        self.patches = [mock.patch.object(onboarding, 'HERE', self.root),
                        mock.patch.object(onboarding.os, 'geteuid', return_value=1000),
                        mock.patch.dict(os.environ, {'DISPLAY': ':1', 'XDG_STATE_HOME': str(self.root / 'state')}, clear=True),
                        mock.patch.object(onboarding.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name)]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def marker(self):
        return json.loads((onboarding.state_directory() / 'onboarding.json').read_text())

    def test_channel_choice_opens_matching_terminal_and_displays_both_versions(self):
        for channel, expected in [('stable', [onboarding.CLIENT, '--setup']),
                                  ('unstable', [onboarding.CLIENT, '--setup', '-unstable'])]:
            marker = onboarding.state_directory() / 'onboarding.json'
            marker.unlink(missing_ok=True)
            result = subprocess.CompletedProcess([], 0, channel + '\n')
            with mock.patch.object(onboarding.subprocess, 'run', return_value=result) as dialog, \
                 mock.patch.object(onboarding, 'open_terminal') as terminal:
                self.assertEqual(onboarding.offer(), 0)
            terminal.assert_called_once_with(channel)
            self.assertIn('1.2.3', dialog.call_args.args[0])
            self.assertIn('2.3.4', dialog.call_args.args[0])
            self.assertEqual(onboarding.setup_arguments(channel), expected)
            self.assertEqual(self.marker(), {'Bootstrap': '26.10.31-1', 'Selection': channel})

    def test_cancel_never_launches_and_dismisses_only_this_bootstrap_release(self):
        result = subprocess.CompletedProcess([], 1, '')
        with mock.patch.object(onboarding.subprocess, 'run', return_value=result) as dialog, \
             mock.patch.object(onboarding, 'open_terminal') as terminal:
            onboarding.offer()
            onboarding.offer()
            self.assertEqual(dialog.call_count, 1)
            self.assertEqual(self.marker()['Selection'], 'dismissed')
            self.data['Bootstrap']['Release'] = 2
            (self.root / 'source.json').write_text(json.dumps(self.data))
            onboarding.offer()
            self.assertEqual(dialog.call_count, 2)
        terminal.assert_not_called()
        self.assertFalse((onboarding.state_directory() / 'consent.json').exists())

    def test_root_and_headless_do_not_show_ui_or_create_state(self):
        with mock.patch.object(onboarding.subprocess, 'run') as dialog:
            with mock.patch.object(onboarding.os, 'geteuid', return_value=0):
                self.assertEqual(onboarding.main([]), 0)
                self.assertEqual(onboarding.main(['--run-setup', 'stable']), 0)
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(onboarding.offer(), 0)
        dialog.assert_not_called()
        self.assertFalse((self.root / 'state').exists())

    def test_dialog_failure_is_deferred_without_marking_dismissed(self):
        with mock.patch.object(onboarding.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2, '')):
            onboarding.offer()
        self.assertFalse((onboarding.state_directory() / 'onboarding.json').exists())

    def test_non_object_marker_does_not_prevent_prompt(self):
        directory = onboarding.state_directory()
        directory.mkdir(parents=True)
        for value in ('null', '[]'):
            (directory / 'onboarding.json').write_text(value)
            with mock.patch.object(onboarding.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '')) as dialog:
                self.assertEqual(onboarding.offer(), 0)
            dialog.assert_called_once()
            self.assertEqual(self.marker()['Selection'], 'dismissed')

    def test_invalid_dialog_output_cannot_become_shell_command(self):
        with mock.patch.object(onboarding.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'stable; touch /tmp/pwn')), \
             mock.patch.object(onboarding, 'open_terminal') as terminal:
            with self.assertRaises(ValueError):
                onboarding.offer()
        terminal.assert_not_called()

    def test_terminal_launch_uses_separate_argv_and_retries_failed_emulator(self):
        failed, successful = mock.Mock(), mock.Mock()
        failed.wait.return_value = 2
        successful.wait.side_effect = subprocess.TimeoutExpired('terminal', 2)
        with mock.patch.object(onboarding.subprocess, 'Popen', side_effect=[failed, successful]) as popen:
            self.assertIs(onboarding.open_terminal('unstable'), successful)
        argv = popen.call_args.args[0]
        self.assertEqual(argv[-3:], [str(self.root / 'onboarding.py'), '--run-setup', 'unstable'])
        self.assertNotIn('shell', popen.call_args.kwargs)
        self.assertNotIn('-c', argv)

    def test_terminal_failure_does_not_mark_selected_or_accept_terms(self):
        with mock.patch.object(onboarding.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'stable')), \
             mock.patch.object(onboarding, 'open_terminal', side_effect=RuntimeError('No terminal')):
            self.assertEqual(onboarding.offer(), 1)
        self.assertFalse((onboarding.state_directory() / 'onboarding.json').exists())

    def test_terminal_setup_runs_exact_command_and_keeps_output_visible(self):
        with mock.patch.object(onboarding.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)) as run, \
             mock.patch('builtins.input') as pause:
            self.assertEqual(onboarding.run_setup('unstable'), 7)
        run.assert_called_once_with([onboarding.CLIENT, '--setup', '-unstable'], check=False)
        pause.assert_called_once()


if __name__ == '__main__':
    unittest.main()
