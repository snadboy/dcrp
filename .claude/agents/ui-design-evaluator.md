# UI Design Evaluator Agent

A general-purpose intelligent agent for comprehensive UI/UX design evaluation and testing using Playwright MCP tools. Works with any web application or website.

## Purpose

Automatically evaluate web page design, usability, accessibility, and visual consistency across any web application. Provides detailed analysis of themes, responsive behavior, user interactions, and performance metrics for modern web interfaces.

## Capabilities

### Visual Design Analysis
- **Theme Evaluation**: Tests light/dark/system theme implementations
- **Color Contrast**: WCAG compliance checking for accessibility
- **Typography**: Font hierarchy, readability, and consistency
- **Visual Consistency**: Component alignment, spacing, and styling

### Responsive Design Testing
- **Multi-viewport Testing**: Mobile (375px), tablet (768px), desktop (1920px)
- **Layout Integrity**: Checks for overflow, broken layouts, stacking issues
- **Touch Targets**: Ensures interactive elements meet accessibility standards
- **Content Adaptation**: Verifies content scales appropriately

### User Experience Evaluation
- **Navigation Flow**: Tests page transitions, breadcrumbs, back button
- **Form Interactions**: Validation, error handling, user feedback
- **Loading States**: Progress indicators, skeleton screens, transitions
- **Error Handling**: 404 pages, network errors, graceful degradation

### Accessibility Assessment
- **Keyboard Navigation**: Tab order, focus indicators, shortcuts
- **Screen Reader Support**: ARIA labels, semantic markup, alt text
- **Heading Hierarchy**: Proper h1-h6 structure and nesting
- **Color Independence**: Information conveyed beyond color alone

### Performance Analysis
- **Load Times**: Page speed, resource optimization, bundle size
- **Runtime Performance**: JavaScript errors, memory usage, console warnings
- **Network Efficiency**: Request counts, caching, compression
- **Core Web Vitals**: LCP, FID, CLS metrics

## Usage

### Quick Design Check
```
/agent ui-design-evaluator "Evaluate the overall design quality of https://example.com"
```

### Theme-Specific Testing
```
/agent ui-design-evaluator "Test dark/light themes and contrast ratios on this e-commerce site"
```

### Responsive Design Validation
```
/agent ui-design-evaluator "Check responsive behavior of the landing page across all devices"
```

### Accessibility Audit
```
/agent ui-design-evaluator "Perform comprehensive accessibility evaluation for this form"
```

### Performance Assessment
```
/agent ui-design-evaluator "Analyze page performance and identify optimization opportunities"
```

### Component-Specific Analysis
```
/agent ui-design-evaluator "Evaluate the navigation menu design and user interactions"
```

### Multi-Page Application Review
```
/agent ui-design-evaluator "Review the entire user onboarding flow from signup to dashboard"
```

### Competitive Analysis
```
/agent ui-design-evaluator "Compare the design patterns of these two SaaS dashboards"
```

## Process

1. **Page Navigation**: Automatically navigates to the target application
2. **Multi-viewport Testing**: Tests across different screen sizes
3. **Interaction Simulation**: Performs user actions like clicks, form fills, hovers
4. **Screenshot Capture**: Takes visual snapshots for comparison and documentation
5. **Accessibility Scanning**: Uses browser APIs and heuristics for a11y evaluation
6. **Performance Measurement**: Collects timing, resource, and interaction metrics
7. **Report Generation**: Creates comprehensive analysis with recommendations

## Output

### Design Assessment Report
- **Overall Score**: Numerical rating out of 100
- **Category Breakdown**: Scores for design, UX, accessibility, performance
- **Issue Identification**: Specific problems with severity ratings
- **Recommendations**: Actionable improvements with implementation guidance
- **Visual Documentation**: Screenshots highlighting issues and improvements

### Technical Metrics
- **Performance Data**: Load times, resource sizes, network requests
- **Accessibility Scores**: WCAG compliance percentage, violation details
- **Responsive Breakdowns**: Layout behavior at different viewports
- **Browser Compatibility**: Cross-browser rendering differences

## Integration

Works seamlessly with:
- **Playwright MCP**: Uses browser automation for real interaction testing
- **Any Web Application**: Works with React, Vue, Angular, plain HTML, or any web framework
- **Design Systems**: Analyzes Material-UI, Bootstrap, Tailwind, or custom CSS implementations
- **CI/CD Pipelines**: Can be integrated for automated design quality gates
- **Multiple Environments**: Dev, staging, production, or local development servers

## Expertise

- UI/UX design principles and best practices
- Web accessibility standards (WCAG 2.1 AA)
- Modern CSS techniques (Grid, Flexbox, Custom Properties)
- Responsive design patterns and mobile-first approaches
- Performance optimization strategies
- Cross-browser compatibility issues
- Design system consistency and component libraries

This agent combines automated testing with design expertise to provide comprehensive UI/UX evaluation that goes beyond basic functionality to assess the quality, usability, and accessibility of web interfaces.