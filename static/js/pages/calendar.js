// Script de la page calendar (extrait de templates/calendar.html).
let currentWeekStart = getStartOfWeek(new Date());
// Passage, samedi ou dimanche directement au lundi suivant
const todayDayOfWeek = new Date().getDay(); // Cela donne 0 pour dimanche et 6 pour samedi
if (todayDayOfWeek === 0 || todayDayOfWeek === 6) {
    currentWeekStart.setDate(currentWeekStart.getDate() + 7);
}
let events = [];
// Jours non ouvrés configurés dans /admin/working-days (ensemble de dates 'YYYY-MM-DD')
let nonWorkingDays = new Set();

// myTeacherId, escapeHtml et dureeParNiveau sont déjà fournis par _request_modal_js.html (inclus plus haut)

// Plage horaire affichée dans la grille (correspond aux horaires proposés dans le formulaire de demande)
const PT_DAY_START_MIN = 9 * 60;   // 9h00
const PT_DAY_END_MIN = 20 * 60 + 15; // 20h15 (marge après le dernier créneau possible : 18h15 + 110 min)
const PT_PX_PER_MIN = 1;           // 1 minute = 1px de hauteur (soit 60px/heure, cf. --pt-hour-px)
const PT_GAP_PX = 2;

function parseHoraireToMinutes(horaire) {
    if (!horaire) return null;
    const match = String(horaire).match(/(\d{1,2})h(\d{0,2})/);
    if (!match) return null;
    const hours = parseInt(match[1], 10);
    const minutes = match[2] ? parseInt(match[2], 10) : 0;
    return hours * 60 + minutes;
}

function getEventDurationMinutes(event) {
    const custom = Number(event.custom_duration);
    if (Number.isFinite(custom) && custom > 0) return custom;
    return dureeParNiveau(event.class_name || '');
}

function getStartOfWeek(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    return new Date(d.setDate(diff));
}

function getWeekDays(startDate) {
    const days = [];
    for (let i = 0; i < 5; i++) { // Only Monday to Friday
        const day = new Date(startDate);
        day.setDate(startDate.getDate() + i);
        days.push(day);
    }
    return days;
}

function ymd(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

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

const DAY_NAMES_FULL = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];

function parseYMD(str) {
    const [y, m, d] = str.split('-').map(Number);
    return new Date(y, m - 1, d);
}

function formatDayDate(date) {
    return `${DAY_NAMES_FULL[date.getDay()]} ${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}`;
}

// Bandeau "date limite" : la prochaine date de cours encore demandable et l'heure du couperet
function renderDeadlineBanner(info) {
    const banner = document.getElementById('deadlineBanner');
    if (!info || !info.request_date || !info.deadline_date) {
        banner.classList.add('d-none');
        return;
    }
    const requestDate = parseYMD(info.request_date);
    const deadlineDate = parseYMD(info.deadline_date);
    const today = parseYMD(ymd(new Date()));
    const dayDiff = Math.round((deadlineDate - today) / 86400000);
    const time = (info.deadline_time || '08h00').replace(/^0/, '').replace(/h00$/, 'h');

    let when;
    if (dayDiff === 0) when = `aujourd'hui avant ${time}`;
    else if (dayDiff === 1) when = `demain ${formatDayDate(deadlineDate)} à ${time}`;
    else when = `${formatDayDate(deadlineDate)} à ${time}`;

    document.getElementById('deadlineBannerText').innerHTML =
        `Vous avez jusqu'à <strong>${when}</strong> pour poster vos demandes pour le <strong>${formatDayDate(requestDate)}</strong>.`;
    banner.classList.remove('d-none');
}

function loadCalendarInfo() {
    fetch('/api/calendar-info', { cache: 'no-store' })
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(data => {
            nonWorkingDays = new Set(data.non_working_days || []);
            renderDeadlineBanner(data.next_deadline);
            renderWeekView();
        })
        .catch(err => console.error('Erreur chargement infos calendrier:', err));
}

