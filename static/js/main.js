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

function getMinimumValidDate() {
    const now = new Date();
    let candidate = new Date(now);
    candidate.setDate(now.getDate() + 1);  // Commencer par demain
    
    // Chercher la première date avec au moins 2 jours ouvrés
    while (true) {
        let workingDaysCount = 0;
        
        // Compter les jours ouvrés entre maintenant et la date candidate (exclus)
        let checkDate = new Date(now);
        checkDate.setDate(now.getDate() + 1);  // Commencer par demain
        
        while (checkDate < candidate) {
            const dayOfWeek = checkDate.getDay();
            // Lundi = 1, Mardi = 2, ..., Vendredi = 5 (jours ouvrés)
            if (dayOfWeek >= 1 && dayOfWeek <= 5) {
                workingDaysCount++;
            }
            checkDate.setDate(checkDate.getDate() + 1);
        }
        
        if (workingDaysCount >= 2) {
            return candidate;
        }
        
        candidate.setDate(candidate.getDate() + 1);
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