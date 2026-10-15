// Script de la page room_availability (extrait de templates/room_availability.html).
class RoomAvailabilityManager {
    constructor() {
        this.slots = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSlots();
    }

    bindEvents() {
        document.getElementById('add-slot-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.addSlot();
        });

        document.getElementById('confirm-delete').addEventListener('click', () => {
            this.confirmDelete();
        });
    }

    async loadSlots() {
        try {
            const response = await fetch('/api/room-availability');
            if (response.ok) {
                this.slots = await response.json();
                this.renderSlots();
                this.renderWeeklyPlanning();
            } else {
                this.showError('Erreur lors du chargement des créneaux');
            }
        } catch (error) {
            console.error('Erreur:', error);
            this.showError('Erreur de connexion');
        }
    }

    async addSlot() {
        const room_id = parseInt(document.getElementById('salle').value);
        const jour = document.getElementById('jour').value;
        const heure_debut_h = document.getElementById('heure_debut_h').value;
        const heure_debut_m = document.getElementById('heure_debut_m').value;
        const heure_fin_h = document.getElementById('heure_fin_h').value;
        const heure_fin_m = document.getElementById('heure_fin_m').value;

        if (!room_id || !jour || !heure_debut_h || !heure_debut_m || !heure_fin_h || !heure_fin_m) {
            this.showError('Tous les champs sont requis');
            return;
        }

        // Construire les heures au format HH:MM
        const heure_debut = `${heure_debut_h}:${heure_debut_m}`;
        const heure_fin = `${heure_fin_h}:${heure_fin_m}`;

        // Vérifier que l'heure de fin est après l'heure de début
        if (heure_debut >= heure_fin) {
            this.showError('L\'heure de fin doit être après l\'heure de début');
            return;
        }

        try {
            const response = await fetch('/api/room-availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    room_id: room_id,
                    jour: jour,
                    heure_debut: heure_debut,
                    heure_fin: heure_fin
                })
            });

            const result = await response.json();

            if (response.ok) {
                this.showSuccess('Créneau ajouté avec succès');
                this.resetForm();
                this.loadSlots();
            } else {
                this.showError(result.error || 'Erreur lors de l\'ajout');
            }
        } catch (error) {
            console.error('Erreur:', error);
            this.showError('Erreur de connexion');
        }
    }

    async toggleLimited(roomId, roomName, checkbox) {
        const limited = checkbox.checked;
        const slotCount = this.slots.filter(slot => slot.room_id === roomId).length;
        if (!limited && slotCount > 0 &&
            !confirm(`La salle ${roomName} redeviendra toujours disponible : ses ${slotCount} créneau(x) seront supprimés. Continuer ?`)) {
            checkbox.checked = true;
            return;
        }
        try {
            const response = await fetch(`/api/rooms/${roomId}/limited-availability`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({limited: limited})
            });
            if (!response.ok) throw new Error((await response.json()).error || 'Erreur');
            window.location.reload();
        } catch (error) {
            checkbox.checked = !limited;
            this.showError(error.message);
        }
    }

    prepareDelete(slotId, slotInfo) {
        this.slotToDelete = slotId;
        document.getElementById('delete-slot-info').textContent = slotInfo;
        new bootstrap.Modal(document.getElementById('deleteModal')).show();
    }

    async confirmDelete() {
        if (!this.slotToDelete) return;

        try {
            const response = await fetch(`/api/room-availability/${this.slotToDelete}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (response.ok) {
                this.showSuccess('Créneau supprimé avec succès');
                bootstrap.Modal.getInstance(document.getElementById('deleteModal')).hide();
                this.loadSlots();
            } else {
                this.showError(result.error || 'Erreur lors de la suppression');
            }
        } catch (error) {
            console.error('Erreur:', error);
            this.showError('Erreur de connexion');
        }

        this.slotToDelete = null;
    }

    renderSlots() {
        const container = document.getElementById('current-slots');
        
        if (this.slots.length === 0) {
            container.innerHTML = '<p class="text-muted text-center">Aucun créneau configuré</p>';
            document.getElementById('total-slots').textContent = '0';
            return;
        }

        let html = '';
        this.slots.forEach(slot => {
            const slotInfo = `${slot.salle} - ${this.capitalizeFirst(slot.jour)} ${slot.heure_debut}-${slot.heure_fin}`;
            html += `
                <div class="slot-item">
                    <span>
                        <strong>${this.escape(slot.salle)}</strong> - ${this.capitalizeFirst(slot.jour)}<br>
                        <small>${slot.heure_debut} - ${slot.heure_fin}</small>
                    </span>
                    <button type="button" class="btn btn-outline-danger btn-remove" 
                            onclick="availabilityManager.prepareDelete(${slot.id}, '${slotInfo}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        });

        container.innerHTML = html;
        document.getElementById('total-slots').textContent = this.slots.length;
    }

    renderWeeklyPlanning() {
        const container = document.getElementById('weekly-planning');
        const jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'];
        
        let html = '<div class="row">';
        
        jours.forEach(jour => {
            const daySlots = this.slots.filter(slot => slot.jour === jour);
            
            html += `
                <div class="col-12 mb-2">
                    <div class="card">
                        <div class="card-header py-2">
                            <h6 class="mb-0">${this.capitalizeFirst(jour)}</h6>
                        </div>
                        <div class="card-body py-2">
            `;
            
            if (daySlots.length === 0) {
                html += '<small class="text-muted">Aucun créneau</small>';
            } else {
                daySlots.forEach(slot => {
                    html += `<div class="badge bg-success me-1 mb-1">${this.escape(slot.salle)} ${slot.heure_debut}-${slot.heure_fin}</div>`;
                });
            }
            
            html += `
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }

    escape(text) {
        const div = document.createElement('div');
        div.textContent = text ?? '';
        return div.innerHTML;
    }

    capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    resetForm() {
        document.getElementById('jour').value = '';
        document.getElementById('heure_debut_h').value = '';
        document.getElementById('heure_debut_m').value = '';
        document.getElementById('heure_fin_h').value = '';
        document.getElementById('heure_fin_m').value = '';
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'danger');
    }

    showNotification(message, type) {
        // Créer une notification toast
        const toastContainer = document.querySelector('.toast-container') || (() => {
            const container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
            return container;
        })();

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);
        new bootstrap.Toast(toast).show();

        // Supprimer le toast après fermeture
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
}

// Initialiser le gestionnaire
const availabilityManager = new RoomAvailabilityManager();
