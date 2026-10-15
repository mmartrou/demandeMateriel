// Script de la page mon_emploi_du_temps (extrait de templates/mon_emploi_du_temps.html).
const dayNames = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi'];

// Plage horaire affichée (identique à Calendrier)
const PT_DAY_START_MIN = 9 * 60;
const PT_DAY_END_MIN = 20 * 60 + 15;
const PT_PX_PER_MIN = 1;

const DUREES_PAR_NIVEAU = window.APP_CONFIG.dureesParNiveau;
function dureeParNiveau(niveau) { return DUREES_PAR_NIVEAU[niveau] || 85; }

function parseHoraireToMinutes(horaire) {
    if (!horaire) return null;
    const match = String(horaire).match(/(\d{1,2})h(\d{0,2})/);
    if (!match) return null;
    const hours = parseInt(match[1], 10);
    const minutes = match[2] ? parseInt(match[2], 10) : 0;
    return hours * 60 + minutes;
}

function showSuccessToast(message) {
    if (typeof window.showToast === 'function') window.showToast('success', 'Succès', message);
    else alert(message);
}
function showErrorToast(message) {
    if (typeof window.showToast === 'function') window.showToast('error', 'Erreur', message);
    else alert(message);
}

function escapeHtmlLocal(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

let currentCourses = [];

function loadRecurringCourses() {
    fetch('/api/recurring-courses')
        .then(r => r.json())
        .then(courses => {
            currentCourses = Array.isArray(courses) ? courses : [];
            renderScheduleGrid();
        })
        .catch(err => {
            document.getElementById('scheduleGrid').innerHTML = `<p class="text-danger p-3">Erreur : ${err.message}</p>`;
        });
}

function renderScheduleGrid() {
    const gridEl = document.getElementById('scheduleGrid');
    const emptyEl = document.getElementById('scheduleEmpty');
    emptyEl.classList.toggle('d-none', currentCourses.length !== 0);
    gridEl.classList.toggle('d-none', currentCourses.length === 0);
    if (currentCourses.length === 0) {
        gridEl.innerHTML = '';
        return;
    }

    const gridHeight = (PT_DAY_END_MIN - PT_DAY_START_MIN) * PT_PX_PER_MIN;

    let headHtml = `<div class="pronote-head-cell"></div>`;
    dayNames.forEach(name => {
        headHtml += `<div class="pronote-head-cell">${name}</div>`;
    });

    let timeColHtml = '';
    for (let m = PT_DAY_START_MIN; m <= PT_DAY_END_MIN; m += 60) {
        const top = (m - PT_DAY_START_MIN) * PT_PX_PER_MIN;
        timeColHtml += `<div class="pronote-time-label" style="top:${top}px;">${Math.floor(m / 60)}h</div>`;
    }

    let dayColsHtml = '';
    for (let day = 0; day < 5; day++) {
        let colHtml = '';
        currentCourses.filter(c => c.day_of_week === day).forEach(c => {
            const startMin = parseHoraireToMinutes(c.horaire);
            if (startMin === null) return;
            const durationMin = dureeParNiveau(c.class_name);
            const clampedStart = Math.max(startMin, PT_DAY_START_MIN);
            const clampedEnd = Math.min(startMin + durationMin, PT_DAY_END_MIN);
            const top = (clampedStart - PT_DAY_START_MIN) * PT_PX_PER_MIN;
            const height = Math.max(18, (clampedEnd - clampedStart) * PT_PX_PER_MIN - 2);
            colHtml += `
                <div class="pronote-event" data-course-id="${c.id}"
                     style="top:${top}px;height:${height}px;left:2px;right:2px;"
                     role="button" tabindex="0" title="Cliquez pour supprimer"
                     aria-label="Supprimer ${escapeHtmlLocal(c.horaire)} ${escapeHtmlLocal(c.class_name)}">
                    <span class="ev-time">${c.horaire}</span>
                    <span class="ev-class">${escapeHtmlLocal(c.class_name)}</span>
                </div>`;
        });
        dayColsHtml += `<div class="pronote-day-col" style="height:${gridHeight}px;">${colHtml}</div>`;
    }

    gridEl.innerHTML = `
        <div class="pronote-head">${headHtml}</div>
        <div class="pronote-body" style="height:${gridHeight}px;">
            <div class="pronote-time-col">${timeColHtml}</div>
            ${dayColsHtml}
        </div>
    `;

    gridEl.querySelectorAll('[data-course-id]').forEach(el => {
        const courseId = el.getAttribute('data-course-id');
        const activate = () => deleteRecurringCourse(courseId);
        el.addEventListener('click', activate);
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
        });
    });
}

document.getElementById('btnAddCourse').addEventListener('click', function() {
    const day_of_week = document.getElementById('dayOfWeek').value;
    const horaire = document.getElementById('courseHoraire').value;
    const class_name = document.getElementById('courseClassName').value;
    if (!horaire || !class_name) {
        showErrorToast('Choisissez un horaire et un niveau.');
        return;
    }
    fetch('/api/recurring-courses', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ day_of_week: parseInt(day_of_week, 10), horaire, class_name })
    })
    .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
    .then(() => {
        showSuccessToast('Créneau ajouté');
        loadRecurringCourses();
    })
    .catch(err => showErrorToast('Erreur : ' + err.message));
});

function deleteRecurringCourse(id) {
    if (!confirm('Supprimer ce créneau de votre emploi du temps type ?')) return;
    fetch(`/api/recurring-courses/${id}`, { method: 'DELETE' })
        .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
        .then(() => {
            showSuccessToast('Créneau supprimé');
            loadRecurringCourses();
        })
        .catch(err => showErrorToast('Erreur : ' + err.message));
}

// Ramène une date quelconque au lundi de sa semaine
function mondayOf(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(d.setDate(diff));
    return `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, '0')}-${String(monday.getDate()).padStart(2, '0')}`;
}

function setDefaultWeekStart() {
    const today = new Date();
    const nextMonday = new Date(today);
    const day = today.getDay();
    const daysUntilMonday = day === 0 ? 1 : day === 1 ? 7 : 8 - day;
    nextMonday.setDate(today.getDate() + daysUntilMonday);
    const ymd = `${nextMonday.getFullYear()}-${String(nextMonday.getMonth() + 1).padStart(2, '0')}-${String(nextMonday.getDate()).padStart(2, '0')}`;
    document.getElementById('weekStart').value = ymd;
}

document.getElementById('btnGenerate').addEventListener('click', function() {
    const picked = document.getElementById('weekStart').value;
    if (!picked) {
        showErrorToast('Choisissez une date.');
        return;
    }
    const week_start = mondayOf(picked);
    const btn = this;
    btn.disabled = true;
    fetch('/api/recurring-courses/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ week_start })
    })
    .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.error); }); return r.json(); })
    .then(data => {
        const resultDiv = document.getElementById('generateResult');
        resultDiv.innerHTML = `<div class="alert alert-info mb-0">
            ✅ ${data.created} cours créé(s) pour la semaine du ${week_start}.
            ${data.skipped > 0 ? `${data.skipped} créneau(x) déjà existant(s), ignoré(s).` : ''}
        </div>`;
    })
    .catch(err => showErrorToast('Erreur : ' + err.message))
    .finally(() => { btn.disabled = false; });
});

loadRecurringCourses();
setDefaultWeekStart();
