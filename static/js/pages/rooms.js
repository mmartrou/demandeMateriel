// Script de la page rooms (extrait de templates/rooms.html).
let rooms = [];

// Load rooms on page load
document.addEventListener('DOMContentLoaded', function() {
    loadRooms();
});

async function loadRooms() {
    try {
        const response = await fetch('/api/rooms');
        rooms = await response.json();
        document.getElementById('emptyRoomsNotice').classList.toggle('d-none', rooms.length > 0);
        displayRooms();
    } catch (error) {
        console.error('Erreur lors du chargement des salles:', error);
        alert('Erreur lors du chargement des salles');
    }
}

function escapeText(value) {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
}

function displayRooms() {
    const tbody = document.getElementById('roomsTableBody');
    tbody.innerHTML = '';

    rooms.forEach((room, index) => {
        const typeColor = room.type === 'physique' ? 'success' : room.type === 'chimie' ? 'info' : 'warning';
        const row = `
            <tr>
                <td class="text-nowrap">
                    <button class="btn btn-sm btn-outline-secondary" title="Monter" onclick="moveRoom(${index}, -1)" ${index === 0 ? 'disabled' : ''}>&uarr;</button>
                    <button class="btn btn-sm btn-outline-secondary" title="Descendre" onclick="moveRoom(${index}, 1)" ${index === rooms.length - 1 ? 'disabled' : ''}>&darr;</button>
                </td>
                <td><strong>${escapeText(room.name)}</strong></td>
                <td>${escapeText(room.room_group) || '<span class="text-muted">&mdash;</span>'}</td>
                <td><span class="badge bg-${typeColor}">${escapeText(room.type)}</span></td>
                <td>${room.ordinateurs}</td>
                <td>${room.chaises}</td>
                <td>${room.eviers}</td>
                <td>${room.hotte ? '✓' : '✗'}</td>
                <td>${room.bancs_optiques ? '✓' : '✗'}</td>
                <td>${room.obscurite_totale ? '✓' : '✗'}</td>
                <td>${room.becs_electriques ? '✓' : '✗'}</td>
                <td>${room.support_filtration ? '✓' : '✗'}</td>
                <td>${room.imprimante ? '✓' : '✗'}</td>
                <td>${room.examen ? '✓' : '✗'}</td>
                <td>${room.limited_availability ? '✓' : '✗'}</td>
                <td class="text-nowrap">
                    <button class="btn btn-sm btn-primary" title="Modifier" onclick="editRoom(${room.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" title="Supprimer" onclick="deleteRoom(${room.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });

    // Suggestions de groupes déjà utilisés
    const groups = [...new Set(rooms.map(r => r.room_group).filter(Boolean))];
    document.getElementById('roomGroupsList').innerHTML = groups.map(g => `<option value="${escapeText(g)}">`).join('');
}

async function moveRoom(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= rooms.length) return;
    [rooms[index], rooms[target]] = [rooms[target], rooms[index]];
    const response = await fetch('/api/rooms/reorder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids: rooms.map(r => r.id)})
    });
    if (!response.ok) alert("Erreur lors du changement d'ordre");
    loadRooms();
}

function fillRoomForm(room) {
    document.getElementById('editRoomId').value = room.id ?? '';
    document.getElementById('editRoomName').value = room.name ?? '';
    document.getElementById('editRoomType').value = room.type ?? 'mixte';
    document.getElementById('editRoomGroup').value = room.room_group ?? '';
    document.getElementById('editRoomLimited').checked = !!room.limited_availability;
    document.getElementById('editRoomOrdinateurs').value = room.ordinateurs ?? 0;
    document.getElementById('editRoomChaises').value = room.chaises ?? 20;
    document.getElementById('editRoomEviers').value = room.eviers ?? 0;
    document.getElementById('editRoomHotte').checked = !!room.hotte;
    document.getElementById('editRoomBancsOptiques').checked = !!room.bancs_optiques;
    document.getElementById('editRoomObscuriteTotale').checked = !!room.obscurite_totale;
    document.getElementById('editRoomBecsElectriques').checked = !!room.becs_electriques;
    document.getElementById('editRoomSupportFiltration').checked = !!room.support_filtration;
    document.getElementById('editRoomImprimante').checked = !!room.imprimante;
    document.getElementById('editRoomExamen').checked = !!room.examen;
}

function newRoom() {
    fillRoomForm({});
    document.getElementById('editRoomTitle').textContent = 'Ajouter une salle';
    new bootstrap.Modal(document.getElementById('editRoomModal')).show();
}

function editRoom(roomId) {
    const room = rooms.find(r => r.id === roomId);
    if (!room) return;
    fillRoomForm(room);
    document.getElementById('editRoomTitle').textContent = 'Modifier la salle';
    new bootstrap.Modal(document.getElementById('editRoomModal')).show();
}

async function deleteRoom(roomId) {
    const room = rooms.find(r => r.id === roomId);
    if (!room) return;
    if (!confirm(`Supprimer la salle ${room.name} ?\n\nLes plannings déjà enregistrés ne sont pas modifiés.`)) return;
    const response = await fetch(`/api/rooms/${roomId}`, {method: 'DELETE'});
    if (response.ok) {
        loadRooms();
    } else {
        const error = await response.json();
        alert('Erreur: ' + error.error);
    }
}

async function saveRoom() {
    try {
        const roomId = document.getElementById('editRoomId').value;
        const roomData = {
            name: document.getElementById('editRoomName').value,
            type: document.getElementById('editRoomType').value,
            room_group: document.getElementById('editRoomGroup').value,
            limited_availability: document.getElementById('editRoomLimited').checked ? 1 : 0,
            ordinateurs: parseInt(document.getElementById('editRoomOrdinateurs').value) || 0,
            chaises: parseInt(document.getElementById('editRoomChaises').value) || 0,
            eviers: parseInt(document.getElementById('editRoomEviers').value) || 0,
            hotte: document.getElementById('editRoomHotte').checked ? 1 : 0,
            bancs_optiques: document.getElementById('editRoomBancsOptiques').checked ? 1 : 0,
            obscurite_totale: document.getElementById('editRoomObscuriteTotale').checked ? 1 : 0,
            becs_electriques: document.getElementById('editRoomBecsElectriques').checked ? 1 : 0,
            support_filtration: document.getElementById('editRoomSupportFiltration').checked ? 1 : 0,
            imprimante: document.getElementById('editRoomImprimante').checked ? 1 : 0,
            examen: document.getElementById('editRoomExamen').checked ? 1 : 0
        };

        const response = await fetch(roomId ? `/api/rooms/${roomId}` : '/api/rooms', {
            method: roomId ? 'PUT' : 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(roomData)
        });

        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('editRoomModal')).hide();
            loadRooms();
        } else {
            const error = await response.json();
            alert('Erreur: ' + error.error);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de la sauvegarde');
    }
}

async function importRoomsCSV() {
    try {
        const fileInput = document.getElementById('csvFile');
        if (!fileInput.files[0]) {
            alert('Veuillez sélectionner un fichier CSV');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        
        const response = await fetch('/api/rooms/import-csv', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('importModal')).hide();
            loadRooms();
            alert('Salles importées avec succès');
        } else {
            const error = await response.json();
            alert('Erreur: ' + error.error);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de l\'import');
    }
}

function exportRoomsCSV() {
    window.location.href = '/api/rooms/export-csv';
}
