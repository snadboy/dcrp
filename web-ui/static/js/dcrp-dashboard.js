// DCRP Dashboard JavaScript
// Uses snadboy-table-lib for sortable/resizable table functionality

// Global variables
let routesTable = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeRoutesTable();
    startHealthRefresh();
});

// Initialize the routes table with sorting and resizing
function initializeRoutesTable() {
    const table = document.getElementById('routes-table');
    if (!table) return;
    
    routesTable = new SortableResizableTable('#routes-table', {
        sortCallback: (column, direction) => {
            sortRoutes(column, direction);
        }
    });
    
    console.log('Routes table initialized with snadboy-table-lib');
}

// Sort routes data
function sortRoutes(column, direction) {
    const tbody = document.getElementById('routes-table-body');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        let aVal = a.dataset[column] || '';
        let bVal = b.dataset[column] || '';
        
        // Convert to lowercase for case-insensitive sorting
        if (typeof aVal === 'string') aVal = aVal.toLowerCase();
        if (typeof bVal === 'string') bVal = bVal.toLowerCase();
        
        let result = 0;
        if (aVal < bVal) result = -1;
        else if (aVal > bVal) result = 1;
        
        return direction === 'desc' ? -result : result;
    });
    
    // Re-append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
    
    console.log(`Routes sorted by ${column} ${direction}`);
}

// Delete confirmation modal
function confirmDelete(routeId, host) {
    document.getElementById('delete-host').textContent = host;
    document.getElementById('delete-route-id').textContent = routeId;
    document.getElementById('delete-form').action = `/routes/${routeId}/delete`;
    
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    modal.show();
    
    // Add loading state to delete button when form is submitted
    const deleteForm = document.getElementById('delete-form');
    const deleteBtn = deleteForm.querySelector('button[type="submit"]');
    
    deleteForm.addEventListener('submit', function(e) {
        if (deleteBtn && window.DCRP && window.DCRP.setButtonLoading) {
            window.DCRP.setButtonLoading(deleteBtn, true);
        }
    });
}

// Refresh health status
function refreshHealth() {
    const refreshBtn = document.querySelector('[onclick="refreshHealth()"]');
    const originalIcon = refreshBtn ? refreshBtn.innerHTML : '';
    
    if (refreshBtn) {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
        refreshBtn.classList.add('loading');
        refreshBtn.disabled = true;
    }
    
    fetch('/api/health')
        .then(response => response.json())
        .then(data => {
            updateStatusIndicator(data.status);
            if (window.DCRP && window.DCRP.showToast) {
                window.DCRP.showToast('Health status refreshed', 'success');
            }
        })
        .catch(error => {
            console.error('Health check failed:', error);
            updateStatusIndicator('offline');
            if (window.DCRP && window.DCRP.showToast) {
                window.DCRP.showToast('Failed to refresh health status', 'error');
            }
        })
        .finally(() => {
            if (refreshBtn) {
                refreshBtn.classList.remove('loading');
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalIcon;
            }
        });
}

// Update status indicator
function updateStatusIndicator(status) {
    const statusIndicator = document.getElementById('status-indicator');
    if (!statusIndicator) return;
    
    const badge = statusIndicator.querySelector('.badge');
    if (!badge) return;
    
    if (status === 'healthy' || status === 'ok') {
        badge.className = 'badge bg-success';
        badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Online';
    } else if (status === 'offline') {
        badge.className = 'badge bg-danger';
        badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Offline';
    } else {
        badge.className = 'badge bg-warning';
        badge.innerHTML = '<i class="bi bi-circle-fill me-1"></i>Error';
    }
}

// Refresh routes without page reload
function refreshRoutes() {
    const refreshBtn = document.querySelector('[onclick="refreshRoutes()"]');
    const originalIcon = refreshBtn ? refreshBtn.innerHTML : '';
    
    if (refreshBtn) {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
        refreshBtn.classList.add('loading');
        refreshBtn.disabled = true;
    }
    
    if (window.DCRP && window.DCRP.showToast) {
        window.DCRP.showToast('Refreshing routes...', 'info');
    }
    
    // For now, just reload the page (can be enhanced later with AJAX)
    setTimeout(() => {
        window.location.reload();
    }, 500);
}

// Auto-refresh health status every 30 seconds
let healthRefreshInterval;
function startHealthRefresh() {
    if (!healthRefreshInterval) {
        healthRefreshInterval = setInterval(() => {
            // Only refresh if not currently resizing table
            if (!routesTable || !routesTable.isResizing) {
                refreshHealth();
            }
        }, 30000);
    }
}

// Expose functions globally for onclick handlers
window.confirmDelete = confirmDelete;
window.refreshHealth = refreshHealth;
window.refreshRoutes = refreshRoutes;