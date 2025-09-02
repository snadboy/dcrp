class SortableResizableTable {
    constructor(tableSelector, options = {}) {
        this.tableSelector = tableSelector;
        this.table = document.querySelector(tableSelector);
        this.options = {
            hasExpandColumn: options.hasExpandColumn || false,
            sortCallback: options.sortCallback || null,
            columns: options.columns || [],
            ...options
        };
        
        // State
        this.currentSort = { column: null, direction: 'asc' };
        this.isResizing = false;
        this.currentResizer = null;
        this.currentHeader = null;
        this.startX = 0;
        this.startWidth = 0;
        
        // Register this instance
        SortableResizableTable.instances.push(this);
        
        this.init();
    }
    
    init() {
        if (!this.table) {
            console.warn(`Table not found: ${this.tableSelector}`);
            return;
        }
        
        this.setupSorting();
        this.setupResizing();
    }
    
    setupSorting() {
        const sortableHeaders = this.table.querySelectorAll('th.sortable');
        
        sortableHeaders.forEach(header => {
            header.addEventListener('click', (e) => {
                // Don't sort if we're clicking on a resizer
                if (e.target.classList.contains('column-resizer')) return;
                
                const sortKey = header.dataset.sort;
                if (!sortKey) return;
                
                // Update sort direction
                if (this.currentSort.column === sortKey) {
                    this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    this.currentSort.column = sortKey;
                    this.currentSort.direction = 'asc';
                }
                
                this.updateSortIndicators();
                
                // Call the sort callback
                if (this.options.sortCallback) {
                    this.options.sortCallback(this.currentSort.column, this.currentSort.direction);
                }
            });
        });
    }
    
    updateSortIndicators() {
        const headers = this.table.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.classList.remove('sort-asc', 'sort-desc');
            if (header.dataset.sort === this.currentSort.column) {
                header.classList.add(this.currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc');
            }
        });
    }
    
    setSortState(column, direction = 'asc') {
        this.currentSort.column = column;
        this.currentSort.direction = direction;
        this.updateSortIndicators();
        
        // Call the sort callback if provided
        if (this.options.sortCallback) {
            this.options.sortCallback(this.currentSort.column, this.currentSort.direction);
        }
    }
    
    setupResizing() {
        // Remove existing resizers
        const existingResizers = this.table.querySelectorAll('.column-resizer');
        existingResizers.forEach(resizer => resizer.remove());
        
        // Determine which headers to make resizable
        let selector = 'th:not(:last-child)'; // All except last column
        if (this.options.hasExpandColumn) {
            selector = 'th:not(:first-child):not(:last-child)'; // Skip first and last
        }
        
        const headers = this.table.querySelectorAll(selector);
        
        headers.forEach(header => {
            const resizer = document.createElement('div');
            resizer.className = 'column-resizer';
            header.appendChild(resizer);
            
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.startResize(e, header, resizer);
            });
        });
        
        // Add global mouse events (only once)
        if (!SortableResizableTable.globalEventsAdded) {
            document.addEventListener('mousemove', (e) => this.handleGlobalMouseMove(e));
            document.addEventListener('mouseup', () => this.handleGlobalMouseUp());
            SortableResizableTable.globalEventsAdded = true;
        }
    }
    
    startResize(e, header, resizer) {
        this.isResizing = true;
        this.currentResizer = resizer;
        this.currentHeader = header;
        this.startX = e.pageX;
        this.startWidth = parseInt(document.defaultView.getComputedStyle(header).width, 10);
        
        const allHeaders = Array.from(this.table.querySelectorAll('th'));
        const targetColumnIndex = allHeaders.indexOf(header);
        
        // Lock widths for columns to the left
        for (let i = 0; i < targetColumnIndex; i++) {
            const leftHeader = allHeaders[i];
            const currentWidth = parseInt(document.defaultView.getComputedStyle(leftHeader).width, 10);
            leftHeader.style.width = currentWidth + 'px';
            
            // Also lock corresponding td widths
            const rows = this.table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const cell = row.children[i];
                if (cell) {
                    cell.style.width = currentWidth + 'px';
                }
            });
        }
        
        // Set initial width for target column
        header.style.width = this.startWidth + 'px';
        const rows = this.table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cell = row.children[targetColumnIndex];
            if (cell) {
                cell.style.width = this.startWidth + 'px';
            }
        });
        
        resizer.classList.add('resizing');
        this.table.closest('.table-container').classList.add('resizing');
    }
    
    handleGlobalMouseMove(e) {
        // Find the active table widget
        const activeWidget = SortableResizableTable.instances.find(widget => widget.isResizing);
        if (activeWidget) {
            activeWidget.doResize(e);
        }
    }
    
    handleGlobalMouseUp() {
        // Find the active table widget and stop resizing
        const activeWidget = SortableResizableTable.instances.find(widget => widget.isResizing);
        if (activeWidget) {
            activeWidget.stopResize();
        }
    }
    
    doResize(e) {
        if (!this.isResizing || !this.currentHeader) return;
        
        const deltaX = e.pageX - this.startX;
        const newWidth = this.startWidth + deltaX;
        const minWidth = 80;
        
        if (newWidth < minWidth) return;
        
        this.currentHeader.style.width = newWidth + 'px';
        
        // Update corresponding td elements
        const allHeaders = Array.from(this.table.querySelectorAll('th'));
        const targetColumnIndex = allHeaders.indexOf(this.currentHeader);
        const rows = this.table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const cell = row.children[targetColumnIndex];
            if (cell) {
                cell.style.width = newWidth + 'px';
            }
        });
    }
    
    stopResize() {
        if (!this.isResizing) return;
        
        this.isResizing = false;
        
        if (this.currentResizer) {
            this.currentResizer.classList.remove('resizing');
            this.currentResizer = null;
        }
        
        this.currentHeader = null;
        this.table.closest('.table-container').classList.remove('resizing');
    }
    
    // Public methods
    setSortState(column, direction) {
        this.currentSort = { column, direction };
        this.updateSortIndicators();
    }
    
    getSortState() {
        return { ...this.currentSort };
    }
}

// Static properties for managing instances
SortableResizableTable.globalEventsAdded = false;
SortableResizableTable.instances = [];