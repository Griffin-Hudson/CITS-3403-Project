(function () {
  'use strict';
  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || '';

  const audio      = document.getElementById('bd-audio');
  const playBtn    = document.getElementById('bd-play');
  const restartBtn = document.getElementById('bd-restart');
  const back15Btn  = document.getElementById('bd-back15');
  const fwd15Btn   = document.getElementById('bd-fwd15');
  const muteBtn    = document.getElementById('bd-mute');
  const seekEl     = document.getElementById('bd-seek');
  const volEl      = document.getElementById('bd-vol');
  const timeEl     = document.getElementById('bd-time');
  const volLabel   = document.getElementById('bd-vol-label');
  const coverWrap  = playBtn && playBtn.closest('.beat-detail-cover-wrap');

  function fmtTime(s) {
    s = Math.floor(s || 0);
    return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  }

  function updateSeek() {
    if (!audio || !audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    seekEl.value = pct;
    seekEl.style.setProperty('--range-pct', pct);
    timeEl.textContent = fmtTime(audio.currentTime) + ' / ' + fmtTime(audio.duration);
  }

  if (audio) {
    audio.addEventListener('timeupdate', updateSeek);
    audio.addEventListener('loadedmetadata', updateSeek);
    audio.addEventListener('ended', function () {
      playBtn.classList.remove('is-playing');
      playBtn.style.opacity = '1';
      playBtn.querySelector('i').className = 'bi bi-play-fill';
    });

    playBtn.addEventListener('click', function () {
      if (audio.paused) {
        audio.play();
        playBtn.classList.add('is-playing');
        playBtn.style.opacity = '0';
        playBtn.querySelector('i').className = 'bi bi-pause-fill';
      } else {
        audio.pause();
        playBtn.classList.remove('is-playing');
        playBtn.style.opacity = '1';
        playBtn.querySelector('i').className = 'bi bi-play-fill';
      }
    });

    if (coverWrap) {
      coverWrap.addEventListener('mouseenter', function () {
        if (playBtn.classList.contains('is-playing')) playBtn.style.opacity = '1';
      });
      coverWrap.addEventListener('mouseleave', function () {
        if (playBtn.classList.contains('is-playing')) playBtn.style.opacity = '0';
      });
    }

    restartBtn.addEventListener('click', function () {
      audio.currentTime = 0;
      if (audio.paused) {
        audio.play();
        playBtn.classList.add('is-playing');
        playBtn.style.opacity = '0';
        playBtn.querySelector('i').className = 'bi bi-pause-fill';
      }
    });

    back15Btn.addEventListener('click', function () {
      audio.currentTime = Math.max(0, audio.currentTime - 15);
    });

    fwd15Btn.addEventListener('click', function () {
      audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 15);
    });

    seekEl.addEventListener('input', function () {
      const pct = parseFloat(seekEl.value);
      seekEl.style.setProperty('--range-pct', pct);
      if (audio.duration) audio.currentTime = (pct / 100) * audio.duration;
    });

    volEl.addEventListener('input', function () {
      const v = parseInt(volEl.value, 10);
      volEl.style.setProperty('--range-pct', v);
      audio.volume = v / 100;
      volLabel.textContent = v + '%';
      const icon = muteBtn.querySelector('i');
      if (v === 0) icon.className = 'bi bi-volume-mute-fill';
      else if (v < 50) icon.className = 'bi bi-volume-down-fill';
      else icon.className = 'bi bi-volume-up-fill';
    });

    const volPopover = document.getElementById('bd-vol-popover');

    muteBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      volPopover.hidden = !volPopover.hidden;
    });

    document.addEventListener('click', function (e) {
      if (!volPopover.hidden && !volPopover.contains(e.target) && e.target !== muteBtn) {
        volPopover.hidden = true;
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') volPopover.hidden = true;
    });
  }

  const likeBtn = document.getElementById('like-btn');
  if (likeBtn) {
    likeBtn.addEventListener('click', function () {
      const beatId = likeBtn.dataset.beatId;
      fetch(`/api/beats/${beatId}/like`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      })
        .then(r => r.json())
        .then(data => {
          likeBtn.classList.toggle('is-liked', data.liked);
          likeBtn.querySelector('i').className = data.liked ? 'bi bi-heart-fill' : 'bi bi-heart';
          document.getElementById('like-count').textContent = data.likes_count;
        });
    });
  }

  const followBtn = document.getElementById('follow-btn');
  if (followBtn) {
    followBtn.addEventListener('click', function () {
      const producerId = followBtn.dataset.producerId;
      fetch(`/api/producers/${producerId}/follow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      })
        .then(r => r.json())
        .then(data => {
          followBtn.classList.toggle('is-following', data.following);
          followBtn.querySelector('i').className = data.following
            ? 'bi bi-person-check-fill' : 'bi bi-person-plus';
          followBtn.childNodes[followBtn.childNodes.length - 1].textContent =
            data.following ? ' Following' : ' Follow';
        });
    });
  }
})();
