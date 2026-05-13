'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const picInput   = document.getElementById('profilePictureInput');
  let   preview    = document.getElementById('profilePicturePreview');
  const uploadForm = document.getElementById('uploadForm');
  const bioArea    = document.getElementById('bio');
  const charCount  = document.getElementById('charCount');

  const MAX_SIZE = 5 * 1024 * 1024;

  if (picInput) {
    picInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (file.size > MAX_SIZE) {
        alert(`File must be under 5 MB (yours is ${(file.size / 1024 / 1024).toFixed(1)} MB).`);
        picInput.value = '';
        return;
      }

      const reader = new FileReader();
      reader.onload = (ev) => {
        // If the placeholder is a <div> (no existing avatar), swap it for an <img>
        if (preview.tagName !== 'IMG') {
          const img = document.createElement('img');
          img.className = preview.className;
          img.alt = '';
          preview.parentNode.replaceChild(img, preview);
          preview = img;
        }
        preview.src = ev.target.result;
        setTimeout(() => uploadForm.submit(), 300);
      };
      reader.readAsDataURL(file);
    });
  }

  if (bioArea && charCount) {
    charCount.textContent = bioArea.value.length;
    bioArea.addEventListener('input', () => {
      charCount.textContent = bioArea.value.length;
    });
  }

  // Label element acts as drag-drop target; syncs dropped file to the hidden input
  // and fires a synthetic 'change' so the existing validation/preview handler runs.
  const uploadLabel = document.querySelector('.btn-upload-file');
  if (uploadLabel && picInput) {
    uploadLabel.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      uploadLabel.classList.add('drag-over');
    });

    uploadLabel.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      uploadLabel.classList.remove('drag-over');
    });

    uploadLabel.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      uploadLabel.classList.remove('drag-over');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        picInput.files = files;
        picInput.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }
});
