// Main JavaScript functions for the Material Request application

// Toast notifications
function showSuccessToast(message) {
    const toast = document.getElementById('successToast');
    const toastBody = document.getElementById('successToastBody');
    toastBody.textContent = message;
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

function showErrorToast(message) {
    const toast = document.getElementById('errorToast');
    const toastBody = document.getElementById('errorToastBody');
    toastBody.textContent = message;
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// Alert messages
function showAlert(message, type) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        console.error("Alert container not found in the DOM.");
        return;
    }

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    alertContainer.appendChild(alertDiv);

    // Automatically remove the alert after 5 seconds
    setTimeout(() => {
        alertDiv.classList.remove('show');
        alertDiv.addEventListener('transitionend', () => alertDiv.remove());
    }, 5000);
}

// Form validation helpers
function validateRequired(elementId, message) {
    const element = document.getElementById(elementId);
    const value = element.value.trim();
    
    if (!value) {
        element.classList.add('is-invalid');
        showErrorToast(message);
        return false;
    } else {
        element.classList.remove('is-invalid');
        element.classList.add('is-valid');
        return true;
    }
}

function validateDate(elementId, message) {
    const element = document.getElementById(elementId);
    const value = element.value;
    
    if (!value) {
        element.classList.add('is-invalid');
        showErrorToast(message);
        return false;
    }
    
    const selectedDate = new Date(value);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (selectedDate < today) {
        element.classList.add('is-invalid');
        showErrorToast('La date ne peut pas être dans le passé');
        return false;
    }
    
    // Validation des 2 jours ouvrés - approximation simple
    const minDate = getMinimumValidDate();
    if (selectedDate < minDate) {
        element.classList.add('is-invalid');
        const minDateStr = minDate.toISOString().split('T')[0];
        showErrorToast(`Délai insuffisant. Première date possible: ${formatDate(minDateStr)} (2 jours ouvrés minimum)`);
        return false;
    }
    
    element.classList.remove('is-invalid');
    element.classList.add('is-valid');
    return true;
}

// ---------------------------------------------------------------------------
// Délai de dépôt : miroir JS de deadline_utils.py. Le couperet est fixé à 8h00, heure de
// Madrid, le premier des N jours ouvrés requis avant la date demandée (N = window.deadline-
// WorkingDays, 2 par défaut) — voir deadline_utils._deadline_moment() côté serveur pour le
// détail de la règle. Ces fonctions ne servent qu'à guider l'utilisateur avant l'envoi : le
// serveur reste toujours la source de vérité finale, qui revalide indépendamment.
// Les jours fériés/exceptions (configurés en base) ne sont pas connus du client : seuls les
// week-ends sont exclus ici. Cela peut rendre ce calcul légèrement optimiste autour d'un jour
// férié — dans ce cas le serveur refusera et affichera son propre message.
// ---------------------------------------------------------------------------

// Convertit un triplet {year, month, day} en Date UTC "neutre", utilisée uniquement pour des
// calculs calendaires (jour de la semaine, +/- N jours) indépendants du fuseau du navigateur.
function _utcCalendarDate(year, month, day) {
    return new Date(Date.UTC(year, month - 1, day));
}

// "Maintenant" en heure de Madrid, quel que soit le fuseau du navigateur.
// Renvoie {date: Date UTC-neutre à minuit, minutesSinceMidnight}.
function nowInMadrid() {
    const parts = Object.fromEntries(
        new Intl.DateTimeFormat('en-CA', {
            timeZone: 'Europe/Madrid',
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hour12: false
        }).formatToParts(new Date()).map(p => [p.type, p.value])
    );
    return {
        date: _utcCalendarDate(parseInt(parts.year, 10), parseInt(parts.month, 10), parseInt(parts.day, 10)),
        minutesSinceMidnight: parseInt(parts.hour, 10) * 60 + parseInt(parts.minute, 10)
    };
}

