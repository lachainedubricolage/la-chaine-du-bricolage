#!/usr/bin/env python3
"""Site statique YouTube pour La chaîne du bricolage. Bibliothèque standard uniquement.

Synchronisation : flux public YouTube (15 entrées récentes), avec import complet
optionnel par YouTube Data API v3 si YOUTUBE_API_KEY est défini.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seo_content import TOPICS, topic_slug, seo_title, seo_summary, documented_points, chapters, video_reference, related_videos

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'site'
ARCHIVE = ROOT / 'data' / 'catalogue.json'
CHANNEL_ID = 'UCyatFL7-rszo54ExBQ7lhRg'
CHANNEL_URL = 'https://www.youtube.com/@Lachainedubricolage'
FEED_URL = f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}'
CHANNEL_NAME = 'La chaîne du bricolage'
CONTACT_EMAIL = 'Contact.lachainedubricolage@gmail.com'
USER_AGENT = 'LaChaineDuBricolageWebsite/1.0 (public YouTube metadata; GitHub Actions)'


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/xml,application/json,*/*'})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=18) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    safe_endpoint = urllib.parse.urlparse(url)
    raise RuntimeError(f'Échec de récupération : {safe_endpoint.scheme}://{safe_endpoint.netloc}{safe_endpoint.path} : {last_error}')


def shorten(text: str, n=185) -> str:
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text if len(text) <= n else text[:n - 1].rsplit(' ', 1)[0] + '…'


def category(title: str, description: str = '') -> str:
    text = (title + ' ' + description[:180]).lower()
    # Donner la priorité aux tutoriels techniques, puis aux essais d'outillage.
    categories = [
        ('Chauffage', ('radiateur', 'purge', 'chauffage', 'pompe à chaleur', 'thermostat', 'circulateur', 'chaudière')),
        ('Plomberie', ('plomberie', 'multicouche', 'sertir', 'raccord', 'robinet', 'évacuation', 'pvc', 'nourrice', 'tuyau', 'siphon')),
        ('Électricité', ('électricit', 'tableau électrique', 'prise électrique', 'disjoncteur', 'interrupteur', 'luminaire')),
        ('Rénovation', ('rénovation', 'peinture', 'enduit', 'carrelage', 'isolation', 'placo', 'porte de garage', 'menuiserie', 'maçonnerie')),
        ('Tests & outillage', ('parkside', 'visseuse', 'perceuse', 'aspirateur', 'déballage', 'test ', 'essai', 'avis ', 'outil', 'meuleuse', 'ponceuse', 'scie')),
    ]
    for label, terms in categories:
        if any(term in text for term in terms):
            return label
    return 'Conseils & astuces'


def classify_short(title: str, description: str = '', duration_seconds=None) -> bool:
    if re.search(r'(?i)(?:#shorts?\b|\bshorts?\b)', title + ' ' + description[:250]):
        return True
    # Depuis octobre 2024, YouTube autorise les Shorts jusqu'à 3 minutes.
    # Il ne s'agit PAS d'un indicateur officiel du format Short.
    return duration_seconds is not None and duration_seconds <= 180


def normalize(item: dict) -> dict | None:
    vid = str(item.get('id', '')).strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
        return None
    title = str(item.get('title') or 'Vidéo de bricolage').strip()
    description = str(item.get('description') or '').strip()
    published = str(item.get('published') or '')
    duration = item.get('duration_seconds')
    if duration is not None:
        try: duration = int(duration)
        except (TypeError, ValueError): duration = None
    result = {
        'id': vid,
        'title': title[:350],
        'description': description[:12000],
        'published': published,
        'url': f'https://www.youtube.com/watch?v={vid}',
        'thumbnail': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg',
        'category': category(title, description),
        'short': classify_short(title, description, duration),
        'duration_seconds': duration,
    }
    return result



def resolve_channel_id() -> str:
    """Obtient l'identifiant public depuis l'URL officielle @Lachainedubricolage.

    Ne pas faire confiance à l'ID stocké si YouTube a renvoyé un autre canal.
    En cas d'échec de résolution, la validation stricte du flux reste active.
    """
    try:
        page = fetch(CHANNEL_URL).decode('utf-8', errors='replace')
        patterns = (
            r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
            r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
            r'"browseId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
            r'channel_id=(UC[A-Za-z0-9_-]{22})',
            r'/channel/(UC[A-Za-z0-9_-]{22})',
        )
        for pattern in patterns:
            match = re.search(pattern, page)
            if match:
                return match.group(1)
        print('Impossible de lire l’identifiant sur la page de la chaîne ; vérification RSS stricte conservée.', file=sys.stderr)
    except Exception as exc:
        print(f'Page YouTube de la chaîne temporairement indisponible : {exc}', file=sys.stderr)
    return CHANNEL_ID


def fetch_rss() -> list[dict]:
    xml = ET.fromstring(fetch(FEED_URL))
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015', 'media': 'http://search.yahoo.com/mrss/'}
    result = []
    channel_id_in_feed = xml.findtext('yt:channelId', default='', namespaces=ns)
    if channel_id_in_feed and channel_id_in_feed not in (CHANNEL_ID, CHANNEL_ID[2:]):
        raise RuntimeError(f'Le flux YouTube ne correspond pas à la chaîne attendue : attendu={CHANNEL_ID}, reçu={channel_id_in_feed}. Vérifier la page @Lachainedubricolage.')
    for entry in xml.findall('atom:entry', ns):
        video_id = entry.findtext('yt:videoId', default='', namespaces=ns)
        media_group = entry.find('media:group', ns)
        description = ''
        if media_group is not None:
            description = media_group.findtext('media:description', default='', namespaces=ns)
        data = normalize({'id': video_id, 'title': entry.findtext('atom:title', default='', namespaces=ns), 'description': description, 'published': entry.findtext('atom:published', default='', namespaces=ns)})
        if data: result.append(data)
    return result


def api_json(endpoint: str, params: dict) -> dict:
    url = 'https://www.googleapis.com/youtube/v3/' + endpoint + '?' + urllib.parse.urlencode(params)
    return json.loads(fetch(url))


def iso_duration_seconds(value: str) -> int | None:
    m = re.fullmatch(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value or '')
    if not m: return None
    d, h, minute, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + minute * 60 + s


def fetch_complete_catalog(key: str) -> list[dict]:
    """Importe les vidéos publiques avec l'API officielle; clé facultative."""
    channels = api_json('channels', {'part': 'contentDetails', 'id': CHANNEL_ID, 'key': key})
    items = channels.get('items', [])
    if not items: raise RuntimeError('Chaîne YouTube introuvable dans l’API.')
    playlist = items[0]['contentDetails']['relatedPlaylists']['uploads']
    ids = []
    page = None
    for _ in range(200):  # garde-fou : 10 000 vidéos maximum
        params = {'part': 'contentDetails', 'playlistId': playlist, 'maxResults': 50, 'key': key}
        if page: params['pageToken'] = page
        data = api_json('playlistItems', params)
        ids.extend(x['contentDetails']['videoId'] for x in data.get('items', []) if x.get('contentDetails', {}).get('videoId'))
        page = data.get('nextPageToken')
        if not page: break
    videos = []
    for i in range(0, len(ids), 50):
        data = api_json('videos', {'part': 'snippet,contentDetails,status', 'id': ','.join(ids[i:i + 50]), 'key': key})
        for entry in data.get('items', []):
            snippet = entry.get('snippet', {})
            if entry.get('status', {}).get('privacyStatus') not in (None, 'public'):
                continue
            videos.append(normalize({
                'id': entry['id'], 'title': snippet.get('title'), 'description': snippet.get('description'),
                'published': snippet.get('publishedAt'),
                'duration_seconds': iso_duration_seconds(entry.get('contentDetails', {}).get('duration', '')),
            }))
    return [x for x in videos if x is not None]


