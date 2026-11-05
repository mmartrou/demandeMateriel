// Script de la page mes_tps (extrait de templates/mes_tps.html).
    console.log('mes_tps.js chargé, myTeacherId =', myTeacherId);
    // Dossiers de l'enseignant pour le niveau affiché : vide = pas de dossiers, la page reste une liste simple.
    let currentChapters = [];

    document.getElementById('levelSelect').addEventListener('change', function() {
        if (!this.value) return;
        const params = `teacher_id=${myTeacherId}&level=${encodeURIComponent(this.value)}`;
        const fetchJson = url => fetch(url).then(r => {
            if (!r.ok) return r.json().then(err => { throw new Error(err.error || r.statusText); });
            return r.json();
        });
        Promise.all([fetchJson(`/api/tp-templates?${params}`), fetchJson(`/api/tp-chapters?${params}`)])
            .then(([templates, chapters]) => {
                if (!Array.isArray(templates) || !Array.isArray(chapters)) {
                    document.getElementById('tp-list').innerHTML = '<p class="text-danger">Réponse inattendue du serveur.</p>';
                    return;
                }
                currentChapters = chapters;
                if (chapters.length === 0) renderTpList('tp-list', templates, true);
                else renderTpAccordion('tp-list', chapters, templates);
            })
            .catch(err => {
                document.getElementById('tp-list').innerHTML = `<p class="text-danger">Erreur : ${escapeHtml(err.message)}</p>`;
            });
    });

    // sortable : poignée ⠿ de glisser-déposer (dossiers de Mes TPs, si SortableJS a pu être chargé)
    function tpItemHtml(tp, editable, sortable = false) {
        const action = editable
            ? `ondblclick="openTpDetail(${tp.id}, true)"`
            : `ondblclick="copyTpTemplate(${tp.id})"`;
        const handle = sortable
            ? '<span class="tp-handle text-muted me-2" title="Glisser pour déplacer ou réordonner" style="cursor: grab;">⠿</span>'
            : '';
        return `
            <div class="list-group-item list-group-item-action${sortable ? ' tp-item' : ''}" data-template-id="${tp.id}"
                ${action} style="cursor: pointer;">
                ${handle}<strong>${escapeHtml(tp.request_name)}</strong>
                <small class="text-muted ms-2">${escapeHtml(tp.room_type || 'Mixte')}</small>
                ${!editable ? '<span class="badge bg-outline-secondary float-end">Double-clic pour copier</span>' : ''}
            </div>`;
    }

    function renderTpList(containerId, templates, editable) {
        const container = document.getElementById(containerId);
        if (!templates.length) {
            container.innerHTML = '<p class="text-muted">Aucun TP trouvé pour ce niveau.</p>';
            return;
        }
        container.innerHTML = `<div class="list-group">${templates.map(tp => tpItemHtml(tp, editable)).join('')}</div>`;
    }

    // Un panneau par dossier (tous ouverts), puis "Sans dossier" (toujours affiché avec le glisser-déposer,
    // pour pouvoir y déposer un TP sorti d'un dossier).
    function renderTpAccordion(containerId, chapters, templates) {
        const sortable = typeof Sortable !== 'undefined';
        const panels = chapters.map(ch => ({ chapter: ch, label: chapterLabel(ch), tps: templates.filter(t => t.chapter_id === ch.id) }));
        const sansDossier = templates.filter(t => !chapters.some(ch => ch.id === t.chapter_id));
        if (sansDossier.length || sortable) panels.push({ chapter: null, label: 'Sans dossier', tps: sansDossier });

        const emptyHint = sortable
            ? 'Aucun TP : glissez-en un ici, ou rangez-le depuis sa fiche.'
            : 'Aucun TP dans ce dossier : rangez-y un TP depuis sa fiche.';
        const html = panels.map(p => {
            const collapseId = `tpChapter-${p.chapter ? p.chapter.id : 'none'}`;
            const actions = p.chapter ? `
                <button type="button" class="btn btn-sm btn-link text-secondary" data-edit-chapter="${p.chapter.id}" title="Modifier le dossier">✏️</button>
                <button type="button" class="btn btn-sm btn-link text-danger" data-delete-chapter="${p.chapter.id}" title="Supprimer le dossier">🗑️</button>` : '';
            // La liste reste présente même vide : c'est la zone où l'on dépose les TP.
            const body = `
                <div class="list-group list-group-flush tp-sortable" data-chapter-id="${p.chapter ? p.chapter.id : ''}" style="min-height: 2.5rem;">
                    ${p.tps.map(tp => tpItemHtml(tp, true, sortable)).join('')}
                    <p class="tp-empty-hint text-muted small m-2"${p.tps.length ? ' style="display: none;"' : ''}>${emptyHint}</p>
                </div>`;
            return `
                <div class="accordion-item">
                    <h2 class="accordion-header d-flex align-items-center">
                        <button class="accordion-button flex-grow-1" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="true" aria-controls="${collapseId}">
                            ${escapeHtml(p.label)} <span class="badge bg-secondary ms-2">${p.tps.length}</span>
                        </button>
                        ${actions}
                    </h2>
                    <div id="${collapseId}" class="accordion-collapse collapse show">
                        <div class="accordion-body p-0">${body}</div>
                    </div>
                </div>`;
        }).join('');

        const container = document.getElementById(containerId);
        container.innerHTML = `<div class="accordion">${html}</div>`;
        container.querySelectorAll('[data-edit-chapter]').forEach(btn => {
            btn.addEventListener('click', () => openChapterModal(chapters.find(ch => ch.id === Number(btn.dataset.editChapter))));
        });
        container.querySelectorAll('[data-delete-chapter]').forEach(btn => {
            btn.addEventListener('click', () => deleteChapter(chapters.find(ch => ch.id === Number(btn.dataset.deleteChapter))));
        });
        if (sortable) {
            container.querySelectorAll('.tp-sortable').forEach(list => new Sortable(list, {
                group: 'mes-tps',          // même groupe : on peut passer d'un dossier à l'autre
                handle: '.tp-handle',
                draggable: '.tp-item',     // le texte "Aucun TP" n'est pas déplaçable
                animation: 150,
                onEnd: evt => {
                    if (evt.from === evt.to && evt.oldIndex === evt.newIndex) return;
                    saveArrangement(evt.to);
                }
            }));
        }
    }

    // Enregistre le contenu d'un dossier après un glisser-déposer. Seul le dossier d'arrivée est
    // envoyé : dans celui de départ, l'ordre relatif des TP restants ne change pas.
    function saveArrangement(list) {
        const templateIds = [...list.querySelectorAll('.tp-item')].map(el => Number(el.dataset.templateId));
        fetch('/api/tp-templates/arrangement', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                chapter_id: list.dataset.chapterId ? Number(list.dataset.chapterId) : null,
                template_ids: templateIds
            })
        })
        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
        .then(() => reloadMyTps())  // met à jour les compteurs et les textes "Aucun TP"
        .catch(err => {
            showErrorToast('Erreur : ' + err.message);
            reloadMyTps();  // remet chaque TP à sa vraie place
        });
    }

    // --- Dossiers : création, modification, suppression ---
    function reloadMyTps() {
        document.getElementById('levelSelect').dispatchEvent(new Event('change'));
    }

    function openChapterModal(chapter) {
        document.getElementById('chapterId').value = chapter ? chapter.id : '';
        document.getElementById('chapterNumber').value = chapter && chapter.number != null ? chapter.number : '';
        document.getElementById('chapterTitle').value = chapter ? (chapter.title || '') : '';
        document.getElementById('chapterModalLabel').textContent = chapter ? 'Modifier le dossier' : 'Nouveau dossier';
        const modalEl = document.getElementById('chapterModal');
        (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
    }

    function saveChapter() {
        const id = document.getElementById('chapterId').value;
        const number = document.getElementById('chapterNumber').value.trim();
        const title = document.getElementById('chapterTitle').value.trim();
        if (!number && !title) {
            showErrorToast('Indiquez un numéro, un nom, ou les deux');
            return;
        }
        const level = document.getElementById('levelSelect').value;
        fetch(id ? `/api/tp-chapters/${id}` : '/api/tp-chapters', {
            method: id ? 'PUT' : 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ level, number, title })
        })
        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
        .then(() => {
            bootstrap.Modal.getInstance(document.getElementById('chapterModal'))?.hide();
            showSuccessToast(id ? 'Dossier modifié' : 'Dossier créé');
            reloadMyTps();
        })
        .catch(err => showErrorToast('Erreur : ' + err.message));
    }

    function deleteChapter(chapter) {
        if (!chapter) return;
        if (!confirm(`Supprimer le dossier « ${chapterLabel(chapter)} » ? Ses TP ne sont pas supprimés, ils iront dans « Sans dossier ».`)) return;
        fetch(`/api/tp-chapters/${chapter.id}`, { method: 'DELETE' })
            .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
            .then(() => {
                showSuccessToast('Dossier supprimé');
                reloadMyTps();
            })
            .catch(err => showErrorToast('Erreur : ' + err.message));
    }

    document.getElementById('btnNewChapter').addEventListener('click', function() {
        if (!document.getElementById('levelSelect').value) {
            showErrorToast('Choisissez d\'abord un niveau pour votre nouveau dossier.');
            return;
        }
        openChapterModal(null);
    });
    document.getElementById('btnSaveChapter').addEventListener('click', saveChapter);

    // Liste "Dossier" ajoutée à la fiche d'un TP (modale partagée avec les autres pages, d'où l'ajout
    // dynamique) ; seulement si l'enseignant a des dossiers pour ce niveau.
    function setTpChapterField(selectedChapterId) {
        document.getElementById('tpChapterField')?.remove();
        if (!currentChapters.length) return;
        const nameCol = document.getElementById('editRequestName')?.closest('.col-md-3');
        if (!nameCol) return;
        nameCol.insertAdjacentHTML('afterend', `
            <div class="col-md-3" id="tpChapterField">
                <label for="tpChapterSelect" class="form-label">📁 Dossier</label>
                <select class="form-select" id="tpChapterSelect"></select>
            </div>`);
        const select = document.getElementById('tpChapterSelect');
        select.appendChild(new Option('Sans dossier', ''));
        currentChapters.forEach(ch => select.appendChild(new Option(chapterLabel(ch), ch.id)));
        select.value = selectedChapterId != null ? String(selectedChapterId) : '';
    }

    // chapter_id à envoyer, ou undefined si la fiche n'a pas de liste "Dossier" (rangement inchangé).
    function readTpChapterField() {
        const select = document.getElementById('tpChapterSelect');
        if (!select) return undefined;
        return select.value ? parseInt(select.value, 10) : null;
    }

    let currentTpTemplateId = null;

    function openTpDetail(templateId, editable) {
        fetch(`/api/tp-templates/${templateId}`)
            .then(r => r.json())
            .then(tp => {
                currentTpTemplateId = templateId;

                const fakeRequest = {
                    id: null,
                    teacher_id: tp.teacher_id || myTeacherId,
                    request_name: tp.request_name || '',
                    request_date: '',
                    horaire: '',
                    class_name: tp.level || '',
                    material_description: tp.material_description || '',
                    selected_materials: tp.selected_materials || '',
                    material_prof: tp.material_prof || '',
                    computers_needed: tp.computers_needed || 0,
                    group_count: tp.group_count ?? 1,
                    notes: tp.notes || '',
                    image_url: tp.image_url || '',
                    room_type: tp.room_type || 'Mixte',
                    prepared: false
                };

                const modalEl = document.getElementById('editRequestModal');
                populateEditForm(fakeRequest);

                // Cacher les champs non pertinents pour un template
                ['editDate', 'editHoraire'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.parentElement?.style.setProperty('display', 'none');
                });
                const relatedCard = document.getElementById('editAllRelated')?.closest('.card');
                if (relatedCard) relatedCard.style.display = 'none';

                // Ajouter un champ d'upload d'image
                const imageSection = document.getElementById('editImageSection');
                if (imageSection && editable) {
                    const existingImg = imageSection.querySelector('img');
                    const previewHtml = existingImg ? existingImg.outerHTML : '';
                    imageSection.innerHTML = `
                        ${previewHtml ? `<div class="mb-2 text-center">${previewHtml}</div>` : ''}
                        <label class="form-label">📷 Image du TP</label>
                        <input type="file" class="form-control" id="tpImageUpload" accept="image/*">
                        <input type="hidden" id="tpImageUrl" value="${tp.image_url || ''}">
                        <div id="tpImageStatus" class="mt-1"></div>`;
                    document.getElementById('tpImageUpload').addEventListener('change', handleTpImageUpload);
                }

                if (editable) setTpChapterField(tp.chapter_id);
                else document.getElementById('tpChapterField')?.remove();

                document.querySelectorAll('#editRequestModal input, #editRequestModal select, #editRequestModal textarea')
                    .forEach(el => el.disabled = !editable);

                const saveBtn = modalEl.querySelector('.modal-footer .btn-primary');
                const delBtn = modalEl.querySelector('.modal-footer .btn-danger');
                const prepBtn = document.getElementById('modalPreparedBtn');
                if (saveBtn) saveBtn.style.display = editable ? '' : 'none';
                if (prepBtn) prepBtn.style.display = 'none';

                // Remplacer le bouton sauvegarder par notre propre logique
                if (saveBtn && editable) {
                    const newBtn = saveBtn.cloneNode(true);
                    newBtn.removeAttribute('onclick');
                    saveBtn.replaceWith(newBtn);
                    newBtn.addEventListener('click', () => saveTpTemplate(templateId));
                }

                // Remplacer le bouton supprimer
                if (delBtn && editable) {
                    const newDelBtn = delBtn.cloneNode(true);
                    newDelBtn.removeAttribute('onclick');
                    delBtn.replaceWith(newDelBtn);
                    newDelBtn.style.display = '';
                    newDelBtn.addEventListener('click', () => deleteTpTemplate(templateId));
                } else if (delBtn) {
                    delBtn.style.display = 'none';
                }

                (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
            })
            .catch(err => console.error('Erreur chargement TP:', err));
    }

    document.getElementById('btnNewTp').addEventListener('click', function() {
        const level = document.getElementById('levelSelect').value;
        if (!level) {
            showErrorToast('Choisissez d\'abord un niveau pour votre nouveau TP.');
            return;
        }
        openNewTpModal(level);
    });

    function openNewTpModal(level) {
        currentTpTemplateId = null;

        const fakeRequest = {
            id: null,
            teacher_id: myTeacherId,
            request_name: '',
            request_date: '',
            horaire: '',
            class_name: level,
            material_description: '',
            selected_materials: '',
            material_prof: '',
            computers_needed: 0,
            group_count: groupesParNiveau(level),
            notes: '',
            image_url: '',
            room_type: 'Mixte',
            prepared: false
        };

        const modalEl = document.getElementById('editRequestModal');
        populateEditForm(fakeRequest);

        // Cacher les champs non pertinents pour un template (pas de date fixe)
        ['editDate', 'editHoraire'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.parentElement?.style.setProperty('display', 'none');
        });
        const relatedCard = document.getElementById('editAllRelated')?.closest('.card');
        if (relatedCard) relatedCard.style.display = 'none';

        // Ajouter un champ d'upload d'image
        const imageSection = document.getElementById('editImageSection');
        if (imageSection) {
            imageSection.innerHTML = `
                <label class="form-label">📷 Image du TP</label>
                <input type="file" class="form-control" id="tpImageUpload" accept="image/*">
                <input type="hidden" id="tpImageUrl" value="">
                <div id="tpImageStatus" class="mt-1"></div>`;
            document.getElementById('tpImageUpload').addEventListener('change', handleTpImageUpload);
        }

        setTpChapterField(null);

        document.querySelectorAll('#editRequestModal input, #editRequestModal select, #editRequestModal textarea')
            .forEach(el => el.disabled = false);

        // Le niveau est fixé par le sélecteur au-dessus de la liste : pas modifiable ici.
        const classNameField = document.getElementById('editClassName');
        if (classNameField) classNameField.disabled = true;

        const saveBtn = modalEl.querySelector('.modal-footer .btn-primary');
        const delBtn = modalEl.querySelector('.modal-footer .btn-danger');
        const prepBtn = document.getElementById('modalPreparedBtn');
        if (prepBtn) prepBtn.style.display = 'none';
        if (delBtn) delBtn.style.display = 'none';

        const title = document.querySelector('#editRequestModal .modal-title');
        if (title) title.textContent = `Nouveau TP (${level})`;

        if (saveBtn) {
            const newBtn = saveBtn.cloneNode(true);
            newBtn.removeAttribute('onclick');
            newBtn.textContent = 'Créer le TP';
            newBtn.disabled = false;
            newBtn.style.display = '';
            saveBtn.replaceWith(newBtn);
            newBtn.addEventListener('click', () => createTpTemplate(level));
        }

        (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
    }

    // Mêmes conventions que saveRequestChanges() dans _request_modal_js.html
    function buildMaterialFields() {
        if (document.getElementById('editAbsent')?.checked) {
            return { selected_materials: 'Absent', material_description: 'Enseignant absent' };
        }
        if (document.getElementById('editNoMaterial')?.checked) {
            return { selected_materials: 'Pas besoin de matériel', material_description: 'Cours théorique sans matériel' };
        }
        if (document.getElementById('editExamMode')?.checked) {
            return { selected_materials: 'Examen', material_description: "Surveillance d'examen" };
        }
        const checkedMaterials = Array.from(document.querySelectorAll('input[name="editMaterials"]:checked'))
            .map(cb => cb.value);
        const freeText = (document.getElementById('editMaterialDescription')?.value || '').trim();
        const allMats = [...checkedMaterials];
        if (freeText) allMats.push(freeText);
        return {
            selected_materials:   allMats.length ? '- ' + allMats.join('\n- ') : '',
            material_description: freeText ? `Matériel requis: ${freeText}` : 'Cours sans matériel spécifique'
        };
    }

    function createTpTemplate(level) {
        const requestName = (document.getElementById('editRequestName')?.value || '').trim();
        if (!requestName) {
            showErrorToast('Le nom du TP est obligatoire.');
            return;
        }

        const data = {
            level:                level,
            request_name:         requestName,
            ...buildMaterialFields(),
            material_prof:        document.getElementById('editMaterialProf')?.value || '',
            computers_needed:     parseInt(document.getElementById('editComputersNeeded')?.value, 10) || 0,
            group_count:          parseGroupCount(document.getElementById('editQuantity')?.value),
            notes:                document.getElementById('editNotes')?.value || '',
            image_url:            document.getElementById('tpImageUrl')?.value || '',
            room_type:            'Mixte'
        };
        const chapterId = readTpChapterField();
        if (chapterId !== undefined) data.chapter_id = chapterId;

        fetch('/api/tp-templates', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
        .then(() => {
            const modalEl = document.getElementById('editRequestModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            showSuccessToast(`TP "${requestName}" créé`);
            const levelSelect = document.getElementById('levelSelect');
            if (levelSelect.value === level) {
                levelSelect.dispatchEvent(new Event('change'));
            } else {
                levelSelect.value = level;
                levelSelect.dispatchEvent(new Event('change'));
            }
        })
        .catch(err => showErrorToast('Erreur : ' + err.message));
    }

    function handleTpImageUpload() {
        const file = this.files[0];
        if (!file) return;
        const status = document.getElementById('tpImageStatus');
        status.innerHTML = '<span class="text-info">⏳ Upload en cours...</span>';
        const formData = new FormData();
        formData.append('image', file);
        fetch('/api/upload-image', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                if (data.success && data.image_url) {
                    document.getElementById('tpImageUrl').value = data.image_url;
                    status.innerHTML = '<span class="text-success">✅ Image uploadée</span>';
                    const section = document.getElementById('editImageSection');
                    const oldPreview = section.querySelector('.text-center');
                    if (oldPreview) {
                        oldPreview.innerHTML = `<img src="${data.image_url}" class="img-thumbnail" style="max-width:120px;max-height:120px;">`;
                    } else {
                        section.insertAdjacentHTML('afterbegin', `<div class="mb-2 text-center"><img src="${data.image_url}" class="img-thumbnail" style="max-width:120px;max-height:120px;"></div>`);
                    }
                } else {
                    status.innerHTML = `<span class="text-danger">❌ ${data.error || 'Erreur'}</span>`;
                }
            })
            .catch(() => { status.innerHTML = '<span class="text-danger">❌ Erreur réseau</span>'; });
    }

    function saveTpTemplate(templateId) {
        const data = {
            request_name:        document.getElementById('editRequestName')?.value || '',
            ...buildMaterialFields(),
            material_prof:       document.getElementById('editMaterialProf')?.value || '',
            computers_needed:    parseInt(document.getElementById('editComputersNeeded')?.value, 10) || 0,
            group_count:         parseGroupCount(document.getElementById('editQuantity')?.value),
            notes:               document.getElementById('editNotes')?.value || '',
            image_url:           document.getElementById('tpImageUrl')?.value || '',
            room_type:           'Mixte'
        };
        const chapterId = readTpChapterField();
        if (chapterId !== undefined) data.chapter_id = chapterId;

        fetch(`/api/tp-templates/${templateId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error || 'Erreur serveur'); }); return r.json(); })
        .then(() => {
            const modalEl = document.getElementById('editRequestModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            showSuccessToast('Template TP sauvegardé');
            // Recharger la liste
            document.getElementById('levelSelect').dispatchEvent(new Event('change'));
        })
        .catch(err => showErrorToast('Erreur : ' + err.message));
    }

    function deleteTpTemplate(templateId) {
        if (!confirm('Supprimer ce TP de vos templates ? Les demandes existantes ne seront pas affectées.')) return;
        fetch(`/api/tp-templates/${templateId}`, { method: 'DELETE' })
            .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
            .then(() => {
                const modalEl = document.getElementById('editRequestModal');
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
                showSuccessToast('Template TP supprimé');
                document.getElementById('levelSelect').dispatchEvent(new Event('change'));
            })
            .catch(err => showErrorToast('Erreur : ' + err.message));
    }

    function copyTpTemplate(templateId) {
        fetch(`/api/tp-templates/${templateId}`)
            .then(r => r.json())
            .then(tp => {
                const fakeRequest = {
                    id: null,
                    teacher_id: tp.teacher_id,
                    request_name: tp.request_name || '',
                    request_date: '',
                    horaire: '',
                    class_name: tp.level || '',
                    material_description: tp.material_description || '',
                    selected_materials: tp.selected_materials || '',
                    material_prof: tp.material_prof || '',
                    computers_needed: tp.computers_needed || 0,
                    group_count: tp.group_count ?? 1,
                    notes: tp.notes || '',
                    image_url: tp.image_url || '',
                    room_type: tp.room_type || 'Mixte',
                    prepared: false
                };

                const modalEl = document.getElementById('editRequestModal');
                populateEditForm(fakeRequest);

                ['editDate', 'editHoraire'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.parentElement?.style.setProperty('display', 'none');
                });
                const relatedCard = document.getElementById('editAllRelated')?.closest('.card');
                if (relatedCard) relatedCard.style.display = 'none';

                // Le dossier d'un collègue ne concerne pas la copie
                document.getElementById('tpChapterField')?.remove();

                // Tout en lecture seule
                document.querySelectorAll('#editRequestModal input, #editRequestModal select, #editRequestModal textarea')
                    .forEach(el => el.disabled = true);

                const prepBtn = document.getElementById('modalPreparedBtn');
                if (prepBtn) prepBtn.style.display = 'none';
                const delBtn = modalEl.querySelector('.modal-footer .btn-danger');
                if (delBtn) delBtn.style.display = 'none';

                // Remplacer le bouton sauvegarder par "Copier vers mes TPs"
                const saveBtn = modalEl.querySelector('.modal-footer .btn-primary');
                if (saveBtn) {
                    const newBtn = saveBtn.cloneNode(true);
                    newBtn.removeAttribute('onclick');
                    newBtn.textContent = '📋 Copier vers mes TPs';
                    newBtn.disabled = false;
                    saveBtn.replaceWith(newBtn);
                    newBtn.addEventListener('click', () => {
                        const name = prompt('Nom pour votre copie de ce TP :', tp.request_name || '');
                        if (!name || !name.trim()) return;
                        const level = document.getElementById('otherLevelSelect').value;
                        fetch('/api/tp-templates/copy', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ source_id: templateId, request_name: name.trim(), level: level })
                        })
                        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
                        .then(() => {
                            const modal = bootstrap.Modal.getInstance(modalEl);
                            if (modal) modal.hide();
                            showSuccessToast(`TP "${name.trim()}" copié dans vos TPs`);
                            const myLevel = document.getElementById('levelSelect');
                            if (myLevel.value === level) myLevel.dispatchEvent(new Event('change'));
                        })
                        .catch(err => showErrorToast('Erreur : ' + err.message));
                    });
                }

                (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
            })
            .catch(err => console.error('Erreur chargement TP:', err));
    }

    document.getElementById('btnVoirAutres').addEventListener('click', function() {
        const section = document.getElementById('autres-section');
        const visible = section.style.display !== 'none';
        section.style.display = visible ? 'none' : '';
        this.textContent = visible ? 'Voir les TPs des autres enseignants' : 'Masquer les TPs des autres enseignants';
    });

    document.getElementById('otherTeacherSelect').addEventListener('change', function() {
        document.getElementById('otherLevelSelect').dispatchEvent(new Event('change'));
    });

    document.getElementById('otherLevelSelect').addEventListener('change', function() {
        const otherId = document.getElementById('otherTeacherSelect').value;
        if (!this.value || !otherId) return;
        fetch(`/api/tp-templates?teacher_id=${otherId}&level=${encodeURIComponent(this.value)}`)
            .then(r => {
                if (!r.ok) return r.json().then(err => { throw new Error(err.error || r.statusText); });
                return r.json();
            })
            .then(templates => {
                if (!Array.isArray(templates)) {
                    document.getElementById('autres-tp-list').innerHTML = '<p class="text-danger">Réponse inattendue du serveur.</p>';
                    return;
                }
                renderTpList('autres-tp-list', templates, false);
            })
            .catch(err => {
                document.getElementById('autres-tp-list').innerHTML = `<p class="text-danger">Erreur : ${err.message}</p>`;
            });
    });
