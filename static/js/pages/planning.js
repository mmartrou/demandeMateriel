// Script de la page planning (extrait de templates/planning.html).
document.getElementById('planningDate').addEventListener('change', function() {
    const date = this.value;

    if (!date) {
        document.getElementById('planningDay').style.display = 'none';
        document.getElementById('planningLegend').style.display = 'none';
        return;
    }
    
    // Mettre à jour le titre avec la date
    const dateObj = new Date(date + 'T00:00:00'); // Forcer le fuseau horaire local
    const options = { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    const formattedDate = dateObj.toLocaleDateString('fr-FR', options);
    document.getElementById('planningDayTitle').textContent = `📅 Planning du ${formattedDate}`;
    
    fetch(`/api/requests?start_date=${date}&end_date=${date}`)
        .then(response => response.json())
        .then(requests => {
            const planningContainer = document.getElementById('planningByTeacher');
            const noResults = document.getElementById('noPlanningResults');
            const planningDay = document.getElementById('planningDay');
            const planningLegend = document.getElementById('planningLegend');
            
            planningContainer.innerHTML = '';
            
            if (requests.length === 0) {
                noResults.classList.remove('d-none');
                planningDay.style.display = 'none';
                planningLegend.style.display = 'none';
                return;
            }
            
            noResults.classList.add('d-none');
            planningDay.style.display = 'block';
            planningLegend.style.display = 'block';
            
            // Grouper les demandes par enseignant
            const requestsByTeacher = {};
            requests.forEach(request => {
                if (!requestsByTeacher[request.teacher_name]) {
                    requestsByTeacher[request.teacher_name] = [];
                }
                requestsByTeacher[request.teacher_name].push(request);
            });
            
            // Créer l'affichage pour chaque enseignant
            Object.keys(requestsByTeacher).sort().forEach(teacherName => {
                const teacherGroup = document.createElement('div');
                teacherGroup.className = 'teacher-group';
                
                const teacherHeader = document.createElement('div');
                teacherHeader.className = 'teacher-name';
                teacherHeader.textContent = teacherName;
                teacherGroup.appendChild(teacherHeader);
                
                // Trier les demandes par horaire avant affichage
                const sortedRequests = requestsByTeacher[teacherName].sort((a, b) => {
                    const timeA = a.horaire || '';
                    const timeB = b.horaire || '';
                    
                    // Si pas d'horaire, mettre à la fin
                    if (!timeA && !timeB) return 0;
                    if (!timeA) return 1;
                    if (!timeB) return -1;
                    
                    // Convertir les horaires en minutes pour comparaison
                    const parseTime = (time) => {
                        const match = time.match(/(\d+)h(\d*)/);
                        if (match) {
                            const hours = parseInt(match[1]);
                            const minutes = match[2] ? parseInt(match[2]) : 0;
                            return hours * 60 + minutes;
                        }
                        return 0;
                    };
                    
                    return parseTime(timeA) - parseTime(timeB);
                });
                
                sortedRequests.forEach(request => {
                    const requestElement = createPlanningRequestElement(request);
                    teacherGroup.appendChild(requestElement);
                });
                
                planningContainer.appendChild(teacherGroup);
            });
        })
        .catch(error => {
            console.error('Error loading requests:', error);
            document.getElementById('noPlanningResults').classList.remove('d-none');
            document.getElementById('planningDay').style.display = 'none';
            document.getElementById('planningLegend').style.display = 'none';
        });
});

function createPlanningRequestElement(request) {
    const requestDiv = document.createElement('div');
    requestDiv.className = 'planning-request';
    
    // Déterminer la couleur de fond selon le statut
    let bgColor = '#007bff'; // Bleu par défaut (demande normale)

    if (request.is_lab_test) {
        bgColor = '#fd7e14'; // Orange pour test au labo (pas de salle attribuée)
    } else if (request.selected_materials === 'Absent') {
        bgColor = '#dc3545'; // Rouge pour absent
    } else if (request.selected_materials === 'Pas besoin de matériel') {
        bgColor = '#20c997'; // Vert clair pour pas besoin de matériel (NOUVELLE COULEUR)
    } else if (request.prepared) {
        bgColor = '#28a745'; // Vert foncé pour préparé
    } else if (request.modified) {
        bgColor = '#ffc107'; // Jaune pour modifié
    }

    console.log(`Demande ${request.id}: ${request.selected_materials} → Couleur: ${bgColor}`);

    requestDiv.style.backgroundColor = bgColor;

    const roomType = request.room_type || 'Mixte';

    requestDiv.innerHTML = `
        <div class="request-header">
            <span class="request-time">🕒 ${request.horaire || 'Non spécifié'}</span>
            <span class="request-class">${request.class_name}</span>
        </div>
        ${request.is_lab_test ? `<div class="mb-2"><span class="badge bg-dark">🧪 Test au labo — aucune salle ne sera attribuée</span></div>` : ''}
        <div class="request-details">
            <div><strong>Matériel:</strong> ${request.material_description}</div>
            <div><strong>Quantité:</strong> ${request.quantity ?? 1}</div>
            ${request.computers_needed ? `<div><strong>Ordinateurs:</strong> ${request.computers_needed}</div>` : ''}
            ${request.notes ? `<div><strong>Notes:</strong> ${request.notes}</div>` : ''}
        </div>
        <select class="room-type-selector" onchange="updateRoomType(${request.id}, this.value)">
            <option value="Mixte" ${roomType === 'Mixte' ? 'selected' : ''}>🔬 Salle Mixte</option>
            <option value="Physique" ${roomType === 'Physique' ? 'selected' : ''}>⚛️ Salle Physique</option>
            <option value="Chimie" ${roomType === 'Chimie' ? 'selected' : ''}>🧪 Salle Chimie</option>
        </select>
    `;
    
    return requestDiv;
}

function updateRoomType(requestId, roomType) {
    fetch(`/api/requests/${requestId}/room-type`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({room_type: roomType})
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Erreur: ' + data.error);
            // Recharger la page pour restaurer l'ancienne valeur
            location.reload();
        } else {
            console.log('Type de salle mis à jour:', roomType);
            // Optionnel: afficher un message de succès
            if (typeof window.showToast === 'function') {
                window.showToast('success', 'Succès', 'Type de salle mis à jour');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Erreur lors de la mise à jour du type de salle');
        location.reload();
    });
}

// Définir la date par défaut au prochain jour ouvrable
function setDefaultDate() {
    const today = new Date();
    let nextWorkDay = new Date(today);
    
    // Ajouter 1 jour par défaut
    nextWorkDay.setDate(today.getDate() + 1);
    
    // Si on est vendredi (5), samedi (6) ou dimanche (0), aller au lundi suivant
    const dayOfWeek = today.getDay();
    if (dayOfWeek === 5) { // Vendredi -> Lundi (+ 3 jours)
        nextWorkDay.setDate(today.getDate() + 3);
    } else if (dayOfWeek === 6) { // Samedi -> Lundi (+ 2 jours)
        nextWorkDay.setDate(today.getDate() + 2);
    } else if (dayOfWeek === 0) { // Dimanche -> Lundi (+ 1 jour)
        nextWorkDay.setDate(today.getDate() + 1);
    }
    
    // Formater la date au format YYYY-MM-DD
    const dateString = nextWorkDay.toISOString().split('T')[0];
    document.getElementById('planningDate').value = dateString;
    
    // Déclencher l'événement change pour charger les demandes
    document.getElementById('planningDate').dispatchEvent(new Event('change'));
}

// Initialiser la date au chargement de la page
document.addEventListener('DOMContentLoaded', setDefaultDate);
