// Script de la page establishment (extrait de templates/establishment.html).
const FIELDS = ['site_name', 'timezone', 'deadline_hour', 'time_slots', 'afternoon_start', 'separators', 'labo_email', 'allowed_domain'];

document.getElementById('establishmentForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = document.getElementById('saveResult');
    const payload = {};
    FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.disabled) payload[id] = el.value;
    });
    result.textContent = 'Enregistrement…';
    result.className = 'text-muted';
    try {
        const response = await fetch('/api/site-settings', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (response.ok) {
            // Réaffiche les valeurs normalisées par le serveur (ex : « 09h00 » devient « 9h00 »)
            FIELDS.forEach(id => {
                const el = document.getElementById(id);
                if (el && !el.disabled && data.settings[id] !== undefined) {
                    el.value = ['time_slots', 'separators'].includes(id) ? data.settings[id].split(',').join(', ') : data.settings[id];
                }
            });
            result.textContent = '✓ Enregistré. Rechargez les autres pages ouvertes pour voir les changements.';
            result.className = 'text-success';
        } else {
            result.textContent = '✗ ' + (data.error || 'Erreur');
            result.className = 'text-danger';
        }
    } catch (error) {
        result.textContent = '✗ Erreur réseau';
        result.className = 'text-danger';
    }
});