document.addEventListener('DOMContentLoaded', function() {
    loadCalendarInfo();

    // Load teachers for filter (un seul enseignant affiché à la fois)
    fetch('/api/teachers')
        .then(response => response.json())
        .then(teachers => {
            const teacherFilter = document.getElementById('calendarFilterTeacher');
            teacherFilter.innerHTML = '';
            const sortedTeachers = [...teachers].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'fr'));
            sortedTeachers.forEach(teacher => {
                const option = document.createElement('option');
                option.value = teacher.id;
                option.textContent = teacher.name;
                teacherFilter.appendChild(option);
            });

            // Par défaut : l'enseignant du compte connecté. Sinon, le dernier consulté, sinon le premier de la liste.
            const savedTeacher = getCookie('selectedTeacher');
            let defaultTeacherId = null;
            if (myTeacherId && sortedTeachers.some(t => String(t.id) === String(myTeacherId))) {
                defaultTeacherId = String(myTeacherId);
            } else if (savedTeacher && sortedTeachers.some(t => String(t.id) === savedTeacher)) {
                defaultTeacherId = savedTeacher;
            } else if (sortedTeachers.length > 0) {
                defaultTeacherId = String(sortedTeachers[0].id);
            }
            if (defaultTeacherId) {
                teacherFilter.value = defaultTeacherId;
                setCookie('selectedTeacher', defaultTeacherId);
            }

            // Load calendar after teacher filter is restored
            loadCalendar();
        });

    // Set up filter change handlers
    document.getElementById('calendarFilterTeacher').addEventListener('change', loadCalendar);
    document.getElementById('calendarFilterStatus').addEventListener('change', loadCalendar);
    document.getElementById('calendarFilterType').addEventListener('change', loadCalendar);

    // Save teacher selection to cookie
    document.getElementById('calendarFilterTeacher').addEventListener('change', function() {
        if (this.value) {
            setCookie('selectedTeacher', this.value);
        }
    });
});

function loadRequests() { loadCalendar(); }

function openNewRequestFromCalendar() {
    // Déterminer la date courante de la vue calendrier (lundi de la semaine affichée)
    const dateStr = currentWeekStart ? currentWeekStart.toISOString().split('T')[0] : new Date().toISOString().split('T')[0];
    const teacherId = document.getElementById('calendarFilterTeacher').value || '';

    // Réinitialiser la modale pour une création
    document.getElementById('editRequestId').value = '';
    document.getElementById('editRequestId').removeAttribute('data-teacher-id');
    document.getElementById('editRequestId').removeAttribute('data-request-name');
    currentRelatedList = [];
    document.getElementById('relatedRequestsList').innerHTML = '';
    updateBulkEditAvailability();
    document.getElementById('editDate').value = dateStr;
    document.getElementById('editRequestName').value = '';
    document.getElementById('editClassName').value = '';
    document.getElementById('editHoraire').value = '';
    document.getElementById('editMaterialDescription').value = '';
    document.getElementById('editMaterialProf').value = '';
    document.getElementById('editNotes').value = '';
    document.getElementById('editQuantity').value = '1';
    document.getElementById('editComputersNeeded').value = '0';
    document.getElementById('editAbsent').checked = false;
    document.getElementById('editNoMaterial').checked = false;
    document.getElementById('editExamMode').checked = false;
    document.getElementById('editLabTest').checked = false;
    document.querySelectorAll('input[name="editMaterials"]').forEach(cb => cb.checked = false);
    // Sélectionner "Pas de matériel spécifique" par défaut
    const noSpecific = document.querySelector('input[name="editMaterials"][value="Pas de matériel spécifique à la salle"]');
    if (noSpecific) noSpecific.checked = true;

    if (teacherId) document.getElementById('editTeacher').value = teacherId;

    // Titre de la modale
    const titleEl = document.getElementById('editRequestModalLabel');
    if (titleEl) titleEl.textContent = 'Nouvelle demande';

    // Cacher le bouton Supprimer, afficher Enregistrer
    const deleteBtn = document.getElementById('deleteRequestBtn');
    if (deleteBtn) deleteBtn.style.display = 'none';

    window.originalRequestData = {};

    const modalEl = document.getElementById('editRequestModal');
    (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).show();
}

