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
    } else {
        element.classList.remove('is-invalid');
        element.classList.add('is-valid');
        return true;
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
    const options = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    return new Date(dateString).toLocaleDateString('fr-FR', options);
}

function formatDateTime(dateTimeString) {
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return new Date(dateTimeString).toLocaleDateString('fr-FR', options);
}

// Loading states
function showLoading(elementId) {
    const element = document.getElementById(elementId);
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
window.validateRequired = validateRequired;
window.validateDate = validateDate;
window.validateNumber = validateNumber;
window.clearValidation = clearValidation;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.apiRequest = apiRequest;