// Miroir JS de deadline_utils._deadline_moment() : couperet à 8h00 (heure de Madrid) le
// premier des `requiredDays` jours ouvrés avant `targetUtcDate` (Date UTC-neutre, minuit).
function deadlineMoment(targetUtcDate, requiredDays) {
    if (requiredDays <= 0) return { date: new Date(targetUtcDate), minutesSinceMidnight: 0 };
    let d = new Date(targetUtcDate);
    let found = 0;
    let deadlineDay = targetUtcDate;
    while (found < requiredDays) {
        d.setUTCDate(d.getUTCDate() - 1);
        if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) {
            found++;
            deadlineDay = new Date(d);
        }
    }
    return { date: deadlineDay, minutesSinceMidnight: 8 * 60 };
}

function _isBeforeMoment(a, b) {
    if (a.date.getTime() !== b.date.getTime()) return a.date.getTime() < b.date.getTime();
    return a.minutesSinceMidnight < b.minutesSinceMidnight;
}

// Le délai de dépôt est-il encore respecté, à l'instant présent, pour `targetUtcDate`
// (Date UTC-neutre à minuit) ? Miroir JS de deadline_utils.is_request_deadline_respected().
function isBeforeDepositDeadline(targetUtcDate, requiredDays) {
    return _isBeforeMoment(nowInMadrid(), deadlineMoment(targetUtcDate, requiredDays));
}

// Retourne la première date (objet Date construit en heure LOCALE du navigateur, pour rester
// compatible avec getFullYear()/getMonth()/getDate()) pour laquelle une nouvelle demande
// serait encore acceptée. Miroir JS de deadline_utils.get_earliest_valid_date().
function getMinimumValidDate() {
    const requiredDays = Number.isFinite(window.deadlineWorkingDays) ? window.deadlineWorkingDays : 2;
    const now = nowInMadrid();
    let candidate = new Date(now.date);
    candidate.setUTCDate(candidate.getUTCDate() + 1); // jamais aujourd'hui

    while (true) {
        if (candidate.getUTCDay() !== 0 && candidate.getUTCDay() !== 6) {
            if (isBeforeDepositDeadline(candidate, requiredDays)) {
                return new Date(candidate.getUTCFullYear(), candidate.getUTCMonth(), candidate.getUTCDate());
            }
        }
        candidate.setUTCDate(candidate.getUTCDate() + 1);
    }
}

function validateNumber(elementId, min, max, message) {
    const element = document.getElementById(elementId);
    const value = parseInt(element.value);
    
    if (isNaN(value) || value < min || (max && value > max)) {
        element.classList.add('is-invalid');
        showErrorToast(message);
        return false;
    } else {
        element.classList.remove('is-invalid');
        element.classList.add('is-valid');
        return true;
    }
}

// Clear validation states
function clearValidation(formId) {
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('.form-control, .form-select');
    
    inputs.forEach(input => {
        input.classList.remove('is-valid', 'is-invalid');
    });
}

// Format dates for display
function formatDate(dateString) {
    // Forcer le fuseau horaire local pour éviter les problèmes
    const date = new Date(dateString + 'T00:00:00');
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

function formatDateTime(dateTimeString) {
    const date = new Date(dateTimeString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

// Loading states
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error(`Element with ID '${elementId}' not found.`);
        return;
    }
    element.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Chargement...</span>
            </div>
            <div class="mt-2">Chargement...</div>
        </div>
    `;
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error(`Element with ID '${elementId}' not found.`);
        return;
    }
    element.innerHTML = '';
}

// API helpers
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in');
        }, index * 100);
    });
});

// Export functions for global use
window.showSuccessToast = showSuccessToast;
window.showErrorToast = showErrorToast;
window.showAlert = showAlert;
window.validateRequired = validateRequired;
window.validateDate = validateDate;
window.validateNumber = validateNumber;
window.clearValidation = clearValidation;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.apiRequest = apiRequest;