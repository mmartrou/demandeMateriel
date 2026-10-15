// Script de la page admin_users (extrait de templates/admin_users.html).
let teacherToDelete = null;

function editShortName(spanEl) {
    const teacherId = spanEl.dataset.id;
    const current = spanEl.textContent === '—' ? '' : spanEl.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = current;
    input.className = 'form-control form-control-sm d-inline-block';
    input.style.width = '120px';
    input.placeholder = 'Nom court…';
    spanEl.replaceWith(input);
    input.focus();

    async function save() {
        const val = input.value.trim();
        const resp = await fetch(`/api/admin/teachers/${teacherId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ short_name: val })
        });
        const span = document.createElement('span');
        span.className = 'short-name-display';
        span.dataset.id = teacherId;
        span.style.cssText = 'cursor:pointer; border-bottom: 1px dashed #aaa;';
        span.title = 'Cliquer pour modifier';
        span.onclick = function() { editShortName(this); };
        span.textContent = val || '—';
        input.replaceWith(span);
    }

    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { input.value = current; input.blur(); }
    });
}

async function saveNewTeacher() {
    const name = document.getElementById('newTeacherName').value.trim();
    const resultEl = document.getElementById('addTeacherResult');
    if (!name) {
        resultEl.innerHTML = '<div class="alert alert-danger py-1">Le nom est requis.</div>';
        return;
    }
    const resp = await fetch('/api/admin/teachers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
    const data = await resp.json();
    if (resp.ok) {
        resultEl.innerHTML = `<div class="alert alert-success py-1">Enseignant créé avec l'id ${data.id}.</div>`;
        document.getElementById('newTeacherName').value = '';
        setTimeout(() => location.reload(), 1200);
    } else {
        resultEl.innerHTML = `<div class="alert alert-danger py-1">${data.error}</div>`;
    }
}

let userToDelete = null;

function confirmDeleteUser(id, email) {
    userToDelete = id;
    document.getElementById('deleteUserEmail').textContent = email;
    new bootstrap.Modal(document.getElementById('deleteUserModal')).show();
}

async function doDeleteUser() {
    if (!userToDelete) return;
    const resp = await fetch(`/api/admin/users/${userToDelete}`, { method: 'DELETE' });
    const data = await resp.json();
    bootstrap.Modal.getInstance(document.getElementById('deleteUserModal')).hide();
    if (resp.ok) {
        location.reload();
    } else {
        alert('Erreur : ' + data.error);
    }
}

function confirmDeleteTeacher(id, name) {
    teacherToDelete = id;
    document.getElementById('deleteTeacherName').textContent = name;
    new bootstrap.Modal(document.getElementById('deleteTeacherModal')).show();
}

async function doDeleteTeacher() {
    if (!teacherToDelete) return;
    const resp = await fetch(`/api/admin/teachers/${teacherToDelete}`, { method: 'DELETE' });
    const data = await resp.json();
    bootstrap.Modal.getInstance(document.getElementById('deleteTeacherModal')).hide();
    if (resp.ok) {
        location.reload();
    } else {
        alert('Erreur : ' + data.error);
    }
}

function prefillLink(email, teacherId) {
    document.getElementById('linkEmail').value = email;
    document.getElementById('linkTeacherId').value = teacherId !== null ? String(teacherId) : '';
    document.getElementById('linkResult').innerHTML = '';
    new bootstrap.Modal(document.getElementById('linkModal')).show();
}

async function saveLink() {
    const email = document.getElementById('linkEmail').value.trim();
    const teacherId = document.getElementById('linkTeacherId').value;
    const resultEl = document.getElementById('linkResult');
    if (!email || !teacherId) {
        resultEl.innerHTML = '<div class="alert alert-danger py-1">Email et enseignant requis.</div>';
        return;
    }
    const resp = await fetch('/api/admin/link-teacher', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, teacher_id: parseInt(teacherId) })
    });
    const data = await resp.json();
    if (resp.ok) {
        resultEl.innerHTML = '<div class="alert alert-success py-1">Association enregistrée.</div>';
        setTimeout(() => location.reload(), 1000);
    } else {
        resultEl.innerHTML = `<div class="alert alert-danger py-1">${data.error}</div>`;
    }
}