def merge(existing: list[dict], incoming: list[dict]) -> list[dict]:
    # Les nouvelles métadonnées remplacent les précédentes sans effacer les champs connus
    by_id = {x['id']: x for x in existing if isinstance(x, dict) and x.get('id')}
    for item in incoming:
        if item['id'] in by_id:
            previous = by_id[item['id']]
            if item.get('duration_seconds') is None and previous.get('duration_seconds') is not None:
                item['duration_seconds'] = previous['duration_seconds']
                item['short'] = classify_short(item['title'], item['description'], item['duration_seconds'])
            if not item.get('description') and previous.get('description'):
                item['description'] = previous['description']
            if not item.get('published') and previous.get('published'):
                item['published'] = previous['published']
        by_id[item['id']] = item
    return sorted(by_id.values(), key=lambda x: x.get('published') or '', reverse=True)


def escape(v) -> str:
    return html.escape(str(v or ''), quote=True)


def path_url(base_path: str, path: str) -> str:
    return base_path + path.lstrip('/')


def date_fr(iso: str) -> str:
    try:
        value = dt.datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return value.strftime('%d/%m/%Y')
    except (ValueError, TypeError): return ''


def card(v: dict, base_path: str) -> str:
    href = path_url(base_path, 'videos/' + v['id'] + '/')
    public_title = seo_title(v)
    summary = seo_summary(v)
    dur = v.get('duration_seconds')
    duration = f'{dur // 60}:{dur % 60:02d}' if dur is not None else ''
    return f'''<article class="video-card">
<a href="{escape(href)}" class="thumb-link" aria-label="Voir {escape(public_title)}">
<img src="{escape(v['thumbnail'])}" alt="Miniature : {escape(public_title)}" loading="lazy" width="480" height="270">
<span class="thumb-play" aria-hidden="true">▶</span>{'<span class="duration">' + duration + '</span>' if duration else ''}
</a><div class="card-content"><h3><a href="{escape(href)}">{escape(public_title)}</a></h3>
<span class="eyebrow">La chaîne du bricolage · {escape(v['category'])}{' · Short' if v['short'] else ''}</span>
<p>{escape(shorten(summary, 88))}</p>
<div class="card-footer"><span>{escape(date_fr(v['published']))}</span><a href="{escape(href)}" aria-label="Découvrir {escape(public_title)}">Voir la vidéo ↗</a></div></div></article>'''

