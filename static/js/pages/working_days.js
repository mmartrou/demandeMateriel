// Script de la page working_days (extrait de templates/working_days.html).
class WorkingDaysCalendar {
    constructor() {
        console.log('WorkingDaysCalendar: Initialisation...');
        this.debugElement = document.getElementById('debug-info');
        this.debugText = document.getElementById('debug-text');
        this.showDebug('Constructor démarré');
        
        this.currentDate = new Date();
        this.currentMonth = this.currentDate.getMonth();
        this.currentYear = this.currentDate.getFullYear();
        this.workingDaysConfig = {};
        this.selectedDate = null;
        
        // Sélection multiple
        this.selectedDays = new Set();
        this.multiSelectMode = false;
        this.lastClickedDay = null;
        
        this.showDebug('Variables initialisées');
        this.init();
    }
    
    showDebug(message) {
        console.log('Calendar Debug:', message);
        if (this.debugElement && this.debugText) {
            this.debugElement.style.display = 'block';
            this.debugText.textContent = message;
        }
    }
    
    init() {
        this.showDebug('Début init()');
        try {
            this.bindEvents();
            this.showDebug('Events bindés');
            this.loadMonth();
            this.showDebug('Mois chargé');
        } catch (error) {
            this.showDebug('Erreur init: ' + error.message);
            console.error('Erreur init calendrier:', error);
        }
    }
    
