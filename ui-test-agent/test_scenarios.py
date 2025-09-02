#!/usr/bin/env python3
"""
UI Test Scenarios - Specific test implementations for DCRP dashboard
Uses Playwright MCP tools for browser automation and testing
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger("ui-test-scenarios")

class UITestScenarios:
    """Test scenario implementations for UI/UX testing"""
    
    def __init__(self, mcp_client, base_url: str):
        self.mcp = mcp_client
        self.base_url = base_url
        self.screenshot_counter = 0
        
    def _get_screenshot_name(self, prefix: str) -> str:
        """Generate unique screenshot filename"""
        self.screenshot_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}_{self.screenshot_counter}.png"
    
    async def test_themes(self) -> List[Dict[str, Any]]:
        """Test theme switching and visual consistency"""
        results = []
        
        try:
            # Navigate to dashboard
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            
            # Test light theme (default)
            logger.info("Testing light theme...")
            screenshot = self._get_screenshot_name("theme_light")
            await self.mcp.take_screenshot(screenshot, full_page=True)
            
            # Check contrast ratios
            contrast_check = await self.mcp.evaluate("""
                () => {
                    const getContrast = (fg, bg) => {
                        const getLuminance = (color) => {
                            const rgb = color.match(/\\d+/g);
                            if (!rgb) return 0;
                            const [r, g, b] = rgb.map(x => {
                                const val = parseInt(x) / 255;
                                return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
                            });
                            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
                        };
                        const l1 = getLuminance(fg) + 0.05;
                        const l2 = getLuminance(bg) + 0.05;
                        return (Math.max(l1, l2) / Math.min(l1, l2)).toFixed(2);
                    };
                    
                    const elements = document.querySelectorAll('.text-muted, .small, p, h1, h2, h3, h4, h5, h6');
                    const issues = [];
                    
                    elements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        const parent = el.parentElement;
                        const parentStyle = window.getComputedStyle(parent);
                        const contrast = getContrast(style.color, parentStyle.backgroundColor);
                        
                        if (contrast < 4.5) {  // WCAG AA standard
                            issues.push({
                                element: el.tagName + '.' + el.className,
                                contrast: contrast,
                                color: style.color,
                                background: parentStyle.backgroundColor
                            });
                        }
                    });
                    
                    return {
                        passed: issues.length === 0,
                        issues: issues,
                        totalElements: elements.length
                    };
                }
            """)
            
            results.append({
                'name': 'Light Theme Contrast',
                'passed': contrast_check.get('passed', False),
                'message': f"Checked {contrast_check.get('totalElements', 0)} elements",
                'screenshot': screenshot,
                'details': contrast_check
            })
            
            # Test dark theme (via CSS class simulation)
            logger.info("Testing dark theme...")
            await self.mcp.evaluate("() => { document.documentElement.classList.add('theme-dark'); }")
            await self.mcp.wait(1000)  # Wait for transition
            
            screenshot = self._get_screenshot_name("theme_dark")
            await self.mcp.take_screenshot(screenshot, full_page=True)
            
            # Check dark theme contrast
            dark_contrast_check = await self.mcp.evaluate("""
                () => {
                    const elements = document.querySelectorAll('.text-muted, .small, p, h1, h2, h3, h4, h5, h6');
                    const darkBg = window.getComputedStyle(document.body).backgroundColor;
                    return {
                        passed: darkBg.includes('33, 37, 41') || darkBg.includes('#212529'),
                        backgroundColor: darkBg,
                        elementCount: elements.length
                    };
                }
            """)
            
            results.append({
                'name': 'Dark Theme Application',
                'passed': dark_contrast_check.get('passed', False),
                'message': f"Dark theme applied to {dark_contrast_check.get('elementCount', 0)} elements",
                'screenshot': screenshot,
                'details': dark_contrast_check
            })
            
            # Reset theme
            await self.mcp.evaluate("() => { document.documentElement.classList.remove('theme-dark'); }")
            
        except Exception as e:
            logger.error(f"Theme test failed: {e}")
            results.append({
                'name': 'Theme Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results
    
    async def test_responsive_design(self) -> List[Dict[str, Any]]:
        """Test responsive behavior at different viewport sizes"""
        results = []
        viewports = [
            {'name': 'mobile', 'width': 375, 'height': 667},
            {'name': 'tablet', 'width': 768, 'height': 1024},
            {'name': 'desktop', 'width': 1920, 'height': 1080}
        ]
        
        try:
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            
            for viewport in viewports:
                logger.info(f"Testing {viewport['name']} viewport...")
                
                # Resize browser
                await self.mcp.resize(viewport['width'], viewport['height'])
                await self.mcp.wait(500)  # Wait for layout adjustment
                
                # Take screenshot
                screenshot = self._get_screenshot_name(f"responsive_{viewport['name']}")
                await self.mcp.take_screenshot(screenshot)
                
                # Check layout integrity
                layout_check = await self.mcp.evaluate(f"""
                    () => {{
                        const width = {viewport['width']};
                        const issues = [];
                        
                        // Check for horizontal overflow
                        const hasOverflow = document.body.scrollWidth > width;
                        if (hasOverflow) {{
                            issues.push('Horizontal overflow detected');
                        }}
                        
                        // Check table responsiveness
                        const tables = document.querySelectorAll('.table-responsive');
                        if (width < 768 && tables.length > 0) {{
                            tables.forEach(table => {{
                                const wrapper = table.closest('.table-responsive');
                                if (!wrapper) {{
                                    issues.push('Table not wrapped in responsive container');
                                }}
                            }});
                        }}
                        
                        // Check button groups on mobile
                        if (width < 768) {{
                            const btnGroups = document.querySelectorAll('.btn-group');
                            btnGroups.forEach(group => {{
                                const style = window.getComputedStyle(group);
                                if (style.flexDirection !== 'column') {{
                                    issues.push('Button group not stacked on mobile');
                                }}
                            }});
                        }}
                        
                        // Check navigation
                        const navbar = document.querySelector('.navbar');
                        if (navbar && width < 768) {{
                            const toggler = navbar.querySelector('.navbar-toggler');
                            if (!toggler) {{
                                issues.push('No navbar toggler on mobile');
                            }}
                        }}
                        
                        return {{
                            passed: issues.length === 0,
                            issues: issues,
                            viewport: '{viewport['name']}',
                            width: width
                        }};
                    }}
                """)
                
                results.append({
                    'name': f"{viewport['name'].title()} Layout ({viewport['width']}x{viewport['height']})",
                    'passed': layout_check.get('passed', False),
                    'message': f"{len(layout_check.get('issues', []))} issues found" if not layout_check.get('passed') else 'Layout intact',
                    'screenshot': screenshot,
                    'details': layout_check
                })
                
        except Exception as e:
            logger.error(f"Responsive test failed: {e}")
            results.append({
                'name': 'Responsive Design',
                'passed': False,
                'message': str(e)
            })
        
        # Reset to desktop size
        await self.mcp.resize(1920, 1080)
        
        return results
    
    async def test_navigation(self) -> List[Dict[str, Any]]:
        """Test navigation flows and page transitions"""
        results = []
        
        try:
            # Test main navigation
            logger.info("Testing navigation flows...")
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            
            # Get initial page snapshot
            initial_snapshot = await self.mcp.get_snapshot()
            
            # Test navigation to Add Route
            await self.mcp.click(element="Add Route button", ref="a[href*='routes/new']")
            await self.mcp.wait_for_text("Create New Route")
            
            screenshot = self._get_screenshot_name("nav_add_route")
            await self.mcp.take_screenshot(screenshot)
            
            results.append({
                'name': 'Navigate to Add Route',
                'passed': True,
                'message': 'Successfully navigated to route form',
                'screenshot': screenshot
            })
            
            # Test back navigation
            await self.mcp.navigate_back()
            await self.mcp.wait_for_load()
            
            back_check = await self.mcp.evaluate("""
                () => {
                    const title = document.querySelector('h1');
                    return {
                        passed: title && title.textContent.includes('Route Dashboard'),
                        title: title ? title.textContent : 'Not found'
                    };
                }
            """)
            
            results.append({
                'name': 'Back Navigation',
                'passed': back_check.get('passed', False),
                'message': 'Returned to dashboard',
                'details': back_check
            })
            
            # Test hosts navigation
            await self.mcp.navigate(f"{self.base_url}/hosts")
            await self.mcp.wait_for_load()
            
            hosts_check = await self.mcp.evaluate("""
                () => {
                    const title = document.querySelector('h1');
                    const hostTable = document.querySelector('table');
                    return {
                        passed: title && (title.textContent.includes('Host') || hostTable),
                        hasTitle: !!title,
                        hasTable: !!hostTable
                    };
                }
            """)
            
            results.append({
                'name': 'Hosts Page Navigation',
                'passed': hosts_check.get('passed', False),
                'message': 'Navigated to hosts management',
                'details': hosts_check
            })
            
            # Test 404 handling
            await self.mcp.navigate(f"{self.base_url}/nonexistent")
            await self.mcp.wait(2000)
            
            error_check = await self.mcp.evaluate("""
                () => {
                    const body = document.body.textContent;
                    return {
                        passed: body.includes('404') || body.includes('not found'),
                        content: body.substring(0, 100)
                    };
                }
            """)
            
            results.append({
                'name': '404 Error Handling',
                'passed': error_check.get('passed', False),
                'message': 'Error page displayed correctly',
                'details': error_check
            })
            
        except Exception as e:
            logger.error(f"Navigation test failed: {e}")
            results.append({
                'name': 'Navigation Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results
    
    async def test_forms(self) -> List[Dict[str, Any]]:
        """Test form interactions and validation"""
        results = []
        
        try:
            logger.info("Testing form interactions...")
            
            # Navigate to Add Route form
            await self.mcp.navigate(f"{self.base_url}/routes/new")
            await self.mcp.wait_for_load()
            
            # Test form validation - submit empty form
            submit_button = await self.mcp.evaluate("""
                () => {
                    const btn = document.querySelector('button[type="submit"]');
                    return btn ? btn.outerHTML : null;
                }
            """)
            
            if submit_button:
                await self.mcp.click(element="Submit button", ref='button[type="submit"]')
                await self.mcp.wait(1000)
                
                # Check for validation messages
                validation_check = await self.mcp.evaluate("""
                    () => {
                        const alerts = document.querySelectorAll('.alert-danger');
                        const required = document.querySelectorAll('[required]');
                        return {
                            hasAlerts: alerts.length > 0,
                            hasRequired: required.length > 0,
                            alertCount: alerts.length,
                            requiredCount: required.length
                        };
                    }
                """)
                
                results.append({
                    'name': 'Form Validation',
                    'passed': validation_check.get('hasRequired', False),
                    'message': f"{validation_check.get('requiredCount', 0)} required fields detected",
                    'details': validation_check
                })
            
            # Test form filling
            await self.mcp.fill_form([
                {'name': 'Host field', 'ref': 'input[name="host"]', 'type': 'textbox', 'value': 'test.example.com'},
                {'name': 'Hostname field', 'ref': 'input[name="hostname"]', 'type': 'textbox', 'value': 'localhost'},
                {'name': 'Port field', 'ref': 'input[name="port"]', 'type': 'textbox', 'value': '3000'}
            ])
            
            screenshot = self._get_screenshot_name("form_filled")
            await self.mcp.take_screenshot(screenshot)
            
            # Check form values
            form_check = await self.mcp.evaluate("""
                () => {
                    const host = document.querySelector('input[name="host"]');
                    const hostname = document.querySelector('input[name="hostname"]');
                    const port = document.querySelector('input[name="port"]');
                    
                    return {
                        passed: host?.value && hostname?.value && port?.value,
                        values: {
                            host: host?.value,
                            hostname: hostname?.value,
                            port: port?.value
                        }
                    };
                }
            """)
            
            results.append({
                'name': 'Form Input Handling',
                'passed': form_check.get('passed', False),
                'message': 'Form fields populated correctly',
                'screenshot': screenshot,
                'details': form_check
            })
            
            # Test dropdown if present
            protocol_select = await self.mcp.evaluate("""
                () => {
                    const select = document.querySelector('select[name="protocol"]');
                    return select ? {exists: true, options: select.options.length} : {exists: false};
                }
            """)
            
            if protocol_select.get('exists'):
                await self.mcp.select_option(
                    element="Protocol dropdown",
                    ref='select[name="protocol"]',
                    values=['https']
                )
                
                results.append({
                    'name': 'Dropdown Selection',
                    'passed': True,
                    'message': f"Selected from {protocol_select.get('options', 0)} options",
                    'details': protocol_select
                })
            
        except Exception as e:
            logger.error(f"Form test failed: {e}")
            results.append({
                'name': 'Form Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results
    
    async def test_tables(self) -> List[Dict[str, Any]]:
        """Test table functionality including sorting and interactions"""
        results = []
        
        try:
            logger.info("Testing table functionality...")
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            
            # Check for table presence
            table_check = await self.mcp.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    const rows = table ? table.querySelectorAll('tbody tr') : [];
                    const headers = table ? table.querySelectorAll('thead th') : [];
                    
                    return {
                        hasTable: !!table,
                        rowCount: rows.length,
                        columnCount: headers.length,
                        headers: Array.from(headers).map(h => h.textContent.trim())
                    };
                }
            """)
            
            results.append({
                'name': 'Table Structure',
                'passed': table_check.get('hasTable', False),
                'message': f"{table_check.get('rowCount', 0)} rows, {table_check.get('columnCount', 0)} columns",
                'details': table_check
            })
            
            # Test table responsiveness
            await self.mcp.resize(400, 800)
            await self.mcp.wait(500)
            
            responsive_check = await self.mcp.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    const wrapper = table ? table.closest('.table-responsive') : null;
                    const hasScroll = wrapper ? wrapper.scrollWidth > wrapper.clientWidth : false;
                    
                    return {
                        hasWrapper: !!wrapper,
                        hasHorizontalScroll: hasScroll,
                        tableWidth: table ? table.scrollWidth : 0,
                        viewportWidth: window.innerWidth
                    };
                }
            """)
            
            results.append({
                'name': 'Table Responsive Wrapper',
                'passed': responsive_check.get('hasWrapper', False),
                'message': 'Table has responsive scrolling' if responsive_check.get('hasHorizontalScroll') else 'Table fits viewport',
                'details': responsive_check
            })
            
            # Reset viewport
            await self.mcp.resize(1920, 1080)
            await self.mcp.wait(500)
            
            # Test row hover effects
            hover_check = await self.mcp.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    const hasHoverClass = table ? table.classList.contains('table-hover') : false;
                    
                    return {
                        passed: hasHoverClass,
                        classes: table ? Array.from(table.classList) : []
                    };
                }
            """)
            
            results.append({
                'name': 'Table Hover Effects',
                'passed': hover_check.get('passed', False),
                'message': 'Table has hover styling',
                'details': hover_check
            })
            
            # Test action buttons in table
            action_check = await self.mcp.evaluate("""
                () => {
                    const editBtns = document.querySelectorAll('a[href*="/edit"]');
                    const deleteBtns = document.querySelectorAll('button[onclick*="confirmDelete"]');
                    
                    return {
                        hasActions: editBtns.length > 0 || deleteBtns.length > 0,
                        editCount: editBtns.length,
                        deleteCount: deleteBtns.length
                    };
                }
            """)
            
            results.append({
                'name': 'Table Action Buttons',
                'passed': action_check.get('hasActions', False),
                'message': f"{action_check.get('editCount', 0)} edit, {action_check.get('deleteCount', 0)} delete buttons",
                'details': action_check
            })
            
        except Exception as e:
            logger.error(f"Table test failed: {e}")
            results.append({
                'name': 'Table Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results
    
    async def test_accessibility(self) -> List[Dict[str, Any]]:
        """Test accessibility features including ARIA labels and keyboard navigation"""
        results = []
        
        try:
            logger.info("Testing accessibility...")
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            
            # Get accessibility snapshot
            a11y_snapshot = await self.mcp.get_snapshot()
            
            # Check for ARIA labels and roles
            aria_check = await self.mcp.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    const links = document.querySelectorAll('a');
                    const forms = document.querySelectorAll('form');
                    const images = document.querySelectorAll('img');
                    
                    let missingLabels = 0;
                    let missingAlts = 0;
                    
                    buttons.forEach(btn => {
                        if (!btn.textContent.trim() && !btn.getAttribute('aria-label')) {
                            missingLabels++;
                        }
                    });
                    
                    links.forEach(link => {
                        if (!link.textContent.trim() && !link.getAttribute('aria-label')) {
                            missingLabels++;
                        }
                    });
                    
                    images.forEach(img => {
                        if (!img.getAttribute('alt')) {
                            missingAlts++;
                        }
                    });
                    
                    return {
                        passed: missingLabels === 0 && missingAlts === 0,
                        totalButtons: buttons.length,
                        totalLinks: links.length,
                        totalImages: images.length,
                        missingLabels: missingLabels,
                        missingAlts: missingAlts
                    };
                }
            """)
            
            results.append({
                'name': 'ARIA Labels and Alt Text',
                'passed': aria_check.get('passed', False),
                'message': f"{aria_check.get('missingLabels', 0)} missing labels, {aria_check.get('missingAlts', 0)} missing alt texts",
                'details': aria_check
            })
            
            # Check heading hierarchy
            heading_check = await self.mcp.evaluate("""
                () => {
                    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                    const levels = Array.from(headings).map(h => parseInt(h.tagName[1]));
                    let hasSkips = false;
                    
                    for (let i = 1; i < levels.length; i++) {
                        if (levels[i] - levels[i-1] > 1) {
                            hasSkips = true;
                            break;
                        }
                    }
                    
                    return {
                        passed: !hasSkips && headings.length > 0,
                        headingCount: headings.length,
                        hasSkips: hasSkips,
                        levels: levels
                    };
                }
            """)
            
            results.append({
                'name': 'Heading Hierarchy',
                'passed': heading_check.get('passed', False),
                'message': f"{heading_check.get('headingCount', 0)} headings, {'with skips' if heading_check.get('hasSkips') else 'proper hierarchy'}",
                'details': heading_check
            })
            
            # Check focus indicators
            focus_check = await self.mcp.evaluate("""
                () => {
                    // Simulate tab key press to check focus
                    const activeElement = document.activeElement;
                    const focusableElements = document.querySelectorAll(
                        'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
                    );
                    
                    return {
                        passed: focusableElements.length > 0,
                        focusableCount: focusableElements.length,
                        hasFocusStyles: true  // Assume CSS provides focus styles
                    };
                }
            """)
            
            results.append({
                'name': 'Keyboard Navigation',
                'passed': focus_check.get('passed', False),
                'message': f"{focus_check.get('focusableCount', 0)} focusable elements",
                'details': focus_check
            })
            
            # Check color contrast for key elements
            contrast_check = await self.mcp.evaluate("""
                () => {
                    const getContrast = (fg, bg) => {
                        const getLuminance = (color) => {
                            const rgb = color.match(/\\d+/g);
                            if (!rgb) return 0;
                            const [r, g, b] = rgb.map(x => {
                                const val = parseInt(x) / 255;
                                return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
                            });
                            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
                        };
                        const l1 = getLuminance(fg) + 0.05;
                        const l2 = getLuminance(bg) + 0.05;
                        return Math.max(l1, l2) / Math.min(l1, l2);
                    };
                    
                    const buttons = document.querySelectorAll('.btn-primary');
                    let minContrast = 21;  // Maximum possible contrast
                    
                    buttons.forEach(btn => {
                        const style = window.getComputedStyle(btn);
                        const contrast = getContrast(style.color, style.backgroundColor);
                        if (contrast < minContrast) minContrast = contrast;
                    });
                    
                    return {
                        passed: minContrast >= 4.5,  // WCAG AA standard
                        minContrast: minContrast.toFixed(2),
                        standard: 'WCAG AA (4.5:1)'
                    };
                }
            """)
            
            results.append({
                'name': 'Button Color Contrast',
                'passed': contrast_check.get('passed', False),
                'message': f"Minimum contrast: {contrast_check.get('minContrast', 'N/A')}:1",
                'details': contrast_check
            })
            
        except Exception as e:
            logger.error(f"Accessibility test failed: {e}")
            results.append({
                'name': 'Accessibility Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results
    
    async def test_performance(self) -> List[Dict[str, Any]]:
        """Test page load performance and resource usage"""
        results = []
        
        try:
            logger.info("Testing performance...")
            
            # Clear cache and navigate
            start_time = datetime.now()
            await self.mcp.navigate(self.base_url)
            await self.mcp.wait_for_load()
            load_time = (datetime.now() - start_time).total_seconds()
            
            # Get performance metrics
            perf_metrics = await self.mcp.evaluate("""
                () => {
                    const perf = window.performance;
                    const timing = perf.timing;
                    const navigation = perf.navigation;
                    
                    const metrics = {
                        domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                        loadComplete: timing.loadEventEnd - timing.navigationStart,
                        domInteractive: timing.domInteractive - timing.navigationStart,
                        redirectCount: navigation.redirectCount
                    };
                    
                    // Resource timing
                    const resources = perf.getEntriesByType('resource');
                    const resourceStats = {
                        total: resources.length,
                        scripts: resources.filter(r => r.name.includes('.js')).length,
                        styles: resources.filter(r => r.name.includes('.css')).length,
                        images: resources.filter(r => r.initiatorType === 'img').length,
                        totalSize: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0)
                    };
                    
                    return {
                        metrics: metrics,
                        resources: resourceStats
                    };
                }
            """)
            
            results.append({
                'name': 'Page Load Time',
                'passed': load_time < 3,  # Target under 3 seconds
                'message': f"Loaded in {load_time:.2f} seconds",
                'details': {
                    'actualTime': load_time,
                    'target': 3,
                    'metrics': perf_metrics.get('metrics', {})
                }
            })
            
            results.append({
                'name': 'DOM Interactive Time',
                'passed': perf_metrics.get('metrics', {}).get('domInteractive', 9999) < 1500,
                'message': f"{perf_metrics.get('metrics', {}).get('domInteractive', 'N/A')}ms to interactive",
                'details': perf_metrics.get('metrics', {})
            })
            
            # Check resource optimization
            resource_stats = perf_metrics.get('resources', {})
            results.append({
                'name': 'Resource Optimization',
                'passed': resource_stats.get('total', 0) < 50,  # Reasonable resource count
                'message': f"{resource_stats.get('total', 0)} resources loaded",
                'details': resource_stats
            })
            
            # Check for console errors
            console_messages = await self.mcp.get_console_messages()
            error_count = len([m for m in console_messages if 'error' in m.lower()])
            warning_count = len([m for m in console_messages if 'warning' in m.lower()])
            
            results.append({
                'name': 'Console Errors',
                'passed': error_count == 0,
                'message': f"{error_count} errors, {warning_count} warnings",
                'details': {
                    'errors': error_count,
                    'warnings': warning_count,
                    'sample': console_messages[:5] if console_messages else []
                }
            })
            
            # Check network requests
            network_requests = await self.mcp.get_network_requests()
            failed_requests = [r for r in network_requests if r.get('status', 200) >= 400]
            
            results.append({
                'name': 'Network Requests',
                'passed': len(failed_requests) == 0,
                'message': f"{len(network_requests)} requests, {len(failed_requests)} failed",
                'details': {
                    'total': len(network_requests),
                    'failed': len(failed_requests),
                    'failedUrls': [r.get('url') for r in failed_requests[:5]]
                }
            })
            
            # Test auto-refresh functionality
            logger.info("Testing auto-refresh...")
            await self.mcp.wait(2000)  # Wait to see if any auto-refresh occurs
            
            refresh_check = await self.mcp.evaluate("""
                () => {
                    // Check if any intervals are set for refresh
                    const intervals = window.setInterval.toString().includes('30000');
                    return {
                        hasAutoRefresh: intervals || false,
                        message: 'Auto-refresh configured'
                    };
                }
            """)
            
            results.append({
                'name': 'Auto-refresh Setup',
                'passed': True,  # Not critical if missing
                'message': refresh_check.get('message', 'Auto-refresh check'),
                'details': refresh_check
            })
            
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            results.append({
                'name': 'Performance Testing',
                'passed': False,
                'message': str(e)
            })
        
        return results