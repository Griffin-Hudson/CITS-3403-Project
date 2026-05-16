(function () {
  'use strict';

  const form = document.getElementById('search-form');
  const resultsBox = document.getElementById('search-results');

  if (!form || !resultsBox) return;

  const apiUrl = resultsBox.dataset.apiUrl || '/api/search';
  const beatUrlTemplate = resultsBox.dataset.beatUrlTemplate || '/beats/0';
  const profileUrlTemplate = resultsBox.dataset.profileUrlTemplate || '/profile/0';

  function urlFromTemplate(template, id) {
    return template.replace(/0(?=$|[/?#])/, String(id));
  }

  function clearResults() {
    resultsBox.replaceChildren();
  }

  function icon(name) {
    const i = document.createElement('i');
    i.className = `bi ${name}`;
    return i;
  }

  function resultCard(href, iconName, title, subtitle, meta) {
    const a = document.createElement('a');
    a.href = href;
    a.className = 'search-result-card';

    const iconWrap = document.createElement('span');
    iconWrap.className = 'search-result-icon';
    iconWrap.appendChild(icon(iconName));

    const main = document.createElement('span');
    main.className = 'search-result-main';
    const strong = document.createElement('strong');
    strong.textContent = title;
    const sub = document.createElement('span');
    sub.textContent = subtitle;
    main.append(strong, sub);

    const metaEl = document.createElement('span');
    metaEl.className = 'search-result-meta';
    metaEl.textContent = meta;

    a.append(iconWrap, main, metaEl);
    return a;
  }

  function statusBlock(className, iconName, text) {
    const box = document.createElement('div');
    box.className = className;
    box.appendChild(icon(iconName));
    if (className === 'search-loading') {
      box.appendChild(document.createTextNode(text));
    } else {
      const p = document.createElement('p');
      p.textContent = text;
      box.appendChild(p);
    }
    return box;
  }

  function section(title, cards) {
    const sec = document.createElement('section');
    sec.className = 'search-section';
    const heading = document.createElement('h2');
    heading.className = 'search-section-title';
    heading.textContent = title;
    const list = document.createElement('div');
    list.className = 'search-result-list';
    list.append(...cards);
    sec.append(heading, list);
    return sec;
  }

  function renderResults(data) {
    const beats = data.beats || [];
    const producers = data.producers || [];
    const query = data.query || '';
    const genre = data.genre_filter || '';

    clearResults();

    if (!query && !genre) return;

    if (!beats.length && !producers.length) {
      resultsBox.appendChild(statusBlock('search-empty', 'bi-search', 'No results found.'));
      return;
    }

    if (beats.length) {
      const cards = beats.map((b) => {
        const details = [
          b.genre || 'Unknown genre',
          b.bpm ? `${b.bpm} BPM` : '',
          b.key || '',
        ].filter(Boolean).join(' | ');
        return resultCard(
          urlFromTemplate(beatUrlTemplate, b.id),
          'bi-music-note-beamed',
          b.title,
          details,
          `${b.likes_count} likes`,
        );
      });
      resultsBox.appendChild(section('Beats', cards));
    }

    if (producers.length) {
      const cards = producers.map((p) => resultCard(
        urlFromTemplate(profileUrlTemplate, p.id),
        'bi-person-circle',
        p.username,
        `${p.followers_count} followers`,
        'Profile',
      ));
      resultsBox.appendChild(section('Creators', cards));
    }
  }

  async function runSearch(params) {
    clearResults();
    resultsBox.appendChild(statusBlock('search-loading', 'bi-arrow-repeat', 'Searching...'));
    try {
      const r = await fetch(`${apiUrl}?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      renderResults(await r.json());
    } catch (_) {
      clearResults();
      resultsBox.appendChild(statusBlock('search-error', 'bi-exclamation-triangle', 'Search failed. Please try again.'));
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    history.pushState({}, '', `?${params}`);
    await runSearch(params);
  });

  const initial = new URLSearchParams(window.location.search);
  if (initial.get('q') || initial.get('genre')) {
    runSearch(initial);
  }
}());
