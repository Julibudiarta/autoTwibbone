document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const form = document.getElementById('uploadForm');
    
    // Twibbon Dropzone
    const twibbonInput = document.getElementById('twibbonFile');
    const dropTwibbon = document.getElementById('drop-twibbon');
    const twibbonPreview = document.getElementById('twibbon-preview');
    const twibbonName = document.getElementById('twibbon-name');
    const clearTwibbonBtn = document.getElementById('clear-twibbon');

    // User Photos Dropzone
    const photosInput = document.getElementById('userFiles');
    const dropPhotos = document.getElementById('drop-photos');
    const photosPreview = document.getElementById('photos-preview');
    const photosCount = document.getElementById('photos-count');
    const clearPhotosBtn = document.getElementById('clear-photos');

    // Actions & Feedback
    const submitBtn = document.getElementById('processBtn');
    const loader = document.getElementById('loadingIndicator');
    const errMsg = document.getElementById('errorMessage');
    
    // Results
    const resultSection = document.getElementById('resultSection');
    const resultGrid = document.getElementById('resultGrid');
    const zipBtn = document.getElementById('downloadZipBtn');

    // ---- SETUP EVENT LISTENERS FOR DRAG AND DROP ----
    
    // Twibbon handling
    twibbonInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            twibbonName.textContent = file.name;
            twibbonPreview.classList.remove('hidden');
        }
    });

    clearTwibbonBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation(); // Avoid triggering file dialog again
        twibbonInput.value = "";
        twibbonPreview.classList.add('hidden');
    });

    // Photos handling
    photosInput.addEventListener('change', (e) => {
        const count = e.target.files.length;
        if (count > 0) {
            photosCount.textContent = `${count} Foto Telah Dipilih`;
            photosPreview.classList.remove('hidden');
        }
    });

    clearPhotosBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        photosInput.value = "";
        photosPreview.classList.add('hidden');
    });

    // Styling drag events for both zones
    [dropTwibbon, dropPhotos].forEach(zone => {
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('drag-active');
        });
        zone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            zone.classList.remove('drag-active');
        });
        zone.addEventListener('drop', (e) => {
            zone.classList.remove('drag-active');
            // The drop event is naturally handled by the input[type=file] child 
            // but we need to update UI depending on which zone it is
        });
    });


    // ---- SUBMIT FORM (AJAX) ----
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Validation
        if (!twibbonInput.files.length) {
            showError("Silakan pilih layout Twibbon terlebih dahulu!");
            return;
        }
        if (!photosInput.files.length) {
            showError("Silakan pilih minimal 1 foto yang akan diproses!");
            return;
        }

        const formData = new FormData();
        formData.append('twibbon', twibbonInput.files[0]);
        for (let i = 0; i < photosInput.files.length; i++) {
            formData.append('user_images', photosInput.files[i]);
        }

        // UI States
        submitBtn.classList.add('hidden');
        loader.classList.remove('hidden');
        errMsg.classList.add('hidden');
        resultSection.classList.add('hidden');

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Terjadi kesalahan server!");
            }

            // Success Output Rendering
            renderResults(data);

        } catch (error) {
            showError(error.message);
        } finally {
            // Restore UI Buttons
            submitBtn.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    });

    function showError(msg) {
        errMsg.textContent = msg;
        errMsg.classList.remove('hidden');
    }

    function renderResults(data) {
        resultGrid.innerHTML = "";
        
        // Populate items
        data.files.forEach(fileObj => {
            const card = document.createElement('div');
            card.className = "bg-white rounded-xl shadow border border-gray-100 p-4 slide-down-anim flex flex-col items-center";
            
            // Image Preview (We don't return directly the image bytes, only URLs)
            // Tapi karena browser bisa cache, lebih aman show dummy logic atau fetch via URL
            // Supaya ringan, UI menampilkan judul file output saja 
            const imgBox = `
                <div class="w-full bg-gray-50 h-32 rounded-lg flex items-center justify-center border border-gray-200 mb-4 overflow-hidden shadow-inner">
                    <img src="${fileObj.result_url}" alt="Preview" class="object-contain w-full h-full" onerror="this.src=''; this.alt='Gambar Selesai'"/>
                </div>
                <p class="text-sm font-semibold truncate w-full text-center text-gray-700" title="${fileObj.filename}">
                    ${fileObj.filename}
                </p>
                <a href="${fileObj.result_url}" download class="mt-4 w-full bg-blue-100 hover:bg-blue-200 text-blue-700 font-semibold py-2 rounded text-center transition">
                    ⬇ Unduh
                </a>
            `;
            
            card.innerHTML = imgBox;
            resultGrid.appendChild(card);
        });

        // Show ZIP Download if available
        if (data.zip_url) {
            zipBtn.href = data.zip_url;
            zipBtn.classList.remove('hidden');
        } else {
            zipBtn.classList.add('hidden');
        }

        // Open Results panel
        form.classList.add('hidden'); // Hide form gracefully
        resultSection.classList.remove('hidden');
    }
});
