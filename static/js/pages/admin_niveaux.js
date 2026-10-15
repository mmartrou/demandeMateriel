// Script de la page admin_niveaux (extrait de templates/admin_niveaux.html).
let levelToDelete = null;

async function saveNewLevel() {
    const name = document.getElementById('newLevelName').value.trim();
    const resultEl = document.getElementById('addLevelResult');
    if (!name) {
        resultEl.innerHTML = '<div class="alert alert-danger py-1">Le nom est requis.</div>';
        return;
    }
    const resp = await fetch('/api/admin/levels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
    const data = await resp.json();
    if (resp.ok) {
        resultEl.innerHTML = `<div class="alert alert-success py-1">Niveau créé.</div>`;
        document.getElementById('newLevelName').value = '';
        setTimeout(() => location.reload(), 1000);
    } else {
        resultEl.innerHTML = `<div class="alert alert-danger py-1">${data.error}</div>`;
    }
}

function confirmDeleteLevel(id, name) {
    levelToDelete = id;
    document.getElementById('deleteLevelName').textContent = name;
    new bootstrap.Modal(document.getElementById('deleteLevelModal')).show();
}

async function doDeleteLevel() {
    if (!levelToDelete) return;
    const resp = await fetch(`/api/admin/levels/${levelToDelete}`, { method: 'DELETE' });
    bootstrap.Modal.getInstance(document.getElementById('deleteLevelModal')).hide();
    if (resp.ok) location.reload();
    else alert('Erreur lors de la suppression.');
}

function editLevelShortName(spanEl, levelId) {
    const current = spanEl.textContent === '—' ? '' : spanEl.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = current;
    input.className = 'form-control form-control-sm d-inline-block';
    input.style.width = '130px';
    input.placeholder = 'Nom court…';
    spanEl.replaceWith(input);
    input.focus();

    async function save() {
        const val = input.value.trim();
        await fetch(`/api/admin/levels/${levelId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ short_name: val })
        });
        const span = document.createElement('span');
        span.className = 'level-short-name-display';
        span.style.cssText = 'cursor:pointer; border-bottom: 1px dashed #aaa;';
        span.title = 'Cliquer pour modifier';
        span.onclick = function() { editLevelShortName(this, levelId); };
        span.textContent = val || '—';
        input.replaceWith(span);
    }

    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = current; input.blur(); }
    });
}

function editLevelDuration(spanEl, levelId) {
    const current = spanEl.textContent.trim();
    const input = document.createElement('input');
    input.type = 'number';
    input.value = current;
    input.min = 1;
    input.className = 'form-control form-control-sm d-inline-block';
    input.style.width = '90px';
    spanEl.replaceWith(input);
    input.focus();

    async function save() {
        const val = parseInt(input.value) || 85;
        await fetch(`/api/admin/levels/${levelId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ default_duration: val })
        });
        const span = document.createElement('span');
        span.className = 'level-duration-display';
        span.style.cssText = 'cursor:pointer; border-bottom: 1px dashed #aaa;';
        span.title = 'Cliquer pour modifier';
        span.onclick = function() { editLevelDuration(this, levelId); };
        span.textContent = val;
        input.replaceWith(span);
    }

    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = current; input.blur(); }
    });
}

function editLevelGroups(spanEl, levelId) {
    const current = spanEl.textContent.trim();
    const input = document.createElement('input');
    input.type = 'number';
    input.value = current;
    input.min = 0;
    input.className = 'form-control form-control-sm d-inline-block';
    input.style.width = '90px';
    spanEl.replaceWith(input);
    input.focus();

    async function save() {
        const val = (Number.isFinite(parseInt(input.value)) ? Math.max(0, parseInt(input.value)) : 1);
        await fetch(`/api/admin/levels/${levelId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ default_groups: val })
        });
        const span = document.createElement('span');
        span.className = 'level-groups-display';
        span.style.cssText = 'cursor:pointer; border-bottom: 1px dashed #aaa;';
        span.title = 'Cliquer pour modifier';
        span.onclick = function() { editLevelGroups(this, levelId); };
        span.textContent = val;
        input.replaceWith(span);
    }

    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = current; input.blur(); }
    });
}
