// Script de la page index (extrait de templates/index.html).
// Gestion des cookies
function setCookie(name, value, days = 30) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
}

function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for(let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

document.addEventListener('DOMContentLoaded', function() {
    // Set today's date as default for planning_date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('planning_date').value = today;

    const teacherSelect = document.getElementById('teacher_id');
    const isTeacherScopedMode = teacherSelect && teacherSelect.dataset.teacherScoped === 'true';

    function enforceConnectedTeacherSelection() {
        if (!isTeacherScopedMode || !teacherSelect) {
            return;
        }

        const availableTeachers = Array.from(teacherSelect.options).filter(option => option.value);
        if (availableTeachers.length === 1) {
            teacherSelect.value = availableTeachers[0].value;
            teacherSelect.setAttribute('disabled', 'disabled');
            teacherSelect.classList.add('bg-light');
        }
    }
    
    // Restaurer l'enseignant depuis le cookie
    const savedTeacher = getCookie('selectedTeacher');
    if (savedTeacher && !isTeacherScopedMode) {
        teacherSelect.value = savedTeacher;
        console.log(`🍪 Enseignant restauré depuis le cookie: ${savedTeacher}`);
    }

    enforceConnectedTeacherSelection();
    
    // Sauvegarder l'enseignant quand il est sélectionné
    teacherSelect.addEventListener('change', function() {
        if (isTeacherScopedMode) {
            enforceConnectedTeacherSelection();
            return;
        }
        if (this.value) {
            setCookie('selectedTeacher', this.value);
        }
        loadTpTemplates();
    });

    document.getElementById('class_name').addEventListener('change', loadTpTemplates);

    // --- Durée personnalisée (depuis la base de données) ---
    const DUREES_PAR_NIVEAU = window.APP_CONFIG.dureesParNiveau;
    function dureeParNiveau(niveau) { return DUREES_PAR_NIVEAU[niveau] || 85; }
    // Nombre de groupes par défaut selon le niveau (réglé dans /admin/niveaux)
    const GROUPES_PAR_NIVEAU = window.APP_CONFIG.groupesParNiveau;
    function groupesParNiveau(niveau) {
        const g = GROUPES_PAR_NIVEAU[niveau];
        return g === undefined ? 1 : g;
    }
    function setCustomDurationInputs(prefix, minutes) {
        document.getElementById(prefix + '_h').value = Math.floor(minutes / 60);
        document.getElementById(prefix + '_m').value = minutes % 60;
    }
    function getCustomDurationValue(prefix) {
        const niveau = document.getElementById('class_name').value;
        const h = parseInt(document.getElementById(prefix + '_h').value) || 0;
        const m = parseInt(document.getElementById(prefix + '_m').value) || 0;
        const minutes = h * 60 + m;
        // On ne renvoie une durée personnalisée que si elle diffère de la durée par défaut du niveau
        return (minutes !== dureeParNiveau(niveau)) ? minutes : null;
    }

    document.getElementById('class_name').addEventListener('change', function() {
        setCustomDurationInputs('custom_duration', dureeParNiveau(this.value));
        document.getElementById('quantity').value = groupesParNiveau(this.value);
    });
    document.getElementById('materialRequestForm').addEventListener('reset', function() {
        setCustomDurationInputs('custom_duration', dureeParNiveau(document.getElementById('class_name').value));
        document.getElementById('quantity').value = groupesParNiveau(document.getElementById('class_name').value);
    });
    // Pré-remplir la durée et le nombre de groupes à l'ouverture du formulaire
    setCustomDurationInputs('custom_duration', dureeParNiveau(document.getElementById('class_name').value));
    document.getElementById('quantity').value = groupesParNiveau(document.getElementById('class_name').value);

    async function loadTpTemplates() {
        const teacherId = teacherSelect.value;
        const level = document.getElementById('class_name').value;
        const section = document.getElementById('tp-template-section');
        const select = document.getElementById('tp_template_select');

        if (!teacherId || !level) {
            section.style.display = 'none';
            return;
        }

        try {
            const resp = await fetch(`/api/tp-templates?teacher_id=${teacherId}&level=${encodeURIComponent(level)}`);
            const templates = await resp.json();

            if (!templates.length) {
                section.style.display = 'none';
                return;
            }

            select.innerHTML = '<option value="">— Nouveau TP —</option>';
            templates.forEach((t, i) => {
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = t.request_name;
                opt.dataset.template = JSON.stringify(t);
                select.appendChild(opt);
            });
            section.style.display = 'block';
        } catch(e) {
            section.style.display = 'none';
        }
    }

    document.getElementById('tp_template_select').addEventListener('change', function() {
        const selected = this.options[this.selectedIndex];
        if (!selected.dataset.template) return;
        const t = JSON.parse(selected.dataset.template);

        document.getElementById('request_name').value = t.request_name || '';
        document.getElementById('selected_materials').value = t.selected_materials || '';
        document.getElementById('material_prof').value = t.material_prof || '';
        document.getElementById('computers_needed').value = t.computers_needed || 0;
        document.getElementById('quantity').value = t.group_count ?? 1;
        document.getElementById('notes').value = t.notes || '';

        // Remettre les cases matériaux
        const materials = (t.selected_materials || '').toLowerCase();
        document.getElementById('eviers').checked = materials.includes('évier') || materials.includes('evier');
        document.getElementById('hotte').checked = materials.includes('hotte');
        document.getElementById('bancs_optiques').checked = materials.includes('bancs optiques');
        document.getElementById('obscurite_totale').checked = materials.includes('obscurité totale') || materials.includes('obscurite totale');
        document.getElementById('becs_electriques').checked = materials.includes('becs électriques') || materials.includes('becs electriques');
        document.getElementById('support_filtration').checked = materials.includes('support de filtration');
        document.getElementById('imprimante').checked = materials.includes('imprimante');
        document.getElementById('aucun_materiel_salle').checked = materials.includes('pas de matériel spécifique') || materials.includes('pas de materiel specifique');

        // Pré-charger l'image si disponible
        const imageUrlInput = document.getElementById('image_url');
        const imagePreview = document.getElementById('image_preview');
        const previewImg = document.getElementById('preview_img');
        if (t.image_url && imageUrlInput && imagePreview && previewImg) {
            imageUrlInput.value = t.image_url;
            previewImg.src = t.image_url;
            imagePreview.style.display = 'block';
        } else if (imageUrlInput) {
            imageUrlInput.value = '';
            if (imagePreview) imagePreview.style.display = 'none';
        }
    });

    const replacementCheckbox = document.getElementById('replacement_mode');
    const replacementTeacherContainer = document.getElementById('replacement_teacher_container');
    const replacementTeacherSelect = document.getElementById('replacement_teacher_id');

    async function loadReplacementTeachers() {
        try {
            const response = await fetch('/api/replacement-teachers');
            const teachers = await response.json();

            replacementTeacherSelect.innerHTML = '<option value="">Sélectionner l\'enseignant absent</option>';
            teachers.forEach(teacher => {
                const option = document.createElement('option');
                option.value = teacher.id;
                option.textContent = teacher.name;
                replacementTeacherSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Erreur chargement remplacements:', error);
            showErrorToast('Impossible de charger la liste des enseignants pour remplacement');
        }
    }

    replacementCheckbox.addEventListener('change', async function() {
        if (this.checked) {
            replacementTeacherContainer.style.display = 'block';
            replacementTeacherSelect.setAttribute('required', 'required');
            await loadReplacementTeachers();
        } else {
            replacementTeacherContainer.style.display = 'none';
            replacementTeacherSelect.removeAttribute('required');
            replacementTeacherSelect.value = '';
        }
    });

    // Gestion des cases "Absent", "Pas besoin de matériel" et "Examen"
    const absentCheckbox = document.getElementById('absent');
    const noMaterialCheckbox = document.getElementById('no_material');
    const examModeCheckbox = document.getElementById('exam_mode');
    // Sections masquées dès qu'un mode spécial est coché
    const sectionsToHide = [
        'material-section',
        'description-section',
        'notes-section',
        'image-section'
    ];
    // Un cours sans matériel de labo peut quand même avoir besoin d'ordinateurs
    // et d'un nombre de groupes : ces deux sections restent visibles dans ce mode-là.
    const sectionsGardeesSansMateriel = [
        'computers-section',
        'quantity-section'
    ];

    function toggleSpecialModes() {
        const isAbsent = absentCheckbox.checked;
        const isNoMaterial = noMaterialCheckbox.checked;
        const isExamMode = examModeCheckbox.checked;
        
        // S'assurer qu'une seule option est cochée à la fois
        const checkedCount = [isAbsent, isNoMaterial, isExamMode].filter(Boolean).length;
        if (checkedCount > 1) {
            // Si plusieurs sont cochées, décocher les autres selon qui a été cliqué en dernier
            if (document.activeElement === absentCheckbox) {
                noMaterialCheckbox.checked = false;
                examModeCheckbox.checked = false;
            } else if (document.activeElement === noMaterialCheckbox) {
                absentCheckbox.checked = false;
                examModeCheckbox.checked = false;
            } else if (document.activeElement === examModeCheckbox) {
                absentCheckbox.checked = false;
                noMaterialCheckbox.checked = false;
            }
        }
        
        const shouldHideSections = absentCheckbox.checked || noMaterialCheckbox.checked || examModeCheckbox.checked;
        // Seul le mode "pas besoin de matériel" conserve ordinateurs et groupes
        const sansMaterielSeul = noMaterialCheckbox.checked && !absentCheckbox.checked && !examModeCheckbox.checked;

        function appliquerVisibilite(sectionId, masquer) {
            const section = document.getElementById(sectionId);
            if (!section) return;
            if (masquer) {
                section.style.display = 'none';
                // Désactiver les champs requis
                const requiredFields = section.querySelectorAll('[required]');
                requiredFields.forEach(field => {
                    field.removeAttribute('required');
                    field.dataset.wasRequired = 'true';
                });
            } else {
                // '' plutôt que 'block' : laisse le CSS d'origine s'appliquer
                section.style.display = '';
                // Réactiver les champs requis
                const wasRequiredFields = section.querySelectorAll('[data-was-required="true"]');
                wasRequiredFields.forEach(field => {
                    field.setAttribute('required', 'required');
                    field.removeAttribute('data-was-required');
                });
            }
        }

        sectionsToHide.forEach(sectionId => appliquerVisibilite(sectionId, shouldHideSections));
        sectionsGardeesSansMateriel.forEach(sectionId =>
            appliquerVisibilite(sectionId, shouldHideSections && !sansMaterielSeul));

        // Afficher/masquer le message d'information
        let infoMessage = document.getElementById('special-mode-info');
        if (shouldHideSections) {
            if (!infoMessage) {
                infoMessage = document.createElement('div');
                infoMessage.id = 'special-mode-info';
                infoMessage.className = 'alert alert-info mt-2';
                absentCheckbox.closest('.mb-3').appendChild(infoMessage);
            }
            // Le texte est recalculé à chaque fois : on peut passer d'un mode à l'autre
            if (sansMaterielSeul) {
                infoMessage.innerHTML = `<i class="fas fa-info-circle"></i> Mode cours sans matériel activé : aucun matériel de labo ne sera préparé, mais vous pouvez toujours demander des ordinateurs et préciser le nombre de groupes.`;
            } else {
                const modeText = absentCheckbox.checked ? 'absence' : 'examen';
                infoMessage.innerHTML = `<i class="fas fa-info-circle"></i> Mode ${modeText} activé : seuls l'enseignant et le niveau sont requis.`;
            }
        } else if (infoMessage) {
            infoMessage.remove();
        }
    }

    absentCheckbox.addEventListener('change', toggleSpecialModes);
    noMaterialCheckbox.addEventListener('change', toggleSpecialModes);
    examModeCheckbox.addEventListener('change', toggleSpecialModes);
    
    // Initialiser l'état au chargement
    toggleSpecialModes();

    // "Pas de matériel spécifique à la salle" est exclusif des autres cases du matériel peu mobile
    const aucunMaterielSalle = document.getElementById('aucun_materiel_salle');
    const autresMaterielsSalle = document.querySelectorAll('input[name="materials"]:not(#aucun_materiel_salle)');
    aucunMaterielSalle.addEventListener('change', function() {
        if (this.checked) {
            autresMaterielsSalle.forEach(cb => { cb.checked = false; });
        }
    });
    autresMaterielsSalle.forEach(cb => {
        cb.addEventListener('change', function() {
            if (this.checked) {
                aucunMaterielSalle.checked = false;
            }
        });
    });

    // Gestion des jours/horaires ajoutés
    let daysHoraires = [];
    const daysList = document.getElementById('daysList');
    const addDayBtn = document.getElementById('addDayBtn');

    addDayBtn.addEventListener('click', function() {
        const date = document.getElementById('planning_date').value;
        const horairesChecked = Array.from(document.querySelectorAll('input[name="horaire"]:checked')).map(cb => cb.value);
        if (!date || horairesChecked.length === 0) {
            showErrorToast('Veuillez choisir une date et au moins un horaire.');
            return;
        }
        // Correction : ajouter le jour + créneaux au tableau avant de réinitialiser
        daysHoraires.push({ date, horaires: horairesChecked });
        updateDaysList();
        // Réinitialise les horaires cochés
        document.querySelectorAll('input[name="horaire"]:checked').forEach(cb => cb.checked = false);
        // Propose le jour suivant
        let nextDate = new Date(date);
        nextDate.setDate(nextDate.getDate() + 1);
        document.getElementById('planning_date').value = nextDate.toISOString().split('T')[0];
    });

    function updateDaysList() {
        const additionalDaysSection = document.getElementById('additional-days-section');
        
        daysList.innerHTML = '';
        
        if (daysHoraires.length > 0) {
            // Afficher la section des jours supplémentaires
            additionalDaysSection.style.display = 'block';
            
            daysHoraires.forEach((dh, idx) => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';

                const labelSpan = document.createElement('span');
                const strongDate = document.createElement('strong');
                strongDate.textContent = dh.date;
                labelSpan.appendChild(strongDate);
                labelSpan.appendChild(document.createTextNode(` : ${dh.horaires.join(', ')}`));

                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.className = 'btn btn-sm btn-danger';
                deleteBtn.dataset.idx = String(idx);
                deleteBtn.textContent = 'Supprimer';

                li.appendChild(labelSpan);
                li.appendChild(deleteBtn);
                daysList.appendChild(li);
            });
            
            // Suppression d'un jour/horaire
            daysList.querySelectorAll('button[data-idx]').forEach(btn => {
                btn.onclick = function() {
                    daysHoraires.splice(parseInt(this.dataset.idx), 1);
                    updateDaysList();
                };
            });
        } else {
            // Masquer la section s'il n'y a pas de jours supplémentaires
            additionalDaysSection.style.display = 'none';
        }
    }

    // Soumission du formulaire
    document.getElementById('materialRequestForm').addEventListener('submit', function(e) {
        e.preventDefault();
        // Ajout automatique du dernier jour si des horaires sont cochés et que ce jour n'est pas déjà dans daysHoraires
        const currentDate = document.getElementById('planning_date').value;
        const currentHoraires = Array.from(document.querySelectorAll('input[name="horaire"]:checked')).map(cb => cb.value);
        let finalDaysHoraires = [...daysHoraires];
        // Vérifie si le jour courant n'est pas déjà dans daysHoraires
        const alreadyAdded = finalDaysHoraires.some(dh => dh.date === currentDate);
        if (currentHoraires.length > 0 && !alreadyAdded) {
            finalDaysHoraires.push({ date: currentDate, horaires: currentHoraires });
        }
        if (finalDaysHoraires.length === 0) {
            showErrorToast('Veuillez choisir une date et au moins un horaire.');
            return;
        }
    const formData = new FormData(this);
    const data = Object.fromEntries(formData.entries());

    // Normaliser le mode remplacement (checkbox absente du FormData si non cochée)
    const replacementMode = replacementCheckbox.checked;
    data.replacement_mode = replacementMode;
    if (!replacementMode) {
        delete data.replacement_teacher_id;
    }

    if (replacementMode && !data.replacement_teacher_id) {
        showErrorToast('Veuillez choisir l\'enseignant absent pour le remplacement.');
        replacementTeacherSelect.focus();
        return;
    }

    // Ajout explicite de l'URL de l'image uploadée
    data.image_url = document.getElementById('image_url') ? document.getElementById('image_url').value : '';

    // Ajouter les nouveaux champs
    data.group_count = document.getElementById('quantity').value;
    data.material_prof = document.getElementById('material_prof').value;
    data.request_name = document.getElementById('request_name').value;
    data.custom_duration = getCustomDurationValue('custom_duration');
        
        // Validation du nom de demande (obligatoire)
        if (!data.request_name || data.request_name.trim() === '') {
            showErrorToast('Le nom de la demande est obligatoire.');
            document.getElementById('request_name').focus();
            return;
        }
        
        // Vérification des modes spéciaux
        const isAbsent = document.getElementById('absent').checked;
        const isNoMaterial = document.getElementById('no_material').checked;
        const isExamMode = document.getElementById('exam_mode').checked;

        // Test au labo : indépendant des modes ci-dessus, le matériel reste à préciser normalement
        data.is_lab_test = document.getElementById('lab_test').checked;
        delete data.lab_test;

        if (isAbsent) {
            // En mode absent, on met des valeurs par défaut
            data.selected_materials = 'Absent';
            data.computers_needed = '0';
            data.material_description = 'Enseignant absent';
            data.notes = '';
            data.quantity = '1';
            data.group_count = '1';
        } else if (isNoMaterial) {
            // En mode pas besoin de matériel : aucun matériel de labo, mais on conserve
            // les ordinateurs et le nombre de groupes saisis (sections restées visibles)
            data.selected_materials = 'Pas besoin de matériel';
            data.computers_needed = document.getElementById('computers_needed').value;
            data.material_description = 'Cours théorique sans matériel';
            data.notes = '';
            data.quantity = document.getElementById('quantity').value;
            data.group_count = document.getElementById('quantity').value;
        } else if (isExamMode) {
            // En mode examen
            data.selected_materials = 'Examen';
            data.computers_needed = '0';
            data.material_description = 'Surveillance d\'examen';
            data.notes = '';
            data.quantity = '1';
            data.group_count = '1';
        } else {
            // Mode normal : récupération du matériel spécifique depuis les checkboxes
            const materialCheckboxes = document.querySelectorAll('input[name="materials"]:checked');
            if (materialCheckboxes.length === 0) {
                showErrorToast('Veuillez cocher au moins une option dans "Matériel peu mobile à avoir dans la salle" (ou "Pas de matériel spécifique à la salle").');
                return;
            }

            const specificMaterials = [];
            materialCheckboxes.forEach(checkbox => {
                specificMaterials.push(checkbox.value);
            });

            // Récupération du matériel libre depuis la zone de texte
            const freeTextMaterial = document.getElementById('selected_materials').value;
            
            // Combinaison des matériaux spécifiques et du texte libre
            let allMaterials = [];
            if (specificMaterials.length > 0) {
                allMaterials.push(...specificMaterials);
            }
            if (freeTextMaterial && freeTextMaterial.trim()) {
                allMaterials.push(freeTextMaterial.trim());
            }
            
            // Pour selected_materials : inclure tous les matériaux (spécifiques + libres)
            data.selected_materials = allMaterials.join('\n- ');
            if (data.selected_materials) {
                data.selected_materials = '- ' + data.selected_materials; // Ajouter le premier tiret
            }
            
            data.computers_needed = document.getElementById('computers_needed').value;
            
            // Pour material_description : seulement le matériel libre (pas les équipements de salle)
            if (freeTextMaterial && freeTextMaterial.trim()) {
                data.material_description = `Matériel requis: ${freeTextMaterial.trim()}`;
            } else {
                data.material_description = 'Cours sans matériel spécifique';
            }
        }
        // Ajoute la liste des jours/horaires (automatique ou manuelle)
        data.days_horaires = finalDaysHoraires;
        // Envoi au backend
        fetch('/api/requests', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSuccessToast('Demande créée avec succès !');
                this.reset();
                daysHoraires = [];
                updateDaysList();
                document.getElementById('planning_date').value = today;
                enforceConnectedTeacherSelection();
                replacementTeacherContainer.style.display = 'none';
                replacementTeacherSelect.removeAttribute('required');
                replacementTeacherSelect.value = '';
                // Réinitialiser l'état des sections après le reset du formulaire
                toggleSpecialModes();
            } else {
                showErrorToast(data.error || 'Erreur lors de la création de la demande');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showErrorToast('Erreur de connexion');
        });
    });

    // Gestion de l'upload d'images
    const imageFileInput = document.getElementById('image_file_input');
    const takePhotoBtn = document.getElementById('take_photo_btn');
    const uploadImageBtn = document.getElementById('upload_image_btn');
    const imagePreview = document.getElementById('image_preview');
    const previewImg = document.getElementById('preview_img');
    const imageError = document.getElementById('image_error');
    const uploadInstructions = document.getElementById('upload_instructions');
    const uploadStatus = document.getElementById('upload_status');
    const imageUrlInput = document.getElementById('image_url');
    const removeImageBtn = document.getElementById('remove_image_btn');
    
    // Éléments pour la caméra
    const cameraSection = document.getElementById('camera_section');
    const cameraVideo = document.getElementById('camera_video');
    const capturePhotoBtn = document.getElementById('capture_photo_btn');
    const cancelPhotoBtn = document.getElementById('cancel_photo_btn');
    const photoCanvas = document.getElementById('photo_canvas');

    let selectedFile = null;
    let mediaStream = null;

    function showImageError(message) {
        imageError.textContent = message;
        imageError.style.display = 'block';
        uploadInstructions.style.display = 'none';
    }

    function hideImageError() {
        imageError.style.display = 'none';
    }

    function updateUploadStatus(message, type = 'info') {
        const className = type === 'success' ? 'text-success' : type === 'error' ? 'text-danger' : 'text-info';
        uploadStatus.textContent = '';
        const statusEl = document.createElement('small');
        statusEl.className = className;
        statusEl.textContent = message;
        uploadStatus.appendChild(statusEl);
    }

    // Variables globales pour la protection de navigation
    let isUploading = false;

    // Protéger contre la navigation pendant l'upload
    window.addEventListener('beforeunload', function(e) {
        if (isUploading) {
            e.preventDefault();
            e.returnValue = 'Un upload est en cours. Si vous quittez maintenant, l\'image ne sera pas sauvegardée.';
            return e.returnValue;
        }
    });

    // Désactiver/réactiver la navigation
    function setNavigationLock(locked) {
        isUploading = locked;
        const navLinks = document.querySelectorAll('a.nav-link, .navbar-brand');
        navLinks.forEach(link => {
            if (locked) {
                link.style.pointerEvents = 'none';
                link.style.opacity = '0.5';
                link.title = 'Upload en cours... Veuillez patienter';
            } else {
                link.style.pointerEvents = '';
                link.style.opacity = '';
                link.title = '';
            }
        });
    }

    function showImagePreview(file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            imagePreview.style.display = 'block';
            uploadImageBtn.disabled = false;
            updateUploadStatus('📁 Image sélectionnée - Cliquez sur "Envoyer l\'image"');
        };
        reader.readAsDataURL(file);
        selectedFile = file;
    }

    function clearImage() {
        imageFileInput.value = '';
        imagePreview.style.display = 'none';
        imageUrlInput.value = '';
        uploadImageBtn.disabled = true;
        selectedFile = null;
        hideImageError();
        uploadInstructions.style.display = 'none';
        updateUploadStatus('');
    }

    function stopCamera() {
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        cameraSection.style.display = 'none';
    }

    // Gestion de la sélection de fichier avec upload automatique
    imageFileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Vérifier le type de fichier
            if (!file.type.startsWith('image/')) {
                showImageError('Veuillez sélectionner un fichier image valide.');
                return;
            }
            
            // Vérifier la taille (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                showImageError('L\'image est trop grande (max 10MB).');
                return;
            }
            
            showImagePreview(file);
            
            // Upload automatique dès sélection
            setTimeout(() => {
                uploadImageBtn.click();
            }, 500);
        }
    });

    // Prise de photo avec la caméra
    takePhotoBtn.addEventListener('click', async function() {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'environment', // Caméra arrière sur mobile
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            });
            cameraVideo.srcObject = mediaStream;
            cameraSection.style.display = 'block';
        } catch (error) {
            console.error('Erreur caméra:', error);
            showImageError('Impossible d\'accéder à la caméra. Vérifiez les permissions.');
        }
    });

    // Capturer la photo
    capturePhotoBtn.addEventListener('click', function() {
        const canvas = photoCanvas;
        const context = canvas.getContext('2d');
        
        canvas.width = cameraVideo.videoWidth;
        canvas.height = cameraVideo.videoHeight;
        
        context.drawImage(cameraVideo, 0, 0, canvas.width, canvas.height);
        
        // Convertir en blob
        canvas.toBlob(function(blob) {
            const file = new File([blob], `photo_${Date.now()}.jpg`, { type: 'image/jpeg' });
            showImagePreview(file);
            stopCamera();
            
            // Upload automatique après capture
            setTimeout(() => {
                uploadImageBtn.click();
            }, 500);
        }, 'image/jpeg', 0.8);
    });

    // Annuler la prise de photo
    cancelPhotoBtn.addEventListener('click', stopCamera);

    // Envoi de l'image au serveur (stockée dans static/uploads/)
    uploadImageBtn.addEventListener('click', function() {
        if (!selectedFile) {
            showImageError('Aucune image sélectionnée');
            return;
        }

        const formData = new FormData();
        formData.append('image', selectedFile);

        // Activer la protection de navigation
        setNavigationLock(true);
        
        uploadImageBtn.disabled = true;
        uploadImageBtn.innerHTML = '⏳ Upload en cours...';
        updateUploadStatus('📤 Envoi de l\'image...<strong>Ne quittez pas la page</strong>', 'info');

        fetch('/api/upload-image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showImageError(data.error);
                updateUploadStatus('❌ Erreur d\'upload', 'error');
            } else if (data.image_url) {
                // Image uploadée avec succès
                imageUrlInput.value = data.image_url;
                
                updateUploadStatus('✅ Image sauvegardée et prête à utiliser!', 'success');
                
                // Plus besoin d'instructions - tout est automatique !
                hideImageError();
                uploadInstructions.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showImageError('Erreur lors de l\'upload');
            updateUploadStatus('❌ Erreur de connexion', 'error');
        })
        .finally(() => {
            // Désactiver la protection de navigation
            setNavigationLock(false);
            
            uploadImageBtn.disabled = false;
            uploadImageBtn.innerHTML = '⬆️ Envoyer l\'image';
        });
    });

    removeImageBtn.addEventListener('click', clearImage);
    
    // Nombre de jours ouvrés requis avant une demande (configurable dans /admin/working-days)
    // Valeur par défaut en attendant la réponse de l'API ; recalculée dès que la vraie valeur arrive.
    // window.deadlineWorkingDays et getMinimumValidDate() sont partagés avec la modale de
    // modification : voir leur définition dans static/js/main.js.
    window.deadlineWorkingDays = window.deadlineWorkingDays || 2;

    // Configuration de la date minimum (N jours ouvrés)
    // Labo et admin sont exemptés : ils peuvent choisir n'importe quelle date
    const isPrivilegedUser = ['admin', 'labo'].includes(document.getElementById('teacher_id')?.dataset.effectiveUserMode);

    function setMinimumDate(inputEl) {
        if (isPrivilegedUser) return; // pas de restriction pour admin/labo
        const minDate = getMinimumValidDate();
        // Utiliser les composantes locales pour éviter le décalage UTC
        const y = minDate.getFullYear();
        const m = String(minDate.getMonth() + 1).padStart(2, '0');
        const d = String(minDate.getDate()).padStart(2, '0');
        const minDateStr = `${y}-${m}-${d}`;
        inputEl.setAttribute('min', minDateStr);
        if (!inputEl.value || inputEl.value < minDateStr) {
            inputEl.value = minDateStr;
        }
    }

    function applyMinimumDateToAllFields() {
        setMinimumDate(document.getElementById('planning_date'));
        document.querySelectorAll('#daysList input[type="date"]').forEach(setMinimumDate);
    }

    // Appliquer au champ principal avec la valeur par défaut, puis recalculer avec la vraie
    // valeur configurée dès qu'elle est connue (évite de bloquer l'UI sur la requête réseau).
    applyMinimumDateToAllFields();
    if (!isPrivilegedUser) {
        fetch('/api/deadline-config')
            .then(r => r.json())
            .then(data => {
                if (data && Number.isFinite(data.deadline_working_days)) {
                    window.deadlineWorkingDays = data.deadline_working_days;
                    applyMinimumDateToAllFields();
                }
            })
            .catch(() => {}); // garde la valeur par défaut (2) en cas d'échec
    }

    // Appliquer aussi aux champs de jours supplémentaires quand ils sont ajoutés
    const originalAddDayBtn = document.getElementById('addDayBtn');
    if (originalAddDayBtn) {
        originalAddDayBtn.addEventListener('click', function() {
            // Attendre que le DOM soit mis à jour puis appliquer le min aux nouveaux inputs date
            setTimeout(() => {
                document.querySelectorAll('#daysList input[type="date"]').forEach(setMinimumDate);
            }, 50);
        });
    }
});
