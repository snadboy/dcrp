#!/usr/bin/env python3
"""
DCRP UI Test Agent - Automated UI/UX testing using Playwright MCP
Tests visual design, responsiveness, accessibility, and interactions
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from flask import Flask, jsonify, render_template_string, send_file
import httpx

from mcp_client import MCPClient
from test_scenarios import UITestScenarios
from report_generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ui-test-agent")

# Configuration
WEB_UI_URL = os.environ.get('WEB_UI_URL', 'http://web-ui:5000')
API_SERVER_URL = os.environ.get('API_SERVER_URL', 'http://api-server:8000')
TEST_RESULTS_DIR = Path('/app/test-results')
SCREENSHOTS_DIR = TEST_RESULTS_DIR / 'screenshots'
REPORTS_DIR = TEST_RESULTS_DIR / 'reports'

# Create directories
TEST_RESULTS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

class UITestAgent:
    """Main UI Test Agent orchestrator"""
    
    def __init__(self):
        self.mcp_client = MCPClient()
        self.test_scenarios = UITestScenarios(self.mcp_client, WEB_UI_URL)
        self.report_generator = ReportGenerator(REPORTS_DIR, SCREENSHOTS_DIR)
        self.current_test_run = None
        self.test_history = []
        
    async def run_full_test_suite(self) -> Dict[str, Any]:
        """Run complete UI/UX test suite"""
        logger.info("Starting full UI test suite")
        
        test_run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.current_test_run = {
            'id': test_run_id,
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'tests': [],
            'summary': {}
        }
        
        try:
            # Initialize browser
            await self.mcp_client.initialize_browser()
            
            # Run test scenarios
            test_results = []
            
            # 1. Theme Testing
            logger.info("Running theme tests...")
            theme_results = await self.test_scenarios.test_themes()
            test_results.append({
                'category': 'Theme & Colors',
                'tests': theme_results,
                'passed': all(t['passed'] for t in theme_results)
            })
            
            # 2. Responsive Design Testing
            logger.info("Running responsive design tests...")
            responsive_results = await self.test_scenarios.test_responsive_design()
            test_results.append({
                'category': 'Responsive Design',
                'tests': responsive_results,
                'passed': all(t['passed'] for t in responsive_results)
            })
            
            # 3. Navigation Testing
            logger.info("Running navigation tests...")
            nav_results = await self.test_scenarios.test_navigation()
            test_results.append({
                'category': 'Navigation',
                'tests': nav_results,
                'passed': all(t['passed'] for t in nav_results)
            })
            
            # 4. Form Interaction Testing
            logger.info("Running form interaction tests...")
            form_results = await self.test_scenarios.test_forms()
            test_results.append({
                'category': 'Form Interactions',
                'tests': form_results,
                'passed': all(t['passed'] for t in form_results)
            })
            
            # 5. Table Functionality Testing
            logger.info("Running table functionality tests...")
            table_results = await self.test_scenarios.test_tables()
            test_results.append({
                'category': 'Table Functionality',
                'tests': table_results,
                'passed': all(t['passed'] for t in table_results)
            })
            
            # 6. Accessibility Testing
            logger.info("Running accessibility tests...")
            a11y_results = await self.test_scenarios.test_accessibility()
            test_results.append({
                'category': 'Accessibility',
                'tests': a11y_results,
                'passed': all(t['passed'] for t in a11y_results)
            })
            
            # 7. Performance Testing
            logger.info("Running performance tests...")
            perf_results = await self.test_scenarios.test_performance()
            test_results.append({
                'category': 'Performance',
                'tests': perf_results,
                'passed': all(t['passed'] for t in perf_results)
            })
            
            # Generate summary
            total_tests = sum(len(cat['tests']) for cat in test_results)
            passed_tests = sum(len([t for t in cat['tests'] if t['passed']]) for cat in test_results)
            
            self.current_test_run['tests'] = test_results
            self.current_test_run['summary'] = {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': total_tests - passed_tests,
                'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
            }
            self.current_test_run['status'] = 'completed'
            self.current_test_run['end_time'] = datetime.now().isoformat()
            
            # Generate report
            report_path = await self.report_generator.generate_html_report(self.current_test_run)
            self.current_test_run['report_path'] = str(report_path)
            
            # Save to history
            self.test_history.append(self.current_test_run)
            self._save_test_history()
            
            logger.info(f"Test suite completed. Pass rate: {self.current_test_run['summary']['pass_rate']:.1f}%")
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            self.current_test_run['status'] = 'failed'
            self.current_test_run['error'] = str(e)
            self.current_test_run['end_time'] = datetime.now().isoformat()
        
        finally:
            # Clean up browser
            await self.mcp_client.close_browser()
        
        return self.current_test_run
    
    async def run_specific_test(self, test_name: str) -> Dict[str, Any]:
        """Run a specific test scenario"""
        logger.info(f"Running specific test: {test_name}")
        
        test_run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        test_result = {
            'id': test_run_id,
            'test_name': test_name,
            'start_time': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            await self.mcp_client.initialize_browser()
            
            # Map test names to methods
            test_map = {
                'themes': self.test_scenarios.test_themes,
                'responsive': self.test_scenarios.test_responsive_design,
                'navigation': self.test_scenarios.test_navigation,
                'forms': self.test_scenarios.test_forms,
                'tables': self.test_scenarios.test_tables,
                'accessibility': self.test_scenarios.test_accessibility,
                'performance': self.test_scenarios.test_performance
            }
            
            if test_name in test_map:
                results = await test_map[test_name]()
                test_result['results'] = results
                test_result['passed'] = all(t['passed'] for t in results)
                test_result['status'] = 'completed'
            else:
                test_result['status'] = 'failed'
                test_result['error'] = f"Unknown test: {test_name}"
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            test_result['status'] = 'failed'
            test_result['error'] = str(e)
        
        finally:
            await self.mcp_client.close_browser()
            test_result['end_time'] = datetime.now().isoformat()
        
        return test_result
    
    def _save_test_history(self):
        """Save test history to file"""
        history_file = TEST_RESULTS_DIR / 'test_history.json'
        with open(history_file, 'w') as f:
            json.dump(self.test_history, f, indent=2)
    
    def _load_test_history(self):
        """Load test history from file"""
        history_file = TEST_RESULTS_DIR / 'test_history.json'
        if history_file.exists():
            with open(history_file, 'r') as f:
                self.test_history = json.load(f)

# Initialize agent
agent = UITestAgent()
agent._load_test_history()

# Flask routes
@app.route('/api/ui-tests/run', methods=['POST'])
async def run_tests():
    """Trigger full test suite"""
    result = await agent.run_full_test_suite()
    return jsonify(result)

@app.route('/api/ui-tests/run/<test_name>', methods=['POST'])
async def run_specific_test(test_name):
    """Run specific test"""
    result = await agent.run_specific_test(test_name)
    return jsonify(result)

@app.route('/api/ui-tests/results')
def get_results():
    """Get latest test results"""
    if agent.current_test_run:
        return jsonify(agent.current_test_run)
    elif agent.test_history:
        return jsonify(agent.test_history[-1])
    else:
        return jsonify({'message': 'No test results available'}), 404

@app.route('/api/ui-tests/history')
def get_history():
    """Get test history"""
    return jsonify(agent.test_history)

@app.route('/api/ui-tests/screenshots/<filename>')
def get_screenshot(filename):
    """Get screenshot file"""
    filepath = SCREENSHOTS_DIR / filename
    if filepath.exists():
        return send_file(filepath, mimetype='image/png')
    return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/ui-tests')
def test_dashboard():
    """Web dashboard for test results"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>UI Test Results - DCRP</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            .test-passed { color: #198754; }
            .test-failed { color: #dc3545; }
            .screenshot-thumb { max-width: 200px; cursor: pointer; }
            .screenshot-modal { max-width: 90vw; }
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <h1><i class="bi bi-palette"></i> UI Test Results</h1>
            <div class="row mt-4">
                <div class="col-md-12">
                    <button class="btn btn-primary" onclick="runTests()">
                        <i class="bi bi-play-circle"></i> Run Full Test Suite
                    </button>
                    <button class="btn btn-secondary" onclick="refreshResults()">
                        <i class="bi bi-arrow-clockwise"></i> Refresh
                    </button>
                </div>
            </div>
            <div id="results" class="mt-4"></div>
        </div>
        
        <script>
            async function runTests() {
                document.getElementById('results').innerHTML = '<div class="spinner-border" role="status"></div>';
                const response = await fetch('/api/ui-tests/run', { method: 'POST' });
                const data = await response.json();
                displayResults(data);
            }
            
            async function refreshResults() {
                const response = await fetch('/api/ui-tests/results');
                const data = await response.json();
                displayResults(data);
            }
            
            function displayResults(data) {
                if (!data.tests) {
                    document.getElementById('results').innerHTML = '<p>No test results available</p>';
                    return;
                }
                
                let html = `
                    <div class="card">
                        <div class="card-header">
                            <h5>Test Run: ${data.id}</h5>
                            <p class="mb-0">Status: ${data.status} | 
                               Pass Rate: ${data.summary?.pass_rate?.toFixed(1)}% |
                               Total: ${data.summary?.total_tests} tests</p>
                        </div>
                        <div class="card-body">
                `;
                
                data.tests.forEach(category => {
                    const icon = category.passed ? 'check-circle' : 'x-circle';
                    const color = category.passed ? 'test-passed' : 'test-failed';
                    html += `
                        <h6 class="${color}">
                            <i class="bi bi-${icon}"></i> ${category.category}
                        </h6>
                        <ul class="list-group mb-3">
                    `;
                    
                    category.tests.forEach(test => {
                        const testIcon = test.passed ? 'check' : 'x';
                        const testColor = test.passed ? 'success' : 'danger';
                        html += `
                            <li class="list-group-item">
                                <i class="bi bi-${testIcon} text-${testColor}"></i>
                                ${test.name}
                                ${test.message ? `<small class="text-muted"> - ${test.message}</small>` : ''}
                                ${test.screenshot ? `<a href="/api/ui-tests/screenshots/${test.screenshot}" target="_blank" class="ms-2"><i class="bi bi-image"></i></a>` : ''}
                            </li>
                        `;
                    });
                    
                    html += '</ul>';
                });
                
                html += `
                        </div>
                    </div>
                `;
                
                document.getElementById('results').innerHTML = html;
            }
            
            // Load results on page load
            refreshResults();
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'ui-test-agent'})

if __name__ == '__main__':
    logger.info("Starting UI Test Agent")
    app.run(host='0.0.0.0', port=8080, debug=False)