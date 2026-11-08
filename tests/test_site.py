import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build_site.py'
spec = importlib.util.spec_from_file_location('build_site', SCRIPT)
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.a = site.normalize({'id': 'abcdefghijk', 'title': 'Purger un radiateur', 'description': 'Conseils pour le chauffage', 'published': '2026-11-08T09:00:00Z'})
        self.b = site.normalize({'id': 'zyxwvutsrqp', 'title': 'Test outil Parkside #Shorts', 'description': 'Présentation de la visseuse', 'published': '2026-11-09T09:00:00Z', 'duration_seconds': 54})

    def test_normalize(self):
        self.assertEqual(self.a['category'], 'Chauffage')
        self.assertTrue(self.b['short'])
        self.assertEqual(self.b['duration_seconds'], 54)

    def test_merge_and_order(self):
        result = site.merge([self.a], [self.b, self.a])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], self.b['id'])

    def test_security(self):
        self.assertIsNone(site.normalize({'id': '<script>alert(1)</script>', 'title': 'evil'}))
        html = site.detail_page({'id': 'abcdefghijk', 'title': '<script>alert(1)</script>', 'description': '<img src=x onerror=alert(1)>', 'published': '2026-11-08T09:00:00Z', 'category': 'Chauffage', 'short': False, 'thumbnail': self.a['thumbnail'], 'url': self.a['url'], 'duration_seconds': None}, [self.a], '/', '')
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)

    def test_paths(self):
        self.assertEqual(site.path_url('/repo/', 'catalogue/'), '/repo/catalogue/')
        self.assertEqual(site.iso_duration_seconds('PT1H4M9S'), 3849)

    def test_visible_video_reader_and_schema(self):
        page = site.detail_page(self.a, [self.a], '/repo/', 'https://example.org/repo/videos/abcdefghijk/')
        self.assertIn('<iframe src="https://www.youtube-nocookie.com/embed/abcdefghijk?rel=0"', page)
        self.assertNotIn('"contentUrl"', page)
        self.assertIn('max-video-preview:-1', page)

    def test_sitemap_video_entries(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(site, 'OUTPUT', Path(tmp) / 'public'):
                site.build([self.a], 'https://example.org/repo/')
                page = (site.OUTPUT / 'videos' / self.a['id'] / 'index.html').read_text(encoding='utf-8')
                self.assertIn('<iframe ', page)
                root = ET.fromstring((site.OUTPUT / 'sitemap.xml').read_text(encoding='utf-8'))
                ns = {'s':'http://www.sitemaps.org/schemas/sitemap/0.9', 'v':'http://www.google.com/schemas/sitemap-video/1.1'}
                self.assertEqual(len(root.findall('s:url', ns)), 3 + len(site.TOPICS))
                self.assertEqual(len(root.findall('.//v:video', ns)), 1)

    def test_v3_titles_points_and_chapters(self):
        video = dict(self.a, title='les différents types de foret #shorts #bricolage',
                     description='Titre :\n\nQuel foret choisir pour le bois, le métal ou le béton ?\n\n✅ Bois : présentation du foret bois\n✅ Métal : présentation du foret métal\n\n00:00 Introduction\n01:15 Démonstration')
        self.assertEqual(site.seo_title(video), 'Quel foret choisir pour le bois, le métal ou le béton ?')
        self.assertEqual(len(site.documented_points(video['description'])), 2)
        self.assertEqual(len(site.chapters(video['description'], video['id'])), 2)
        page = site.detail_page(video, [video, self.b], '/repo/', 'https://example.org/repo/videos/abcdefghijk/')
        self.assertIn('Chapitres indiqués par la chaîne', page)
        self.assertIn('Dans ce tutoriel', page)
        self.assertIn('sujets/chauffage/', page)

    def test_v3_topic_page_and_internal_links(self):
        from unittest import mock
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(site, 'OUTPUT', Path(d) / 'publish'):
                site.build([self.a, self.b], 'https://example.org/repo/')
                path = site.OUTPUT / 'sujets' / 'chauffage' / 'index.html'
                self.assertTrue(path.exists())
                self.assertIn('Purger un radiateur', path.read_text(encoding='utf-8'))
                data = json.loads((site.OUTPUT / 'data' / 'videos.json').read_text(encoding='utf-8'))
                self.assertIn('seo_title', data[0])
                self.assertIn('seo_summary', data[0])

    def test_v3_indexnow_tracks_only_changed_videos(self):
        import importlib.util
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'indexnow.py'
        spec = importlib.util.spec_from_file_location('indexnow', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        example = [self.a, self.b]
        current = module.snapshot(example)
        self.assertEqual(len(current), 2)
        self.assertEqual(module.changed_urls('https://example.org/site/',example,current,current), [])
        urls = module.changed_urls('https://example.org/site/',example,{},current)
        self.assertIn('https://example.org/site/videos/abcdefghijk/', urls)
        self.assertIn('https://example.org/site/sujets/chauffage/', urls)
        self.assertIn('https://example.org/site/', urls)

    def test_optional_analytics_snippet_only_with_token(self):
        from unittest import mock
        with mock.patch.dict('os.environ', {'CF_WEB_ANALYTICS_TOKEN':'0123456789abcdef0123456789abcdef'}):
            page = site.layout('Titre','Description','<p>Texte</p>','/site/')
            self.assertIn('static.cloudflareinsights.com/beacon.min.js', page)
        with mock.patch.dict('os.environ', {'CF_WEB_ANALYTICS_TOKEN':'not-a-token'}):
            page = site.layout('Titre','Description','<p>Texte</p>','/site/')
            self.assertNotIn('static.cloudflareinsights.com/beacon.min.js', page)

    def test_video_schema(self):
        page = site.detail_page(self.a, [self.a, self.b], '/repo/', 'https://example.org/repo/videos/abcdefghijk/')
        self.assertIn('VideoObject', page)
        self.assertIn('https://example.org/repo/videos/abcdefghijk/', page)
        self.assertIn('/repo/assets/style.css', page)


    def test_v4_search_questions_tags_guide_and_sitemap(self):
        from unittest import mock
        import tempfile
        video = site.normalize({
            'id': '-rfWTS3UIzE',
            'title': 'Tuto Faire son Installation de Plomberie en Multicouche',
            'description': "Présentation de la conception du réseau sanitaire, des nourrices et du réducteur de pression.\n#Plomberie #Multicouche #Bricolage",
            'published': '2025-12-31T06:00:01Z'
        })
        page = site.detail_page(video, [video], '/repo/', 'https://example.org/repo/videos/-rfWTS3UIzE/')
        self.assertIn('Comment refaire la plomberie', page)
        self.assertIn('Questions sur ce tutoriel', page)
        self.assertIn('#Plomberie', page)
        self.assertIn('guides/plomberie-multicouche/', page)
        self.assertIn('keywords', page)
        self.assertEqual(site.video_hashtags(video), ['#Plomberie', '#Multicouche', '#Bricolage'])
        self.assertEqual(site.search_questions(self.a), [])
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(site, 'OUTPUT', Path(tmp) / 'publication'):
                site.build([video, self.a], 'https://example.org/repo/')
                self.assertTrue((site.OUTPUT / 'guides' / 'plomberie-multicouche' / 'index.html').exists())
                sitemap = (site.OUTPUT / 'sitemap.xml').read_text(encoding='utf-8')
                self.assertIn('/guides/plomberie-multicouche/', sitemap)
                import xml.etree.ElementTree as ET
                ET.fromstring(sitemap)
                plumber_page = (site.OUTPUT / 'sujets' / 'plomberie' / 'index.html').read_text(encoding='utf-8')
                self.assertIn('guides/plomberie-multicouche/', plumber_page)


if __name__ == '__main__':
    unittest.main()
