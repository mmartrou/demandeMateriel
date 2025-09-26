// Minimal Bootstrap-like JavaScript for Material Request Application

// Toast functionality
class Toast {
    constructor(element) {
        this.element = element;
    }
    
    show() {
        this.element.style.display = 'block';
        this.element.classList.add('show');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.hide();
        }, 5000);
    }
    
    hide() {
        this.element.classList.remove('show');
        setTimeout(() => {
            this.element.style.display = 'none';
        }, 300);
    }
}

// Modal functionality
class Modal {
    constructor(element) {
        this.element = element;
    }
    
    show() {
        this.element.style.display = 'block';
        this.element.classList.add('show');
        document.body.style.overflow = 'hidden';
    }
    
    hide() {
        this.element.classList.remove('show');
        setTimeout(() => {
            this.element.style.display = 'none';
            document.body.style.overflow = '';
        }, 300);
    }
}

// Bootstrap-like object
window.bootstrap = {
    Toast: Toast,
    Modal: Modal
};

// Handle modal close buttons
document.addEventListener('click', function(e) {
    if (e.target.hasAttribute('data-bs-dismiss')) {
        const dismissType = e.target.getAttribute('data-bs-dismiss');
        if (dismissType === 'modal') {
            const modal = e.target.closest('.modal');
            if (modal) {
                const modalInstance = new Modal(modal);
                modalInstance.hide();
            }
        } else if (dismissType === 'toast') {
            const toast = e.target.closest('.toast');
            if (toast) {
                const toastInstance = new Toast(toast);
                toastInstance.hide();
            }
        }
    }
});

// Simple form validation
function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Add CSS for validation states
const style = document.createElement('style');
style.textContent = `
    .is-invalid {
        border-color: #dc3545 !important;
    }
    
    .is-valid {
        border-color: #28a745 !important;
    }
    
    .toast {
        position: fixed;
        bottom: 20px;
        right: 20px;
        min-width: 350px;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 0.25rem;
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
        display: none;
        z-index: 1050;
        transition: opacity 0.3s ease;
    }
    
    .toast.show {
        opacity: 1;
    }
    
    .toast-header {
        display: flex;
        align-items: center;
        padding: 0.5rem 0.75rem;
        color: #6c757d;
        background-color: rgba(255, 255, 255, 0.85);
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    }
    
    .toast-body {
        padding: 0.75rem;
    }
    
    .btn-close {
        box-sizing: content-box;
        width: 1em;
        height: 1em;
        padding: 0.25em 0.25em;
        color: #000;
        background: transparent url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='%23000'%3e%3cpath d='m.235 1.027 4.728-4.728.708.708L.94 1.735z'/%3e%3cpath d='m.94 1.735 4.728 4.728-.708.708L.235 2.443z'/%3e%3c/svg%3e") center/1em auto no-repeat;
        border: 0;
        border-radius: 0.25rem;
        opacity: 0.5;
    }
    
    .btn-close:hover {
        color: #000;
        text-decoration: none;
        opacity: 0.75;
    }
    
    .btn-close-white {
        filter: invert(1) grayscale(100%) brightness(200%);
    }
    
    .modal {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 1055;
        display: none;
        width: 100%;
        height: 100%;
        overflow-x: hidden;
        overflow-y: auto;
        outline: 0;
        background-color: rgba(0, 0, 0, 0.5);
    }
    
    .modal.show {
        display: block !important;
    }
    
    .modal-dialog {
        position: relative;
        width: auto;
        margin: 1.75rem auto;
        max-width: 500px;
        pointer-events: none;
    }
    
    .modal-content {
        position: relative;
        display: flex;
        flex-direction: column;
        width: 100%;
        pointer-events: auto;
        background-color: #fff;
        background-clip: padding-box;
        border: 1px solid rgba(0, 0, 0, 0.2);
        border-radius: 0.3rem;
        outline: 0;
    }
    
    .modal-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        padding: 1rem 1rem;
        border-bottom: 1px solid #dee2e6;
        border-top-left-radius: calc(0.3rem - 1px);
        border-top-right-radius: calc(0.3rem - 1px);
    }
    
    .modal-title {
        margin-bottom: 0;
        line-height: 1.5;
    }
    
    .modal-body {
        position: relative;
        flex: 1 1 auto;
        padding: 1rem;
    }
    
    .modal-footer {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: flex-end;
        padding: 0.75rem;
        border-top: 1px solid #dee2e6;
        border-bottom-right-radius: calc(0.3rem - 1px);
        border-bottom-left-radius: calc(0.3rem - 1px);
    }
    
    .spinner-border {
        display: inline-block;
        width: 2rem;
        height: 2rem;
        vertical-align: text-bottom;
        border: 0.25em solid currentColor;
        border-right-color: transparent;
        border-radius: 50%;
        animation: spinner-border 0.75s linear infinite;
    }
    
    @keyframes spinner-border {
        to { transform: rotate(360deg); }
    }
    
    .visually-hidden {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        padding: 0 !important;
        margin: -1px !important;
        overflow: hidden !important;
        clip: rect(0, 0, 0, 0) !important;
        white-space: nowrap !important;
        border: 0 !important;
    }
`;
document.head.appendChild(style);

// Export for global access
window.validateForm = validateForm;