def logo(base_path: str) -> str:
    avatar = path_url(base_path, 'assets/chaine-logo.jpg')
    return f'''<a class="brand" href="{escape(base_path)}" aria-label="La chaîne du bricolage : accueil"><span class="brand-icon"><img src="{escape(avatar)}" alt="" width="53" height="53"></span><span class="brand-copy"><strong>LA CHAÎNE DU <em>BRICOLAGE</em></strong><small>TUTOS · ASTUCES · OUTILLAGE</small></span></a>'''

def layout(title: str, description: str, content: str, base_path: str, full_url: str = '', image: str = '', schema: str = '', extra_head: str = '') -> str:
    canonical = f'<link rel="canonical" href="{escape(full_url)}">' if full_url else ''
    ogurl = f'<meta property="og:url" content="{escape(full_url)}">' if full_url else ''
    ogimage = f'<meta property="og:image" content="{escape(image)}">' if image else ''
    safe_schema = schema.replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e')
    schema_tag = f'<script type="application/ld+json">{safe_schema}</script>' if schema else ''
    css = path_url(base_path, 'assets/style.css')
    script = path_url(base_path, 'assets/app.js')
    search_url = path_url(base_path, 'catalogue/')
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#ffffff"><meta name="color-scheme" content="light"><title>{escape(title)}</title><meta name="description" content="{escape(description)}">
{canonical}<meta property="og:type" content="website"><meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{escape(description)}">{ogurl}{ogimage}<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index, follow, max-image-preview:large, max-video-preview:-1"><link rel="alternate" type="application/atom+xml" title="Nouvelles vidéos" href="{escape(path_url(base_path, 'feed.xml'))}"><link rel="icon" href="{escape(path_url(base_path, 'assets/chaine-logo.jpg'))}" type="image/jpeg"><link rel="stylesheet" href="{escape(css)}">{schema_tag}{extra_head}</head>
<body data-base="{escape(base_path)}"><a class="skip" href="#contenu">Aller au contenu</a>
<header class="site-header"><div class="container nav-shell">{logo(base_path)}
<form class="header-search" role="search" action="{escape(search_url)}" method="get"><input type="search" name="q" aria-label="Rechercher un tutoriel" placeholder="Rechercher un tuto, un outil…"><button type="submit" aria-label="Lancer la recherche">⌕</button></form>
<nav class="nav-links" aria-label="Navigation principale"><a href="{escape(base_path)}">Accueil</a><a href="{escape(search_url)}">Vidéos</a><a href="{escape(path_url(base_path, 'catalogue/?format=court'))}">Shorts</a></nav>
<a class="nav-cta" href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer"><span class="yt-mark" aria-hidden="true">▶</span>S’abonner</a>
<button class="mobile-menu" type="button" aria-label="Ouvrir le menu" aria-expanded="false">☰</button></div>
<nav class="mobile-nav" aria-label="Menu mobile" hidden><a href="{escape(base_path)}">Accueil</a><a href="{escape(search_url)}">Toutes les vidéos</a><a href="{escape(path_url(base_path, 'catalogue/?categorie=Tests%20%26%20outillage'))}">Tests d’outils</a><a href="{escape(path_url(base_path, 'catalogue/?format=court'))}">Shorts</a></nav></header>
<main id="contenu">{content}</main>
<footer class="footer"><div class="container footer-main"><div>{logo(base_path)}<p>La chaîne d’un bricoleur pour les bricoleurs. Des vidéos pratiques pour apprendre, progresser et réussir ses travaux.</p></div>
<div><span class="footer-label">EXPLORER</span><a href="{escape(search_url)}">Vidéos & tutoriels</a><a href="{escape(path_url(base_path, 'catalogue/?format=court'))}">Shorts</a><a href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer">Chaîne YouTube</a><a href="{escape(path_url(base_path, 'feed.xml'))}">Flux des publications</a></div>
<div><span class="footer-label">NOUS CONTACTER</span><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a><p>Les démonstrations ne remplacent pas les consignes de sécurité, les notices fabricants ni l’intervention d’un professionnel lorsque nécessaire.</p></div></div>
<div class="container footer-bottom"><span>© {dt.datetime.now().year} La chaîne du bricolage</span><span>Site indépendant, vidéos diffusées via YouTube</span></div></footer>
<script src="{escape(script)}" defer></script></body></html>'''

def render_grid(videos: list[dict], base_path: str) -> str:
    if videos: return '<div class="video-grid" id="video-grid">' + ''.join(card(v, base_path) for v in videos) + '</div>'
    return '''<div class="empty-state" id="video-grid"><div class="empty-icon">↻</div><h3>Les vidéos arrivent ici automatiquement</h3><p>Le catalogue sera renseigné dès la première synchronisation YouTube après publication du site.</p><a href="https://www.youtube.com/@Lachainedubricolage" target="_blank" rel="noopener noreferrer">Accéder à la chaîne YouTube ↗</a></div>'''


def filters() -> str:
    return '''<div class="filters" id="filters"><div class="search-wrap"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Une question, un outil, un matériau…" aria-label="Rechercher une vidéo" autocomplete="off"></div><div class="filter-row"><select id="category" aria-label="Filtrer par sujet"><option value="">Tous les sujets</option><option>Chauffage</option><option>Plomberie</option><option>Électricité</option><option>Rénovation</option><option>Tests &amp; outillage</option><option>Conseils &amp; astuces</option></select><select id="format" aria-label="Filtrer par durée"><option value="">Tous les formats</option><option value="court">Formats courts</option><option value="long">Vidéos longues / autres</option></select><span id="result-count" aria-live="polite"></span></div></div>'''


