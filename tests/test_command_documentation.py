from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CommandDocumentationTests(unittest.TestCase):
    def test_copr_addendum_contains_only_the_appendable_usage_section(self):
        text=(ROOT/'docs/copr-command-addendum.md').read_text()
        for heading in ('## Launch Spotify','## Command help','## Available client versions','## Common commands'):
            self.assertIn(heading,text)
        for command in ('spotify','spot-fly-light --help','spot-fly-light -h','spot..fly..light --help',
                        'spot..fly..light -h','spot..fly..light --client-versions','spot..fly..light -cl.ver'):
            self.assertIn(command,text)
        self.assertNotIn('dnf copr enable',text)
        self.assertNotIn('## Sources, licensing',text)
        self.assertIn('without `sudo`',text)
        self.assertIn('pinned catalog',text)

    def test_readme_and_copr_draft_share_the_exact_usage_addendum(self):
        text=(ROOT/'docs/copr-command-addendum.md').read_text()
        for filename in ('README.md','docs/copr-description.md'):
            self.assertIn(text,(ROOT/filename).read_text())

    def test_documented_options_exist_in_the_actual_help_interface(self):
        run=subprocess.run([sys.executable,str(ROOT/'bootstrap/spot..fly..light.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        for option in ('--setup','--update','-unstable','--debug','--safe-mode','--status','--install',
                       '--rebuild','--gpu-mode','--client-versions','-cl.ver','--help','-h'):
            self.assertIn(option,run.stdout)
            self.assertIn(option,(ROOT/'docs/copr-command-addendum.md').read_text())


if __name__=='__main__':unittest.main()
