/* ============================================================
   TUNEFEED — Upload page interactions
   - Live cover image preview from URL
   - Audio preview when a plausible audio URL is pasted
   - Mood quick-fill chips
   - Visual highlight on tier cards when their price has a value
   ============================================================ */
(function () {
  'use strict';

  /* ── Cover preview ───────────────────────────────────────
     Reads the chosen file with URL.createObjectURL so the
     image shows up without an upload round-trip.
     ──────────────────────────────────────────────────────── */
  const coverInput = document.getElementById('cover_file');
  const coverFrame = document.getElementById('cover-frame');
  const coverImg   = document.getElementById('cover-preview-img');
  const coverEmpty = document.getElementById('cover-empty');

  // remember last blob url so we can revoke it
  let lastCoverBlob = null;

  function showCoverFromFile(file) {
    if (!coverImg || !coverFrame || !coverEmpty) return;
    if (lastCoverBlob) {
      URL.revokeObjectURL(lastCoverBlob);
      lastCoverBlob = null;
    }
    if (!file) {
      coverImg.hidden = true;
      coverImg.removeAttribute('src');
      coverEmpty.hidden = false;
      coverFrame.classList.remove('has-cover');
      return;
    }
    lastCoverBlob = URL.createObjectURL(file);
    coverImg.onload = function () {
      coverImg.hidden = false;
      coverEmpty.hidden = true;
      coverFrame.classList.add('has-cover');
    };
    coverImg.onerror = function () {
      coverImg.hidden = true;
      coverEmpty.hidden = false;
      coverFrame.classList.remove('has-cover');
    };
    coverImg.src = lastCoverBlob;
  }

  if (coverInput) {
    coverInput.addEventListener('change', function () {
      showCoverFromFile(coverInput.files && coverInput.files[0]);
    });
  }

  /* ── Audio preview ───────────────────────────────────────
     Custom themed player: play/pause button, draggable
     progress bar, current/total time. The native <audio>
     element is kept as the source of truth for playback but
     hidden via CSS.
     ──────────────────────────────────────────────────────── */
  const audioInput  = document.getElementById('audio_file');
  const audioBox    = document.getElementById('audio-preview');
  const audioPlayer = document.getElementById('audio-preview-player');
  const playBtn     = document.getElementById('audio-play-btn');
  const trackEl     = document.getElementById('audio-player-track');
  const fillEl      = document.getElementById('audio-player-fill');
  const thumbEl     = document.getElementById('audio-player-thumb');
  const nameEl      = document.getElementById('audio-player-name');
  const curEl       = document.getElementById('audio-player-current');
  const durEl       = document.getElementById('audio-player-duration');

  let lastAudioBlob = null;

  function fmtTime(s) {
    if (!isFinite(s) || s < 0) return '0:00';
    var m = Math.floor(s / 60);
    var sec = Math.floor(s % 60);
    return m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  function setPercent(p) {
    p = Math.max(0, Math.min(100, p));
    if (fillEl)  fillEl.style.width  = p + '%';
    if (thumbEl) thumbEl.style.left  = p + '%';
  }

  function setPlayIcon(playing) {
    if (!playBtn) return;
    var icon = playBtn.querySelector('i');
    if (icon) icon.className = playing ? 'bi bi-pause-fill' : 'bi bi-play-fill';
    playBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
    if (audioBox) audioBox.classList.toggle('is-playing', playing);
  }

  function setAudioPreviewFromFile(file) {
    if (!audioBox || !audioPlayer) return;
    if (lastAudioBlob) {
      URL.revokeObjectURL(lastAudioBlob);
      lastAudioBlob = null;
    }
    if (!file) {
      audioBox.hidden = true;
      audioPlayer.removeAttribute('src');
      audioPlayer.load();
      setPlayIcon(false);
      setPercent(0);
      if (curEl) curEl.textContent = '0:00';
      if (durEl) durEl.textContent = '0:00';
      return;
    }
    lastAudioBlob = URL.createObjectURL(file);
    audioPlayer.src = lastAudioBlob;
    audioBox.hidden = false;
    if (nameEl) nameEl.textContent = file.name;
    if (curEl) curEl.textContent = '0:00';
    if (durEl) durEl.textContent = '0:00';
    setPercent(0);
    setPlayIcon(false);
    audioPlayer.onerror = function () { audioBox.hidden = true; };
  }

  if (audioInput) {
    audioInput.addEventListener('change', function () {
      setAudioPreviewFromFile(audioInput.files && audioInput.files[0]);
    });
  }

  if (playBtn && audioPlayer) {
    playBtn.addEventListener('click', function () {
      if (audioPlayer.paused) audioPlayer.play();
      else audioPlayer.pause();
    });
  }

  if (audioPlayer) {
    audioPlayer.addEventListener('play',  function () { setPlayIcon(true);  });
    audioPlayer.addEventListener('pause', function () { setPlayIcon(false); });
    audioPlayer.addEventListener('ended', function () {
      setPlayIcon(false);
      setPercent(0);
      if (curEl) curEl.textContent = '0:00';
    });
    audioPlayer.addEventListener('loadedmetadata', function () {
      if (durEl) durEl.textContent = fmtTime(audioPlayer.duration);
    });
    audioPlayer.addEventListener('timeupdate', function () {
      if (curEl) curEl.textContent = fmtTime(audioPlayer.currentTime);
      if (audioPlayer.duration) {
        setPercent((audioPlayer.currentTime / audioPlayer.duration) * 100);
      }
    });
  }

  if (trackEl && audioPlayer) {
    var dragging = false;
    function seekFromEvent(e) {
      if (!audioPlayer.duration) return;
      var rect = trackEl.getBoundingClientRect();
      var clientX = (e.touches && e.touches[0]) ? e.touches[0].clientX : e.clientX;
      var pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      audioPlayer.currentTime = pct * audioPlayer.duration;
    }
    trackEl.addEventListener('mousedown', function (e) { dragging = true; seekFromEvent(e); });
    document.addEventListener('mousemove', function (e) { if (dragging) seekFromEvent(e); });
    document.addEventListener('mouseup',   function ()  { dragging = false; });
    trackEl.addEventListener('touchstart', function (e) { dragging = true; seekFromEvent(e); }, { passive: true });
    trackEl.addEventListener('touchmove',  function (e) { if (dragging) seekFromEvent(e); }, { passive: true });
    trackEl.addEventListener('touchend',   function ()  { dragging = false; });
  }

  /* ── Drop zone wiring ────────────────────────────────────
     Handles click-to-browse and drag-and-drop for file inputs.
     ──────────────────────────────────────────────────────── */
  function acceptsFile(input, file) {
    var accept = (input.accept || '').trim();
    if (!accept) return true;
    var name = file.name.toLowerCase();
    var mime = (file.type || '').toLowerCase();
    return accept.split(',').some(function (p) {
      p = p.trim().toLowerCase();
      if (p.startsWith('.')) return name.endsWith(p);
      if (p.endsWith('/*')) return mime.startsWith(p.slice(0, -1));
      return mime === p;
    });
  }

  function wireDropzone(zoneId, input, nameId) {
    var zone   = document.getElementById(zoneId);
    var nameEl = nameId ? document.getElementById(nameId) : null;
    if (!zone || !input) return;

    var fileClass = (zoneId === 'cover-frame') ? 'has-cover' : 'has-file';

    function markFile(file) {
      if (!file) return;
      if (nameEl) { nameEl.textContent = file.name; nameEl.hidden = false; }
      zone.classList.add(fileClass);
    }

    zone.addEventListener('click', function (e) {
      if (e.target === input) return;
      input.click();
    });

    zone.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });

    zone.addEventListener('dragover', function (e) {
      e.preventDefault();
      zone.classList.add('is-over');
    });

    zone.addEventListener('dragleave', function (e) {
      if (!zone.contains(e.relatedTarget)) zone.classList.remove('is-over');
    });

    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      zone.classList.remove('is-over');
      var files = e.dataTransfer && e.dataTransfer.files;
      if (!files || !files[0]) return;
      if (!acceptsFile(input, files[0])) return;
      var dt = new DataTransfer();
      dt.items.add(files[0]);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });

    input.addEventListener('change', function () {
      markFile(input.files && input.files[0]);
    });
  }

  wireDropzone('audio-drop', audioInput, 'audio-drop-name');
  wireDropzone('cover-frame', coverInput, null);

  /* ── Multi-tag system ────────────────────────────────────
     Hidden input stores comma-separated tags. Visual box
     shows pill spans + a transparent text input. Chips
     toggle tags on/off instead of overwriting.
     ──────────────────────────────────────────────────────── */
  const hiddenInput = document.getElementById('mood_tag');
  const tagsBox     = document.getElementById('tags-box');
  const tagsType    = document.getElementById('tags-type');
  const chipRow     = document.querySelector('.upload-chip-row[data-target="mood_tag"]');
  const chips       = chipRow ? chipRow.querySelectorAll('.upload-chip') : [];
  const MAX_TAGS    = 5;

  function getTags() {
    const v = (hiddenInput ? hiddenInput.value : '').trim();
    return v ? v.split(',').map(function (t) { return t.trim(); }).filter(Boolean) : [];
  }

  function setTags(tags) {
    if (!hiddenInput) return;
    hiddenInput.value = tags.join(',');
    renderTags(tags);
    syncChips(tags);
  }

  function escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderTags(tags) {
    if (!tagsBox || !tagsType) return;
    tagsBox.querySelectorAll('.upload-tag-pill').forEach(function (p) { p.remove(); });
    tags.forEach(function (tag) {
      const pill = document.createElement('span');
      pill.className = 'upload-tag-pill';
      const label = document.createElement('span');
      label.textContent = tag;
      const rm = document.createElement('button');
      rm.type = 'button';
      rm.className = 'upload-tag-remove';
      rm.setAttribute('aria-label', 'Remove ' + tag);
      rm.innerHTML = '&times;';
      rm.addEventListener('click', function () {
        setTags(getTags().filter(function (t) { return t !== tag; }));
      });
      pill.appendChild(label);
      pill.appendChild(rm);
      tagsBox.insertBefore(pill, tagsType);
    });
  }

  function syncChips(tags) {
    const lower = tags.map(function (t) { return t.toLowerCase(); });
    chips.forEach(function (chip) {
      const v = (chip.dataset.value || '').toLowerCase();
      chip.classList.toggle('is-active', v && lower.indexOf(v) !== -1);
    });
  }

  function addTag(raw) {
    const val = raw.trim().replace(/,/g, '');
    if (!val) return;
    const tags = getTags();
    if (tags.length >= MAX_TAGS) return;
    const lower = tags.map(function (t) { return t.toLowerCase(); });
    if (lower.indexOf(val.toLowerCase()) !== -1) return;
    setTags(tags.concat(val));
  }

  if (tagsType) {
    tagsType.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ',') && tagsType.value.trim()) {
        e.preventDefault();
        addTag(tagsType.value);
        tagsType.value = '';
      } else if (e.key === 'Backspace' && !tagsType.value) {
        const tags = getTags();
        if (tags.length) setTags(tags.slice(0, -1));
      }
    });
    tagsType.addEventListener('blur', function () {
      if (tagsType.value.trim()) {
        addTag(tagsType.value);
        tagsType.value = '';
      }
    });
  }

  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      const val = chip.dataset.value || '';
      const tags = getTags();
      const lower = tags.map(function (t) { return t.toLowerCase(); });
      if (lower.indexOf(val.toLowerCase()) !== -1) {
        setTags(tags.filter(function (t) { return t.toLowerCase() !== val.toLowerCase(); }));
      } else {
        addTag(val);
      }
    });
  });

  if (tagsBox) {
    tagsBox.addEventListener('click', function () { tagsType && tagsType.focus(); });
  }

  if (hiddenInput && hiddenInput.value) {
    renderTags(getTags());
    syncChips(getTags());
  }

  /* ── Tier card highlighting ──────────────────────────────
     Adds .is-active to a tier when its price input has a
     value, so the user can see at a glance which tiers will
     be active on their listing.
     ──────────────────────────────────────────────────────── */
  function bindTierHighlight(inputId, tierSelector) {
    const input = document.getElementById(inputId);
    const tier  = document.querySelector(tierSelector);
    if (!input || !tier) return;

    function update() {
      const v = parseFloat(input.value);
      tier.classList.toggle('is-active', !Number.isNaN(v) && v > 0);
    }
    input.addEventListener('input', update);
    update();
  }

  bindTierHighlight('price',           '.upload-tier-basic');
  bindTierHighlight('premium_price',   '.upload-tier-premium');
  bindTierHighlight('exclusive_price', '.upload-tier-exclusive');

  /* ── Currency symbol sync ───────────────────────────────────
     Updates the prefix symbol on all three price inputs whenever
     the currency dropdown changes. AUD/USD share $; EUR uses €;
     GBP uses £.
     ─────────────────────────────────────────────────────────── */
  var CURRENCY_SYMBOLS = { AUD: '$', USD: '$', EUR: '€', GBP: '£' };
  var currencySelect = document.getElementById('currency');

  function updateCurrencySymbols() {
    var sym = CURRENCY_SYMBOLS[currencySelect.value] || '$';
    document.querySelectorAll('.price-currency-sym').forEach(function (el) {
      el.textContent = sym;
    });
  }

  if (currencySelect) {
    currencySelect.addEventListener('change', updateCurrencySymbols);
  }
})();