def homepage(videos: list[dict], base_path: str, site_url: str) -> str:
    latest = videos[0] if videos else None
    logo_src = escape(path_url(base_path, 'assets/chaine-logo.jpg'))
    banner_src = escape(path_url(base_path, 'assets/chaine-banniere-couleurs.jpg'))
    featured = f'''<div class="hero-video"><a href="{escape(path_url(base_path, 'videos/' + latest['id'] + '/'))}"><img src="{escape(latest['thumbnail'])}" alt="{escape(latest['title'])}" width="640" height="360"><span class="featured-play" aria-hidden="true">▶</span></a><div class="feature-caption"><small>DERNIÈRE VIDÉO PUBLIÉE</small><strong>{escape(latest['title'])}</strong></div></div>''' if latest else f'''<div class="hero-video hero-placeholder"><div class="placeholder-visual"><img src="{logo_src}" alt="" width="80" height="80"><span>TUTOS · ASTUCES · OUTILLAGE</span></div><div class="feature-caption"><small>NOUVELLES PUBLICATIONS</small><strong>Les dernières vidéos apparaîtront ici automatiquement</strong></div></div>'''
    header = f'''<div class="channel-wrap"><div class="container"><div class="channel-banner"><img src="{banner_src}" alt="Bannière officielle de La chaîne du bricolage, bleue et orange" width="1776" height="616"></div><div class="channel-profile"><img class="profile-avatar" src="{logo_src}" alt="Logo officiel de La chaîne du bricolage" width="102" height="102"><div class="profile-info"><h1>La chaîne du bricolage</h1><p class="profile-handle">@Lachainedubricolage · Tutoriels & tests d’outillage</p><p class="profile-bio">La chaîne d’un bricoleur pour les bricoleurs. Apprenez les bons gestes et réalisez vos projets vous-même.</p></div><a class="subscribe-btn" href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer">▶ &nbsp;S’abonner sur YouTube</a></div><nav class="channel-tabs" aria-label="Rubriques de la chaîne"><a href="{escape(base_path)}" aria-current="page">Accueil</a><a href="{escape(path_url(base_path, 'catalogue/'))}">Vidéos</a><a href="{escape(path_url(base_path, 'catalogue/?format=court'))}">Shorts</a><a href="{escape(path_url(base_path, 'catalogue/?categorie=Tests%20%26%20outillage'))}">Tests d’outillage</a><a href="{escape(path_url(base_path, 'catalogue/?categorie=Plomberie'))}">Plomberie</a><a href="{escape(path_url(base_path, 'catalogue/?categorie=Chauffage'))}">Chauffage</a></nav></div></div>'''
    welcome = f'''<section class="home-main"><div class="container"><div class="welcome-strip"><div class="welcome-copy"><span class="label-row">BIENVENUE SUR LA CHAÎNE</span><h2>Le bricolage,<br><em>à la portée de tous.</em></h2><p>Plomberie, chauffage, rénovation et outillage : des démonstrations claires, des astuces utiles et des tests concrets pour avancer dans vos projets.</p><div class="welcome-actions"><a class="btn btn-primary" href="{escape(path_url(base_path, 'catalogue/'))}">Découvrir les tutoriels →</a><a class="btn btn-outline" href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer">Voir sur YouTube ▶</a></div></div>{featured}</div></div></section>'''
    themes=[('Chauffage','♨','Chauffage'),('Plomberie','⌁','Plomberie'),('Tests & outillage','⚒','Tests & outillage'),('Rénovation','▱','Rénovation'),('Électricité','ϟ','Électricité')]
    theme_cards=''.join(f'<a class="theme-card" href="{escape(path_url(base_path, "sujets/" + topic_slug(c) + "/"))}"><span class="theme-glyph" aria-hidden="true">{icon}</span><strong>{escape(label)}</strong></a>' for label, icon,c in themes)
    sections=f'''<section class="section-top"><div class="container"><div class="section-heading"><div><span class="overline">RETROUVEZ VOS SUJETS</span><h2>Qu’est-ce qu’on bricole aujourd’hui ?</h2></div><p>Un sujet, un bon geste, le bon tuto. Explorez la chaîne selon vos besoins.</p></div><div class="theme-grid">{theme_cards}</div></div></section>
<section class="listing-section"><div class="container"><div class="section-heading"><div><span class="overline">LES NOUVEAUTÉS DE LA CHAÎNE</span><h2>Dernières vidéos & Shorts</h2></div><a class="text-link" href="{escape(path_url(base_path, 'catalogue/'))}">Voir toutes les vidéos →</a></div>{render_grid(videos[:9],base_path)}<div class="center-action"><a class="btn btn-dark" href="{escape(path_url(base_path, 'catalogue/'))}">Explorer toutes les vidéos →</a></div></div></section>
<section class="mission"><div class="container mission-inner"><div class="mission-graphic" aria-hidden="true"><span>APPRENDRE.</span><span>BRICOLER.</span><span>RÉUSSIR.</span></div><div class="mission-copy"><span class="overline">LA PHILOSOPHIE DE LA CHAÎNE</span><h2>Du concret, pour <em>bricoler soi-même.</em></h2><p>Débutant ou passionné, retrouvez des tutos, des essais d’outillage à main et électroportatif, et des explications utiles sans discours promotionnel inutile.</p><a class="btn btn-primary" href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer">Rejoindre la chaîne YouTube →</a></div></div></section>
<section class="newsletter-like"><div class="container closing"><span class="overline">À RETROUVER ICI</span><h2>Une nouvelle vidéo publiée ? <em>Elle arrive ici.</em></h2><p>Le site récupère automatiquement les nouvelles publications YouTube après la mise en ligne et l’activation de la synchronisation.</p><a class="btn btn-dark" href="{escape(path_url(base_path, 'catalogue/'))}">Voir la vidéothèque →</a></div></section>'''
    schema=json.dumps({'@context':'https://schema.org','@type':'WebSite','name':CHANNEL_NAME,**({'url':site_url} if site_url else {}),'inLanguage':'fr-FR','sameAs':[CHANNEL_URL],'description':'Tutoriels et tests de bricolage, rénovation, plomberie, chauffage et outillage.'},ensure_ascii=False)
    return layout('La chaîne du bricolage | Tutos, vidéos & Shorts','Tutoriels de bricolage, plomberie, chauffage et rénovation, et tests d’outillage. Retrouvez les nouvelles vidéos et Shorts automatiquement.',header+welcome+sections,base_path,site_url,image=(site_url.rstrip('/')+'/assets/chaine-banniere-couleurs.jpg' if site_url else ''),schema=schema)

