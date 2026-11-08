'use strict';
(() => {
  const menu = document.querySelector('.mobile-menu');
  const mobile = document.querySelector('.mobile-nav');
  if (menu && mobile) {
    menu.addEventListener('click', () => {
      const opened = menu.getAttribute('aria-expanded') === 'true';
      menu.setAttribute('aria-expanded', String(!opened));
      mobile.hidden = opened;
    });
  }
  const player = document.querySelector('.player[data-video]');
  const playButton = document.querySelector('.player-button');
  if (player && playButton) {
    playButton.addEventListener('click', () => {
      const id = player.dataset.video;
      if (!/^[\w-]{11}$/.test(id)) return;
      const iframe = document.createElement('iframe');
      iframe.title = 'Lecteur YouTube';
      iframe.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.allowFullscreen = true;
      player.replaceChildren(iframe);
      player.style.backgroundImage = 'none';
    });
  }
  const grid = document.getElementById('video-grid');
  const search = document.getElementById('search');
  if (!grid || !search) return;
  const base = document.body.dataset.base || '/';
  const cat = document.getElementById('category');
  const format = document.getElementById('format');
  const more = document.getElementById('more');
  const count = document.getElementById('result-count');
  const limit = 24;
  let visible = limit;
  let videos = [];
  const esc = text => String(text == null ? '' : text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const simple = text => String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const niceDate = value => { const s = String(value || '').slice(0,10).split('-'); return s.length === 3 ? `${s[2]}/${s[1]}/${s[0]}` : ''; };
  const preview = text => { const s = String(text || '').replace(/\s+/g,' ').trim(); return s.length < 112 ? s : s.slice(0, 110).trim() + '…'; };
  const card = v => {
    const url = `${base}videos/${encodeURIComponent(v.id)}/`;
    const duration = v.duration_seconds == null ? '' : `<span class="duration">${Math.floor(v.duration_seconds/60)}:${String(v.duration_seconds%60).padStart(2,'0')}</span>`;
    return `<article class="video-card"><a href="${esc(url)}" class="thumb-link" aria-label="Voir ${esc(v.seo_title || v.title)}"><img loading="lazy" width="480" height="270" src="${esc(v.thumbnail)}" alt="Miniature : ${esc(v.title)}"><span class="thumb-play" aria-hidden="true">▶</span>${duration}</a><div class="card-content"><h3><a href="${esc(url)}">${esc(v.title)}</a></h3><span class="eyebrow">La chaîne du bricolage · ${esc(v.category)}${v.short ? ' · Short' : ''}</span><p>${esc(preview(v.seo_summary || v.description) || 'Retrouvez cette vidéo sur notre chaîne YouTube.')}</p><div class="card-footer"><span>${esc(niceDate(v.published))}</span><a href="${esc(url)}">Voir la vidéo ↗</a></div></div></article>`;
  };
  const update = () => {
    const q = simple(search.value.trim());
    const c = cat.value;
    const f = format.value;
    if (videos.length === 0 && !q && !c && !f) {
      count.textContent = 'Catalogue en cours de synchronisation';
      if (more) more.hidden = true;
      return;
    }
    const found = videos.filter(v => {
      if (c && v.category !== c) return false;
      if (f === 'court' && !v.short) return false;
      if (f === 'long' && v.short) return false;
      return !q || simple(`${v.title} ${v.description} ${v.category}`).includes(q);
    });
    grid.className = 'video-grid';
    grid.innerHTML = found.length ? found.slice(0, visible).map(card).join('') : '<div class="empty-state" style="grid-column:1/-1"><h3>Aucune vidéo trouvée</h3><p>Essayez un autre sujet ou un autre mot-clé.</p></div>';
    count.textContent = `${found.length} résultat${found.length > 1 ? 's' : ''}`;
    if (more) more.hidden = found.length <= visible;
  };
  const params = new URLSearchParams(location.search);
  if (params.has('q')) search.value = params.get('q') || '';
  if (params.has('categorie')) cat.value = params.get('categorie');
  if (params.has('format')) format.value = params.get('format');
  fetch(`${base}data/videos.json`)
    .then(r => { if (!r.ok) throw new Error('Catalogue indisponible'); return r.json(); })
    .then(data => {
      if (!Array.isArray(data)) throw new Error('Format de catalogue invalide');
      videos = data;
      update();
    })
    .catch(e => { console.warn(e); count.textContent = 'Recherche temporairement indisponible'; });
  search.addEventListener('input', () => { visible = limit; update(); });
  cat.addEventListener('change', () => { visible = limit; update(); });
  format.addEventListener('change', () => { visible = limit; update(); });
  if (more) more.addEventListener('click', () => { visible += 24; update(); });
})();
