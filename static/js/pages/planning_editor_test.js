// Script de la page planning_editor_test (extrait de templates/planning_editor_test.html).
    // Rafraîchit la carte d'une demande modifiée/supprimée via la modale,
    // sans relancer l'optimiseur (les autres cours ne bougent pas).
    async function loadRequests() {
        loadAllRequestsForRelatedDetection(); // garde window.allRequests à jour après la sauvegarde
        if (!planningData) return;
        const requestId = document.getElementById('editRequestId').value;
        if (!requestId) return;

        const idx = planningData.courses.findIndex(c => String(c.request_id) === String(requestId));
        if (idx === -1) return;

        const targetDate = document.getElementById('target-date').value;
        try {
            const response = await fetch(`/api/planning-editor/course/${requestId}?date=${targetDate}`);
            if (response.status === 404) {
                // La demande a été supprimée : retirer la carte et son emplacement
                const removedId = planningData.courses[idx].id;
                planningData.courses.splice(idx, 1);
                delete currentRoomAssignments[removedId];
                if (planningData.room_assignments) delete planningData.room_assignments[removedId];
            } else if (response.ok) {
                const updated = await response.json();
                const oldId = planningData.courses[idx].id;
                planningData.courses[idx] = Object.assign({}, planningData.courses[idx], updated, { id: oldId });
            } else {
                return;
            }
            await syncPreparedStates();
            renderPlanningGrid();
            updateStats();
            await savePlanningData();
        } catch (e) {
            console.warn('loadRequests: rafraîchissement impossible:', e);
        }
    }
    // Hook: update prepared badge on card when toggled from the modal
    window.onPreparedToggled = function(requestId, isPrepared) {
        const card = document.querySelector(`.course-card[data-request-id="${requestId}"]`);
        if (!card) return;
        const badge = card.querySelector('.prepared-badge');
        if (isPrepared && !badge) {
            const span = document.createElement('span');
            span.className = 'prepared-badge';
            span.textContent = '✓';
            card.insertBefore(span, card.firstChild);
        } else if (!isPrepared && badge) {
            badge.remove();
        }
        card.dataset.prepared = isPrepared ? '1' : '0';
        const course = planningData?.courses?.find(c => c.request_id == requestId);
        if (course) course.prepared = isPrepared;
    };

    let planningData = null;
    let currentAssignments = {};
    let currentRoomAssignments = {};
    let draggedElement = null;
    let originalPosition = null;

    // Identifiant de la colonne "stockage temporaire" (pas une vraie salle) et données
    // de la colonne "Occupation standard" ({slot: valeur}) pour le jour de semaine affiché
    const TEMP_STORAGE_ID = '__TEMP__';
    let standardOccupationData = {};

    async function syncPreparedStates() {
        if (!planningData?.courses) return;
        const ids = planningData.courses.map(c => c.request_id).filter(id => id != null && Number.isInteger(Number(id)));
        if (ids.length === 0) return;
        try {
            const resp = await fetch(`/api/requests/prepared-states?ids=${ids.join(',')}`);
            if (!resp.ok) return;
            const states = await resp.json();
            planningData.courses.forEach(course => {
                if (course.request_id != null) {
                    const s = states[String(course.request_id)];
                    if (s !== undefined) course.prepared = s;
                }
            });
        } catch (e) {
            console.warn('syncPreparedStates failed:', e);
        }
    }
    const isPrivileged = ['admin', 'labo'].includes(window.APP_CONFIG.userRole);

    // Charge les demandes à venir (tous enseignants) pour que la modale d'édition puisse
    // détecter les demandes liées (même enseignant + même nom), comme sur "Voir les
    // demandes" et le calendrier — sans ça window.allRequests reste vide ici et aucun TP
    // lié n'apparaît jamais.
    function loadAllRequestsForRelatedDetection() {
        const todayStr = new Date().toISOString().split('T')[0];
        return fetch(`/api/requests?start_date=${todayStr}`, { cache: 'no-store' })
            .then(r => r.json())
            .then(data => { window.allRequests = Array.isArray(data) ? data : []; })
            .catch(error => console.warn('loadAllRequestsForRelatedDetection:', error));
    }

    // Initialiser la date par défaut (demain) et charger le planning correspondant s'il existe
    document.addEventListener('DOMContentLoaded', function() {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const targetDate = tomorrow.toISOString().split('T')[0];
        document.getElementById('target-date').value = targetDate;
        updatePlanningDateHeading();
        reloadPlanningIfExists(targetDate);
    });
    
    // Charger les données du planning
    async function loadPlanningData() {
        const targetDate = document.getElementById('target-date').value;
        
        if (!targetDate) {
            showAlert('Veuillez sélectionner une date.', 'warning');
            return;
        }
        
        showLoading('loading-container');

        try {
            console.log('🔄 Appel API avec date:', targetDate);
            // Lancée en parallèle de la requête principale (pas après) pour ne pas ajouter
            // un aller-retour réseau supplémentaire au temps de chargement perçu.
            const standardOccupationPromise = loadStandardOccupationForDate(targetDate);
            const labTestPromise = loadLabTestRequests(targetDate);
            loadAllRequestsForRelatedDetection();
            const response = await fetch(`/api/planning-editor/data?date=${targetDate}`);
            console.log('📡 Réponse API status:', response.status);
            const data = await response.json();
            console.log('📋 Données reçues:', data);

            if (response.ok) {
                if (data.error) {
                    throw new Error(data.error);
                }
                if (!data.courses || data.courses.length === 0) {
                    throw new Error('Aucun cours trouvé pour cette date.');
                }

                planningData = data;
                currentAssignments = { ...data.assignments };
                currentRoomAssignments = { ...data.room_assignments || {} };

                document.getElementById('observations-section').style.display = '';

                await Promise.all([syncPreparedStates(), standardOccupationPromise, labTestPromise]);
                renderPlanningGrid();
                updateStats();
                document.getElementById('generate-btn').disabled = false;
                showAlert('Planning généré et prêt à éditer!', 'success');

                // Enregistrement automatique dès la première génération
                await savePlanningData();
            } else {
                throw new Error(data.error || 'Erreur lors de la génération');
            }
        } catch (error) {
            console.error('Erreur:', error);
            showAlert(`Erreur lors de la génération: ${error.message}`, 'danger');
        } finally {
            hideLoading('loading-container');
        }
    }
    
    // Affiche "Mercredi 09/09/2026" au-dessus de la grille, à partir de la date sélectionnée
    function updatePlanningDateHeading() {
        const heading = document.getElementById('planning-date-heading');
        if (!heading) return;
        const dateStr = document.getElementById('target-date').value;
        if (!dateStr) { heading.textContent = ''; return; }
        const dayNames = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
        const d = new Date(`${dateStr}T00:00:00`);
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        heading.textContent = `${dayNames[d.getDay()]} ${dd}/${mm}/${d.getFullYear()}`;
    }

    // Afficher le planning en grille type Excel
    function renderPlanningGrid() {
        console.log('🎨 renderPlanningGrid() appelée, planningData:', planningData);
        if (!planningData) {
            console.log('❌ Pas de planningData, arrêt');
            return;
        }
        updatePlanningDateHeading();
        
        const container = document.getElementById('rooms-container');
        console.log('📦 Container trouvé:', container);
        
        // IMPORTANT: Réinitialiser complètement le container pour éviter les cours fantômes
        console.log('🧹 Nettoyage du container avant re-rendu');
        container.innerHTML = '';
        container.className = 'table-responsive'; // Ajouter classe responsive pour défilement horizontal
        
        const rooms = planningData.rooms;
        console.log('🔍 DEBUG: planningData structure:', Object.keys(planningData));
        console.log('🔍 DEBUG: rooms variable:', rooms);
        console.log('🔍 DEBUG: rooms type:', typeof rooms);
        console.log('🔍 DEBUG: rooms is array?', Array.isArray(rooms));
        
        // Générer tous les créneaux de 15 minutes de 9h00 à 19h15 côté client
        const timeSlots = generateAllTimeSlots();
        
        console.log('🏢 Salles disponibles:', rooms);
        console.log('⏰ Créneaux horaires complets (15min):', timeSlots);
        console.log('📊 Total créneaux:', timeSlots.length);
        
        // Créer la grille principale
        const grid = document.createElement('div');
        grid.className = 'planning-grid';
        console.log('📋 Grille créée:', grid);
        
        // En-tête avec les noms des salles
        const headerRow = document.createElement('div');
        headerRow.className = 'grid-header';
        
        // Cellule vide pour l'angle
        const cornerCell = document.createElement('div');
        cornerCell.className = 'time-header';
        cornerCell.textContent = 'Horaire';
        headerRow.appendChild(cornerCell);
        
        // En-têtes des salles
        rooms.forEach(room => {
            const roomHeaderCell = document.createElement('div');
            roomHeaderCell.className = 'room-header-cell';
            roomHeaderCell.dataset.room = room.name;
            roomHeaderCell.textContent = room.name;
            headerRow.appendChild(roomHeaderCell);
        });

        // En-têtes des 3 colonnes additionnelles : stockage temporaire, occupation standard, occupation calculée
        const tempHeaderCell = document.createElement('div');
        tempHeaderCell.className = 'room-header-cell extra-col-header';
        tempHeaderCell.dataset.room = TEMP_STORAGE_ID;
        tempHeaderCell.textContent = 'Stockage';
        tempHeaderCell.title = 'Zone temporaire pour échanger deux cours (à vider avant enregistrement)';
        headerRow.appendChild(tempHeaderCell);

        const standardHeaderCell = document.createElement('div');
        standardHeaderCell.className = 'room-header-cell extra-col-header';
        standardHeaderCell.title = 'Occupation standard';
        headerRow.appendChild(standardHeaderCell);

        const computedHeaderCell = document.createElement('div');
        computedHeaderCell.className = 'room-header-cell extra-col-header';
        computedHeaderCell.title = 'Cours simultanés';
        headerRow.appendChild(computedHeaderCell);

        grid.appendChild(headerRow);
        
        // Debug des correspondances IDs
        console.log('🔍 Premiers cours (IDs):', planningData.courses.slice(0, 3).map(c => ({id: c.id, teacher: c.teacher, subject: c.subject})));
        console.log('🔍 Room assignments (clés):', Object.keys(currentRoomAssignments).slice(0, 5));
        console.log('🔍 currentRoomAssignments complet:', currentRoomAssignments);
        console.log('🔍 Correspondance ID cours 0:', {
            courseId: planningData.courses[0]?.id,
            assignment: currentRoomAssignments[planningData.courses[0]?.id]
        });
        
        // Compteur de placement des cours
        let totalCoursesPlaced = 0;
        let placementByRoom = {};
        rooms.forEach(room => placementByRoom[room.name] = 0);
        
        // Créneaux dont la ligne de début doit être davantage mise en évidence
        // (repère pause déjeuner / après-midi)
        const strongBoundarySlots = window.SITE_CONFIG.separators;
        // Référence des cellules horaires, pour positionner les repères une fois la grille insérée dans le DOM
        // (mesure réelle plutôt qu'un calcul manuel, pour rester fiable quel que soit le rendu du CSS Grid)
        const slotBoundaryCells = [];

        // Créer une ligne pour chaque créneau horaire avec hauteur proportionnelle à la durée
        timeSlots.forEach((slot, slotIndex) => {
            const row = document.createElement('div');
            row.className = 'grid-row';

            // Calculer la hauteur en fonction de la durée du créneau
            const slotDuration = getSlotDuration(slot);
            // Base: 60px pour 30min, 90px pour 45min, 120px pour 60min (1,5x la taille d'origine)
            const cellHeight = (slotDuration / 30) * 60; // 30min → 60px, 45min → 90px, 60min → 120px
            const isOddRow = slotIndex % 2 === 1;
            const isStrongBoundary = strongBoundarySlots.includes(slot);

            // Cellule de l'horaire
            const timeCell = document.createElement('div');
            timeCell.className = 'time-cell';
            if (isOddRow) timeCell.classList.add('row-odd');
            if (slotIndex === 0) timeCell.classList.add('first-slot');
            timeCell.dataset.slot = slot;
            timeCell.style.height = `${cellHeight}px`;
            const timeLabel = document.createElement('span');
            timeLabel.className = 'time-label';
            timeLabel.textContent = slot;
            timeCell.appendChild(timeLabel);
            row.appendChild(timeCell);
            slotBoundaryCells.push({ el: timeCell, isStrong: isStrongBoundary, isOdd: isOddRow });

            // Cellules vides pour chaque salle (les cours seront positionnés par position absolute)
            rooms.forEach((room, roomIndex) => {
                const roomCell = document.createElement('div');
                roomCell.className = 'room-cell drop-zone';
                if (isOddRow) roomCell.classList.add('row-odd');
                if (isStrongBoundary) roomCell.classList.add('time-boundary-strong');
                roomCell.dataset.room = room.name;
                roomCell.dataset.slot = slot;
                roomCell.dataset.slotIndex = slotIndex;
                roomCell.dataset.roomIndex = roomIndex;
                roomCell.style.height = `${cellHeight}px`;

                // Configurer les événements de drop
                setupDropZone(roomCell);

                row.appendChild(roomCell);
            });

            // Colonne de stockage temporaire (échange de deux cours) : se comporte comme une salle
            // "virtuelle" pour le drag & drop, mais n'est jamais persistée comme une vraie salle
            const tempCell = document.createElement('div');
            tempCell.className = 'room-cell drop-zone temp-storage-cell';
            if (isOddRow) tempCell.classList.add('row-odd');
            if (isStrongBoundary) tempCell.classList.add('time-boundary-strong');
            tempCell.dataset.room = TEMP_STORAGE_ID;
            tempCell.dataset.slot = slot;
            tempCell.dataset.slotIndex = slotIndex;
            tempCell.style.height = `${cellHeight}px`;
            setupDropZone(tempCell);
            row.appendChild(tempCell);

            // Colonne "Occupation standard" : saisie manuelle, persistée par jour de semaine + créneau
            const standardCell = document.createElement('div');
            standardCell.className = 'extra-col-cell standard-occupation-cell';
            if (isOddRow) standardCell.classList.add('row-odd');
            if (isStrongBoundary) standardCell.classList.add('time-boundary-strong');
            standardCell.style.height = `${cellHeight}px`;
            const standardInput = document.createElement('input');
            standardInput.type = 'number';
            standardInput.min = '0';
            standardInput.className = 'standard-occupation-input';
            const existingStandardValue = standardOccupationData[slot];
            standardInput.value = (existingStandardValue === undefined || existingStandardValue === null) ? '' : existingStandardValue;
            standardCell.appendChild(standardInput);
            row.appendChild(standardCell);

            // Colonne "Cours simultanés" : calculée par l'application, comparée à l'occupation standard
            const computedCell = document.createElement('div');
            computedCell.className = 'extra-col-cell computed-occupation-cell';
            if (isOddRow) computedCell.classList.add('row-odd');
            if (isStrongBoundary) computedCell.classList.add('time-boundary-strong');
            computedCell.style.height = `${cellHeight}px`;
            row.appendChild(computedCell);

            const refreshComputedCell = () => {
                const count = countSimultaneousCourses(slot);
                computedCell.textContent = count;
                const standardValue = standardOccupationData[slot];
                computedCell.classList.remove('occupation-match', 'occupation-mismatch');
                if (standardValue !== undefined && standardValue !== null && standardValue !== '') {
                    computedCell.classList.add(count === Number(standardValue) ? 'occupation-match' : 'occupation-mismatch');
                }
            };
            refreshComputedCell();

            standardInput.addEventListener('change', async () => {
                const raw = standardInput.value;
                const value = raw === '' ? null : parseInt(raw, 10);
                if (value !== null) standardOccupationData[slot] = value;
                else delete standardOccupationData[slot];
                refreshComputedCell();
                await saveStandardOccupation(document.getElementById('target-date').value, slot, value);
            });

            grid.appendChild(row);
        });

        // Placer les cours dans leurs cellules de début avec débordement contrôlé
        planningData.courses.forEach(course => {
            const assignedRoom = currentRoomAssignments[course.id];
            if (!assignedRoom) return;
            
            // Trouver l'index du créneau de début
            const startSlotIndex = timeSlots.findIndex(slot => slot === course.time);
            if (startSlotIndex === -1) {
                console.warn(`⚠️ Créneau introuvable pour ${course.time}`, timeSlots);
                return;
            }
            
            // Trouver l'index de la salle (le stockage temporaire n'est pas une vraie salle mais reste valide)
            const roomIndex = rooms.findIndex(room => room.name === assignedRoom);
            if (roomIndex === -1 && assignedRoom !== TEMP_STORAGE_ID) return;
            
            // Trouver la cellule de départ
            const startCell = grid.querySelector(`[data-slot="${course.time}"][data-room="${assignedRoom}"]`);
            if (!startCell) {
                console.warn(`⚠️ Cellule introuvable pour ${course.time} - ${assignedRoom}`);
                return;
            }
            
            // Créer le cours avec débordement sur plusieurs cellules
            const courseCard = createCourseCardWithOverflow(course, startSlotIndex, timeSlots);
            
            // L'ajouter à la cellule de départ
            startCell.appendChild(courseCard);
            
            totalCoursesPlaced++;
            if (placementByRoom[assignedRoom] !== undefined) placementByRoom[assignedRoom]++;
        });
        
        container.appendChild(grid);
        console.log('✅ Grille ajoutée au container');

        // Overlay de repères horaires dessiné par-dessus les cartes de cours :
        // une ligne fine, la suivante en pointillé, en alternance, avec 12h15/15h15 renforcées.
        // Positionné par mesure réelle (getBoundingClientRect) une fois la grille dans le DOM,
        // pour rester fiable quels que soient les gaps/bordures du CSS Grid.
        const linesOverlay = document.createElement('div');
        linesOverlay.className = 'time-lines-overlay';
        const gridRect = grid.getBoundingClientRect();
        slotBoundaryCells.forEach(boundary => {
            const cellRect = boundary.el.getBoundingClientRect();
            const line = document.createElement('div');
            line.className = 'time-line' + (boundary.isStrong ? ' time-line-strong' : (boundary.isOdd ? ' time-line-dashed' : ''));
            line.style.top = `${cellRect.top - gridRect.top}px`;
            linesOverlay.appendChild(line);
        });
        grid.appendChild(linesOverlay);
        
        // Debug du placement final
        console.log('📊 PLACEMENT FINAL:', {
            totalCoursesPlaced: totalCoursesPlaced,
            placementByRoom: placementByRoom,
            totalCoursesExpected: planningData.courses.length
        });
        
        // Masquer le message "aucun planning"
        const noMsg = document.getElementById('no-planning-message');
        const statsPanel = document.getElementById('stats-panel');
        console.log('🎭 Masquage du message "aucun planning", éléments:', noMsg, statsPanel);
        
        if (noMsg) noMsg.style.display = 'none';
        if (statsPanel) statsPanel.style.display = 'block';
        
        console.log('✅ renderPlanningGrid() terminé avec succès');
    }
    
    // Créer une carte de cours
    function createCourseCard(course, startSlotIndex, timeSlots) {
        const card = document.createElement('div');
        card.className = `course-card ${getCourseType(course.subject)}`;
        card.draggable = true;
        card.dataset.courseId = course.id;
        
        // Calculer la position de fin précise du cours
        const durationInMinutes = typeof course.duration === 'number' ? course.duration : parseDurationToMinutes(course.duration || 85);
        const endSlotPosition = calculateEndSlotPosition(startSlotIndex, durationInMinutes);
        
        // Utiliser CSS Grid pour positionner et étendre le cours
        // +2 car nous avons une ligne d'en-tête (index 1), les créneaux commencent à l'index 2
        const gridRowStart = startSlotIndex + 2;
        const gridRowEnd = endSlotPosition + 2;
        
        card.style.gridRowStart = gridRowStart;
        card.style.gridRowEnd = gridRowEnd;
        card.style.zIndex = '10';
        
        // Formatage de la durée pour affichage
        const durationText = course.duration ? formatDuration(course.duration) : '';
        
        // Construire la liste des équipements spécifiques
        const equipments = [];
        if (course.ordinateurs > 0) equipments.push(`💻 ${course.ordinateurs} PC`);
        if (course.eviers > 0) equipments.push(`🚰 ${course.eviers} éviers`);
        if (course.hotte > 0) equipments.push(`🌬️ Hotte`);
        if (course.bancs_optiques > 0) equipments.push(`🔬 Bancs opt.`);
        if (course.obscurite_totale > 0) equipments.push(`🌑 Obscurité totale`);
        if (course.becs_electriques > 0) equipments.push(`🔥 Becs élec.`);
        if (course.support_filtration > 0) equipments.push(`⚗️ Filtration`);
        if (course.imprimante > 0) equipments.push(`🖨️ Imprimante`);
        if (course.examen > 0) equipments.push(`📝 Examen`);
        
        const equipmentLine = equipments.length > 0 ? `<div class="course-equipment" style="font-size: 0.7em; margin-top: 2px;">${equipments.join(', ')}</div>` : '';
        const requestNameLine = course.request_name ? `<div class="course-request-name" style="font-size: 0.75em; font-style: italic; margin-top: 1px; color: #555;">${course.request_name}</div>` : '';
        
        card.innerHTML = `
            <div class="course-title">${course.subject}</div>
            <div class="course-level">${course.level}</div>
            <div class="course-teacher">${course.teacher}</div>
            <div class="course-time">${course.time}${durationText ? ` (${durationText})` : ''}</div>
            ${requestNameLine}
            ${equipmentLine}
        `;
        
        console.log(`📅 Cours ${course.subject} - Grid: lignes ${gridRowStart} à ${gridRowEnd} (${durationInMinutes}min)`);
        
        // Ajouter les événements de drag
        setupDragEvents(card);
        
        return card;
    }

    // Créer une carte de cours avec débordement contrôlé
    function createCourseCardWithOverflow(course, startSlotIndex, timeSlots) {
        const card = document.createElement('div');
        card.className = `course-card ${getCourseType(course.subject)}`;
        card.draggable = true;
        card.dataset.courseId = course.id;
        
        // Calculer la durée en minutes
        const durationInMinutes = typeof course.duration === 'number' ? course.duration : parseDurationToMinutes(course.duration || 85);
        
        // Calculer la hauteur totale en cumulant les hauteurs des créneaux traversés
        let totalHeight = 0;
        let remainingDuration = durationInMinutes;
        let currentSlotIndex = startSlotIndex;
        
        while (remainingDuration > 0 && currentSlotIndex < timeSlots.length) {
            const slot = timeSlots[currentSlotIndex];
            const slotDuration = getSlotDuration(slot);
            const usedDuration = Math.min(remainingDuration, slotDuration);
            
            // Calculer la hauteur proportionnelle de ce créneau
            const baseCellHeight = (slotDuration / 30) * 60; // 30min → 60px, 45min → 90px, 60min → 120px
            const proportionalHeight = (usedDuration / slotDuration) * baseCellHeight;
            
            totalHeight += proportionalHeight;
            remainingDuration -= usedDuration;
            currentSlotIndex++;
        }

        // Utiliser position absolute pour déborder sur les cellules suivantes
        card.style.position = 'absolute';
        card.style.top = '1px';
        card.style.left = '1px';
        card.style.right = '1px';
        card.style.height = `${totalHeight - 2}px`; // -2px pour les marges
        card.style.zIndex = '10';
        
        // Formatage de la durée pour affichage
        const durationText = course.duration ? formatDuration(course.duration) : '';

        // Supprimer les mots "chimie", "physique" ou "mixte" du sujet
        const filteredSubject = course.subject.replace(/\b(chimie|physique|mixte)\b/gi, '').trim();

        // Construire la liste des équipements spécifiques
        const equipments = [];
        if (course.ordinateurs > 0) equipments.push(`💻 ${course.ordinateurs} PC`);
        if (course.eviers > 0) equipments.push(`🚰 ${course.eviers} éviers`);
        if (course.hotte > 0) equipments.push(`🌬️ Hotte`);
        if (course.bancs_optiques > 0) equipments.push(`🔬 Bancs opt.`);
        if (course.obscurite_totale > 0) equipments.push(`🌑 Obscurité totale`);
        if (course.becs_electriques > 0) equipments.push(`🔥 Becs élec.`);
        if (course.support_filtration > 0) equipments.push(`⚗️ Filtration`);
        if (course.imprimante > 0) equipments.push(`🖨️ Imprimante`);
        if (course.examen > 0) equipments.push(`📝 Examen`);
        
        const equipmentLine = equipments.length > 0 ? `<div class="course-equipment" style="font-size: 0.7em; margin-top: 2px;">${equipments.join(', ')}</div>` : '';
        const requestNameLine = course.request_name ? `<div class="course-request-name" style="font-size: 0.75em; font-style: italic; margin-top: 1px; color: #555;">${course.request_name}</div>` : '';

        const preparedBadge = course.prepared ? '<span class="prepared-badge">✓</span>' : '';

        const teacherDisplay = course.teacher_short_name || course.teacher;
        const levelDisplay = course.level_short_name || course.level;
        const laboObs = course.labo_observations ? `<div style="font-size:0.75em; color:#555; margin-top:2px; font-style:italic;">${course.labo_observations}</div>` : '';
        const isClasseEntiere = course.level === '2nd Classe';
        const studentLine = (isClasseEntiere && course.students > 0)
            ? `<div style="font-weight:bold; font-size:1.5em; margin-top:1px;">${course.students}</div>` : '';
        const computersColor = course.ordinateurs_overflow ? 'color:#dc3545;' : '';
        const computersLine = (course.ordinateurs > 0)
            ? `<div style="font-weight:bold; font-size:1.5em; margin-top:1px; ${computersColor}">💻 ${course.ordinateurs}</div>` : '';

        card.innerHTML = `
            ${preparedBadge}
            <div style="font-weight:bold; font-size:1.5em; line-height:1.2;">${teacherDisplay}</div>
            <div style="font-size:0.9em;">${levelDisplay}</div>
            ${laboObs}
            ${studentLine}
            ${computersLine}
        `;

        card.dataset.prepared = course.prepared ? '1' : '0';
        if (course.request_id) card.dataset.requestId = course.request_id;

        console.log(`📅 Cours ${course.subject} - Hauteur cumulée: ${totalHeight.toFixed(1)}px (${durationInMinutes}min)`);

        // Ajouter les événements de drag
        setupDragEvents(card);

        // Double-clic : ouvrir la modale de modification
        card.addEventListener('dblclick', function(e) {
            e.stopPropagation();
            const dbId = course.request_id && Number.isInteger(Number(course.request_id)) ? course.request_id : null;
            if (!dbId) {
                showAlert('Régénérez le planning (bouton "Générer et éditer") pour activer la visualisation des demandes.', 'warning');
                return;
            }
            editRequest(dbId);
        });

        return card;
    }
    
    // Calculer la hauteur d'un cours basée sur sa durée
    function calculateCourseHeight(duration) {
        // Système de hauteur proportionnelle à la durée réelle
        // Base : 40px pour 55min (cours le plus court)
        // Échelle : 55min=40px, 85min=60px, 110min=80px
        const baseHeight = 40; // pixels pour 55 minutes (cours le plus court)
        const baseDuration = 55; // minutes (cours le plus court)
        
        // Convertir la durée en minutes si nécessaire
        let durationInMinutes = duration;
        if (typeof duration === 'string') {
            // Parser la durée si c'est une chaîne (ex: "1h30", "90min", "1.5h")
            durationInMinutes = parseDurationToMinutes(duration);
        }
        
        // Calculer la hauteur proportionnelle avec un facteur d'échelle légèrement réduit
        const scaleFactor = 0.7; // Pour éviter des cours trop hauts
        const rawHeight = (durationInMinutes / baseDuration) * baseHeight;
        const calculatedHeight = Math.max(35, Math.min(120, rawHeight * scaleFactor));
        
        console.log(`📏 Durée: ${duration} (${durationInMinutes}min) -> Hauteur: ${Math.round(calculatedHeight)}px`);
        return Math.round(calculatedHeight);
    }
    
    // Mesurer dynamiquement la hauteur réelle des lignes de la grille
    function getCellHeight() {
        // Chercher une ligne de la grille (grid-row) existante pour mesurer sa hauteur réelle
        const gridRow = document.querySelector('.grid-row .time-cell');
        if (gridRow) {
            const computedHeight = gridRow.getBoundingClientRect().height;
            console.log(`📏 Hauteur ligne grille mesurée: ${computedHeight}px`);
            return computedHeight;
        }
        
        // Alternative: mesurer une cellule room-cell si time-cell n'est pas disponible
        const roomCell = document.querySelector('.room-cell');
        if (roomCell) {
            const computedHeight = roomCell.getBoundingClientRect().height;
            console.log(`📏 Hauteur cellule salle mesurée: ${computedHeight}px`);
            return computedHeight;
        }
        
        // Valeur de fallback si aucune cellule n'est trouvée
        console.log('📏 Hauteur cellule fallback: 27px');
        return 27; // Correspond au min-height du CSS
    }

    // Recalculer la hauteur des cours lors du redimensionnement
    function updateCourseHeights() {
        const courseCards = document.querySelectorAll('.course-card');
        const newCellHeight = getCellHeight();
        
        courseCards.forEach(card => {
            const courseId = card.dataset.courseId;
            const course = planningData?.courses?.find(c => c.id === courseId);
            if (course) {
                const durationInMinutes = typeof course.duration === 'number' ? course.duration : parseDurationToMinutes(course.duration || 85);
                const newHeight = (durationInMinutes / 15) * newCellHeight * 1.3;
                card.style.height = `${newHeight}px`;
                console.log(`🔄 Cours ${courseId}: nouvelle hauteur ${newHeight}px`);
            }
        });
    }

    // Événement de redimensionnement de la fenêtre
    let resizeTimeout;
    window.addEventListener('resize', () => {
        // Debounce pour éviter trop d'appels
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (planningData) {
                console.log('🔄 Redimensionnement détecté, recalcul des hauteurs...');
                updateCourseHeights();
            }
        }, 250);
    });

    // Lignes de la grille du planning : créneaux de début de cours + lignes intermédiaires,
    // calculés à partir des réglages de /admin/establishment (voir site_settings.get_time_layout).
    function generateAllTimeSlots() {
        const rows = window.SITE_CONFIG.editorRows;
        console.log(`📅 Lignes du planning: ${rows.length} (${rows.join(', ')})`);
        return rows;
    }

    // Durée en minutes d'une ligne de la grille (jusqu'à la ligne suivante)
    function getSlotDuration(slot) {
        return window.SITE_CONFIG.slotDurations[slot] || 30;
    }

    // Convertir un horaire "9h30" en minutes depuis minuit
    function slotToMinutes(slot) {
        const m = /^(\d+)h(\d+)$/.exec(slot || '');
        if (!m) return null;
        return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
    }

    // Nombre de cours réellement en cours (assignés à une vraie salle, hors stockage temporaire)
    // à l'instant de début du créneau donné
    function countSimultaneousCourses(slot) {
        if (!planningData || !planningData.courses) return 0;
        const slotStart = slotToMinutes(slot);
        if (slotStart === null) return 0;

        return planningData.courses.filter(course => {
            const room = currentRoomAssignments[course.id];
            if (!room || room === 'Non assigné' || room === TEMP_STORAGE_ID) return false;

            const courseStart = slotToMinutes(course.time);
            if (courseStart === null) return false;
            const duration = course.duration || 0;

            return slotStart >= courseStart && slotStart < courseStart + duration;
        }).length;
    }

    // Nom du jour de semaine en français (lundi, mardi, ...) pour une date "YYYY-MM-DD"
    function getWeekdayName(dateStr) {
        const dayNames = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
        const date = new Date(`${dateStr}T00:00:00`);
        return dayNames[date.getDay()];
    }

    // Charger l'occupation standard (colonne 2) pour le jour de semaine correspondant à la date affichée
    async function loadStandardOccupationForDate(dateStr) {
        standardOccupationData = {};
        const day = getWeekdayName(dateStr);
        if (!['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi'].includes(day)) return;
        try {
            const response = await fetch(`/api/standard-occupation?day=${day}`);
            if (response.ok) {
                standardOccupationData = await response.json();
            }
        } catch (e) {
            console.warn('loadStandardOccupationForDate a échoué:', e);
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : String(str);
        return div.innerHTML;
    }

    // Charger et afficher les demandes "Test au labo" pour cette date : elles n'ont
    // pas de salle attribuée (donc absentes de la grille OR-Tools) mais doivent
    // rester visibles pour le labo.
    async function loadLabTestRequests(dateStr) {
        const box = document.getElementById('lab-test-box');
        if (!box) return;
        try {
            const response = await fetch(`/api/requests?start_date=${dateStr}&end_date=${dateStr}`);
            if (!response.ok) return;
            const requests = await response.json();
            const labTests = (requests || []).filter(r => r.is_lab_test);
            if (labTests.length === 0) {
                box.style.display = 'none';
                box.innerHTML = '';
                return;
            }
            const items = labTests.map(r => {
                const time = escapeHtml(r.horaire || '');
                const teacher = escapeHtml(r.teacher_name || '');
                const level = escapeHtml(r.class_name || '');
                const name = r.request_name ? ` — ${escapeHtml(r.request_name)}` : '';
                const desc = r.material_description ? `<div class="small text-muted">${escapeHtml(r.material_description)}</div>` : '';
                return `<li>${time ? `<strong>${time}</strong> — ` : ''}${teacher}${level ? ` (${level})` : ''}${name}${desc}</li>`;
            }).join('');
            box.innerHTML = `<strong>🧪 Tests au labo :</strong><ul class="mb-0">${items}</ul>`;
            box.style.display = '';
        } catch (e) {
            console.warn('loadLabTestRequests a échoué:', e);
        }
    }

    // Enregistrer une valeur de la colonne "Occupation standard"
    async function saveStandardOccupation(dateStr, slot, value) {
        const day = getWeekdayName(dateStr);
        try {
            await fetch('/api/standard-occupation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ day, slot, value })
            });
        } catch (e) {
            console.warn('saveStandardOccupation a échoué:', e);
        }
    }

    // Calculer la position de fin exacte d'un cours selon sa durée
    function calculateEndSlotPosition(startSlotIndex, durationInMinutes) {
        // Chaque créneau = 15 minutes
        // Position de fin = position de début + (durée / 15)
        // Utilisation de nombres décimaux pour CSS Grid (ex: 5.5 pour s'arrêter au milieu du 6ème créneau)
        const exactEndPosition = startSlotIndex + (durationInMinutes / 15);
        
        console.log(`📐 Position: début=${startSlotIndex}, durée=${durationInMinutes}min, fin=${exactEndPosition}`);
        
        return exactEndPosition;
    }

    // Calculer combien de créneaux de 15min un cours doit occuper (fonction de compatibilité)
    function calculateSlotsNeeded(duration) {
        const durationInMinutes = typeof duration === 'number' ? duration : parseDurationToMinutes(duration);
        const slotsNeeded = Math.ceil(durationInMinutes / 15);
        console.log(`📐 Durée ${duration} (${durationInMinutes}min) = ${slotsNeeded} créneaux de 15min`);
        return slotsNeeded;
    }

    // Parser une durée en string vers des minutes
    function parseDurationToMinutes(durationStr) {
        if (typeof durationStr === 'number') return durationStr;
        if (!durationStr) return 60; // Durée par défaut
        
        const str = durationStr.toString().toLowerCase();
        
        // Format "XhY" ou "Xh Y" (ex: "1h30", "2h 15")
        const hoursMinutesMatch = str.match(/(\d+)h\s*(\d*)/);
        if (hoursMinutesMatch) {
            const hours = parseInt(hoursMinutesMatch[1]) || 0;
            const minutes = parseInt(hoursMinutesMatch[2]) || 0;
            return hours * 60 + minutes;
        }
        
        // Format "X.Yh" (ex: "1.5h")
        const decimalHoursMatch = str.match(/(\d+\.?\d*)h/);
        if (decimalHoursMatch) {
            const hours = parseFloat(decimalHoursMatch[1]);
            return Math.round(hours * 60);
        }
        
        // Format "Xmin" (ex: "90min")
        const minutesMatch = str.match(/(\d+)min/);
        if (minutesMatch) {
            return parseInt(minutesMatch[1]);
        }
        
        // Format numérique simple (assumé en minutes)
        const numberMatch = str.match(/^(\d+)$/);
        if (numberMatch) {
            return parseInt(numberMatch[1]);
        }
        
        // Par défaut, retourner 60 minutes
        console.warn(`⚠️ Impossible de parser la durée "${durationStr}", utilisation de 60min par défaut`);
        return 60;
    }

    // Formater une durée en minutes vers une chaîne lisible
    function formatDuration(duration) {
        const minutes = typeof duration === 'number' ? duration : parseDurationToMinutes(duration);
        
        if (minutes < 60) {
            return `${minutes}min`;
        } else {
            const hours = Math.floor(minutes / 60);
            const remainingMinutes = minutes % 60;
            if (remainingMinutes === 0) {
                return `${hours}h`;
            } else {
                return `${hours}h${remainingMinutes.toString().padStart(2, '0')}`;
            }
        }
    }

    // Obtenir le type de cours pour le style
    function getCourseType(subject) {
        const subjectLower = subject.toLowerCase();
        if (subjectLower.includes('physique') || subjectLower.includes('physics')) {
            return 'physics';
        } else if (subjectLower.includes('chimie') || subjectLower.includes('chemistry')) {
            return 'chemistry';
        } else {
            return 'other';
        }
    }
    
    // Formater l'en-tête des jours
    function formatDayHeader(day) {
        const date = new Date(day);
        const dayNames = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
        const dayName = dayNames[date.getDay()];
        const dayNum = date.getDate();
        const month = date.getMonth() + 1;
        return `${dayName} ${dayNum}/${month}`;
    }
    
    // Configurer les événements de drag pour les cours
    function setupDragEvents(card) {
        card.addEventListener('dragstart', function(e) {
            draggedElement = this;
            originalPosition = this.parentElement;
            this.classList.add('dragging');
            
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', this.outerHTML);
        });
        
        card.addEventListener('dragend', function(e) {
            this.classList.remove('dragging');
            clearDragHighlights();
            draggedElement = null;
            originalPosition = null;
        });
    }
    
    // Effacer toutes les mises en relief de drag (case, ligne d'horaire, colonne de salle)
    function clearDragHighlights() {
        document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
        document.querySelectorAll('.drag-target').forEach(el => el.classList.remove('drag-target'));
    }

    // Configurer les zones de drop
    function setupDropZone(cell) {
        cell.addEventListener('dragover', function(e) {
            e.preventDefault();
            if (!this.classList.contains('drag-over')) {
                clearDragHighlights();
                this.classList.add('drag-over');

                // Mettre en relief l'horaire et la salle de destination
                const targetRoom = this.dataset.room;
                const targetSlot = this.dataset.slot;
                const headerCell = document.querySelector(`.room-header-cell[data-room="${targetRoom}"]`);
                if (headerCell) headerCell.classList.add('drag-target');
                const timeCell = document.querySelector(`.time-cell[data-slot="${targetSlot}"]`);
                if (timeCell) timeCell.classList.add('drag-target');
            }
        });

        cell.addEventListener('dragleave', function(e) {
            this.classList.remove('drag-over');
        });

        cell.addEventListener('drop', function(e) {
            e.preventDefault();
            clearDragHighlights();
            
            if (draggedElement) {
                const courseId = draggedElement.dataset.courseId; // Ne pas convertir en int !
                const newRoom = this.dataset.room;
                const newSlot = this.dataset.slot;
                
                console.log(`🔄 Déplacement: ${courseId} vers ${newRoom} à ${newSlot}`);
                
                // Mettre à jour l'assignation de salle
                if (newRoom && courseId) {
                    currentRoomAssignments[courseId] = newRoom;
                    
                    // IMPORTANT: Mettre à jour aussi planningData.room_assignments pour la sauvegarde
                    if (planningData && planningData.room_assignments) {
                        planningData.room_assignments[courseId] = newRoom;
                    }
                    
                    // Mettre à jour le cours dans planningData
                    const course = planningData.courses.find(c => c.id === courseId); // Comparaison stricte
                    if (course) {
                        course.room = newRoom;
                        course.time = newSlot;
                        console.log(`✅ Cours mis à jour:`, course);
                    } else {
                        console.log(`❌ Cours non trouvé: ${courseId}`);
                    }
                    
                    console.log(`💾 Assignations mises à jour pour sauvegarde:`, planningData.room_assignments[courseId]);
                }
                
                // Re-rendre la grille
                renderPlanningGrid();
                updateStats();
                savePlanningData();

                showAlert(`Cours déplacé vers ${newRoom} à ${newSlot}`, 'success');
            }
        });
    }
    
    // Obtenir l'info de position à partir de la cellule
    function getPositionFromCell(cell) {
        if (!cell || !cell.dataset) return null;
        return {
            room: cell.dataset.room,
            slot: cell.dataset.slot
        };
    }
    
    // Mettre à jour les statistiques
    function updateStats() {
        if (!planningData) return;
        
        const statsContent = document.getElementById('stats-content');
        const totalCourses = planningData.courses.length;
        
        // Compter les cours assignés à des salles (le stockage temporaire ne compte pas comme une vraie salle)
        const assignedCourses = planningData.courses.filter(c =>
            currentRoomAssignments[c.id] && currentRoomAssignments[c.id] !== 'Non assigné' && currentRoomAssignments[c.id] !== TEMP_STORAGE_ID
        ).length;
        const unassignedCourses = totalCourses - assignedCourses;

        // Détecter les conflits (plusieurs cours même salle même heure)
        const conflicts = new Map();
        planningData.courses.forEach(course => {
            const room = currentRoomAssignments[course.id];
            if (!room || room === 'Non assigné' || room === TEMP_STORAGE_ID) return;
            const key = `${room}_${course.time}`;
            if (!conflicts.has(key)) {
                conflicts.set(key, []);
            }
            conflicts.get(key).push(course.id);
        });

        const conflictCount = Array.from(conflicts.values()).filter(courses => courses.length > 1).length;

        // Compter les salles utilisées
        const usedRooms = new Set(Object.values(currentRoomAssignments).filter(room => room !== 'Non assigné' && room !== TEMP_STORAGE_ID)).size;
        
        statsContent.innerHTML = `
            <div class="stat-item">
                <strong>Cours total:</strong> ${totalCourses}
            </div>
            <div class="stat-item">
                <strong>Cours assignés:</strong> ${assignedCourses}
            </div>
            <div class="stat-item ${unassignedCourses > 0 ? 'warning' : ''}">
                <strong>Non assignés:</strong> ${unassignedCourses}
            </div>
            <div class="stat-item ${conflictCount > 0 ? 'error' : ''}">
                <strong>Conflits salle/heure:</strong> ${conflictCount}
            </div>
            <div class="stat-item">
                <strong>Salles utilisées:</strong> ${usedRooms}/${planningData.rooms.length}
            </div>
        `;
    }
    
    // Réinitialiser le planning
    function resetPlanning() {
        if (planningData && confirm('Êtes-vous sûr de vouloir réinitialiser le planning aux assignations automatiques ?')) {
            currentAssignments = { ...planningData.assignments };
            renderPlanningGrid();
            updateStats();
            showAlert('Planning réinitialisé!', 'info');
        }
    }
    
    // Générer le planning Excel final
    async function generateFinalPlanning() {
        if (!planningData) {
            showAlert('Aucun planning chargé.', 'warning');
            return;
        }

        const coursesInTempStorage = planningData.courses.filter(c => currentRoomAssignments[c.id] === TEMP_STORAGE_ID).length;
        if (coursesInTempStorage > 0) {
            showAlert(`Impossible de générer: ${coursesInTempStorage} cours reste(nt) dans la colonne de stockage temporaire. Placez-les dans une salle d'abord.`, 'danger');
            return;
        }

        const targetDate = document.getElementById('target-date').value;

        showLoading('loading-container');
        
        try {
            // Créer les assignments basés sur les positions actuelles des cours
            const finalAssignments = {};
            planningData.courses.forEach(course => {
                const slotKey = `${planningData.days[0]}_${course.time}`;
                if (!finalAssignments[slotKey]) {
                    finalAssignments[slotKey] = [];
                }
                finalAssignments[slotKey].push(course.id);
            });
            
            const response = await fetch('/api/planning-editor/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    assignments: finalAssignments,
                    room_assignments: currentRoomAssignments,
                    date: targetDate
                })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `planning_personnalise_${targetDate}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showAlert('Planning Excel généré avec succès!', 'success');
            } else {
                const data = await response.json();
                throw new Error(data.error || 'Erreur lors de la génération');
            }
        } catch (error) {
            console.error('Erreur:', error);
            showAlert(`Erreur lors de la génération: ${error.message}`, 'danger');
        } finally {
            hideLoading('loading-container');
        }
    }
    
    // Enregistrer le planning dans la base de données
    async function savePlanningData() {
        if (!planningData) {
            console.log('❌ Aucun planning à enregistrer.');
            showAlert('Aucun planning à enregistrer.', 'warning');
            return;
        }

        const coursesInTempStorage = planningData.courses.filter(c => currentRoomAssignments[c.id] === TEMP_STORAGE_ID).length;
        if (coursesInTempStorage > 0) {
            showAlert(`Attention: ${coursesInTempStorage} cours reste(nt) dans la colonne de stockage temporaire.`, 'warning');
        }

        const targetDate = document.getElementById('target-date').value;
        const payload = {
            date: targetDate,
            data: planningData
        };

        try {
            console.log('🔄 Envoi des données à /api/save-planning:', payload);
            const response = await fetch('/api/save-planning', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            console.log('📡 Réponse API status:', response.status);
            if (response.ok) {
                showAlert('Planning enregistré avec succès!', 'success');
            } else {
                const errorData = await response.json();
                showAlert(`Erreur: ${errorData.error}`, 'danger');
            }
        } catch (error) {
            console.error('Erreur lors de l\'enregistrement du planning:', error);
            showAlert('Erreur lors de l\'enregistrement du planning.', 'danger');
        }
    }

    // Note : savePlanningData() est appelé automatiquement dans loadPlanningData() et après chaque drag.
    
    document.getElementById('target-date').addEventListener('change', function() {
        updatePlanningDateHeading();
        if (this.value) {
            reloadPlanningIfExists(this.value);
        }
    });

// Fonctions supprimées car on utilise maintenant reloadPlanning() automatiquement

// Move the reloadPlanning function definition to global scope
async function reloadPlanning() {
    const targetDate = document.getElementById('target-date').value;

    if (!targetDate) {
        showAlert('Veuillez sélectionner une date.', 'warning');
        return;
    }

    showLoading('loading-container');

    try {
        // Lancée en parallèle de la requête principale (pas après)
        const standardOccupationPromise = loadStandardOccupationForDate(targetDate);
        const labTestPromise = loadLabTestRequests(targetDate);
        loadAllRequestsForRelatedDetection();
        const response = await fetch(`/api/get-planning?date=${targetDate}`);
        if (response.ok) {
            const data = await response.json();
            console.log('🔍 Raw API response:', data);

            // Parse the JSON string if needed
            if (typeof data.planning === 'string') {
                planningData = JSON.parse(data.planning);
            } else {
                planningData = data.planning || data;
            }

            // Update currentRoomAssignments with loaded data
            currentRoomAssignments = { ...planningData.room_assignments || {} };

            console.log('🔍 Assigned planningData:', planningData);
            console.log('🔍 planningData.rooms:', planningData.rooms);
            console.log('🔍 Updated currentRoomAssignments:', currentRoomAssignments);
            await Promise.all([syncPreparedStates(), standardOccupationPromise, labTestPromise]);
            renderPlanningGrid(); // Fonction existante pour afficher le planning
            showAlert('Planning chargé avec succès!', 'success');
        } else {
            const errorData = await response.json();
            showAlert(`Erreur: ${errorData.error}`, 'danger');
        }
    } catch (error) {
        console.error('Erreur lors du chargement du planning:', error);
        showAlert('Erreur lors du chargement du planning.', 'danger');
    } finally {
        hideLoading('loading-container');
    }
}

// Impression : ouvre la page imprimable (A4 paysage, mise en page dédiée) construite côté serveur à
// partir du planning enregistré en base. L'état affiché dans l'éditeur est enregistré d'abord, pour que
// l'impression corresponde exactement à ce qu'on voit.
async function printPlanning() {
    if (!planningData) {
        showAlert('Aucun planning chargé à imprimer.', 'warning');
        return;
    }
    const date = document.getElementById('target-date').value;
    if (!date) {
        showAlert('Veuillez sélectionner une date.', 'warning');
        return;
    }
    // L'onglet est ouvert tout de suite (dans le geste de l'utilisateur) pour ne pas être bloqué par le
    // navigateur, puis dirigé vers la page imprimable une fois le planning enregistré.
    const onglet = window.open('', '_blank');
    await savePlanningData();
    const url = `/admin/planning-print?date=${encodeURIComponent(date)}&print=1`;
    if (onglet) {
        onglet.location.href = url;
    } else {
        window.location.href = url;
    }
}

async function reloadPlanningIfExists(targetDate) {
    try {
        // Lancée en parallèle de la requête principale (pas après)
        const standardOccupationPromise = loadStandardOccupationForDate(targetDate);
        const labTestPromise = loadLabTestRequests(targetDate);
        loadAllRequestsForRelatedDetection();
        const response = await fetch(`/api/get-planning?date=${targetDate}`);
        if (response.status === 404) {
            // Aucun planning sauvegardé pour cette date : état vide sans erreur
            planningData = null;
            currentAssignments = {};
            currentRoomAssignments = {};
            document.getElementById('rooms-container').innerHTML = '';
            document.getElementById('rooms-container').className = 'row';
            document.getElementById('no-planning-message').style.display = '';
            document.getElementById('stats-panel').style.display = 'none';
            document.getElementById('generate-btn').disabled = true;
            document.getElementById('observations-section').style.display = 'none';
            document.getElementById('planningObservations').value = '';
            await labTestPromise;
            return;
        }
        if (!response.ok) {
            return; // Autre erreur serveur : on n'affiche rien
        }
        const data = await response.json();
        if (typeof data.planning === 'string') {
            planningData = JSON.parse(data.planning);
        } else {
            planningData = data.planning || data;
        }
        currentRoomAssignments = { ...planningData.room_assignments || {} };
        document.getElementById('planningObservations').value = data.observations || '';
        document.getElementById('observations-section').style.display = '';
        await Promise.all([syncPreparedStates(), standardOccupationPromise, labTestPromise]);
        renderPlanningGrid();
        updateStats();
        document.getElementById('generate-btn').disabled = false;
        showAlert('Planning existant chargé.', 'info');
    } catch (error) {
        // Erreur réseau ou parse : on ignore silencieusement
        console.warn('reloadPlanningIfExists:', error);
    }
}


let _obsDebounce = null;
async function saveObservations() {
    const date = document.getElementById('target-date').value;
    const statusEl = document.getElementById('obs-save-status');
    if (!date) return;
    statusEl.textContent = 'Sauvegarde…';
    statusEl.className = 'text-muted';
    try {
        const resp = await fetch('/api/planning-observations', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, observations: document.getElementById('planningObservations').value })
        });
        if (resp.ok) {
            statusEl.textContent = '✓ Sauvegardé';
            statusEl.className = 'text-success';
            setTimeout(() => { statusEl.textContent = ''; }, 3000);
        } else {
            const err = await resp.json().catch(() => ({}));
            statusEl.textContent = '✗ Erreur: ' + (err.error || resp.status);
            statusEl.className = 'text-danger';
        }
    } catch (e) {
        statusEl.textContent = '✗ Erreur réseau';
        statusEl.className = 'text-danger';
        console.error('saveObservations:', e);
    }
}
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('planningObservations').addEventListener('input', () => {
        const statusEl = document.getElementById('obs-save-status');
        statusEl.textContent = '…';
        statusEl.className = 'text-muted';
        clearTimeout(_obsDebounce);
        _obsDebounce = setTimeout(saveObservations, 1500);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    // Attach reloadPlanning to the window object to make it globally accessible
    window.reloadPlanning = reloadPlanning;
    console.log('reloadPlanning function attached to window:', window.reloadPlanning);
    
    window.savePlanningData = savePlanningData;
    window.reloadPlanningIfExists = reloadPlanningIfExists;
});