def catalogue_page(videos: list[dict], base_path: str, site_url: str) -> str:
    content = f'''<section class="catalog-head"><div class="container"><span class="overline">VIDÉOS & SHORTS</span><h1>Tous les tutos.<br><em>Au même endroit.</em></h1><p>Recherchez dans toutes les vidéos récupérées depuis la chaîne YouTube. Un nouveau contenu est ajouté automatiquement à chaque synchronisation.</p></div></section><section class="catalog-section"><div class="container">{filters()}{render_grid(videos[:24],base_path)}<div class="center-action"><button id="more" class="btn btn-dark" type="button" hidden>Afficher plus de vidéos ↓</button></div><div class="catalog-footnote">Les formats courts sont identifiés à partir du titre ou de la durée lorsqu'elle est disponible. Cette distinction ne correspond pas toujours à la classification officielle des Shorts sur YouTube.</div></div></section>'''
    return layout('Toutes les vidéos | La chaîne du bricolage', 'Retrouvez et recherchez tous les tutoriels, les astuces bricolage et les tests d’outillage publiés sur La chaîne du bricolage.', content, base_path, site_url)


def topic_page(category: str, videos: list[dict], base_path: str, site_url: str) -> str:
    slug, subtitle = TOPICS[category]
    selection = [v for v in videos if v.get('category') == category]
    breadcrumb = f'<nav aria-label="Fil d’Ariane"><a href="{escape(base_path)}">Accueil</a> / <a href="{escape(path_url(base_path, "catalogue/"))}">Vidéos</a> / {escape(category)}</nav>'
    content = f'<section class="catalog-head"><div class="container">{breadcrumb}<span class="overline">NOS VIDÉOS PAR SUJET</span><h1>{escape(category)}</h1><p>{escape(subtitle)}</p><p>{len(selection)} vidéos et Shorts classés dans cette rubrique.</p></div></section><section class="catalog-section"><div class="container">{render_grid(selection, base_path)}<p><a href="{escape(path_url(base_path, "catalogue/"))}">Voir toutes les vidéos et les autres thèmes ↗</a></p></div></section>'
    schema = json.dumps({'@context':'https://schema.org', '@type':'CollectionPage', 'name':category + ' – La chaîne du bricolage', 'url':site_url, 'description':subtitle, 'inLanguage':'fr-FR'},ensure_ascii=False)
    return layout(category + ' : tutoriels et vidéos | La chaîne du bricolage',subtitle,content,base_path,site_url,schema=schema)