    bindEvents() {
        document.getElementById('prevMonth').addEventListener('click', () => {
            this.currentMonth--;
            if (this.currentMonth < 0) {
                this.currentMonth = 11;
                this.currentYear--;
            }
            this.loadMonth();
        });
        
        document.getElementById('nextMonth').addEventListener('click', () => {
            this.currentMonth++;
            if (this.currentMonth > 11) {
                this.currentMonth = 0;
                this.currentYear++;
            }
            this.loadMonth();
        });
        
        // Modal events
        document.getElementById('saveDayConfig').addEventListener('click', () => {
            this.saveDayConfig();
        });
        
        document.getElementById('resetDayConfig').addEventListener('click', () => {
            this.resetDayConfig();
        });
        
        // Sélection multiple events
        document.getElementById('markSelectedWorking').addEventListener('click', () => {
            this.markSelectedAs(true);
        });
        
        document.getElementById('markSelectedNonWorking').addEventListener('click', () => {
            this.markSelectedAs(false);
        });
        
        document.getElementById('clearSelection').addEventListener('click', () => {
            this.clearSelection();
        });
        
        // Écouter les touches Ctrl/Shift pour activer mode multi-sélection
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.shiftKey) {
                this.multiSelectMode = true;
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (!e.ctrlKey && !e.shiftKey) {
                this.multiSelectMode = false;
            }
        });
    }
    
    async loadMonth() {
        this.showDebug(`Chargement mois ${this.currentMonth + 1}/${this.currentYear}`);
        const startDate = new Date(this.currentYear, this.currentMonth, 1);
        const endDate = new Date(this.currentYear, this.currentMonth + 1, 0);
        
        // Charger la configuration pour le mois
        try {
            const url = `/api/working-days?start_date=${this.formatDate(startDate)}&end_date=${this.formatDate(endDate)}`;
            this.showDebug(`Requête API: ${url}`);
            
            const response = await fetch(url);
            if (response.ok) {
                const config = await response.json();
                this.workingDaysConfig = {};
                config.forEach(item => {
                    this.workingDaysConfig[item.date] = item;
                });
                this.showDebug(`Config chargée: ${config.length} éléments`);
            } else {
                this.showDebug(`Erreur API: ${response.status}`);
            }
        } catch (error) {
            this.showDebug(`Erreur fetch: ${error.message}`);
            console.error('Erreur chargement configuration:', error);
        }
        
        this.showDebug('Début rendu calendrier');
        this.renderCalendar();
        this.updateStats();
    }
    
    renderCalendar() {
        this.showDebug('renderCalendar() démarré');
        try {
            const monthNames = [
                'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
            ];
            
            const dayNames = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
            
            // Mise à jour du titre
            const titleElement = document.getElementById('currentMonthYear');
            if (!titleElement) {
                this.showDebug('Erreur: élément currentMonthYear non trouvé');
                return;
            }
            
            titleElement.textContent = `${monthNames[this.currentMonth]} ${this.currentYear}`;
            this.showDebug('Titre mis à jour');
            
            // Génération du calendrier
            const firstDay = new Date(this.currentYear, this.currentMonth, 1);
            const lastDay = new Date(this.currentYear, this.currentMonth + 1, 0);
            const startCalendar = new Date(firstDay);
            // Ajuster pour commencer par lundi (0=dim, 1=lun, etc.)
            const dayOffset = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;
            startCalendar.setDate(startCalendar.getDate() - dayOffset);
        
        let html = '<table class="calendar-table table">';
        
        // En-têtes des jours
        html += '<thead><tr>';
        dayNames.forEach(day => {
            html += `<th>${day}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Génération des semaines
        const current = new Date(startCalendar);
        const today = new Date();
        
        while (current <= lastDay || current.getDay() !== 0) {
            html += '<tr>';
            
            for (let day = 0; day < 7; day++) {
                const dateStr = this.formatDate(current);
                const isCurrentMonth = current.getMonth() === this.currentMonth;
                const isToday = current.toDateString() === today.toDateString();
                const config = this.workingDaysConfig[dateStr];
                
                let dayClass = 'calendar-day';
                let statusIcon = '';
                
                // Déterminer le statut du jour
                if (config) {
                    if (config.is_working_day) {
                        dayClass += ' working';
                        statusIcon = '<i class="fas fa-check"></i>';
                    } else {
                        dayClass += ' non-working';
                        statusIcon = '<i class="fas fa-times"></i>';
                    }
                } else {
                    // Défaut: lun-ven ouvrés, WE non-ouvrés
                    const weekday = current.getDay();
                    if (weekday >= 1 && weekday <= 5) {
                        dayClass += ' working';
                        statusIcon = '<i class="fas fa-check"></i>';
                    } else {
                        dayClass += ' non-working';
                        statusIcon = '<i class="fas fa-times"></i>';
                    }
                }
                
                if (!isCurrentMonth) {
                    dayClass += ' other-month';
                }
                
                if (isToday) {
                    dayClass += ' today';
                }
                
                html += `
                    <td>
                        <div class="${dayClass}" data-date="${dateStr}" onclick="calendar.handleDayClick(event, '${dateStr}')">
                            <div class="day-number">${current.getDate()}</div>
                            <div class="day-status">${statusIcon}</div>
                        </div>
                    </td>
                `;
                
                current.setDate(current.getDate() + 1);
            }
            
            html += '</tr>';
            
            if (current > lastDay && current.getDay() === 1) break; // Arrêter au lundi suivant
        }
        
        html += '</tbody></table>';
        
        const calendarElement = document.getElementById('workingDaysCalendar');
        if (calendarElement) {
            calendarElement.innerHTML = html;
            this.showDebug('Calendrier HTML injecté');
        } else {
            this.showDebug('Erreur: élément workingDaysCalendar non trouvé');
        }
        
        } catch (error) {
            this.showDebug('Erreur renderCalendar: ' + error.message);
            console.error('Erreur rendu calendrier:', error);
        }
    }
    
    formatDate(date) {
        // Avoid timezone shift: always use local date parts
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    handleDayClick(event, dateStr) {
        if (event.shiftKey && this.lastClickedDay) {
            // Sélection par plage (Shift)
            event.preventDefault();
            this.selectRange(this.lastClickedDay, dateStr);
        } else if (event.ctrlKey) {
            // Sélection multiple (Ctrl)
            event.preventDefault();
            this.toggleDaySelection(dateStr);
            this.lastClickedDay = dateStr;
        } else if (this.selectedDays.size > 0) {
            // Clic simple avec sélection active - annuler sélection
            this.clearSelection();
            this.openDayModal(dateStr);
        } else {
            // Clic normal
            this.openDayModal(dateStr);
            this.lastClickedDay = dateStr;
        }
    }
    
    toggleDaySelection(dateStr) {
        if (this.selectedDays.has(dateStr)) {
            this.selectedDays.delete(dateStr);
        } else {
            this.selectedDays.add(dateStr);
        }
        this.updateSelectionUI();
    }
    
    selectRange(startDateStr, endDateStr) {
        // Convertir les dates pour comparaison
        const startDate = new Date(startDateStr);
        const endDate = new Date(endDateStr);
        
        // S'assurer que startDate <= endDate
        const fromDate = startDate <= endDate ? startDate : endDate;
        const toDate = startDate <= endDate ? endDate : startDate;
        
        // Vider la sélection actuelle
        this.selectedDays.clear();
        
        // Sélectionner tous les jours dans la plage
        const currentDate = new Date(fromDate);
        while (currentDate <= toDate) {
            const dateStr = this.formatDate(currentDate);
            this.selectedDays.add(dateStr);
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        this.updateSelectionUI();
    }
    
    updateSelectionUI() {
        // Mettre à jour le compteur
        document.getElementById('selectedDaysCount').textContent = this.selectedDays.size;
        
        // Afficher/masquer les contrôles
        const controls = document.getElementById('multiSelectControls');
        if (this.selectedDays.size > 0) {
            controls.style.display = 'block';
        } else {
            controls.style.display = 'none';
        }
        
        // Mettre à jour l'apparence des jours sélectionnés
        document.querySelectorAll('.calendar-day').forEach(dayElement => {
            const dateStr = dayElement.getAttribute('data-date');
            if (this.selectedDays.has(dateStr)) {
                dayElement.classList.add('selected');
            } else {
                dayElement.classList.remove('selected');
            }
        });
    }
    
    clearSelection() {
        this.selectedDays.clear();
        this.lastClickedDay = null;
        this.updateSelectionUI();
    }
    
    async markSelectedAs(isWorking) {
        if (this.selectedDays.size === 0) return;
        
        const updates = [];
        for (const dateStr of this.selectedDays) {
            updates.push({
                date: dateStr,
                is_working_day: isWorking,
                description: `Modification groupée - ${isWorking ? 'Ouvré' : 'Non ouvré'}`
            });
        }
        
        try {
            const response = await fetch('/api/working-days/bulk', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    updates: updates
                })
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Erreur lors de la mise à jour');
            }
            
            // Recharger le mois pour refléter les changements
            await this.loadMonth();
            this.clearSelection();
            
            let message = `${result.updated_count} jour(s) modifié(s) avec succès !`;
            if (result.errors && result.errors.length > 0) {
                message += `\n\nAvertissements:\n${result.errors.join('\n')}`;
            }
            
            alert(message);
            
        } catch (error) {
            console.error('Erreur lors de la modification groupée:', error);
            alert('Erreur lors de la modification : ' + error.message);
        }
    }
    
    openDayModal(dateStr) {
        this.selectedDate = dateStr;
        const config = this.workingDaysConfig[dateStr];
        
        document.getElementById('modalDate').value = dateStr;
        
        if (config) {
            document.getElementById(config.is_working_day ? 'isWorking' : 'isNotWorking').checked = true;
            document.getElementById('dayDescription').value = config.description || '';
        } else {
            // Défaut basé sur le jour de la semaine
            const date = new Date(dateStr);
            const isWeekday = date.getDay() >= 1 && date.getDay() <= 5;
            document.getElementById(isWeekday ? 'isWorking' : 'isNotWorking').checked = true;
            document.getElementById('dayDescription').value = '';
        }
        
        new bootstrap.Modal(document.getElementById('dayDetailsModal')).show();
    }
    
    async saveDayConfig() {
        const isWorking = document.getElementById('isWorking').checked;
        const description = document.getElementById('dayDescription').value;
        
        try {
            const response = await fetch(`/api/working-days/${this.selectedDate}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    is_working_day: isWorking,
                    description: description
                })
            });
            
            if (response.ok) {
                bootstrap.Modal.getInstance(document.getElementById('dayDetailsModal')).hide();
                this.loadMonth(); // Recharger le calendrier
                this.showNotification('Configuration sauvegardée avec succès', 'success');
            } else {
                this.showNotification('Erreur lors de la sauvegarde', 'danger');
            }
        } catch (error) {
            console.error('Erreur sauvegarde:', error);
            this.showNotification('Erreur lors de la sauvegarde', 'danger');
        }
    }
    
    async resetDayConfig() {
        try {
            const response = await fetch(`/api/working-days/${this.selectedDate}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                bootstrap.Modal.getInstance(document.getElementById('dayDetailsModal')).hide();
                this.loadMonth(); // Recharger le calendrier
                this.showNotification('Configuration réinitialisée', 'info');
            } else {
                this.showNotification('Erreur lors de la réinitialisation', 'danger');
            }
        } catch (error) {
            console.error('Erreur réinitialisation:', error);
            this.showNotification('Erreur lors de la réinitialisation', 'danger');
        }
    }
    
    updateStats() {
        let workingCount = 0;
        let nonWorkingCount = 0;
        
        // Calculer pour tous les jours du mois affiché
        const firstDay = new Date(this.currentYear, this.currentMonth, 1);
        const lastDay = new Date(this.currentYear, this.currentMonth + 1, 0);
        
        const currentDate = new Date(firstDay);
        while (currentDate <= lastDay) {
            const dateStr = this.formatDate(currentDate);
            const config = this.workingDaysConfig[dateStr];
            
            let isWorking;
            if (config) {
                // Jour configuré
                isWorking = config.is_working_day;
            } else {
                // Jour par défaut : lun-ven ouvrés, sam-dim non-ouvrés
                const weekday = currentDate.getDay();
                isWorking = weekday >= 1 && weekday <= 5;
            }
            
            if (isWorking) {
                workingCount++;
            } else {
                nonWorkingCount++;
            }
            
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        document.getElementById('workingDaysCount').textContent = workingCount;
        document.getElementById('nonWorkingDaysCount').textContent = nonWorkingCount;
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
        
        // Supprimer après 5 secondes
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
}

// Initialiser le calendrier
let calendar;
document.addEventListener('DOMContentLoaded', () => {
    calendar = new WorkingDaysCalendar();
    loadDeadlineDays();
});

async function loadDeadlineDays() {
    try {
        const resp = await fetch('/api/deadline-config');
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Erreur');
        const input = document.getElementById('deadlineDaysInput');
        if (input) input.value = data.deadline_working_days;
        const readonly = document.getElementById('deadlineDaysReadonly');
        if (readonly) readonly.textContent = data.deadline_working_days;
    } catch (error) {
        console.error('Erreur chargement délai de dépôt:', error);
    }
}

const saveDeadlineBtn = document.getElementById('saveDeadlineDays');
if (saveDeadlineBtn) {
    saveDeadlineBtn.addEventListener('click', async () => {
        const input = document.getElementById('deadlineDaysInput');
        const resultEl = document.getElementById('deadlineDaysResult');
        const value = parseInt(input.value, 10);
        if (isNaN(value) || value < 0) {
            resultEl.innerHTML = '<div class="alert alert-danger py-1 mb-0">Valeur invalide.</div>';
            return;
        }
        try {
            const resp = await fetch('/api/deadline-config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ deadline_working_days: value })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'Erreur');
            resultEl.innerHTML = '<div class="alert alert-success py-1 mb-0">Délai mis à jour.</div>';
        } catch (error) {
            resultEl.innerHTML = `<div class="alert alert-danger py-1 mb-0">${error.message}</div>`;
        }
    });
}