function loadCalendar() {
    // Get filter values
    const teacherId = document.getElementById('calendarFilterTeacher').value;
    const statusFilter = document.getElementById('calendarFilterStatus').value;
    const typeFilter = document.getElementById('calendarFilterType').value;

    // Un enseignant doit toujours être sélectionné (plus de vue "tous les enseignants")
    if (!teacherId) {
        events = [];
        renderWeekView();
        return;
    }

    // Build query string
    const params = new URLSearchParams();
    params.append('teacher_id', teacherId);
    if (statusFilter) params.append('status', statusFilter);
    if (typeFilter) params.append('type', typeFilter);

    // Charge les événements affichés dans la grille, ainsi que les demandes complètes de cet
    // enseignant (utilisées par la modale d'édition : pré-remplissage instantané + détection
    // des demandes liées, comme sur la page "Voir les demandes").
    Promise.all([
        fetch(`/api/calendar-events?${params.toString()}`, { cache: 'no-store' }).then(r => r.json()),
        fetch(`/api/requests?teacher_id=${encodeURIComponent(teacherId)}`, { cache: 'no-store' }).then(r => r.json())
    ])
        .then(([calendarEvents, fullRequests]) => {
            events = calendarEvents;
            window.allRequests = Array.isArray(fullRequests) ? fullRequests : [];
            renderWeekView();
        })
        .catch(error => {
            console.error('Error loading events:', error);
        });
}

