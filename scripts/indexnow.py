#!/usr/bin/env python3
"""IndexNow: announce only genuinely updated video URLs, after successful publication.

IndexNow is not an indexing guarantee. On shared GitHub Pages hosts, acceptance
depends on successful ownership validation of the key under the site subpath.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / 'data' / 'catalogue.json'
STATE = ROOT / 'data' / 'indexnow-state.json'
KEY = 'a0e21430e607e359e7b289360c1db2be'
VERSION = 'seo-v4-1'


def url_for_site() -> str:
    explicit = os.environ.get('SITE_URL', '').strip()
    if explicit:
        parsed = urllib.parse.urlparse(explicit)
        if parsed.scheme != 'https' or not parsed.hostname:
            raise ValueError('SITE_URL doit être une URL HTTPS valide.')
        return explicit.rstrip('/') + '/'
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if '/' not in repo:
        return ''
    owner, name = repo.split('/', 1)
    if not owner or not name:
        return ''
    return f'https://{owner}.github.io/{name}/'


def snapshot(catalog: list[dict]) -> dict[str,str]:
    result={}
    for item in catalog:
        video_id = str(item.get('id', ''))
        if len(video_id) != 11:
            continue
        stable = {k:item.get(k) for k in ('id', 'title', 'description', 'published', 'duration_seconds', 'category', 'short')}
        encoded = json.dumps([VERSION, stable], ensure_ascii=False, sort_keys=True).encode('utf-8')
        result[video_id]=hashlib.sha256(encoded).hexdigest()
    return result


def changed_urls(base: str, catalog: list[dict], previous: dict[str,str], current: dict[str,str]) -> list[str]:
    changed = [v for v in catalog if v.get('id') in current and previous.get(v['id']) != current[v['id']]]
    if not changed:
        return []
    topics = sorted({v.get('category') for v in changed if v.get('category')})
    from seo_content import topic_slug
    urls = [base, base+'catalogue/']
    urls += [base+'sujets/'+topic_slug(category)+'/' for category in topics]
    urls += [base+'videos/'+v['id']+'/' for v in changed]
    if any(v.get('category') == 'Plomberie' for v in changed):
        urls.append(base+'guides/plomberie-multicouche/')
    return list(dict.fromkeys(urls))


def submit_indexnow(base: str, urls: list[str]) -> int:
    key_url = base + KEY + '.txt'
    payload = {
        'host': urllib.parse.urlparse(base).netloc,
        'key': KEY,
        'keyLocation': key_url,
        'urlList': urls[:10000],
    }
    req = urllib.request.Request(
        'https://api.indexnow.org/indexnow',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8','User-Agent':'LaChaineDuBricolageSite/3.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req,timeout=24) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        details = exc.read(350).decode('utf-8',errors='replace')
        raise RuntimeError(f'IndexNow HTTP {exc.code} : {details}') from exc


def main() -> int:
    base = url_for_site()
    if not base:
        print('IndexNow non exécuté hors GitHub Pages : SITE_URL ou GITHUB_REPOSITORY manquant.')
        return 0
    if not ARCHIVE.exists():
        print('Catalogue non disponible pour IndexNow.')
        return 0
    catalog = json.loads(ARCHIVE.read_text(encoding='utf-8'))
    try:
        previous = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    except (ValueError, OSError):
        previous = {}
    now = snapshot(catalog)
    changed = changed_urls(base,catalog,previous,now)
    if not changed:
        print('IndexNow : aucune page modifiée, aucun envoi inutile.')
        return 0
    try:
        status = submit_indexnow(base,changed)
        if status not in (200,202):
            raise RuntimeError(f'Code inattendu IndexNow : {status}')
    except Exception as exc:
        # Site deployment must never be blocked by third-party indexing services.
        print(f'::warning title=IndexNow temporairement indisponible::{exc}',file=sys.stderr)
        print('Les URL restent accessibles dans le sitemap vidéo, nouvel essai à la prochaine synchronisation.')
        return 0
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(now,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'IndexNow : {len(changed)} URL nouvelles ou modifiées déclarées (HTTP {status}).')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as out:
            out.write(f'\n### IndexNow\n- {len(changed)} URL nouvelles ou modifiées signalées (HTTP {status}).\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
