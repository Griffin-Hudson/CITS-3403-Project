const form = document.getElementById('search-form');
const resultsBox = document.getElementById('search-results');

if (form && resultsBox) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    history.pushState({}, '', `?${params}`);
    await runSearch(params);
  });

  // Auto-run if the page was loaded with a pre-filled query (e.g. shared link)
  const initial = new URLSearchParams(window.location.search);
  if (initial.get('q') || initial.get('genre')) {
    runSearch(initial);
  }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function runSearch(params) {
  resultsBox.innerHTML = `
    <div class="search-loading">
      <i class="bi bi-arrow-repeat"></i>
      Searching...
    </div>`;
  try {
    const r = await fetch(`/api/search?${params}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderResults(data);
  } catch (_) {
    resultsBox.innerHTML = `
      <div class="search-error">
        <i class="bi bi-exclamation-triangle"></i>
        <p>Search failed. Please try again.</p>
      </div>`;
  }
}

function renderResults(data) {
  const beats = data.beats || [];
  const producers = data.producers || [];
  const query = data.query || '';
  const genre = data.genre_filter || '';

  if ((query || genre) && !beats.length && !producers.length) {
    resultsBox.innerHTML = `
      <div class="search-empty">
        <i class="bi bi-search"></i>
        <p>No results found.</p>
      </div>`;
    return;
  }

  if (!query && !genre) {
    resultsBox.innerHTML = '';
    return;
  }

  let html = '';

  if (beats.length) {
    html += '<section class="search-section"><h2 class="search-section-title">Beats</h2><div class="search-result-list">';
    beats.forEach((b) => {
      html += `
        <a href="/beats/${b.id}" class="search-result-card">
          <span class="search-result-icon"><i class="bi bi-music-note-beamed"></i></span>
          <span class="search-result-main">
            <strong>${escHtml(b.title)}</strong>
            <span>
              ${escHtml(b.genre || 'Unknown genre')}
              ${b.bpm ? ` | ${b.bpm} BPM` : ''}
              ${b.key ? ` | ${escHtml(b.key)}` : ''}
            </span>
          </span>
          <span class="search-result-meta">${b.likes_count} likes</span>
        </a>`;
    });
    html += '</div></section>';
  }

  if (producers.length) {
    html += '<section class="search-section"><h2 class="search-section-title">Creators</h2><div class="search-result-list">';
    producers.forEach((p) => {
      html += `
        <a href="/profile/${p.id}" class="search-result-card">
          <span class="search-result-icon"><i class="bi bi-person-circle"></i></span>
          <span class="search-result-main">
            <strong>${escHtml(p.username)}</strong>
            <span>${p.followers_count} followers</span>
          </span>
          <span class="search-result-meta">Profile</span>
        </a>`;
    });
    html += '</div></section>';
  }

  resultsBox.innerHTML = html;
}