// Fonction pour normaliser les dates en format YYYY-MM-DD
function normalizeDateToYMD(dateValue) {
    if (!dateValue) return null;

    let date;

    // Si c'est déjà une chaîne au format YYYY-MM-DD
    if (typeof dateValue === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateValue)) {
        return dateValue;
    }

    // Si c'est une chaîne de date GMT ou autre format
    if (typeof dateValue === 'string') {
        date = new Date(dateValue);
    }
    // Si c'est déjà un objet Date
    else if (dateValue instanceof Date) {
        date = dateValue;
    }
    // Sinon, essayer de le convertir
    else {
        date = new Date(dateValue);
    }

    // Vérifier si la date est valide
    if (isNaN(date.getTime())) {
        console.error('Date invalide:', dateValue);
        return null;
    }

    // Retourner au format YYYY-MM-DD
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Répartit les événements qui se chevauchent en colonnes (comme un vrai emploi du temps)
function layoutDayEvents(dayEvents) {
    const sorted = [...dayEvents].sort((a, b) => a.startMin - b.startMin || a.endMin - b.endMin);
    const clusters = [];
    let current = [];
    let currentEnd = -Infinity;

    sorted.forEach(ev => {
        if (current.length === 0 || ev.startMin < currentEnd) {
            current.push(ev);
            currentEnd = Math.max(currentEnd, ev.endMin);
        } else {
            clusters.push(current);
            current = [ev];
            currentEnd = ev.endMin;
        }
    });
    if (current.length) clusters.push(current);

    clusters.forEach(cluster => {
        const columnEnds = [];
        cluster.forEach(ev => {
            let placed = false;
            for (let c = 0; c < columnEnds.length; c++) {
                if (columnEnds[c] <= ev.startMin) {
                    columnEnds[c] = ev.endMin;
                    ev.col = c;
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                columnEnds.push(ev.endMin);
                ev.col = columnEnds.length - 1;
            }
        });
        cluster.forEach(ev => { ev.totalCols = columnEnds.length; });
    });

    return sorted;
}

function renderWeekView() {
    const weekDays = getWeekDays(currentWeekStart);
    const weekEnd = new Date(currentWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 4); // Friday

    // Update week header
    const monthNames = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ];

    const startStr = `${currentWeekStart.getDate()} ${monthNames[currentWeekStart.getMonth()]}`;
    const endStr = `${weekEnd.getDate()} ${monthNames[weekEnd.getMonth()]} ${weekEnd.getFullYear()}`;
    document.getElementById('currentWeek').textContent = `Semaine du ${startStr} au ${endStr}`;

    const dayNames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi'];
    const showTeacherName = !document.getElementById('calendarFilterTeacher').value;
    const todayStr = ymd(new Date());
    const gridHeight = (PT_DAY_END_MIN - PT_DAY_START_MIN) * PT_PX_PER_MIN;

    // Répartir les événements par jour, avec calcul de leur position temporelle
    const eventsByDay = weekDays.map(day => {
        const dayDate = ymd(day);
        const dayEvents = events
            .filter(event => normalizeDateToYMD(event.start) === dayDate)
            .map(event => {
                const startMin = parseHoraireToMinutes(event.horaire);
                if (startMin === null) return { ...event, hasTime: false };
                const durationMin = getEventDurationMinutes(event);
                return { ...event, hasTime: true, startMin, endMin: startMin + durationMin };
            });
        return { day, dayDate, timed: layoutDayEvents(dayEvents.filter(e => e.hasTime)), untimed: dayEvents.filter(e => !e.hasTime) };
    });

    // Seulement les demandes de la semaine affichée (`events` contient toutes les semaines)
    const totalEvents = eventsByDay.reduce((n, d) => n + d.timed.length + d.untimed.length, 0);
    // La grille reste toujours visible (pour voir les jours fériés hachurés même sans demande)
    // Semaine entièrement non ouvrée (vacances) : message dédié à la place de "Aucune demande"
    const isHolidayWeek = eventsByDay.every(d => nonWorkingDays.has(d.dayDate));
    document.getElementById('holidayWeekMessage').classList.toggle('d-none', !isHolidayWeek);
    document.getElementById('noPlanningResults').classList.toggle('d-none', isHolidayWeek || totalEvents !== 0);

    const hasUntimed = eventsByDay.some(d => d.untimed.length > 0);

    // ---- En-tête (jours) ----
    let headHtml = `<div class="pronote-head-cell"></div>`;
    eventsByDay.forEach(({ day, dayDate }, index) => {
        const isToday = dayDate === todayStr;
        const isHoliday = nonWorkingDays.has(dayDate);
        headHtml += `
            <div class="pronote-head-cell${isToday ? ' today' : ''}${isHoliday ? ' holiday' : ''}">
                ${dayNames[index]}
                <span class="pronote-head-daynum">${day.getDate()}/${day.getMonth() + 1}</span>
            </div>`;
    });

    // ---- Colonne des heures ----
    let timeColHtml = '';
    for (let m = PT_DAY_START_MIN; m <= PT_DAY_END_MIN; m += 60) {
        const top = (m - PT_DAY_START_MIN) * PT_PX_PER_MIN;
        timeColHtml += `<div class="pronote-time-label" style="top:${top}px;">${Math.floor(m / 60)}h</div>`;
    }

    // ---- Colonnes des jours (créneaux positionnés) ----
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    let dayColsHtml = '';
    eventsByDay.forEach(({ dayDate, timed }) => {
        const isToday = dayDate === todayStr;
        let colHtml = '';
        timed.forEach(ev => {
            const clampedStart = Math.max(ev.startMin, PT_DAY_START_MIN);
            const clampedEnd = Math.min(ev.endMin, PT_DAY_END_MIN);
            const top = (clampedStart - PT_DAY_START_MIN) * PT_PX_PER_MIN;
            const height = Math.max(18, (clampedEnd - clampedStart) * PT_PX_PER_MIN - PT_GAP_PX);
            const widthPct = 100 / ev.totalCols;
            const leftPct = ev.col * widthPct;
            colHtml += buildEventHtml(ev, showTeacherName, {
                position: 'absolute',
                top: `${top}px`,
                height: `${height}px`,
                left: `calc(${leftPct}% + 2px)`,
                width: `calc(${widthPct}% - 4px)`
            });
        });
        if (isToday && nowMin >= PT_DAY_START_MIN && nowMin <= PT_DAY_END_MIN) {
            const top = (nowMin - PT_DAY_START_MIN) * PT_PX_PER_MIN;
            colHtml += `<div class="pronote-now-line" style="top:${top}px;"></div>`;
        }
        const isHoliday = nonWorkingDays.has(dayDate);
        dayColsHtml += `<div class="pronote-day-col${isToday ? ' today' : ''}${isHoliday ? ' holiday' : ''}" style="height:${gridHeight}px;">${colHtml}</div>`;
    });

    // ---- Ligne "sans horaire" (absences, pas besoin de matériel non planifiés, etc.) ----
    let noHorRowHtml = '';
    if (hasUntimed) {
        noHorRowHtml = `<div class="pronote-noh-label">sans<br>horaire</div>`;
        eventsByDay.forEach(({ dayDate, untimed }) => {
            let chips = '';
            untimed.forEach(ev => {
                chips += buildChipHtml(ev, showTeacherName);
            });
            const isHoliday = nonWorkingDays.has(dayDate);
            noHorRowHtml += `<div class="pronote-noh-cell${isHoliday ? ' holiday' : ''}">${chips}</div>`;
        });
    }

    document.getElementById('pronoteTimetable').innerHTML = `
        <div class="pronote-head">${headHtml}</div>
        <div class="pronote-body" style="height:${gridHeight}px;">
            <div class="pronote-time-col">${timeColHtml}</div>
            ${dayColsHtml}
        </div>
        ${hasUntimed ? `<div class="pronote-noh-row">${noHorRowHtml}</div>` : ''}
    `;

    // Rattacher les gestionnaires de double-clic/clavier (CSP-friendly, pas d'attributs inline)
    // Un double-clic sur un créneau ouvre la modale de modification (cohérent avec le reste du site).
    document.querySelectorAll('#pronoteTimetable [data-event-id]').forEach(el => {
        const eventId = el.getAttribute('data-event-id');
        el.addEventListener('dblclick', () => editRequest(eventId));
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                editRequest(eventId);
            }
        });
    });
}

