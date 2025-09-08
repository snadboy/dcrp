// DCRP Hosts JavaScript - Working DataGrid implementation
console.log('Hosts JS loaded - working DataGrid implementation');

// Define getCurrentTheme globally so observer can access it
function getCurrentTheme() {
    const html = document.documentElement;
    const theme = html.getAttribute('data-bs-theme');
    // Handle null, undefined, 'light' as empty (light theme)
    return theme === 'dark' ? 'dark' : '';
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, checking for container and hosts data');

    const container = document.getElementById('hosts-datagrid');
    if (!container) {
        console.error('Container #hosts-datagrid not found');
        return;
    }

    console.log('Container found, DataGrid available:', typeof DataGrid !== 'undefined');

    // Get hosts data from template
    let hostsData = [];
    const dataScript = document.getElementById('hosts-data');
    if (dataScript) {
        try {
            hostsData = JSON.parse(dataScript.textContent);
            console.log('Hosts data loaded:', hostsData.length + ' hosts');
        } catch (error) {
            console.error('Failed to parse hosts data:', error);
        }
    }

    // Use real backend data only
    if (hostsData.length === 0) {
        console.warn('No hosts data available from backend');
    }

    try {
        console.log('Creating hosts DataGrid...');
        
        const grid = new DataGrid('#hosts-datagrid', {
            columns: [
                {
                    field: 'host_id',
                    header: 'Host ID',
                    width: '120px',
                    sortable: true,
                    resizable: true
                },
                {
                    field: 'hostname',
                    header: 'Hostname',
                    width: '200px',
                    sortable: true,
                    resizable: true
                },
                {
                    field: 'user',
                    header: 'SSH User',
                    width: '100px',
                    sortable: true,
                    resizable: true
                },
                {
                    field: 'status',
                    header: 'Status',
                    width: '260px',
                    sortable: true,
                    resizable: true,
                    renderer: function (value, row, column) {
                        if (value === 'connected') {
                            return '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Connected</span>';
                        } else if (value && value.includes('failed')) {
                            // Handle SSH connection failed errors - make badge clickable
                            const errorText = value.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
                            return `
                                <span class="badge bg-danger" 
                                      style="cursor: pointer;" 
                                      onclick="showErrorModal('${errorText}')" 
                                      title="Click to view full error details">
                                    <i class="bi bi-exclamation-triangle me-1"></i>Connection Error
                                </span>
                            `;
                        } else if (value === 'connecting') {
                            return '<span class="badge bg-warning"><i class="bi bi-clock me-1"></i>Connecting</span>';
                        } else {
                            return '<span class="badge bg-secondary" title="' + (value || 'Unknown status') + '">' + (value ? 'Error' : 'Unknown') + '</span>';
                        }
                    }
                },
                {
                    field: 'last_seen',
                    header: 'Last Seen',
                    width: '180px',
                    sortable: true,
                    resizable: true,
                    renderer: function (value, row, column) {
                        if (!value) {
                            return '<span class="text-muted">Never</span>';
                        }

                        // Try to parse the date
                        const date = new Date(value);
                        if (isNaN(date.getTime())) {
                            return '<span class="text-muted">' + value + '</span>';
                        }

                        // Format as relative time
                        const now = new Date();
                        const diff = now - date;
                        const minutes = Math.floor(diff / 60000);
                        const hours = Math.floor(minutes / 60);
                        const days = Math.floor(hours / 24);

                        if (minutes < 1) {
                            return '<span class="text-success">Just now</span>';
                        } else if (minutes < 60) {
                            return '<span class="text-success">' + minutes + 'm ago</span>';
                        } else if (hours < 24) {
                            return '<span class="text-warning">' + hours + 'h ago</span>';
                        } else if (days < 7) {
                            return '<span class="text-danger">' + days + 'd ago</span>';
                        } else {
                            return '<span class="text-muted">' + date.toLocaleDateString() + '</span>';
                        }
                    }
                },
                {
                    field: 'actions',
                    header: 'Actions',
                    width: '150px',
                    sortable: false,
                    resizable: false,
                    renderer: function (value, row, column) {
                        const hostId = row.host_id || row.id;
                        return `
                            <div class="btn-group btn-group-sm" role="group">
                                <a href="/hosts/edit/${hostId}" class="btn btn-outline-primary btn-sm" title="Edit Host">
                                    <i class="bi bi-pencil"></i>
                                </a>
                                <button type="button" class="btn btn-outline-danger btn-sm" 
                                        onclick="confirmDeleteHost('${hostId}', '${row.hostname || row.name}')" 
                                        title="Delete Host">
                                    <i class="bi bi-trash"></i>
                                </button>
                                <button type="button" class="btn btn-outline-info btn-sm" 
                                        onclick="testHostConnection('${hostId}')" 
                                        title="Test Connection">
                                    <i class="bi bi-wifi"></i>
                                </button>
                            </div>
                        `;
                    }
                }
            ],
            data: hostsData,
            resizable: true,
            sortable: true,
            selectable: false,
            reorderable: true,
            theme: getCurrentTheme() === 'dark' ? 'dark bordered' : 'bordered',
            minColumnWidth: 80,
            maxColumnWidth: 400,
            onSort: function (column, direction) {
                console.log('Sorting column:', column.field, 'direction:', direction);
            },
            onResize: function (columnIndex, newWidth) {
                console.log('Resized column', columnIndex, 'to width:', newWidth);
            },
            onReorder: function (fromIndex, toIndex, columns) {
                console.log('Reordered column from', fromIndex, 'to', toIndex);
            },
            onCellClick: function (row, column, cell) {
                console.log('Cell clicked:', row, column.field, cell);
            }
        });
        console.log('Hosts DataGrid created successfully:', grid);
        
        // Watch for theme changes and update DataGrid
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
                    const newTheme = getCurrentTheme() === 'dark' ? 'dark bordered' : 'bordered';
                    console.log('Theme changed, updating Hosts DataGrid to:', newTheme);
                    
                    // Always use direct container class update (more reliable)
                    const container = document.getElementById('hosts-datagrid');
                    if (container) {
                        // Remove existing theme classes
                        container.className = container.className.replace(/\b(dark|light|bordered)\b/g, '').trim();
                        
                        // Add correct theme classes
                        container.classList.add('datagrid-container'); // Ensure base class
                        newTheme.split(' ').forEach(cls => {
                            if (cls) container.classList.add(cls);
                        });
                        
                        console.log('Updated hosts container classes to:', container.className);
                    }
                    
                    // Also try the setTheme method as backup
                    if (grid && grid.setTheme) {
                        grid.setTheme(newTheme);
                    }
                }
            });
        });
        
        // Start observing theme changes
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-bs-theme']
        });
        
    } catch (error) {
        console.error('Failed to create hosts DataGrid:', error);
    }
});

