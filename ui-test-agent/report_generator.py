#!/usr/bin/env python3
"""
Report Generator - Creates HTML and JSON reports for UI test results
Generates comprehensive reports with screenshots, metrics, and visual data
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger("report-generator")

class ReportGenerator:
    """Generates HTML and JSON reports for UI test results"""
    
    def __init__(self, reports_dir: Path, screenshots_dir: Path):
        self.reports_dir = reports_dir
        self.screenshots_dir = screenshots_dir
        
    async def generate_html_report(self, test_run: Dict[str, Any]) -> Path:
        """Generate comprehensive HTML report"""
        try:
            logger.info(f"Generating HTML report for run: {test_run.get('id')}")
            
            # Generate report HTML
            html_content = self._create_html_report(test_run)
            
            # Save to file
            report_filename = f"test_report_{test_run.get('id', 'unknown')}.html"
            report_path = self.reports_dir / report_filename
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML report saved: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"HTML report generation failed: {e}")
            raise
    
    async def generate_json_report(self, test_run: Dict[str, Any]) -> Path:
        """Generate JSON report for API consumption"""
        try:
            logger.info(f"Generating JSON report for run: {test_run.get('id')}")
            
            # Create structured JSON report
            json_report = {
                'meta': {
                    'generated_at': datetime.now().isoformat(),
                    'test_run_id': test_run.get('id'),
                    'status': test_run.get('status'),
                    'duration': self._calculate_duration(test_run)
                },
                'summary': test_run.get('summary', {}),
                'test_results': test_run.get('tests', []),
                'screenshots': self._get_screenshot_list(test_run),
                'performance': self._extract_performance_data(test_run)
            }
            
            # Save to file
            report_filename = f"test_report_{test_run.get('id', 'unknown')}.json"
            report_path = self.reports_dir / report_filename
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(json_report, f, indent=2, default=str)
            
            logger.info(f"JSON report saved: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"JSON report generation failed: {e}")
            raise
    
    def _create_html_report(self, test_run: Dict[str, Any]) -> str:
        """Create HTML report content"""
        
        # Extract data
        test_id = test_run.get('id', 'unknown')
        status = test_run.get('status', 'unknown')
        summary = test_run.get('summary', {})
        tests = test_run.get('tests', [])
        start_time = test_run.get('start_time', '')
        end_time = test_run.get('end_time', '')
        duration = self._calculate_duration(test_run)
        
        # Status styling
        status_class = 'success' if status == 'completed' and summary.get('failed', 0) == 0 else 'danger'
        status_icon = 'check-circle' if status_class == 'success' else 'x-circle'
        
        # Generate test category sections
        test_sections = []
        for category in tests:
            category_tests = category.get('tests', [])
            category_passed = category.get('passed', False)
            
            category_icon = 'check-circle-fill text-success' if category_passed else 'x-circle-fill text-danger'
            
            test_items = []
            for test in category_tests:
                test_passed = test.get('passed', False)
                test_icon = 'check text-success' if test_passed else 'x text-danger'
                test_name = test.get('name', 'Unknown Test')
                test_message = test.get('message', '')
                test_screenshot = test.get('screenshot', '')
                
                screenshot_link = ''
                if test_screenshot:
                    screenshot_link = f'''
                        <a href="#" onclick="showScreenshot('/api/ui-tests/screenshots/{test_screenshot}', '{test_name}')" 
                           class="btn btn-sm btn-outline-primary ms-2" title="View Screenshot">
                            <i class="bi bi-image"></i>
                        </a>
                    '''
                
                details_section = ''
                if test.get('details'):
                    details_json = json.dumps(test['details'], indent=2)
                    details_section = f'''
                        <div class="collapse mt-2" id="details-{test_name.replace(' ', '-').lower()}">
                            <div class="card card-body">
                                <pre class="mb-0"><code>{details_json}</code></pre>
                            </div>
                        </div>
                    '''
                
                test_items.append(f'''
                    <li class="list-group-item">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <i class="bi bi-{test_icon} me-2"></i>
                                <strong>{test_name}</strong>
                                {f'<span class="text-muted ms-2">- {test_message}</span>' if test_message else ''}
                            </div>
                            <div>
                                {screenshot_link}
                                {f'<button class="btn btn-sm btn-outline-secondary ms-1" type="button" data-bs-toggle="collapse" data-bs-target="#details-{test_name.replace(" ", "-").lower()}" aria-expanded="false"><i class="bi bi-info-circle"></i></button>' if test.get('details') else ''}
                            </div>
                        </div>
                        {details_section}
                    </li>
                ''')
            
            test_sections.append(f'''
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="bi bi-{category_icon} me-2"></i>
                            {category.get('category', 'Unknown Category')}
                        </h5>
                    </div>
                    <div class="card-body p-0">
                        <ul class="list-group list-group-flush">
                            {''.join(test_items)}
                        </ul>
                    </div>
                </div>
            ''')
        
        # Performance chart data
        perf_data = self._extract_performance_data(test_run)
        perf_chart = self._create_performance_chart(perf_data)
        
        # Screenshot gallery
        screenshot_gallery = self._create_screenshot_gallery(test_run)
        
        # Generate full HTML
        html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI Test Report - {test_id}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .screenshot-thumb {{ 
            max-width: 150px; 
            cursor: pointer; 
            transition: transform 0.2s;
        }}
        .screenshot-thumb:hover {{ 
            transform: scale(1.05); 
        }}
        .test-summary-card {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .metric-card {{ 
            border-left: 4px solid #007bff;
        }}
        .metric-card.success {{ 
            border-left-color: #28a745;
        }}
        .metric-card.warning {{ 
            border-left-color: #ffc107;
        }}
        .metric-card.danger {{ 
            border-left-color: #dc3545;
        }}
        .code-block {{ 
            background: #f8f9fa; 
            border-radius: 4px; 
            max-height: 300px; 
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="container-fluid mt-4">
        <!-- Header -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="test-summary-card card text-white">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col-md-8">
                                <h1 class="card-title mb-2">
                                    <i class="bi bi-{status_icon} me-2"></i>
                                    UI Test Report
                                </h1>
                                <p class="card-text mb-2">
                                    <strong>Test Run:</strong> {test_id} | 
                                    <strong>Status:</strong> {status.title()} | 
                                    <strong>Duration:</strong> {duration}
                                </p>
                                <p class="card-text mb-0">
                                    <strong>Started:</strong> {start_time} | 
                                    <strong>Completed:</strong> {end_time or 'In Progress'}
                                </p>
                            </div>
                            <div class="col-md-4 text-end">
                                <div class="display-4 mb-2">{summary.get('pass_rate', 0):.1f}%</div>
                                <div>Pass Rate</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Metrics -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="metric-card card success">
                    <div class="card-body text-center">
                        <div class="display-6 text-success">{summary.get('passed', 0)}</div>
                        <div class="text-muted">Passed</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card card danger">
                    <div class="card-body text-center">
                        <div class="display-6 text-danger">{summary.get('failed', 0)}</div>
                        <div class="text-muted">Failed</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card card">
                    <div class="card-body text-center">
                        <div class="display-6 text-primary">{summary.get('total_tests', 0)}</div>
                        <div class="text-muted">Total Tests</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card card warning">
                    <div class="card-body text-center">
                        <div class="display-6 text-warning">{len(tests)}</div>
                        <div class="text-muted">Categories</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Performance Chart -->
        {perf_chart}
        
        <!-- Test Results -->
        <div class="row">
            <div class="col-md-8">
                <h2 class="mb-3"><i class="bi bi-list-check me-2"></i>Test Results</h2>
                {''.join(test_sections)}
            </div>
            
            <!-- Screenshot Gallery -->
            <div class="col-md-4">
                {screenshot_gallery}
            </div>
        </div>
        
        <!-- Export Options -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Export Results</h5>
                        <div class="btn-group" role="group">
                            <button type="button" class="btn btn-outline-primary" onclick="exportJson()">
                                <i class="bi bi-download me-1"></i>Export JSON
                            </button>
                            <button type="button" class="btn btn-outline-secondary" onclick="window.print()">
                                <i class="bi bi-printer me-1"></i>Print Report
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Screenshot Modal -->
    <div class="modal fade" id="screenshotModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="screenshotModalLabel">Screenshot</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center">
                    <img id="screenshotImage" src="" class="img-fluid" alt="Screenshot">
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function showScreenshot(url, title) {{
            document.getElementById('screenshotImage').src = url;
            document.getElementById('screenshotModalLabel').textContent = title;
            const modal = new bootstrap.Modal(document.getElementById('screenshotModal'));
            modal.show();
        }}
        
        function exportJson() {{
            const data = {json.dumps(test_run, indent=2, default=str)};
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'ui-test-results-{test_id}.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>
        '''
        
        return html_content
    
    def _create_performance_chart(self, perf_data: Dict[str, Any]) -> str:
        """Create performance chart section"""
        if not perf_data:
            return ""
        
        chart_data = perf_data.get('metrics', {})
        if not chart_data:
            return ""
        
        return f'''
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-speedometer2 me-2"></i>Performance Metrics</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="performanceChart" width="400" height="150"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            const ctx = document.getElementById('performanceChart').getContext('2d');
            const chart = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: ['Page Load', 'DOM Interactive', 'Resources', 'Network Requests'],
                    datasets: [{{
                        label: 'Time (ms)',
                        data: [
                            {chart_data.get('load_time', 0) * 1000},
                            {chart_data.get('dom_interactive', 0)},
                            {chart_data.get('resource_count', 0) * 10},
                            {chart_data.get('network_requests', 0) * 10}
                        ],
                        backgroundColor: [
                            'rgba(75, 192, 192, 0.8)',
                            'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)',
                            'rgba(153, 102, 255, 0.8)'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        </script>
        '''
    
    def _create_screenshot_gallery(self, test_run: Dict[str, Any]) -> str:
        """Create screenshot gallery section"""
        screenshots = self._get_screenshot_list(test_run)
        
        if not screenshots:
            return '''
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0"><i class="bi bi-images me-2"></i>Screenshots</h5>
                </div>
                <div class="card-body text-center text-muted">
                    <i class="bi bi-image display-1"></i>
                    <p class="mt-2">No screenshots available</p>
                </div>
            </div>
            '''
        
        thumbnail_html = []
        for screenshot in screenshots[:10]:  # Limit to 10 screenshots
            thumbnail_html.append(f'''
                <div class="mb-3">
                    <img src="/api/ui-tests/screenshots/{screenshot['filename']}" 
                         class="screenshot-thumb img-thumbnail" 
                         alt="{screenshot['description']}"
                         onclick="showScreenshot('/api/ui-tests/screenshots/{screenshot['filename']}', '{screenshot['description']}')">
                    <div class="small text-muted mt-1">{screenshot['description']}</div>
                </div>
            ''')
        
        return f'''
        <div class="card sticky-top">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-images me-2"></i>Screenshots</h5>
            </div>
            <div class="card-body" style="max-height: 600px; overflow-y: auto;">
                {''.join(thumbnail_html)}
                {f'<div class="text-muted small mt-2">+ {len(screenshots) - 10} more screenshots</div>' if len(screenshots) > 10 else ''}
            </div>
        </div>
        '''
    
    def _get_screenshot_list(self, test_run: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract screenshot information from test run"""
        screenshots = []
        
        for category in test_run.get('tests', []):
            for test in category.get('tests', []):
                if test.get('screenshot'):
                    screenshots.append({
                        'filename': test['screenshot'],
                        'description': f"{category.get('category', 'Unknown')} - {test.get('name', 'Unknown')}",
                        'category': category.get('category', 'Unknown'),
                        'test_name': test.get('name', 'Unknown')
                    })
        
        return screenshots
    
    def _extract_performance_data(self, test_run: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance metrics from test results"""
        perf_data = {}
        
        for category in test_run.get('tests', []):
            if category.get('category') == 'Performance':
                for test in category.get('tests', []):
                    details = test.get('details', {})
                    if details:
                        perf_data.update(details)
        
        return perf_data
    
    def _calculate_duration(self, test_run: Dict[str, Any]) -> str:
        """Calculate test run duration"""
        try:
            start = test_run.get('start_time', '')
            end = test_run.get('end_time', '')
            
            if start and end:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                duration = end_dt - start_dt
                
                total_seconds = int(duration.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                
                if minutes > 0:
                    return f"{minutes}m {seconds}s"
                else:
                    return f"{seconds}s"
            
            return "Unknown"
            
        except Exception as e:
            logger.error(f"Duration calculation failed: {e}")
            return "Error"