function eventLabel(ev) {
    const tpName = ev.request_name ? ` "${ev.request_name}"` : '';
    const labTest = ev.is_lab_test ? ' (Test au labo, pas de salle)' : '';
    const draft = ev.is_draft ? ' (Cours régulier, à vérifier)' : '';
    const room = ev.room ? ` - salle ${ev.room}` : '';
    return `${ev.horaire ? ev.horaire + ' - ' : ''}${ev.teacher_name || ev.title.split(' - ')[0]} - ${ev.class_name || ev.title.split(' - ')[1] || ''}${tpName}${room}${labTest}${draft}. ${ev.description}`;
}

function buildEventHtml(ev, showTeacherName, styleObj) {
    const bgColor = ev.backgroundColor || '#007bff';
    const styleStr = Object.entries(styleObj).map(([k, v]) => `${k.replace(/[A-Z]/g, c => '-' + c.toLowerCase())}:${v}`).join(';');
    const className = ev.class_name || (ev.title || '').split(' - ')[1] || '';
    const teacherName = ev.teacher_name || (ev.title || '').split(' - ')[0] || '';
    return `
        <div class="pronote-event" data-event-id="${ev.id}"
             style="${styleStr};background-color:${bgColor};"
             role="button" tabindex="0" title="Double-cliquez pour modifier"
             aria-label="Détails de la demande: ${eventLabel(ev).replace(/"/g, '&quot;')}">
            <span class="ev-time">${ev.horaire || ''}${ev.is_lab_test ? ' 🧪' : ''}${ev.is_draft ? ' ⏳' : ''}</span>
            ${showTeacherName ? `<span class="ev-teacher">${teacherName}</span>` : ''}
            <span class="ev-class">${className}</span>
            ${ev.room ? `<span class="ev-room">${escapeHtml(ev.room)}</span>` : ''}
            ${ev.request_name ? `<span class="ev-name">${escapeHtml(ev.request_name)}</span>` : ''}
        </div>`;
}

function buildChipHtml(ev, showTeacherName) {
    const bgColor = ev.backgroundColor || '#007bff';
    const className = ev.class_name || (ev.title || '').split(' - ')[1] || '';
    const teacherName = ev.teacher_name || (ev.title || '').split(' - ')[0] || '';
    const namePart = ev.request_name ? ` — ${escapeHtml(ev.request_name)}` : '';
    const roomPart = ev.room ? ` (${escapeHtml(ev.room)})` : '';
    const label = (showTeacherName ? `${teacherName} - ${className}` : className) + namePart + roomPart;
    return `
        <span class="pronote-noh-chip" data-event-id="${ev.id}"
              style="background-color:${bgColor};"
              role="button" tabindex="0" title="Double-cliquez pour modifier"
              aria-label="Détails de la demande: ${eventLabel(ev).replace(/"/g, '&quot;')}">
            ${label}
        </span>`;
}

function previousWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() - 7);
    renderWeekView();
}

function nextWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() + 7);
    renderWeekView();
}

// Toast functions
function showSuccessToast(message) {
    if (typeof window.showToast === 'function') {
        window.showToast('success', 'Succès', message);
    } else {
        alert(message);
    }
}

function showErrorToast(message) {
    if (typeof window.showToast === 'function') {
        window.showToast('error', 'Erreur', message);
    } else {
        alert(message);
    }
}

// Ajout du bouton "Générer la semaine" pour créer automatiquement les demandes de matériel pour la semaine affichée

document.getElementById('btnGenerateWeek').addEventListener('click', function() {
    const week_start = ymd(currentWeekStart);
    this.disabled = true;
    fetch('/api/recurring-courses/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ week_start })
    })
    .then(r => r.json().then(d => ({ ok: r.ok, data: d })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error);
        showSuccessToast(`${data.created} cours créé(s) pour la semaine du ${week_start}.`);
        loadCalendar();
    })
    .catch(err => showErrorToast('Erreur : ' + err.message))
    .finally(() => { this.disabled = false; });
});