// Function to show error modal
function showErrorModal(errorText) {
    // Decode HTML entities
    const decodedText = errorText.replace(/&#39;/g, "'").replace(/&quot;/g, '"');
    
    // Set the error text in the modal
    document.getElementById('errorModalText').textContent = decodedText;
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('errorModal'));
    modal.show();
    
    // Add escape key support
    const handleEscape = function(event) {
        if (event.key === 'Escape') {
            modal.hide();
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);
    
    // Clean up escape listener when modal is hidden
    document.getElementById('errorModal').addEventListener('hidden.bs.modal', function() {
        document.removeEventListener('keydown', handleEscape);
    }, { once: true });
}

// Function to copy error text to clipboard
function copyErrorText() {
    const errorText = document.getElementById('errorModalText').textContent;
    navigator.clipboard.writeText(errorText).then(function() {
        // Show success feedback
        const copyBtn = document.getElementById('copyErrorBtn');
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="bi bi-check me-1"></i>Copied!';
        copyBtn.classList.add('btn-success');
        copyBtn.classList.remove('btn-secondary');
        
        setTimeout(function() {
            copyBtn.innerHTML = originalText;
            copyBtn.classList.remove('btn-success');
            copyBtn.classList.add('btn-secondary');
        }, 2000);
    }).catch(function(err) {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy to clipboard');
    });
}

// Make functions globally available
window.showErrorModal = showErrorModal;
window.copyErrorText = copyErrorText;