def detail_page(v: dict, videos: list[dict], base_path: str, site_url: str) -> str:
    description = v['description'].strip() or 'Découvrez la démonstration complète en vidéo sur La chaîne du bricolage.'
    display_title = seo_title(v)
    summary = seo_summary(v)
    topics = documented_points(description)
    timeline = chapters(description, v['id'])
    full_video = video_reference(description, v['id'], videos)
    topic_href = path_url(base_path, 'sujets/' + topic_slug(v['category']) + '/')
    topic_link = f'<p class="seo-topic-ref">Explorer les autres vidéos : <a href="{escape(topic_href)}">{escape(v["category"])}</a></p>'
    points_html = ('<section class="documented-points"><h2>Dans ce tutoriel</h2><p>Points indiqués dans la description publiée par la chaîne :</p><ul>' + ''.join('<li>' + escape(point) + '</li>' for point in topics) + '</ul></section>') if topics else ''
    timeline_html = ('<section class="documented-chapters"><h2>Chapitres indiqués par la chaîne</h2><ol>' + ''.join(f'<li><a href="{escape(ch["url"])}" target="_blank" rel="noopener noreferrer"><time>{escape(ch["stamp"])}</time> {escape(ch["label"])}</a></li>' for ch in timeline) + '</ol></section>') if timeline else ''
    full_html = (f'<aside class="full-video-link"><strong>Voir le tutoriel complet</strong><p>Cette vidéo courte renvoie à une démonstration plus longue :</p><a href="{escape(path_url(base_path, "videos/" + full_video["id"] + "/"))}">{escape(seo_title(full_video))} ↗</a></aside>') if full_video else ''
    related = related_videos(v, videos, limit=4)
    iso = v['published']
    schema = {'@context': 'https://schema.org', '@type': 'VideoObject', 'name': v['title'], 'description': shorten(description, 4000), 'thumbnailUrl': [v['thumbnail']], 'embedUrl': f'https://www.youtube-nocookie.com/embed/{v["id"]}', 'sameAs': v['url'], 'inLanguage': 'fr-FR', 'publisher': {'@type': 'Organization', 'name': CHANNEL_NAME, 'sameAs': CHANNEL_URL}}
    if iso: schema['uploadDate'] = iso
    if v.get('duration_seconds') is not None: schema['duration'] = f'PT{v["duration_seconds"]}S'
    if timeline:
        schema['hasPart'] = [{'@type': 'Clip', 'name': ch['label'], 'startOffset': ch['start'], 'url': ch['url']} for ch in timeline]
    if site_url:
        schema['mainEntityOfPage'] = site_url
        schema['url'] = site_url
    else:
        schema['url'] = v['url']
    desc_html = '<p>' + '</p><p>'.join(escape(block).replace('\n', '<br>') for block in re.split(r'\n\s*\n', description[:8000]) if block.strip()) + '</p>'
    content = f'''<section class="detail-head"><div class="container"><a class="back-link" href="{escape(path_url(base_path, 'catalogue/'))}">← Retour aux vidéos</a><span class="overline">{escape(v['category'])}{' · FORMAT COURT' if v['short'] else ''}</span><h1>{escape(display_title)}</h1><div class="detail-meta"><span>La chaîne du bricolage</span>{'<span>·</span><span>' + escape(date_fr(iso)) + '</span>' if iso else ''}</div></div></section><section class="detail-body"><div class="container"><div class="player"><iframe src="https://www.youtube-nocookie.com/embed/{escape(v['id'])}?rel=0" title="Regarder : {escape(display_title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div><div class="video-layout"><article class="video-text"><span class="overline">À PROPOS DE CETTE VIDÉO</span><h2>Ce que la chaîne présente</h2><p class="seo-summary">{escape(summary)}</p>{points_html}{timeline_html}{full_html}{desc_html}{topic_link}<p>Pour les informations les plus récentes, consultez également la description de la vidéo sur YouTube.</p><a class="btn btn-dark" href="{escape(v['url'])}" target="_blank" rel="noopener noreferrer">Ouvrir sur YouTube ↗</a></article><aside class="side-panel"><span class="overline">À RETENIR</span><h3>Le bricolage en toute confiance</h3><p>Respectez les notices des fabricants, protégez-vous et coupez les alimentations lorsque c'est nécessaire. Certains travaux exigent un professionnel qualifié.</p><a href="{escape(path_url(base_path, 'catalogue/'))}">Explorer d’autres tutoriels ↗</a></aside></div></div></section>{'<section class="related-section"><div class="container"><div class="section-heading"><div><span class="overline">CONTINUER À APPRENDRE</span><h2>À découvrir <em>ensuite</em></h2></div></div>' + render_grid(related,base_path) + '</div></section>' if related else ''}'''
    return layout(f'{display_title} | La chaîne du bricolage', shorten(summary, 155), content, base_path, site_url, image=v['thumbnail'], schema=json.dumps(schema, ensure_ascii=False))