/* ============================================================
   Genre combobox — searchable + free-text genre field
   ============================================================ */
(function () {
  'use strict';

  const GENRE_GROUPS = [
    { label: 'Urban',              genres: ['Hip-Hop', 'Trap', 'Drill', 'R&B / Soul', 'Afrobeats', 'Dancehall'] },
    { label: 'Electronic',         genres: ['Electronic / EDM', 'House', 'Techno', 'Drum & Bass', 'Ambient', 'Lo-Fi'] },
    { label: 'Pop & Global',       genres: ['Pop', 'Latin', 'Reggaeton', 'World Music'] },
    { label: 'Live & Traditional', genres: ['Jazz', 'Blues', 'Funk', 'Gospel', 'Classical', 'Rock', 'Alternative', 'Country'] },
    { label: 'Specialty',          genres: ['Cinematic', 'Experimental', 'Soundtrack'] },
  ];

  const hiddenEl = document.getElementById('genre');
  const comboEl  = document.getElementById('genre-combo');
  const inputEl  = document.getElementById('genre-input');
  const clearEl  = document.getElementById('genre-clear');
  const dropEl   = document.getElementById('genre-dropdown');

  if (!hiddenEl || !inputEl || !dropEl) return;

  let isOpen    = false;
  let highlight = -1;
  let flatOpts  = [];
  let prevVal   = hiddenEl.value;

  function allGenres() {
    return GENRE_GROUPS.reduce((acc, g) => acc.concat(g.genres), []);
  }

  function open() {
    if (isOpen) return;
    isOpen = true;
    prevVal = hiddenEl.value;
    comboEl.classList.add('is-open');
    inputEl.setAttribute('aria-expanded', 'true');
    renderList(inputEl.value.trim());
    dropEl.hidden = false;
    const sel = dropEl.querySelector('.is-selected');
    if (sel) setTimeout(() => { sel.scrollIntoView({ block: 'nearest' }); }, 0);
  }

  function close(accept) {
    if (!isOpen) return;
    isOpen = false;
    highlight = -1;
    flatOpts  = [];
    comboEl.classList.remove('is-open');
    inputEl.setAttribute('aria-expanded', 'false');
    dropEl.hidden = true;
    if (!accept) inputEl.value = prevVal;
  }

  function commit(val) {
    hiddenEl.value = val;
    inputEl.value  = val;
    clearEl.hidden = !val;
    close(true);
  }

  function renderList(q) {
    dropEl.innerHTML = '';
    flatOpts = [];
    const ql = (q || '').toLowerCase();
    let hasAny = false;

    GENRE_GROUPS.forEach((group) => {
      const matches = ql
        ? group.genres.filter((g) => g.toLowerCase().indexOf(ql) !== -1)
        : group.genres;
      if (!matches.length) return;

      const hdr = document.createElement('li');
      hdr.className = 'genre-group-header';
      hdr.textContent = group.label;
      hdr.setAttribute('aria-hidden', 'true');
      dropEl.appendChild(hdr);

      matches.forEach((g) => {
        hasAny = true;
        const idx = flatOpts.length;
        flatOpts.push({ value: g, custom: false });
        dropEl.appendChild(makeItem(g, idx, false));
      });
    });

    /* Custom entry if typed value has no exact match */
    if (q) {
      const exact = allGenres().some((g) => g.toLowerCase() === ql);
      if (!exact) {
        const idx = flatOpts.length;
        flatOpts.push({ value: q, custom: true });
        dropEl.appendChild(makeItem(q, idx, true));
        hasAny = true;
      }
    }

    if (!hasAny) {
      const empty = document.createElement('li');
      empty.className = 'genre-empty';
      empty.textContent = 'No genres match — keep typing to use a custom one.';
      dropEl.appendChild(empty);
    }

    highlight = -1;
    refreshHighlight();
  }

  function makeItem(value, idx, custom) {
    const li = document.createElement('li');
    li.className = 'genre-item' + (custom ? ' is-custom' : '');
    li.setAttribute('role', 'option');
    li.dataset.idx = idx;

    const icon = document.createElement('i');
    icon.className = (custom ? 'bi bi-plus-circle-dotted' : 'bi bi-music-note') + ' genre-lead';

    const span = document.createElement('span');
    span.textContent = custom ? 'Use “' + value + '”' : value;

    li.appendChild(icon);
    li.appendChild(span);

    if (!custom && hiddenEl.value === value) {
      li.classList.add('is-selected');
      const check = document.createElement('i');
      check.className = 'bi bi-check2 genre-check';
      li.appendChild(check);
    }

    li.addEventListener('mousedown', (e) => {
      e.preventDefault();
      commit(value);
    });
    li.addEventListener('mousemove', () => { setHL(idx); });
    return li;
  }

  function setHL(idx) {
    highlight = idx;
    refreshHighlight();
  }

  function refreshHighlight() {
    dropEl.querySelectorAll('.genre-item').forEach((el) => {
      el.classList.toggle('is-highlighted', parseInt(el.dataset.idx, 10) === highlight);
    });
  }

  function stepHL(dir) {
    const next = highlight + dir;
    if (next < 0 || next >= flatOpts.length) return;
    setHL(next);
    const el = dropEl.querySelector('[data-idx="' + highlight + '"]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }

  inputEl.addEventListener('focus', () => { open(); });

  inputEl.addEventListener('input', () => {
    clearEl.hidden = !inputEl.value;
    renderList(inputEl.value.trim());
    if (!isOpen) open();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen) { open(); return; }
      stepHL(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      stepHL(-1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (!isOpen) { open(); return; }
      if (highlight >= 0 && flatOpts[highlight]) {
        commit(flatOpts[highlight].value);
      } else if (inputEl.value.trim()) {
        commit(inputEl.value.trim());
      }
    } else if (e.key === 'Escape') {
      if (isOpen) close(false);
    } else if (e.key === 'Tab') {
      if (isOpen) {
        if (highlight >= 0 && flatOpts[highlight]) {
          commit(flatOpts[highlight].value);
        } else if (inputEl.value.trim()) {
          hiddenEl.value = inputEl.value.trim();
          clearEl.hidden = false;
        }
        close(true);
      }
    }
  });

  inputEl.addEventListener('blur', () => {
    setTimeout(() => {
      if (!isOpen) return;
      const v = inputEl.value.trim();
      if (v) { hiddenEl.value = v; clearEl.hidden = false; }
      else   { hiddenEl.value = ''; clearEl.hidden = true; }
      close(true);
    }, 160);
  });

  clearEl.addEventListener('mousedown', (e) => {
    e.preventDefault();
    commit('');
    inputEl.focus();
  });

  /* Click on icon or chevron area toggles the panel */
  comboEl.addEventListener('mousedown', (e) => {
    if (inputEl.contains(e.target) || clearEl.contains(e.target)) return;
    e.preventDefault();
    if (isOpen) { close(true); inputEl.blur(); }
    else { inputEl.focus(); }
  });
}());
