// DCRP Routes JavaScript - Working DataGrid implementation
console.log('Routes JS loaded - working DataGrid implementation');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, checking for container and routes data');
    
    const container = document.getElementById('routes-datagrid');
    if (!container) {
        console.error('Container #routes-datagrid not found');
        return;
    }
    
    console.log('Container found, DataGrid available:', typeof DataGrid !== 'undefined');
    
    // Get routes data from template
    let routesData = [];
    const dataScript = document.getElementById('routes-data');
    if (dataScript) {
        try {
            routesData = JSON.parse(dataScript.textContent);
            console.log('Routes data loaded:', routesData.length + ' routes');
        } catch (error) {
            console.error('Failed to parse routes data:', error);
        }
    }
    
    // Use real backend data only
    if (routesData.length === 0) {
        console.warn('No routes data available from backend');
    }
    
    try {
        console.log('Creating routes DataGrid...');
        
        // Detect current theme
        function getCurrentTheme() {
            const html = document.documentElement;
            if (html.getAttribute('data-bs-theme') === 'dark') {
                return 'dark';
            } else {
                return '';
            }
        }
        
        // Enhanced configuration with custom renderers and advanced features
        const grid = new DataGrid('#routes-datagrid', {
            columns: [
                { 
                    field: 'source', 
                    header: 'Source',
                    width: '100px',
                    sortable: true,
                    resizable: true,
                    renderer: function(value, row, column) {
                        if (value === 'monitor') {
                            return '<span class="badge bg-success"><i class="bi bi-gear-fill me-1"></i>Auto</span>';
                        } else if (value === 'static') {
                            return '<span class="badge bg-primary"><i class="bi bi-person-fill me-1"></i>Manual</span>';
                        } else {
                            return '<span class="badge bg-secondary">' + (value || 'Unknown') + '</span>';
                        }
                    }
                },
                { 
                    field: 'host', 
                    header: 'Host',
                    width: '2fr',
                    sortable: true,
                    resizable: true 
                },
                { 
                    field: 'upstream', 
                    header: 'Upstream',
                    width: '1.5fr',
                    sortable: true,
                    resizable: true,
                    renderer: function(value, row, column) {
                        const protocol = row.upstream_protocol || 'http';
                        const fullUrl = `${protocol.toUpperCase()}://${value}`;
                        return `<code class="upstream-code">${fullUrl}</code>`;
                    }
                },
                { 
                    field: 'route_id', 
                    header: 'Route ID',
                    width: '1fr',
                    sortable: true,
                    resizable: true,
                    renderer: function(value, row, column) {
                        if (value && value.length > 30) {
                            const shortened = value.substring(0, 20) + '...' + value.substring(value.length - 10);
                            return `<code title="${value}">${shortened}</code>`;
                        }
                        return `<code>${value || 'N/A'}</code>`;
                    }
                },
                {
                    field: 'actions',
                    header: 'Actions',
                    width: '200px',
                    sortable: false,
                    resizable: false,
                    renderer: function(value, row, column) {
                        const routeId = row.route_id;
                        const source = row.source;
                        
                        if (source === 'monitor') {
                            return '<span class="text-muted small"><i class="bi bi-gear-fill me-1"></i>Managed by Docker Monitor</span>';
                        } else {
                            return `
                                <div class="btn-group btn-group-sm" role="group">
                                    <a href="/routes/edit/${routeId}" class="btn btn-outline-primary btn-sm" title="Edit Route">
                                        <i class="bi bi-pencil"></i>
                                    </a>
                                    <button type="button" class="btn btn-outline-danger btn-sm" 
                                            onclick="confirmDeleteRoute('${routeId}', '${row.host}')" 
                                            title="Delete Route">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            `;
                        }
                    }
                }
            ],
            data: routesData,
            resizable: true,
            sortable: true,
            selectable: false,
            reorderable: true,
            theme: getCurrentTheme() === 'dark' ? 'dark bordered' : 'bordered',
            minColumnWidth: 80,
            maxColumnWidth: 500
        });
        console.log('Routes DataGrid created successfully:', grid);
        
        // Watch for theme changes and update DataGrid
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
                    const newTheme = getCurrentTheme() === 'dark' ? 'dark bordered' : 'bordered';
                    console.log('Theme changed, updating Routes DataGrid to:', newTheme);
                    
                    // Always use direct container class update (more reliable)
                    const container = document.getElementById('routes-datagrid');
                    if (container) {
                        // Remove existing theme classes
                        container.className = container.className.replace(/\b(dark|light|bordered)\b/g, '').trim();
                        
                        // Add correct theme classes
                        container.classList.add('datagrid-container'); // Ensure base class
                        newTheme.split(' ').forEach(cls => {
                            if (cls) container.classList.add(cls);
                        });
                        
                        console.log('Updated routes container classes to:', container.className);
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
        console.error('Failed to create routes DataGrid:', error);
    }
});