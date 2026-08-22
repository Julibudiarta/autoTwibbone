(function () {
  const $ = (id) => document.getElementById(id);

  // ---- Upload form elements ----
  const uploadForm = $('uploadForm');
  const twibbonInput = $('twibbonFile');
  const dropTwibbon = $('drop-twibbon');
  const twibbonPreview = $('twibbon-preview');
  const twibbonName = $('twibbon-name');
  const clearTwibbonBtn = $('clear-twibbon');
  const nonPngBadge = $('twibbon-non-png-badge');
  const openColorRemoverBtn = $('open-color-remover-btn');
  const twibbonHint = $('twibbon-hint');

  const userFilesInput = $('userFiles');
  const dropPhotos = $('drop-photos');
  const photosPreview = $('photos-preview');
  const photosCount = $('photos-count');
  const clearPhotosBtn = $('clear-photos');

  const processBtn = $('processBtn');
  const loadingIndicator = $('loadingIndicator');
  const errorMessage = $('errorMessage');

  const resultSection = $('resultSection');
  const resultGrid = $('resultGrid');
  const downloadZipBtn = $('downloadZipBtn');

  // ---- History elements ----
  const historyToggleBtn = $('historyToggleBtn');
  const historyOverlay = $('historyOverlay');
  const historyPanel = $('historyPanel');
  const closeHistoryBtn = $('closeHistoryBtn');
  const historyList = $('historyList');
  const clearHistoryBtn = $('clearHistoryBtn');

  // ---- Position editor elements ----
  const editorOverlay = $('positionEditorOverlay');
  const editorStage = $('editorStage');
  const editorPhoto = $('editorPhoto');
  const editorFrame = $('editorFrame');
  const editorZoom = $('editorZoom');
  const editorStatus = $('editorStatus');
  const editorSaveBtn = $('editorSave');
  const editorCancelBtn = $('editorCancel');
  const editorResetBtn = $('editorReset');

  let editorState = null;
  let dragging = false;
  let dragStart = null;

  // ---- Color remover elements ----
  const colorRemoverOverlay = $('colorRemoverOverlay');
  const colorRemoverClose = $('colorRemoverClose');
  const colorPickerCanvas = $('colorPickerCanvas');
  const offscreenCanvas = $('offscreenCanvas');
  const colorCursorDot = $('colorCursorDot');
  const eyedropperToggle = $('eyedropperToggle');
  const eyedropperLabel = $('eyedropperLabel');
  const eyedropperIcon = $('eyedropperIcon');
  const colorSwatches = $('colorSwatches');
  const noColorMsg = $('noColorMsg');
  const hexColorInput = $('hexColorInput');
  const nativeColorInput = $('nativeColorInput');
  const hexPreviewDot = $('hexPreviewDot');
  const addColorBtn = $('addColorBtn');
  const toleranceSlider = $('toleranceSlider');
  const toleranceValue = $('toleranceValue');
  const previewRemoveBtn = $('previewRemoveBtn');
  const resetPreviewBtn = $('resetPreviewBtn');
  const colorRemoverStatus = $('colorRemoverStatus');
  const applyColorRemoveBtn = $('applyColorRemoveBtn');

  // ── Color remover state ──
  const crState = {
    originalFile: null,       // File object — the raw twibbon file
    originalImageData: null,  // ImageData of the original (for canvas reset)
    colors: [],               // [{ hex, r, g, b }] — selected colors
    activeColor: null,        // hex of currently active swatch
    eyedropperActive: false,
    isPreviewing: false,
    convertedBlob: null,      // last result from server
    convertedUrl: null,
    convertedFilename: null,
    convertedStoragePath: null,
  };

  // ================= Helpers =================
  function clamp(v, min, max) { return Math.min(Math.max(v, min), max); }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorMessage.classList.remove('hidden');
  }

  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    if (h.length !== 6) return null;
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }

  function rgbToHex(r, g, b) {
    return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
  }

  /** Contrast colour (black or white) for a given background hex */
  function contrastColor(hex) {
    const rgb = hexToRgb(hex);
    if (!rgb) return '#000';
    const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
    return luminance > 0.55 ? '#000000' : '#ffffff';
  }

  function bindDropzone(input, onChange) {
    const zone = input.closest('.dropzone');
    input.addEventListener('change', onChange);
    ['dragover', 'dragenter'].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
      })
    );
    ['dragleave', 'dragend'].forEach((evt) =>
      zone.addEventListener(evt, () => zone.classList.remove('drag-over'))
    );
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        onChange();
      }
    });
  }

  // ================= Twibbon dropzone =================
  // Elemen preview thumbnail
  let twibbonThumbEl = null;

  function showTwibbonThumbnail(file) {
    // Tampilkan thumbnail gambar pakai FileReader (100% client-side)
    const reader = new FileReader();
    reader.onload = (e) => {
      if (!twibbonThumbEl) {
        twibbonThumbEl = document.createElement('img');
        twibbonThumbEl.className = 'w-20 h-20 object-contain rounded-xl border-2 border-white shadow-md';
        twibbonThumbEl.alt = 'Preview twibbon';
        // Sisipkan sebelum twibbonName
        twibbonPreview.insertBefore(twibbonThumbEl, twibbonPreview.firstChild);
      }
      twibbonThumbEl.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  bindDropzone(twibbonInput, () => {
    if (!twibbonInput.files.length) return;
    const file = twibbonInput.files[0];
    twibbonName.textContent = file.name;
    twibbonPreview.classList.remove('hidden');
    showTwibbonThumbnail(file);

    const isPng = file.name.toLowerCase().endsWith('.png') || file.type === 'image/png';
    nonPngBadge.classList.toggle('hidden', isPng);
    openColorRemoverBtn.classList.toggle('hidden', false); // always show once file loaded
    twibbonHint.classList.toggle('hidden', isPng);

    // Reset any previous conversion when a new file is selected
    crState.originalFile = file;
    crState.convertedBlob = null;
    crState.convertedUrl = null;
    crState.convertedFilename = null;
    crState.convertedStoragePath = null;
  });

  clearTwibbonBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    twibbonInput.value = '';
    twibbonPreview.classList.add('hidden');
    nonPngBadge.classList.add('hidden');
    openColorRemoverBtn.classList.add('hidden');
    twibbonHint.classList.add('hidden');
    if (twibbonThumbEl) { twibbonThumbEl.src = ''; }
    crState.originalFile = null;
    crState.convertedBlob = null;
    crState.convertedUrl = null;
  });

  // ================= Photos dropzone =================
  bindDropzone(userFilesInput, () => {
    if (!userFilesInput.files.length) return;
    const files = Array.from(userFilesInput.files);
    photosCount.textContent = `${files.length} foto dipilih`;
    photosPreview.classList.remove('hidden');

    // Tampilkan grid thumbnail mini dari foto yang dipilih (max 6)
    let thumbGrid = photosPreview.querySelector('.thumb-grid');
    if (!thumbGrid) {
      thumbGrid = document.createElement('div');
      thumbGrid.className = 'thumb-grid flex flex-wrap gap-1 justify-center mt-2 max-h-20 overflow-hidden';
      photosPreview.insertBefore(thumbGrid, photosPreview.querySelector('#clear-photos'));
    }
    thumbGrid.innerHTML = '';
    files.slice(0, 6).forEach((f) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const img = document.createElement('img');
        img.src = ev.target.result;
        img.className = 'w-12 h-12 object-cover rounded-lg border-2 border-white shadow';
        img.alt = f.name;
        thumbGrid.appendChild(img);
      };
      reader.readAsDataURL(f);
    });
    if (files.length > 6) {
      const more = document.createElement('span');
      more.className = 'w-12 h-12 rounded-lg flex items-center justify-center text-xs font-bold border-2 border-white shadow';
      more.style.cssText = 'background:var(--plum); color:var(--marigold);';
      more.textContent = `+${files.length - 6}`;
      thumbGrid.appendChild(more);
    }
  });

  clearPhotosBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    userFilesInput.value = '';
    photosPreview.classList.add('hidden');
    const thumbGrid = photosPreview.querySelector('.thumb-grid');
    if (thumbGrid) thumbGrid.innerHTML = '';
  });

  // ================= Submit upload =================
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMessage.classList.add('hidden');

    if (!twibbonInput.files.length || !userFilesInput.files.length) {
      showError('Lengkapi dulu Twibbon dan minimal satu foto ya.');
      return;
    }

    const formData = new FormData();

    // If we have a converted twibbon blob, use it instead of the original file
    if (crState.convertedBlob) {
      const convertedFile = new File([crState.convertedBlob], crState.convertedFilename || 'twibbon_converted.png', { type: 'image/png' });
      formData.append('twibbon', convertedFile);
    } else {
      formData.append('twibbon', twibbonInput.files[0]);
    }

    Array.from(userFilesInput.files).forEach((f) => formData.append('user_images', f));

    processBtn.disabled = true;
    loadingIndicator.classList.remove('hidden');

    try {
      const res = await fetch('/upload', { method: 'POST', body: formData });
      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await res.text();
        console.error('Non-JSON response:', text.slice(0, 300));
        throw new Error('Server mengembalikan error. Silakan cek koneksi/konsol server.');
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Terjadi kesalahan saat memproses.');

      renderResults(data);
      resultSection.classList.remove('hidden');
      resultSection.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      showError(err.message);
    } finally {
      processBtn.disabled = false;
      loadingIndicator.classList.add('hidden');
    }
  });

  // ================= Render results grid =================
  function renderResults(batch) {
    resultGrid.innerHTML = '';

    if (batch.zip_url) {
      downloadZipBtn.href = batch.zip_url;
      downloadZipBtn.classList.remove('hidden');
    } else {
      downloadZipBtn.classList.add('hidden');
    }

    batch.files.forEach((file) => {
      const card = document.createElement('div');
      card.className = 'result-card p-3 flex flex-col';
      const dlUrl = file.download_url || `/download/${batch.uid}/${batch.batch_id}/${file.filename}`;
      card.innerHTML = `
        <div class="rounded-xl overflow-hidden mb-3" style="background:var(--paper-dim)">
          <img src="${file.result_url}" alt="Hasil twibbon ${file.original}" class="w-full h-48 object-contain">
        </div>
        <p class="text-xs font-mono truncate mb-3" style="color:var(--ink-muted)" title="${file.original}">${file.original}</p>
        <div class="flex gap-2 mt-auto">
          <button type="button" class="edit-position-btn flex-1 text-xs font-semibold py-2 rounded-full" style="background:var(--paper-dim); color:var(--plum)">✏️ Atur Posisi</button>
          <a href="${dlUrl}" download="${file.original}" class="download-link flex-1 text-xs font-semibold py-2 rounded-full text-center" style="background:var(--marigold); color:var(--plum-deep)">⬇ Unduh</a>
        </div>
      `;
      const img = card.querySelector('img');
      const editBtn = card.querySelector('.edit-position-btn');
      editBtn.addEventListener('click', () => openEditor(batch, file, img));
      resultGrid.appendChild(card);
    });
  }

  // ================= Position editor =================
  async function openEditor(batch, file, imgEl) {
    editorState = {
      uid: batch.uid,
      batchId: batch.batch_id,
      filename: file.filename,
      posX: file.pos_x ?? 0.5,
      posY: file.pos_y ?? 0.5,
      zoom: file.zoom ?? 1.0,
      imgEl,
    };

    const previewName = file.preview_input || file.user_input;
    editorPhoto.src = file.preview_url || `/source_photo/${batch.uid}/${batch.batch_id}/${previewName}`;
    editorFrame.src = batch.twibbon_url || `/source_twibbon/${batch.uid}/${batch.batch_id}`;
    editorZoom.value = editorState.zoom;
    editorStatus.classList.add('hidden');

    await new Promise((resolve) => {
      if (editorFrame.complete && editorFrame.naturalWidth) return resolve();
      editorFrame.onload = resolve;
      editorFrame.onerror = resolve;
    });

    const w = editorFrame.naturalWidth || 1;
    const h = editorFrame.naturalHeight || 1;
    editorStage.style.aspectRatio = `${w} / ${h}`;

    applyEditorTransform();
    editorOverlay.classList.remove('hidden');
  }

  function applyEditorTransform() {
    if (!editorState) return;
    const { posX, posY, zoom } = editorState;
    editorPhoto.style.objectPosition = `${posX * 100}% ${posY * 100}%`;
    editorPhoto.style.transformOrigin = `${posX * 100}% ${posY * 100}%`;
    editorPhoto.style.transform = `scale(${zoom})`;
  }

  editorZoom.addEventListener('input', () => {
    if (!editorState) return;
    editorState.zoom = parseFloat(editorZoom.value);
    applyEditorTransform();
  });

  editorResetBtn.addEventListener('click', () => {
    if (!editorState) return;
    editorState.posX = 0.5;
    editorState.posY = 0.5;
    editorState.zoom = 1.0;
    editorZoom.value = 1.0;
    applyEditorTransform();
  });

  editorCancelBtn.addEventListener('click', closeEditor);

  function closeEditor() {
    editorOverlay.classList.add('hidden');
    editorState = null;
    dragging = false;
  }

  editorStage.addEventListener('pointerdown', (e) => {
    if (!editorState) return;
    dragging = true;
    dragStart = { x: e.clientX, y: e.clientY, posX: editorState.posX, posY: editorState.posY };
    editorStage.setPointerCapture(e.pointerId);
    editorStage.classList.add('cursor-grabbing');
  });

  editorStage.addEventListener('pointermove', (e) => {
    if (!dragging || !editorState) return;
    const rect = editorStage.getBoundingClientRect();
    const dx = (e.clientX - dragStart.x) / rect.width;
    const dy = (e.clientY - dragStart.y) / rect.height;
    editorState.posX = clamp(dragStart.posX - dx, 0, 1);
    editorState.posY = clamp(dragStart.posY - dy, 0, 1);
    applyEditorTransform();
  });

  ['pointerup', 'pointercancel', 'pointerleave'].forEach((evt) => {
    editorStage.addEventListener(evt, () => {
      dragging = false;
      editorStage.classList.remove('cursor-grabbing');
    });
  });

  function renderCanvasReposition(userImg, twibbonImg, posX, posY, zoom) {
    return new Promise((resolve, reject) => {
      try {
        const W = twibbonImg.naturalWidth || 2048;
        const H = twibbonImg.naturalHeight || 2048;
        const uW = userImg.naturalWidth || 2048;
        const uH = userImg.naturalHeight || 2048;

        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        const wRatio = W / uW;
        const hRatio = H / uH;
        const scale = Math.max(wRatio, hRatio) * Math.max(1.0, zoom);

        const targetW = uW * scale;
        const targetH = uH * scale;

        const slackX = targetW - W;
        const slackY = targetH - H;

        const left = -(slackX * Math.min(Math.max(posX, 0), 1));
        const top = -(slackY * Math.min(Math.max(posY, 0), 1));

        ctx.clearRect(0, 0, W, H);
        ctx.drawImage(userImg, left, top, targetW, targetH);
        ctx.drawImage(twibbonImg, 0, 0, W, H);

        // Export sebagai PNG Lossless Full HD jernih
        const dataUrl = canvas.toDataURL('image/png');
        resolve(dataUrl);
      } catch (err) {
        reject(err);
      }
    });
  }

  editorSaveBtn.addEventListener('click', async () => {
    if (!editorState) return;
    editorStatus.classList.remove('hidden');
    editorStatus.style.color = 'var(--ink-muted)';
    editorStatus.textContent = 'Menyimpan posisi...';
    editorSaveBtn.disabled = true;

    try {
      let resultUrl = null;
      let downloadUrl = null;

      // Jika gambar berformat data: (Browser Mode / Vercel Stateless),
      // render posisi langsung di browser (100% instan, bebas error RAM 404!)
      const isDataUrl = (editorPhoto.src && editorPhoto.src.startsWith('data:')) ||
                        (editorFrame.src && editorFrame.src.startsWith('data:'));

      if (isDataUrl) {
        resultUrl = await renderCanvasReposition(
          editorPhoto,
          editorFrame,
          editorState.posX,
          editorState.posY,
          editorState.zoom
        );
        downloadUrl = resultUrl;
      } else {
        // Coba via server (Local / Supabase)
        try {
          const res = await fetch('/reposition', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              batch_id: editorState.batchId,
              filename: editorState.filename,
              pos_x: editorState.posX,
              pos_y: editorState.posY,
              zoom: editorState.zoom,
            }),
          });
          if (res.ok) {
            const contentType = res.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
              const data = await res.json();
              resultUrl = data.result_url;
              downloadUrl = data.download_url;
            }
          }
        } catch (serverErr) {
          console.warn('[reposition fallback to canvas]', serverErr);
        }

        // Fallback jika server mengembalikan 404 / file RAM hilang
        if (!resultUrl) {
          resultUrl = await renderCanvasReposition(
            editorPhoto,
            editorFrame,
            editorState.posX,
            editorState.posY,
            editorState.zoom
          );
          downloadUrl = resultUrl;
        }
      }

      // Simpan koordinat baru di editorState
      editorState.imgEl.src = resultUrl;
      if (downloadUrl) {
        const cardDlLink = editorState.imgEl.closest('.result-card')?.querySelector('.download-link');
        if (cardDlLink) cardDlLink.href = downloadUrl;
      }

      editorStatus.style.color = '#1a7f4c';
      editorStatus.textContent = 'Posisi tersimpan!';
      setTimeout(closeEditor, 400);
    } catch (err) {
      editorStatus.style.color = 'var(--coral)';
      editorStatus.textContent = err.message || 'Gagal menyimpan posisi.';
    } finally {
      editorSaveBtn.disabled = false;
    }
  });

  // ================= History panel =================
  async function loadHistory() {
    historyList.innerHTML = `<p class="text-xs" style="color:var(--ink-muted)">Memuat riwayat...</p>`;
    try {
      const res = await fetch('/history');
      const data = await res.json();
      renderHistory(data.batches || []);
    } catch (err) {
      historyList.innerHTML = `<p class="text-xs" style="color:var(--ink-muted)">Gagal memuat riwayat.</p>`;
    }
  }

  function renderHistory(batches) {
    if (!batches.length) {
      historyList.innerHTML = `<p class="text-xs" style="color:var(--ink-muted)">Belum ada Twibbon yang kamu buat di sesi ini.</p>`;
      return;
    }
    historyList.innerHTML = '';
    batches.forEach((batch) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'w-full text-left p-3 rounded-xl border transition hover:shadow-md';
      item.style.borderColor = '#E7DFC9';
      item.style.background = 'var(--paper-dim)';
      item.innerHTML = `
        <p class="text-sm font-semibold" style="color:var(--ink)">${batch.files.length} foto</p>
        <p class="text-xs font-mono" style="color:var(--ink-muted)">${batch.created_at}</p>
      `;
      item.addEventListener('click', () => {
        renderResults(batch);
        resultSection.classList.remove('hidden');
        toggleHistory(false);
        resultSection.scrollIntoView({ behavior: 'smooth' });
      });
      historyList.appendChild(item);
    });
  }

  function toggleHistory(show) {
    historyOverlay.classList.toggle('hidden', !show);
    historyPanel.classList.toggle('hidden', !show);
    if (show) loadHistory();
  }

  historyToggleBtn.addEventListener('click', () => toggleHistory(true));
  closeHistoryBtn.addEventListener('click', () => toggleHistory(false));
  historyOverlay.addEventListener('click', () => toggleHistory(false));

  clearHistoryBtn.addEventListener('click', async () => {
    await fetch('/history', { method: 'DELETE' });
    loadHistory();
  });

  // =====================================================================
  // =================== COLOR REMOVER FEATURE ===========================
  // =====================================================================

  /**
   * Draw a File/Blob onto the color picker canvas, fit to the container.
   * Stores the resulting ImageData in crState.originalImageData.
   */
  function loadImageOntoCanvas(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        // Fit within 480×320 display, keep aspect ratio
        const maxW = 480, maxH = 320;
        const ratio = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight, 1);
        const dw = Math.round(img.naturalWidth * ratio);
        const dh = Math.round(img.naturalHeight * ratio);

        colorPickerCanvas.width = dw;
        colorPickerCanvas.height = dh;
        offscreenCanvas.width = dw;
        offscreenCanvas.height = dh;

        const ctx = colorPickerCanvas.getContext('2d');
        ctx.clearRect(0, 0, dw, dh);
        ctx.drawImage(img, 0, 0, dw, dh);

        // Store clean copy
        crState.originalImageData = ctx.getImageData(0, 0, dw, dh);

        URL.revokeObjectURL(url);
        resolve();
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Gagal memuat gambar.')); };
      img.src = url;
    });
  }

  /** Open color remover modal with the current twibbon file */
  async function openColorRemover() {
    const file = twibbonInput.files[0];
    if (!file) return;

    crState.originalFile = file;
    crState.colors = [];
    crState.activeColor = null;
    crState.isPreviewing = false;
    crState.convertedBlob = null;
    crState.convertedUrl = null;
    crState.convertedFilename = null;
    crState.convertedStoragePath = null;
    crState.eyedropperActive = false;

    renderSwatches();
    setEyedropperActive(false);
    crShowStatus('', false);
    colorRemoverOverlay.classList.remove('hidden');

    try {
      await loadImageOntoCanvas(file);
    } catch (err) {
      crShowStatus('Gagal memuat gambar: ' + err.message, true);
    }
  }

  function closeColorRemover() {
    colorRemoverOverlay.classList.add('hidden');
    setEyedropperActive(false);
  }

  openColorRemoverBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    openColorRemover();
  });
  colorRemoverClose.addEventListener('click', closeColorRemover);
  colorRemoverOverlay.addEventListener('click', (e) => {
    if (e.target === colorRemoverOverlay) closeColorRemover();
  });

  // ── Eyedropper toggle ──
  function setEyedropperActive(active) {
    crState.eyedropperActive = active;
    eyedropperToggle.classList.toggle('active', active);
    eyedropperLabel.textContent = active ? 'Aktif — Klik Gambar' : 'Mode Pilih Warna';
    eyedropperIcon.textContent = active ? '🎯' : '🔍';
    colorPickerCanvas.style.cursor = active ? 'crosshair' : 'default';
  }

  eyedropperToggle.addEventListener('click', () => {
    setEyedropperActive(!crState.eyedropperActive);
  });

  // ── Canvas click — sample pixel color ──
  colorPickerCanvas.addEventListener('click', (e) => {
    if (!crState.eyedropperActive) return;
    const rect = colorPickerCanvas.getBoundingClientRect();
    const scaleX = colorPickerCanvas.width / rect.width;
    const scaleY = colorPickerCanvas.height / rect.height;
    const px = Math.floor((e.clientX - rect.left) * scaleX);
    const py = Math.floor((e.clientY - rect.top) * scaleY);

    const ctx = colorPickerCanvas.getContext('2d');
    const pixel = ctx.getImageData(px, py, 1, 1).data;
    const hex = rgbToHex(pixel[0], pixel[1], pixel[2]);

    addColor(hex);
    setEyedropperActive(false); // auto-deactivate after pick
  });

  // ── Mouse move over canvas — show cursor dot + live hex preview ──
  colorPickerCanvas.addEventListener('mousemove', (e) => {
    if (!crState.eyedropperActive) {
      colorCursorDot.classList.add('hidden');
      return;
    }
    const rect = colorPickerCanvas.getBoundingClientRect();
    const scaleX = colorPickerCanvas.width / rect.width;
    const scaleY = colorPickerCanvas.height / rect.height;
    const px = Math.floor((e.clientX - rect.left) * scaleX);
    const py = Math.floor((e.clientY - rect.top) * scaleY);

    const ctx = colorPickerCanvas.getContext('2d');
    const pixel = ctx.getImageData(px, py, 1, 1).data;
    const hex = rgbToHex(pixel[0], pixel[1], pixel[2]);

    // Position the dot relative to canvas container
    const canvasRect = colorPickerCanvas.getBoundingClientRect();
    colorCursorDot.style.left = (e.clientX - canvasRect.left) + 'px';
    colorCursorDot.style.top  = (e.clientY - canvasRect.top)  + 'px';
    colorCursorDot.style.background = hex;
    colorCursorDot.classList.remove('hidden');

    // Update hex input live while hovering
    hexColorInput.value = hex;
    hexPreviewDot.style.background = hex;
    nativeColorInput.value = hex;
  });

  colorPickerCanvas.addEventListener('mouseleave', () => {
    colorCursorDot.classList.add('hidden');
  });

  // ── Swatch management ──
  function addColor(hex) {
    hex = hex.toLowerCase();
    if (crState.colors.find((c) => c.hex === hex)) return; // no duplicates

    const rgb = hexToRgb(hex);
    if (!rgb) return;
    crState.colors.push({ hex, ...rgb });
    crState.activeColor = hex;
    renderSwatches();

    // Sync inputs
    hexColorInput.value = hex;
    hexPreviewDot.style.background = hex;
    nativeColorInput.value = hex;
  }

  function removeColor(hex) {
    crState.colors = crState.colors.filter((c) => c.hex !== hex);
    if (crState.activeColor === hex) {
      crState.activeColor = crState.colors.length ? crState.colors[crState.colors.length - 1].hex : null;
    }
    renderSwatches();
    // If was previewing, reset canvas to original
    if (crState.isPreviewing) resetToOriginal();
  }

  function renderSwatches() {
    colorSwatches.innerHTML = '';

    if (!crState.colors.length) {
      noColorMsg.style.display = 'inline';
      colorSwatches.appendChild(noColorMsg);
      return;
    }

    noColorMsg.style.display = 'none';
    crState.colors.forEach(({ hex }) => {
      const wrap = document.createElement('div');
      wrap.className = 'color-swatch' + (hex === crState.activeColor ? ' active-swatch' : '');
      wrap.style.background = hex;
      wrap.title = hex;

      const rm = document.createElement('span');
      rm.className = 'swatch-remove';
      rm.textContent = '×';
      rm.addEventListener('click', (e) => { e.stopPropagation(); removeColor(hex); });
      wrap.appendChild(rm);

      wrap.addEventListener('click', () => {
        crState.activeColor = hex;
        hexColorInput.value = hex;
        hexPreviewDot.style.background = hex;
        nativeColorInput.value = hex;
        renderSwatches();
      });

      colorSwatches.appendChild(wrap);
    });
  }

  // ── Hex input sync ──
  hexColorInput.addEventListener('input', () => {
    let v = hexColorInput.value.trim();
    if (!v.startsWith('#')) v = '#' + v;
    hexColorInput.value = v;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) {
      hexPreviewDot.style.background = v;
      nativeColorInput.value = v;
    }
  });

  nativeColorInput.addEventListener('input', () => {
    const v = nativeColorInput.value;
    hexColorInput.value = v;
    hexPreviewDot.style.background = v;
  });

  addColorBtn.addEventListener('click', () => {
    let v = hexColorInput.value.trim();
    if (!v.startsWith('#')) v = '#' + v;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) {
      addColor(v);
    } else {
      crShowStatus('Masukkan kode warna hex yang valid, misal #00FF00', true);
    }
  });

  // Enter key on hex input also adds
  hexColorInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addColorBtn.click();
  });

  // ── Tolerance slider ──
  function updateToleranceSlider() {
    const pct = ((toleranceSlider.value - toleranceSlider.min) / (toleranceSlider.max - toleranceSlider.min) * 100).toFixed(1);
    toleranceSlider.style.setProperty('--pct', pct + '%');
    toleranceValue.textContent = toleranceSlider.value;
  }
  toleranceSlider.addEventListener('input', () => {
    updateToleranceSlider();
    // Auto re-preview if currently showing a preview
    if (crState.isPreviewing && crState.colors.length) {
      drawClientPreview();
    }
  });
  updateToleranceSlider();

  // ── Client-side preview (canvas only, no server round-trip) ──
  /**
   * Draw a live preview directly on the canvas by applying tolerance-based
   * alpha removal in JS. Purely visual, does not affect the final PNG.
   */
  function drawClientPreview() {
    if (!crState.originalImageData || !crState.colors.length) return;

    const tolerance = parseInt(toleranceSlider.value, 10);
    const ctx = colorPickerCanvas.getContext('2d');

    // Clone original data
    const preview = new ImageData(
      new Uint8ClampedArray(crState.originalImageData.data),
      crState.originalImageData.width,
      crState.originalImageData.height
    );

    const data = preview.data;
    const tol2 = tolerance * tolerance * 3; // squared Euclidean threshold

    for (let i = 0; i < data.length; i += 4) {
      const pr = data[i], pg = data[i + 1], pb = data[i + 2];

      // Check against every selected color
      for (const { r, g, b } of crState.colors) {
        const dr = pr - r, dg = pg - g, db = pb - b;
        const dist2 = dr * dr + dg * dg + db * db;
        if (dist2 <= tol2) {
          // Fade based on distance within tolerance
          const fade = Math.sqrt(dist2 / (tol2 + 1));
          data[i + 3] = Math.round(data[i + 3] * Math.min(fade * 1.5, 1));
          break;
        }
      }
    }

    ctx.clearRect(0, 0, preview.width, preview.height);
    ctx.putImageData(preview, 0, 0);
    crState.isPreviewing = true;
  }

  function resetToOriginal() {
    if (!crState.originalImageData) return;
    const ctx = colorPickerCanvas.getContext('2d');
    ctx.putImageData(crState.originalImageData, 0, 0);
    crState.isPreviewing = false;
  }

  previewRemoveBtn.addEventListener('click', () => {
    if (!crState.colors.length) {
      crShowStatus('Pilih setidaknya satu warna dulu.', true);
      return;
    }
    drawClientPreview();
  });

  resetPreviewBtn.addEventListener('click', () => {
    resetToOriginal();
    crShowStatus('', false);
  });

  // ── Status helper ──
  function crShowStatus(msg, isError) {
    if (!msg) {
      colorRemoverStatus.classList.add('hidden');
      return;
    }
    colorRemoverStatus.textContent = msg;
    colorRemoverStatus.style.background = isError ? '#FDECEA' : '#ECFDF5';
    colorRemoverStatus.style.color = isError ? '#B3261E' : '#065F46';
    colorRemoverStatus.classList.remove('hidden');
  }

  // ── Apply: send to server, get PNG back, use it as twibbon ──
  applyColorRemoveBtn.addEventListener('click', async () => {
    if (!crState.colors.length) {
      crShowStatus('Pilih setidaknya satu warna yang ingin dihapus.', true);
      return;
    }
    if (!crState.originalFile) {
      crShowStatus('File twibbon tidak ditemukan.', true);
      return;
    }

    applyColorRemoveBtn.disabled = true;
    crShowStatus('Memproses... mohon tunggu ⏳', false);

    try {
      const tolerance = parseInt(toleranceSlider.value, 10);

      // First pass: use the original File object directly
      // Subsequent passes: use the PNG blob returned from the previous pass
      let currentFile = crState.originalFile;
      let lastData = null;

      for (let i = 0; i < crState.colors.length; i++) {
        const colorHex = crState.colors[i].hex.replace('#', '');

        const formData = new FormData();
        // Always send as a proper named PNG file so the server never gets an empty filename
        const passFile = i === 0
          ? new File([currentFile], currentFile.name || 'twibbon.png', { type: currentFile.type || 'image/png' })
          : new File([currentFile], 'twibbon_pass.png', { type: 'image/png' });
        formData.append('twibbon', passFile);
        formData.append('color', colorHex);
        formData.append('tolerance', tolerance);

        const res = await fetch('/remove_bg_color', { method: 'POST', body: formData });

        // Guard: server might still return HTML on crash
        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          const text = await res.text();
          console.error('Non-JSON response:', text.slice(0, 300));
          throw new Error('Server mengembalikan error. Cek konsol untuk detailnya.');
        }

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Gagal memproses warna.');

        lastData = data;

        // For next iteration: fetch the result as a blob from the server
        // Use /converted_twibbon route which always works regardless of storage backend
        const uid = data.storage_path.split('/')[0];
        const fname = data.filename;
        const blobRes = await fetch(`/converted_twibbon/${uid}/${fname}`);
        if (!blobRes.ok) throw new Error('Gagal mengambil hasil konversi dari server.');
        currentFile = await blobRes.blob(); // becomes a Blob for next iteration
      }

      // Store final result as blob
      crState.convertedBlob = currentFile instanceof Blob ? currentFile : await (async () => {
        const r = await fetch(`/converted_twibbon/${lastData.storage_path.split('/')[0]}/${lastData.filename}`);
        return r.blob();
      })();
      crState.convertedFilename = lastData.filename;
      crState.convertedStoragePath = lastData.storage_path;
      crState.convertedUrl = URL.createObjectURL(crState.convertedBlob);

      // Update canvas to show final result
      const previewImg = new Image();
      previewImg.onload = () => {
        const ctx = colorPickerCanvas.getContext('2d');
        ctx.clearRect(0, 0, colorPickerCanvas.width, colorPickerCanvas.height);
        ctx.drawImage(previewImg, 0, 0, colorPickerCanvas.width, colorPickerCanvas.height);
        crState.originalImageData = ctx.getImageData(0, 0, colorPickerCanvas.width, colorPickerCanvas.height);
        crState.isPreviewing = false;
      };
      previewImg.src = crState.convertedUrl;

      // Update twibbon dropzone badge
      twibbonName.textContent = lastData.filename;
      nonPngBadge.classList.add('hidden');
      twibbonHint.classList.add('hidden');

      const colorCount = crState.colors.length;
      crShowStatus(`✅ Berhasil! ${colorCount} warna dihapus. Tutup modal untuk lanjut proses twibbon.`, false);

      // Reset swatch selection so user can add more colors if needed
      // but keep them visible so they know what was applied
      setTimeout(() => {
        applyColorRemoveBtn.disabled = false;
        // Auto-close after 2s
        setTimeout(closeColorRemover, 2000);
      }, 400);

    } catch (err) {
      console.error('applyColorRemove error:', err);
      crShowStatus('Error: ' + err.message, true);
      applyColorRemoveBtn.disabled = false;
    }
  });

})();
