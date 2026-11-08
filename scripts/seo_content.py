"""SEO presentation built solely from public video metadata; never generates technical facts."""
from __future__ import annotations

import html
import re
import unicodedata

TOPICS = {
    'Chauffage': ('chauffage', 'Radiateurs, chauffe-eau et chauffage : retrouver les vidéos de la chaîne sur ces sujets.'),
    'Plomberie': ('plomberie', 'Plomberie sanitaire, raccords, multicouche et évacuations : parcourir les tutoriels disponibles.'),
    'Électricité': ('electricite', 'Électricité et équipements : retrouver les démonstrations de la chaîne et les consignes des auteurs.'),
    'Rénovation': ('renovation', 'Rénovation et aménagement : parcourir les vidéos publiées par La chaîne du bricolage.'),
    'Tests & outillage': ('tests-outillage', 'Tests et présentations d’outillage à main ou électroportatif, selon les publications de la chaîne.'),
    'Conseils & astuces': ('conseils-astuces', 'Astuces et conseils bricolage : retrouver les publications de la chaîne dans cette rubrique.'),
}
_STOP = {'avec','sans','pour','dans','vous','nous','votre','vos','des','les','une','sur','par','diy','shorts','short','bricolage','astuce','renovation','video','cette','comment','faire','tuto','test','chaine','lidl','plus','tout','tous','bien'}

def topic_slug(category: str) -> str:
    return TOPICS.get(category, TOPICS['Conseils & astuces'])[0]

def seo_title(v: dict) -> str:
    """Reuse the title written by the creator when the description explicitly supplies it."""
    raw = str(v.get('title') or 'Tutoriel de bricolage').strip()
    description = v.get('description') or ''
    m = re.search(r'(?im)^\s*Titre\s*:\s*(?:\n\s*)?([^\n]{12,130})\s*$', description)
    if m and not m.group(1).strip().lower().startswith('description'):
        return m.group(1).strip(' -:')
    clean = re.sub(r'(?<!\w)#[\w-]+', '', raw)
    clean = re.sub(r'\s+', ' ', clean).strip(' -|:')
    return clean[:125] or raw[:125]

def seo_summary(v: dict) -> str:
    description = (v.get('description') or '').strip()
    chunks = re.split(r'\n\s*\n', description)
    for chunk in chunks:
        line = re.sub(r'\s+', ' ', chunk).strip()
        if not 55 <= len(line) <= 600:
            continue
        if re.search(r'(?i)^(titre|description|lien|contact|abonne|https?://)',line):
            continue
        if 'https://' in line or 'http://' in line:
            continue
        if re.search(r'(?i)(abonnez-vous|abonne-toi|lien en description)',line):
            continue
        return line[:250].rsplit(' ',1)[0]+'…' if len(line)>250 else line
    return 'Regardez la vidéo « '+seo_title(v)+' » sur La chaîne du bricolage : présentation, démonstration et informations publiées par son auteur.'

def documented_points(description: str) -> list[str]:
    """Only bullets explicitly present in the creator's original description."""
    out = []
    for line in (description or '').splitlines():
        m = re.match(r'^\s*(?:✅|☑️?|✔️?|🔹|•|➤|\d{1,2}[.)])\s*(.{8,170})\s*$', line)
        if not m:
            continue
        body = m.group(1).strip().rstrip(' .')
        if re.search(r'(?i)(https?://|abonnez|abonne-toi|commentaire|lien|pouce bleu|promo|chaine youtube|partag)',body):
            continue
        if len(body) > 140:
            continue
        if body not in out:
            out.append(body)
        if len(out) >= 9:
            break
    return out if len(out) >= 2 else []

def chapters(description: str, video_id: str) -> list[dict]:
    """Timestamps copied from descriptions, never inferred from the video."""
    result = []
    for line in (description or '').splitlines():
        m = re.match(r'^\s*[-•]?\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s+[-–—]?[ ]*(.{3,120})\s*$',line)
        if not m:
            continue
        raw, label = m.groups()
        parts = [int(x) for x in raw.split(':')]
        if any(x>59 for x in parts[-2:]):
            continue
        seconds = sum(x*mult for x,mult in zip(reversed(parts),(1,60,3600)))
        if any(p['start']==seconds for p in result):
            continue
        result.append({'start':seconds,'stamp':raw,'label':label.strip(),'url':f'https://www.youtube.com/watch?v={video_id}&t={seconds}s'})
        if len(result) >= 35:
            break
    return result if len(result)>1 else []

def video_reference(description: str, current_id: str, catalog: list[dict]) -> dict | None:
    """Return a linked long video only when the Short description explicitly says full video."""
    if not re.search(r'(?i)vid[eé]o\s+compl[eè]te',description or ''):
        return None
    ids = set(v['id'] for v in catalog)
    for match in re.finditer(r'(?:youtu\.be/|youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})', description):
        video_id = match.group(1)
        if video_id in ids and video_id != current_id:
            return next(v for v in catalog if v['id']==video_id)
    return None

def _tokens(v: dict) -> set[str]:
    text = str(v.get('title') or '')+' '+str(v.get('description') or '')[:160]
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    return {w for w in re.findall(r'[a-z0-9]{4,}', text) if w not in _STOP}

def related_videos(video: dict, catalog: list[dict], limit: int=4) -> list[dict]:
    reference_tokens = _tokens(video)
    ranked=[]
    for candidate in catalog:
        if candidate['id']==video['id']:
            continue
        overlap=len(reference_tokens & _tokens(candidate))
        score=(6 if candidate.get('category')==video.get('category') else 0) + 2*min(overlap,6)
        if video.get('short') and not candidate.get('short') and overlap>0:
            score+=3
        if score:
            ranked.append((-score, candidate.get('published',''),candidate))
    ranked.sort(key=lambda v:(v[0],v[1]))
    return [row[2] for row in ranked[:limit]]

def html_list(items: list[str], class_name: str) -> str:
    return f'<ul class="{class_name}">'+''.join('<li>'+html.escape(v,quote=True)+'</li>' for v in items)+'</ul>'
