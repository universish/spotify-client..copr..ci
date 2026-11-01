import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fontconfig_runtime', ROOT / 'src/fontconfig_runtime.py')
fonts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fonts)
RECORD = {'SHA256': 'a' * 64, 'Channel': 'stable'}
PROFILE = {'Name': 'spot-fly-light'}


class FontconfigIsolationTests(unittest.TestCase):
    def configuration(self, folder):
        home, config = folder / 'home', folder / 'etc/fonts'
        home.mkdir(); (config / 'conf.d').mkdir(parents=True)
        (config / 'fonts').mkdir()
        (home / '.config/fontconfig').mkdir(parents=True)
        (home / '.config/fontconfig/fonts.conf').write_text('<fontconfig><dir>~/.fonts</dir><cachedir>~/.fontconfig</cachedir><alias><family>sans-serif</family><prefer><family>Noto Sans</family></prefer></alias></fontconfig>')
        (config / 'conf.d/50-user.conf').write_text('<fontconfig><include prefix="xdg">fontconfig/fonts.conf</include><cachedir>/shared/cache</cachedir></fontconfig>')
        (config / 'fonts.conf').write_text('<fontconfig><dir prefix="relative">fonts</dir><include>conf.d</include><cachedir prefix="xdg">fontconfig</cachedir></fontconfig>')
        return config / 'fonts.conf', {'HOME': str(home), 'FONTCONFIG_PATH': str(config), 'XDG_CACHE_HOME': str(home / '.cache')}

    def test_recursive_includes_preserve_fonts_and_aliases_but_replace_every_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source, env = self.configuration(root)
            child, info = fonts.prepare_fontconfig(env, RECORD, PROFILE, source_config=source)
            trees = [ET.parse(p) for p in Path(child['FONTCONFIG_PATH']).glob('*.conf')]
            cachedirs = [node.text for tree in trees for node in tree.iter('cachedir')]
            self.assertEqual(cachedirs, [info['Cache']])
            self.assertTrue(all(Path(n.text).is_file() for tree in trees for n in tree.iter('include')))
            self.assertIn(str(source.parent / 'fonts'), [n.text for tree in trees for n in tree.iter('dir')])
            self.assertIn(str(root / 'home/.fonts'), [n.text for tree in trees for n in tree.iter('dir')])
            self.assertIn('Noto Sans', [n.text for tree in trees for n in tree.iter('family')])
            self.assertNotIn('FONTCONFIG_FILE', env)
            self.assertEqual(child['XDG_CACHE_HOME'], env['XDG_CACHE_HOME'])

    def test_real_cache_headers_and_wrong_symlinks_in_shared_directory_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            shared=Path(env['XDG_CACHE_HOME'])/'fontconfig';shared.mkdir(parents=True)
            newer=shared/'example-le64.cache-12';newer.write_bytes(struct.pack('<II',0xfc02fc04,12)+b'newer')
            old=shared/'example-le64.cache-11';old.symlink_to(newer.name)
            genuine=shared/'genuine-le64.cache-11';genuine.write_bytes(struct.pack('<II',0xfc02fc04,11)+b'older')
            before={p.name:(p.is_symlink(),os.readlink(p) if p.is_symlink() else p.read_bytes()) for p in shared.iterdir()}
            child,info=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            after={p.name:(p.is_symlink(),os.readlink(p) if p.is_symlink() else p.read_bytes()) for p in shared.iterdir()}
            self.assertEqual(before,after)
            self.assertNotEqual(Path(info['Cache']),shared)
            self.assertEqual(list(Path(info['Cache']).iterdir()),[])
            self.assertNotIn(str(shared),Path(child['FONTCONFIG_FILE']).read_text())

    def test_repeat_launch_reuses_snapshot_and_changed_rules_or_source_get_new_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,env=self.configuration(Path(tmp))
            one,first=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            initial=Path(one['FONTCONFIG_FILE']).stat().st_mtime_ns
            two,again=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            self.assertEqual(first,again)
            self.assertEqual(Path(two['FONTCONFIG_FILE']).stat().st_mtime_ns,initial)
            source.write_text(source.read_text().replace('</fontconfig>','<alias><family>changed</family></alias></fontconfig>'))
            _,changed=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            self.assertNotEqual(changed['Identity'],first['Identity'])
            _,different=fonts.prepare_fontconfig(env,dict(RECORD,SHA256='b'*64),PROFILE,source_config=source)
            self.assertNotEqual(different['Identity'],changed['Identity'])

    def test_xml_special_characters_in_cache_path_and_environment_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            env['FONTCONFIG_NO_CHECK_CACHE_VERSION']='1'
            child,info=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source,cache_root=root/'cache & fonts')
            self.assertNotIn('FONTCONFIG_NO_CHECK_CACHE_VERSION',child)
            for path in Path(child['FONTCONFIG_PATH']).glob('*.conf'): ET.parse(path)

    def test_reuse_quarantines_only_mislabelled_private_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            _,info=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            cache=Path(info['Cache'])
            valid=cache/'font-le64.cache-12';valid.write_bytes(struct.pack('<II',0xfc02fc04,12)+b'format12')
            invalid=cache/'font-le64.cache-11';invalid.symlink_to(valid.name)
            _,again=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            self.assertEqual(again['RejectedCacheEntries'],['font-le64.cache-11'])
            self.assertFalse(invalid.is_symlink())
            self.assertEqual(valid.read_bytes(),struct.pack('<II',0xfc02fc04,12)+b'format12')
            self.assertEqual(len(list((cache.parent/'rejected-cache').iterdir())),1)

    def test_host_configuration_can_be_parsed_without_font_tools_or_cache_writes(self):
        source=Path('/etc/fonts/fonts.conf')
        if not source.is_file(): self.skipTest('Fontconfig configuration is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            child,info=fonts.prepare_fontconfig(dict(os.environ),RECORD,PROFILE,source_config=source,cache_root=Path(tmp)/'fonts')
            self.assertTrue(Path(child['FONTCONFIG_FILE']).is_file())
            self.assertGreater(info['SourceFiles'],1)
            self.assertEqual(list(Path(info['Cache']).iterdir()),[])

    def test_private_cache_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            (root/'outside').mkdir();(root/'cache').symlink_to(root/'outside',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symbolic link'):
                fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source,cache_root=root/'cache')

    def test_symlink_aliases_of_one_rule_keep_native_realpath_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            rule=root/'shared-rule.conf'
            rule.write_text('<fontconfig><match target="font"><edit name="pixelsize" mode="assign"><times><name>pixelsize</name><double>2</double></times></edit></match></fontconfig>')
            (source.parent/'conf.d/10-first.conf').symlink_to(rule)
            (source.parent/'conf.d/20-second.conf').symlink_to(rule)
            child,_=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            files=list(Path(child['FONTCONFIG_PATH']).glob('*.conf'))
            shared=[p for p in files if '<times>' in p.read_text()]
            self.assertEqual(len(shared),1)
            main=ET.parse(child['FONTCONFIG_FILE'])
            links=[n.text for n in main.iter('include')]
            self.assertEqual(links.count(str(shared[0])),2)

    def test_default_include_search_does_not_use_custom_main_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            search=root/'search';search.mkdir()
            (search/'chosen.conf').write_text('<fontconfig><alias><family>correct search path</family></alias></fontconfig>')
            (source.parent/'chosen.conf').write_text('<fontconfig><alias><family>incorrect sibling</family></alias></fontconfig>')
            source.write_text('<fontconfig><include>chosen.conf</include></fontconfig>')
            env['FONTCONFIG_PATH']=str(search)
            child,_=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            text=''.join(p.read_text() for p in Path(child['FONTCONFIG_PATH']).glob('*.conf'))
            self.assertIn('correct search path',text)
            self.assertNotIn('incorrect sibling',text)
            self.assertNotIn(source.parent,fonts.Configuration({},source).search)

    def test_optional_include_directory_skips_broken_member_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,env=self.configuration(root)
            source.write_text('<fontconfig><include ignore_missing="yes">conf.d</include></fontconfig>')
            missing=source.parent/'conf.d/10-removed.conf'
            missing.symlink_to(root/'removed-font-package.conf')
            child,info=fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)
            self.assertTrue(Path(child['FONTCONFIG_FILE']).is_file())
            identity=json.loads((Path(info['Cache']).parent/'source.json').read_text())
            self.assertIn('missing:'+str(missing),identity['configuration'])
            source.write_text('<fontconfig><include>conf.d</include></fontconfig>')
            with self.assertRaises(FileNotFoundError):
                fonts.prepare_fontconfig(env,RECORD,PROFILE,source_config=source)

    def test_native_font_matching_writes_real_private_caches_and_finds_turkish_fonts(self):
        executable=shutil.which('fc-match-64') or shutil.which('fc-match')
        if not executable or not Path('/etc/fonts/fonts.conf').is_file():
            self.skipTest('Native Fontconfig/font configuration is unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            child,info=fonts.prepare_fontconfig(dict(os.environ),RECORD,PROFILE,cache_root=Path(tmp)/'fonts')
            first=subprocess.run([executable,'-f','%{family}|%{file}\\n','sans-serif:lang=tr'],env=child,text=True,capture_output=True,timeout=30)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertIn('|',first.stdout)
            self.assertNotIn('We will not regenerate',first.stderr)
            files=list(Path(info['Cache']).glob('*.cache-*'))
            self.assertTrue(files,'The real Fontconfig backend must create a private cache')
            for path in files:
                if path.is_symlink():self.fail('A genuine cache must not be a format-alias symlink')
                magic,version=struct.unpack('<II',path.read_bytes()[:8])
                self.assertEqual(magic,0xfc02fc04)
                self.assertEqual(version,int(path.name.rsplit('cache-',1)[1]))
            before={path.name:path.stat().st_mtime_ns for path in files}
            again=subprocess.run([executable,'-f','%{family}|%{file}\\n','sans-serif:lang=tr'],env=child,text=True,capture_output=True,timeout=30)
            self.assertEqual(again.stdout,first.stdout)
            self.assertNotIn('We will not regenerate',again.stderr)
            self.assertEqual({path.name:path.stat().st_mtime_ns for path in files},before)

    def test_turkish_and_cjk_rendering_uses_the_private_configuration(self):
        viewer=shutil.which('pango-view');matcher=shutil.which('fc-match-64') or shutil.which('fc-match')
        if not viewer or not matcher or not Path('/etc/fonts/fonts.conf').is_file():
            self.skipTest('Pango/Fontconfig rendering tools are unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            child,info=fonts.prepare_fontconfig(dict(os.environ),RECORD,PROFILE,cache_root=root/'fonts')
            family=subprocess.run([matcher,'-f','%{family}','Noto Sans CJK KR'],env=child,capture_output=True,text=True,timeout=30)
            if 'CJK' not in family.stdout:self.skipTest('Noto CJK fonts are unavailable')
            output=root/'text.png'
            result=subprocess.run([viewer,'--no-display','--font=Noto Sans CJK KR 20',
                '--text=Türkçe: İstanbul ığüşöç İĞÜŞÖÇ\n한국어: 음악 재생\n中文: 音乐播放\n日本語: 音楽再生',
                '--output='+str(output)],env=child,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('Fontconfig warning',result.stderr)
            self.assertTrue(output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertGreater(output.stat().st_size,1000)


if __name__ == '__main__': unittest.main()
