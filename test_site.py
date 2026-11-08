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

    def test_video_schema(self):
        page = site.detail_page(self.a, [self.a, self.b], '/repo/', 'https://example.org/repo/videos/abcdefghijk/')
        self.assertIn('VideoObject', page)
        self.assertIn('https://example.org/repo/videos/abcdefghijk/', page)
        self.assertIn('/repo/assets/style.css', page)


if __name__ == '__main__':
    unittest.main()
