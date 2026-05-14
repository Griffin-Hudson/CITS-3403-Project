// AJAX search — intercepts form submission and replaces #search-results without a
// full page reload.  The page remains fully functional without JS: the server renders
// initial results via Jinja2, and bookmarked/shared URLs work because history.pushState
// keeps the query string in sync.

const form       = document.getElementById('search-form');
const resultsBox = document.getElementById('search-results');

if (form && resultsBox) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    // Keep the URL bookmarkable and shareable
    history.pushState({}, '', `?${params}`);
    await runSearch(params);
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function runSearch(params) {
  resultsBox.innerHTML = '<div class="text-center py-4 text-muted"><i class="bi bi-arrow-repeat"></i> Searching…</div>';
  try {
    const r    = await fetch(`/api/search?${params}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderResults(data);
  } catch (_) {
    resultsBox.innerHTML = '<p class="text-danger">Search failed. Please try again.</p>';
  }
}

function renderResults(data) {
  const beats     = data.beats     || [];
  const producers = data.producers || [];
  const query     = data.query     || '';
  const genre     = data.genre_filter || '';

  if ((query || genre) && !beats.length && !producers.length) {
    resultsBox.innerHTML = '<p class="text-muted">No results found.</p>';
    return;
  }

  if (!query && !genre) {
    resultsBox.innerHTML = '';
    return;
  }

  let html = '';

  if (beats.length) {
    html += '<section class="mb-4"><h2 class="h5">Beats</h2><div class="list-group">';
    beats.forEach(b => {
      html += `
        <a href="/beats/${b.id}" class="list-group-item list-group-item-action">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <strong>${escHtml(b.title)}</strong>
              <div class="small text-muted">
                ${escHtml(b.genre || 'Unknown genre')}
                ${b.bpm ? ` | ${b.bpm} BPM` : ''}
                ${b.key ? ` | ${escHtml(b.key)}` : ''}
              </div>
            </div>
            <span class="badge text-bg-dark">${b.likes_count} likes</span>
          </div>
        </a>`;
    });
    html += '</div></section>';
  }

  if (producers.length) {
    html += '<section><h2 class="h5">Producers</h2><div class="list-group">';
    producers.forEach(p => {
      html += `
        <a href="/profile/${p.id}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
          <span>${escHtml(p.username)}</span>
          <span class="text-muted small">${p.followers_count} followers</span>
        </a>`;
    });
    html += '</div></section>';
  }

  resultsBox.innerHTML = html;
}
