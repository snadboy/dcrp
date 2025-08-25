// DCRP Web UI JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });

    // Initialize status checking
    checkSystemStatus();
    
    // Check status every 30 seconds
    setInterval(checkSystemStatus, 30000);
});

/**
 * Check system status and update UI
 */
async function checkSystemStatus() {
    const statusIndicator = document.getElementById('status-indicator');
    if (!statusIndicator) return;

    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        updateStatusIndicator(data.status === 'healthy' || data.status === 'ok' ? 'online' : 'error');
    } catch (error) {
        console.error('Status check failed:', error);
        updateStatusIndicator('offline');
    }
}

/**
 * Update the status indicator in the navbar
 * @param {string} status - 'online', 'offline', or 'error'
 */
function updateStatusIndicator(status) {
    const statusIndicator = document.getElementById('status-indicator');
    if (!statusIndicator) return;

    const badge = statusIndicator.querySelector('.badge');
    if (!badge) return;

    switch (status) {
        case 'online':
            badge.className = 'badge bg-success';
            badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Online';
            break;
        case 'offline':
            badge.className = 'badge bg-danger';
            badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Offline';
            break;
        case 'error':
            badge.className = 'badge bg-warning';
            badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Error';
            break;
        default:
            badge.className = 'badge bg-secondary';
            badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Unknown';
    }
}

/**
 * Show loading state on buttons
 * @param {HTMLElement} button 
 * @param {boolean} loading 
 */
function setButtonLoading(button, loading) {
    if (loading) {
        button.disabled = true;
        button.setAttribute('data-original-text', button.innerHTML);
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Loading...';
    } else {
        button.disabled = false;
        const originalText = button.getAttribute('data-original-text');
        if (originalText) {
            button.innerHTML = originalText;
        }
    }
}

/**
 * Show toast notification
 * @param {string} message 
 * @param {string} type - 'success', 'error', 'warning', 'info'
 */
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';
        document.body.appendChild(toastContainer);
    }

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert">
            <div class="toast-header">
                <i class="bi bi-${getToastIcon(type)} text-${type} me-2"></i>
                <strong class="me-auto">DCRP</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Remove from DOM after hiding
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

/**
 * Get appropriate icon for toast type
 * @param {string} type 
 * @returns {string}
 */
function getToastIcon(type) {
    switch (type) {
        case 'success':
            return 'check-circle';
        case 'error':
            return 'exclamation-triangle';
        case 'warning':
            return 'exclamation-circle';
        case 'info':
        default:
            return 'info-circle';
    }
}

/**
 * Confirm action with user
 * @param {string} message 
 * @param {Function} callback 
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

/**
 * Copy text to clipboard
 * @param {string} text 
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard!', 'success');
    } catch (error) {
        console.error('Failed to copy:', error);
        showToast('Failed to copy to clipboard', 'error');
    }
}

/**
 * Format upstream URL for display
 * @param {string} upstream 
 * @returns {string}
 */
function formatUpstream(upstream) {
    if (upstream.includes('://')) {
        return upstream;
    }
    return `http://${upstream}`;
}

/**
 * Validate form inputs
 * @param {HTMLFormElement} form 
 * @returns {boolean}
 */
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        const value = field.value.trim();
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        
        if (!value) {
            field.classList.add('is-invalid');
            if (feedback) {
                feedback.textContent = `${field.labels[0]?.textContent || field.name} is required`;
            }
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        }
    });
    
    return isValid;
}

/**
 * Handle form submission with loading state
 * @param {HTMLFormElement} form 
 * @param {HTMLButtonElement} submitBtn 
 */
function handleFormSubmission(form, submitBtn) {
    if (!validateForm(form)) {
        return false;
    }
    
    setButtonLoading(submitBtn, true);
    return true;
}

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showToast('An unexpected error occurred', 'error');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('Network error occurred', 'error');
});

// Utility functions for specific components
window.DCRP = {
    checkSystemStatus,
    updateStatusIndicator,
    setButtonLoading,
    showToast,
    confirmAction,
    copyToClipboard,
    formatUpstream,
    validateForm,
    handleFormSubmission
};