def build(videos: list[dict], site_url: str) -> None:
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    shutil.copytree(ROOT / 'assets', OUTPUT / 'assets', dirs_exist_ok=True)
    (OUTPUT / '.nojekyll').write_text('', encoding='utf-8')
    # Conserver les vérifications Google et Bing à chaque régénération automatique.
    for filename in ('googlefd66cc36e99efde5.html', 'BingSiteAuth.xml'):
        verification = ROOT / filename
        if verification.is_file():
            shutil.copy2(verification, OUTPUT / filename)
    base_path = '/' + urllib.parse.urlparse(site_url).path.strip('/') + '/' if site_url and urllib.parse.urlparse(site_url).path.strip('/') else '/'
    def absolute(rel=''):
        return site_url.rstrip('/') + '/' + rel if site_url else ''
    (OUTPUT / 'index.html').write_text(homepage(videos, base_path, absolute()), encoding='utf-8')
    (OUTPUT / 'catalogue').mkdir()
    (OUTPUT / 'catalogue' / 'index.html').write_text(catalogue_page(videos, base_path, absolute('catalogue/')), encoding='utf-8')
    topics_folder = OUTPUT / 'sujets'
    topics_folder.mkdir()
    for topic, (slug, _) in TOPICS.items():
        folder = topics_folder / slug
        folder.mkdir()
        (folder / 'index.html').write_text(topic_page(topic, videos, base_path, absolute('sujets/' + slug + '/')), encoding='utf-8')
    data_dir = OUTPUT / 'data'
    data_dir.mkdir()
    public_videos = [dict(v, seo_title=seo_title(v), seo_summary=seo_summary(v)) for v in videos]
    (data_dir / 'videos.json').write_text(json.dumps(public_videos, indent=2, ensure_ascii=False), encoding='utf-8')
    urls = [(absolute(), None), (absolute('catalogue/'), None)] if site_url else []
    for v in videos:
        directory = OUTPUT / 'videos' / v['id']
        directory.mkdir(parents=True)
        uri = 'videos/' + v['id'] + '/'
        (directory / 'index.html').write_text(detail_page(v, videos, base_path, absolute(uri)), encoding='utf-8')
        if site_url: urls.append((absolute(uri), v.get('published', '')[:10]))
    if site_url:
        pages = [
            f'<url><loc>{escape(absolute())}</loc></url>',
            f'<url><loc>{escape(absolute("catalogue/"))}</loc></url>',
            *(f'<url><loc>{escape(absolute("sujets/" + slug + "/"))}</loc></url>' for slug, _ in TOPICS.values()),
        ]
        for v in videos:
            url = absolute('videos/' + v['id'] + '/')
            date = v.get('published') or ''
            lastmod = f'<lastmod>{escape(date[:10])}</lastmod>' if re.match(r'^\d{4}-\d{2}-\d{2}', date) else ''
            pub = f'<video:publication_date>{escape(date)}</video:publication_date>' if date else ''
            secs = v.get('duration_seconds')
            duration = f'<video:duration>{secs}</video:duration>' if secs is not None and 1 <= secs <= 28800 else ''
            video = (
                '<video:video>'
                f'<video:thumbnail_loc>{escape(v["thumbnail"])}</video:thumbnail_loc>'
                f'<video:title>{escape(shorten(v["title"], 100))}</video:title>'
                f'<video:description>{escape(shorten(v["description"] or v["title"], 1900))}</video:description>'
                f'<video:player_loc allow_embed="yes">{escape("https://www.youtube-nocookie.com/embed/" + v["id"])}</video:player_loc>'
                f'{pub}{duration}'
                '</video:video>'
            )
            pages.append(f'<url><loc>{escape(url)}</loc>{lastmod}{video}</url>')
        sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">\n'
            + '\n'.join(pages)
            + '\n</urlset>\n'
        )
        (OUTPUT / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    (OUTPUT / 'robots.txt').write_text('User-agent: *\nAllow: /\n' + (f'Sitemap: {absolute("sitemap.xml")}\n' if site_url else ''), encoding='utf-8')
    entries = ''.join('<entry><title>' + escape(v['title']) + '</title><id>' + escape(v['url']) + '</id><link href="' + escape(v['url']) + '"/><updated>' + escape(v['published'] or '2026-01-01T00:00:00Z') + '</updated><summary>' + escape(shorten(v['description'], 600)) + '</summary></entry>' for v in videos[:50])
    feed = '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>La chaîne du bricolage — nouvelles vidéos</title><id>' + escape(CHANNEL_URL) + '</id><updated>' + dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z') + '</updated>' + entries + '</feed>'
    (OUTPUT / 'feed.xml').write_text(feed, encoding='utf-8')
    print(f'Site généré : {len(videos)} vidéos, base : {base_path}, destination : {OUTPUT}')


def inferred_url() -> str:
    env_url = os.environ.get('SITE_URL', '').strip()
    if env_url:
        parsed = urllib.parse.urlparse(env_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ValueError('SITE_URL doit être une URL http(s) complète.')
        return env_url.rstrip('/') + '/'
    repo = os.environ.get('GITHUB_REPOSITORY', '').strip()
    if '/' in repo:
        owner, name = repo.split('/', 1)
        base = f'https://{owner}.github.io/'
        return base if name.lower() == f'{owner.lower()}.github.io' else base + urllib.parse.quote(name) + '/'
    return ''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='Ne pas accéder à YouTube : créer la prévisualisation à partir du catalogue local.')
    parser.add_argument('--site-url', default=None, help='URL publique complète du site (GitHub Pages, domaine propre...)')
    args = parser.parse_args()
    global CHANNEL_ID, FEED_URL
    resolved = resolve_channel_id() if not args.offline else CHANNEL_ID
    if resolved != CHANNEL_ID:
        print(f'Identifiant YouTube corrigé depuis le profil officiel : {CHANNEL_ID} -> {resolved}')
        CHANNEL_ID = resolved
        FEED_URL = f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}'
    current = []
    if ARCHIVE.exists():
        try: current = json.loads(ARCHIVE.read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc: raise RuntimeError('Catalogue local invalide : ' + str(exc))
    incoming = []
    api_count = None
    if not args.offline:
        key = os.environ.get('YOUTUBE_API_KEY', '').strip()
        if key:
            try:
                incoming = fetch_complete_catalog(key)
                api_count = len(incoming)
                print(f'Import officiel complet YouTube : {api_count} vidéos')
            except Exception as exc:
                print(f'::warning title=Import historique YouTube incomplet::La clé API est présente, mais l’import officiel a échoué : {exc}', file=sys.stderr)
                print(f'API YouTube indisponible, repli sur le flux : {exc}', file=sys.stderr)
        else:
            print('::notice title=Importer les anciennes vidéos::Configurer le secret YOUTUBE_API_KEY pour récupérer tout l’historique.')
        try:
            incoming = merge(incoming, fetch_rss())
            print(f'Flux YouTube actualisé : {len(incoming)} entrées')
        except Exception as exc:
            if not incoming and not current: raise
            print(f'Flux indisponible : conservation du catalogue existant ({exc})', file=sys.stderr)
    result = merge(current, incoming)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if not ARCHIVE.exists() or ARCHIVE.read_text(encoding='utf-8') != serialized:
        ARCHIVE.write_text(serialized, encoding='utf-8')
    build(result, (args.site_url if args.site_url is not None else inferred_url()).strip())
    print(f'Catalogue du site : {len(result)} vidéos et Shorts enregistrés')
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY', '')
    if summary_path:
        if api_count is not None:
            import_status = f'✅ Import de la chaîne publique par API réussi : {api_count} vidéos renvoyées'
        elif os.environ.get('YOUTUBE_API_KEY', '').strip():
            import_status = '⚠️ La clé API est configurée, mais l’import historique a échoué. Le flux RSS et le catalogue précédent sont conservés.'
        else:
            import_status = '⏳ Import historique non activé : renseigner le secret YOUTUBE_API_KEY. Seules les publications récentes sont récupérées.'
        with open(summary_path, 'a', encoding='utf-8') as summary:
            summary.write('### La chaîne du bricolage — mise à jour du catalogue\n')
            summary.write(f'- Vidéos et Shorts enregistrés : **{len(result)}**\n')
            summary.write(f'- {import_status}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
