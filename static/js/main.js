(function () {
  const $ = (id) => document.getElementById(id);

  // ---- Upload form elements ----
  const uploadForm = $('uploadForm');
  const twibbonInput = $('twibbonFile');
  const dropTwibbon = $('drop-twibbon');
  const twibbonPreview = $('twibbon-preview');
  const twibbonName = $('twibbon-name');
  const clearTwibbonBtn = $('clear-twibbon');

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

  let editorState = null; // { uid, batchId, filename, posX, posY, zoom, imgEl }
  let dragging = false;
  let dragStart = null;

  // ================= Helpers =================
  function clamp(v, min, max) { return Math.min(Math.max(v, min), max); }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorMessage.classList.remove('hidden');
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
  bindDropzone(twibbonInput, () => {
    if (twibbonInput.files.length) {
      twibbonName.textContent = twibbonInput.files[0].name;
      twibbonPreview.classList.remove('hidden');
    }
  });

  clearTwibbonBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    twibbonInput.value = '';
    twibbonPreview.classList.add('hidden');
  });

  // ================= Photos dropzone =================
  bindDropzone(userFilesInput, () => {
    if (userFilesInput.files.length) {
      photosCount.textContent = `${userFilesInput.files.length} foto dipilih`;
      photosPreview.classList.remove('hidden');
    }
  });

  clearPhotosBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    userFilesInput.value = '';
    photosPreview.classList.add('hidden');
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
    formData.append('twibbon', twibbonInput.files[0]);
    Array.from(userFilesInput.files).forEach((f) => formData.append('user_images', f));

    processBtn.disabled = true;
    loadingIndicator.classList.remove('hidden');

    try {
      const res = await fetch('/upload', { method: 'POST', body: formData });
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
      card.innerHTML = `
        <div class="rounded-xl overflow-hidden mb-3" style="background:var(--paper-dim)">
          <img src="${file.result_url}" alt="Hasil twibbon ${file.original}" class="w-full h-48 object-contain">
        </div>
        <p class="text-xs font-mono truncate mb-3" style="color:var(--ink-muted)" title="${file.original}">${file.original}</p>
        <div class="flex gap-2 mt-auto">
          <button type="button" class="edit-position-btn flex-1 text-xs font-semibold py-2 rounded-full" style="background:var(--paper-dim); color:var(--plum)">✏️ Atur Posisi</button>
          <a href="${file.result_url}" download class="flex-1 text-xs font-semibold py-2 rounded-full text-center" style="background:var(--marigold); color:var(--plum-deep)">⬇ Unduh</a>
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
    editorPhoto.src = `/source_photo/${batch.uid}/${batch.batch_id}/${previewName}`;
    editorFrame.src = `/source_twibbon/${batch.uid}/${batch.batch_id}`;
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

  // Drag to pan (mouse + touch, via Pointer Events)
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

  editorSaveBtn.addEventListener('click', async () => {
    if (!editorState) return;
    editorStatus.classList.remove('hidden');
    editorStatus.style.color = 'var(--ink-muted)';
    editorStatus.textContent = 'Menyimpan posisi...';
    editorSaveBtn.disabled = true;

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
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal menyimpan posisi.');

      editorState.imgEl.src = data.result_url;
      editorStatus.style.color = '#1a7f4c';
      editorStatus.textContent = 'Posisi tersimpan!';
      setTimeout(closeEditor, 500);
    } catch (err) {
      editorStatus.style.color = 'var(--coral)';
      editorStatus.textContent = err.message;
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
})();