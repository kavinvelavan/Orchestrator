// Error Monitoring Dashboard JavaScript

class ErrorDashboard {
    constructor() {
        this.errorData = [];
        this.filteredData = [];
        this.s3Bucket = this.getS3BucketFromUrl();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setDefaultDate();
        this.loadErrorData();
    }

    getS3BucketFromUrl() {
        // Extract bucket name from current URL or use default
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('bucket') || 'error-monitoring-bucket';
    }

    setupEventListeners() {
        document.getElementById('dateFilter').addEventListener('change', () => this.applyFilters());
        document.getElementById('serviceFilter').addEventListener('change', () => this.applyFilters());
        document.getElementById('statusFilter').addEventListener('change', () => this.applyFilters());
    }

    setDefaultDate() {
        document.getElementById('dateFilter').value = new Date().toISOString().split('T')[0];
    }

    async loadErrorData() {
        try {
            this.showLoading();
            const date = document.getElementById('dateFilter').value;
            
            // In production, this would call an API endpoint that reads from S3
            // For demo purposes, we'll use mock data
            this.errorData = await this.fetchErrorDataFromS3(date);
            this.filteredData = [...this.errorData];
            
            this.updateDashboard();
            this.hideLoading();
        } catch (error) {
            console.error('Error loading data:', error);
            this.showError('Failed to load error data');
            this.hideLoading();
        }
    }

    async fetchErrorDataFromS3(date) {
        // Try to load real RCA data from the test file first
        try {
            const response = await fetch('./latest_rca_result.json');
            if (response.ok) {
                const realData = await response.json();
                console.log('Loaded real RCA data from test file');
                return [realData];
            }
        } catch (error) {
            console.log('Could not load real RCA data, falling back to mock data');
        }
        
        // Fallback to mock data
        return this.getMockErrorData(date);
    }

    getMockErrorData(date) {
        return [
            {
                alert_info: {
                    service_name: "payment-service",
                    error_code: "500",
                    endpoint: "/api/payments/endpoint1",
                    alert_timestamp: `${date}T10:30:00Z`
                },
                knowledge_analysis: {
                    dependencies: {
                        upstream_services: ["order-service", "user-service"],
                        downstream_services: ["notification-service", "transaction-service"],
                        related_services: ["auth-service", "account-service"]
                    },
                    past_incidents: [
                        {
                            incident_id: "INC-001",
                            service_name: "payment-service",
                            error_type: "Database connection timeout",
                            root_cause: "Database connection pool exhaustion",
                            resolution: "Increased connection pool size and added connection retry logic",
                            timestamp: `${date}T09:30:00Z`,
                            impact: "Service unavailable for 15 minutes"
                        }
                    ],
                    analysis_timestamp: `${date}T10:40:00Z`
                },
                log_analysis: {
                    primary_service_logs: [
                        {
                            log_id: "LOG-PAYMENT-SERVICE-001",
                            service: "payment-service",
                            timestamp: `${date}T10:15:00Z`,
                            status_code: 500,
                            error: "Database connection timeout",
                            url: "/api/payments/endpoint1",
                            level: "ERROR",
                            message: "payment-service encountered Database connection timeout",
                            duration_ms: 100,
                            request_id: "REQ-0000-000"
                        }
                    ],
                    related_service_logs: [],
                    total_error_logs: 5,
                    total_related_logs: 20,
                    fetch_timestamp: `${date}T10:40:00Z`
                },
                rca_summary: {
                    error_start_time: `${date}T10:15:00Z`,
                    error_code: 500,
                    impacted_dependencies: ["notification-service", "transaction-service"],
                    endpoints: ["/api/payments/endpoint1"],
                    cause_of_error: "Database connection pool exhaustion similar to past incident INC-001",
                    action_taken: [
                        "Increase database connection pool size",
                        "Implement connection retry logic",
                        "Check database server health"
                    ],
                    severity: "High",
                    error_pattern: "Intermittent service failures detected",
                    business_impact: "Service degradation affecting user experience"
                },
                ongoing_errors: [
                    {
                        service: "payment-service",
                        timestamp: `${date}T10:38:00Z`,
                        error: "Database connection timeout",
                        status_code: 500,
                        url: "/api/payments/endpoint1",
                        severity: "High"
                    }
                ],
                processed_at: `${date}T10:45:00Z`,
                dashboard_data: {
                    failed_services: ["notification-service", "transaction-service"],
                    impacted_endpoints: ["/api/payments/endpoint1"],
                    severity: "High",
                    business_impact: "Service degradation affecting user experience"
                }
            },
            {
                alert_info: {
                    service_name: "user-service",
                    error_code: "401",
                    endpoint: "/api/users/profile",
                    alert_timestamp: `${date}T09:15:00Z`
                },
                knowledge_analysis: {
                    dependencies: {
                        upstream_services: ["auth-service"],
                        downstream_services: ["profile-service"],
                        related_services: ["notification-service"]
                    },
                    past_incidents: [
                        {
                            incident_id: "INC-002",
                            service_name: "user-service",
                            error_type: "Authentication token expiration",
                            root_cause: "Token refresh mechanism failure",
                            resolution: "Implemented automatic token refresh with retry logic",
                            timestamp: `${date}T08:30:00Z`,
                            impact: "Users unable to access profile information"
                        }
                    ],
                    analysis_timestamp: `${date}T09:25:00Z`
                },
                log_analysis: {
                    primary_service_logs: [
                        {
                            log_id: "LOG-USER-SERVICE-001",
                            service: "user-service",
                            timestamp: `${date}T09:14:30Z`,
                            status_code: 401,
                            error: "Authentication token expired",
                            url: "/api/users/profile",
                            level: "ERROR",
                            message: "user-service encountered authentication token expiration",
                            duration_ms: 50,
                            request_id: "REQ-0001-000"
                        }
                    ],
                    related_service_logs: [],
                    total_error_logs: 3,
                    total_related_logs: 15,
                    fetch_timestamp: `${date}T09:25:00Z`
                },
                rca_summary: {
                    error_start_time: `${date}T09:14:30Z`,
                    error_code: 401,
                    impacted_dependencies: ["profile-service"],
                    endpoints: ["/api/users/profile"],
                    cause_of_error: "Token refresh mechanism failure similar to past incident INC-002",
                    action_taken: [
                        "Implement automatic token refresh",
                        "Add retry logic for failed authentication",
                        "Monitor token expiration patterns"
                    ],
                    severity: "Medium",
                    error_pattern: "Periodic authentication failures",
                    business_impact: "User profile access temporarily unavailable"
                },
                ongoing_errors: [
                    {
                        service: "user-service",
                        timestamp: `${date}T09:20:00Z`,
                        error: "Authentication token expired",
                        status_code: 401,
                        url: "/api/users/profile",
                        severity: "Medium"
                    }
                ],
                processed_at: `${date}T09:30:00Z`,
                dashboard_data: {
                    failed_services: ["profile-service"],
                    impacted_endpoints: ["/api/users/profile"],
                    severity: "Medium",
                    business_impact: "User profile access temporarily unavailable"
                }
            },
            {
                alert_info: {
                    service_name: "order-service",
                    error_code: "200",
                    endpoint: "/api/orders/create",
                    alert_timestamp: `${date}T08:45:00Z`
                },
                knowledge_analysis: {
                    dependencies: {
                        upstream_services: ["user-service", "inventory-service"],
                        downstream_services: ["payment-service", "shipping-service"],
                        related_services: ["notification-service"]
                    },
                    past_incidents: [],
                    analysis_timestamp: `${date}T08:55:00Z`
                },
                log_analysis: {
                    primary_service_logs: [],
                    related_service_logs: [],
                    total_error_logs: 0,
                    total_related_logs: 10,
                    fetch_timestamp: `${date}T08:55:00Z`
                },
                rca_summary: {
                    error_start_time: null,
                    error_code: null,
                    impacted_dependencies: [],
                    endpoints: [],
                    cause_of_error: null,
                    action_taken: [],
                    severity: "Low",
                    error_pattern: null,
                    business_impact: "No impact detected"
                },
                ongoing_errors: [],
                processed_at: `${date}T09:00:00Z`,
                dashboard_data: {
                    failed_services: [],
                    impacted_endpoints: [],
                    severity: "Low",
                    business_impact: "No impact detected"
                }
            }
        ];
    }

    updateDashboard() {
        this.updateSummaryCards();
        this.updateErrorTimeline();
        this.updateServiceFlow();
        this.updateServiceFilter();
        this.updateLastRefreshTime();
    }

    updateSummaryCards() {
        const totalAlerts = this.filteredData.length;
        const failedServices = this.filteredData.filter(item => 
            item.dashboard_data.failed_services && item.dashboard_data.failed_services.length > 0
        ).length;
        const healthyServices = totalAlerts - failedServices;
        const errorRate = totalAlerts > 0 ? ((failedServices / totalAlerts) * 100).toFixed(1) : 0;

        document.getElementById('totalAlerts').textContent = totalAlerts;
        document.getElementById('failedServices').textContent = failedServices;
        document.getElementById('healthyServices').textContent = healthyServices;
        document.getElementById('errorRate').textContent = `${errorRate}%`;
    }

    updateErrorTimeline() {
        const timelineContainer = document.getElementById('errorTimeline');
        
        if (this.filteredData.length === 0) {
            timelineContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    <i class="fas fa-info-circle text-4xl mb-4"></i>
                    <p>No error data found for the selected filters</p>
                </div>
            `;
            return;
        }

        timelineContainer.innerHTML = this.filteredData.map(item => {
            const hasErrors = item.dashboard_data.failed_services && item.dashboard_data.failed_services.length > 0;
            const severity = item.dashboard_data.severity || 'Low';
            const severityColor = severity === 'High' ? 'red' : severity === 'Medium' ? 'yellow' : 'green';
            
            return `
            <div class="flex space-x-4 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer service-card ${hasErrors ? 'error-row' : 'healthy-row'}"
                 onclick="dashboard.showErrorDetails('${item.alert_info.service_name}', '${item.alert_info.alert_timestamp}')">
                <div class="flex-shrink-0">
                    <div class="timeline-dot ${hasErrors ? 'error-dot' : ''}"></div>
                </div>
                <div class="flex-1">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="font-semibold text-gray-900">${item.alert_info.service_name}</h3>
                            <p class="text-sm text-gray-500">${this.formatTimestamp(item.alert_info.alert_timestamp)}</p>
                            <p class="text-xs text-gray-400">Error Code: ${item.alert_info.error_code || 'N/A'}</p>
                        </div>
                        <div class="text-right">
                            ${hasErrors ? 
                                `<span class="error-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-${severityColor}-100 text-${severityColor}-800">
                                    <i class="fas fa-exclamation-triangle mr-1"></i>
                                    ${severity} Severity
                                </span>` :
                                `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    <i class="fas fa-check-circle mr-1"></i>
                                    Healthy
                                </span>`
                            }
                        </div>
                    </div>
                    ${hasErrors ? `
                        <div class="mt-2 space-y-1">
                            <div class="text-sm text-red-600">
                                <i class="fas fa-times-circle mr-1"></i>
                                Failed Services: ${item.dashboard_data.failed_services.join(', ')}
                            </div>
                            <div class="text-sm text-orange-600">
                                <i class="fas fa-map-marker-alt mr-1"></i>
                                Impacted Endpoints: ${item.dashboard_data.impacted_endpoints.join(', ')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        }).join('');
    }

    updateServiceFlow() {
        const flowContainer = document.getElementById('serviceFlow');
        
        if (this.filteredData.length === 0) {
            flowContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    <i class="fas fa-info-circle text-4xl mb-4"></i>
                    <p>No service flow data found for the selected filters</p>
                </div>
            `;
            return;
        }

        flowContainer.innerHTML = this.filteredData.map(item => {
            const deps = item.knowledge_analysis.dependencies;
            const hasErrors = item.dashboard_data.failed_services && item.dashboard_data.failed_services.length > 0;
            
            return `
            <div class="border rounded-lg p-4">
                <div class="flex justify-between items-center mb-3">
                    <h3 class="font-semibold text-gray-900">${item.alert_info.service_name}</h3>
                    <span class="text-sm text-gray-500">${this.formatTimestamp(item.alert_info.alert_timestamp)}</span>
                </div>
                
                <!-- Dependencies -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div class="bg-blue-50 p-3 rounded">
                        <h4 class="font-medium text-blue-900 mb-2">
                            <i class="fas fa-arrow-up mr-1"></i>Upstream Services
                        </h4>
                        <div class="space-y-1">
                            ${(deps.upstream_services || []).map(service => `
                                <div class="text-sm text-blue-700">• ${service}</div>
                            `).join('')}
                            ${!deps.upstream_services || deps.upstream_services.length === 0 ? 
                                '<div class="text-sm text-gray-500">None</div>' : ''}
                        </div>
                    </div>
                    
                    <div class="bg-green-50 p-3 rounded">
                        <h4 class="font-medium text-green-900 mb-2">
                            <i class="fas fa-bullseye mr-1"></i>Service
                        </h4>
                        <div class="text-sm font-medium text-green-700">${item.alert_info.service_name}</div>
                        <div class="text-xs text-gray-600">Endpoint: ${item.alert_info.endpoint || 'N/A'}</div>
                    </div>
                    
                    <div class="bg-orange-50 p-3 rounded">
                        <h4 class="font-medium text-orange-900 mb-2">
                            <i class="fas fa-arrow-down mr-1"></i>Downstream Services
                        </h4>
                        <div class="space-y-1">
                            ${(deps.downstream_services || []).map(service => `
                                <div class="text-sm text-orange-700">• ${service}</div>
                            `).join('')}
                            ${!deps.downstream_services || deps.downstream_services.length === 0 ? 
                                '<div class="text-sm text-gray-500">None</div>' : ''}
                        </div>
                    </div>
                </div>
                
                <!-- RCA Summary -->
                ${hasErrors ? `
                    <div class="bg-red-50 border border-red-200 rounded p-3">
                        <h4 class="font-medium text-red-900 mb-2">
                            <i class="fas fa-exclamation-triangle mr-1"></i>RCA Analysis
                        </h4>
                        <div class="space-y-2">
                            <div class="text-sm">
                                <strong>Root Cause:</strong> ${item.rca_summary.cause_of_error || 'Unknown'}
                            </div>
                            <div class="text-sm">
                                <strong>Recommended Actions:</strong>
                                <ul class="list-disc list-inside mt-1">
                                    ${(item.rca_summary.action_taken || []).map(action => `
                                        <li>${action}</li>
                                    `).join('')}
                                </ul>
                            </div>
                            <div class="text-sm">
                                <strong>Business Impact:</strong> ${item.dashboard_data.business_impact}
                            </div>
                        </div>
                    </div>
                ` : `
                    <div class="bg-green-50 border border-green-200 rounded p-3">
                        <h4 class="font-medium text-green-900 mb-2">
                            <i class="fas fa-check-circle mr-1"></i>Service Status
                        </h4>
                        <div class="text-sm text-green-700">No issues detected - Service is operating normally</div>
                    </div>
                `}
            </div>
        `;
        }).join('');
    }

    updateServiceFilter() {
        const serviceFilter = document.getElementById('serviceFilter');
        const allServices = new Set();
        
        this.errorData.forEach(item => {
            allServices.add(item.alert_info.service_name);
            // Also add dependency services
            const deps = item.knowledge_analysis.dependencies;
            if (deps.upstream_services) {
                deps.upstream_services.forEach(service => allServices.add(service));
            }
            if (deps.downstream_services) {
                deps.downstream_services.forEach(service => allServices.add(service));
            }
            if (deps.related_services) {
                deps.related_services.forEach(service => allServices.add(service));
            }
        });

        const currentValue = serviceFilter.value;
        serviceFilter.innerHTML = '<option value="">All Services</option>';
        
        Array.from(allServices).sort().forEach(service => {
            serviceFilter.innerHTML += `<option value="${service}">${service}</option>`;
        });
        
        serviceFilter.value = currentValue;
    }

    applyFilters() {
        const dateFilter = document.getElementById('dateFilter').value;
        const serviceFilter = document.getElementById('serviceFilter').value;
        const statusFilter = document.getElementById('statusFilter').value;

        this.filteredData = this.errorData.filter(item => {
            // Date filter
            const itemDate = item.alert_info.alert_timestamp.split('T')[0];
            if (dateFilter && itemDate !== dateFilter) return false;

            // Service filter
            if (serviceFilter) {
                const hasService = item.alert_info.service_name === serviceFilter ||
                    item.knowledge_analysis.dependencies.upstream_services?.includes(serviceFilter) ||
                    item.knowledge_analysis.dependencies.downstream_services?.includes(serviceFilter) ||
                    item.knowledge_analysis.dependencies.related_services?.includes(serviceFilter);
                if (!hasService) return false;
            }

            // Status filter (based on severity)
            if (statusFilter) {
                const severity = item.dashboard_data.severity;
                const hasStatus = (statusFilter === 'FAILED' && severity !== 'Low') ||
                                (statusFilter === 'HEALTHY' && severity === 'Low');
                if (!hasStatus) return false;
            }

            return true;
        });

        this.updateDashboard();
    }

    showErrorDetails(applicationName, timestamp) {
        const errorItem = this.filteredData.find(item => 
            item.alert_info.service_name === applicationName && item.alert_info.alert_timestamp === timestamp
        );

        if (!errorItem) return;

        const modalContent = document.getElementById('errorModalContent');
        modalContent.innerHTML = `
            <div class="space-y-4">
                <div class="border-b pb-4">
                    <h4 class="font-semibold text-gray-900 mb-2">Service: ${errorItem.alert_info.service_name}</h4>
                    <p class="text-sm text-gray-600">Alert Time: ${this.formatTimestamp(errorItem.alert_info.alert_timestamp)}</p>
                    <p class="text-sm text-gray-600">Error Code: ${errorItem.alert_info.error_code || 'N/A'}</p>
                    <p class="text-sm text-gray-600">Endpoint: ${errorItem.alert_info.endpoint || 'N/A'}</p>
                    <p class="text-sm text-gray-600">Processed: ${this.formatTimestamp(errorItem.processed_at)}</p>
                </div>
                
                <div>
                    <h5 class="font-medium text-gray-900 mb-2">Dependencies</h5>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="bg-blue-50 p-3 rounded">
                            <h6 class="font-medium text-blue-900 mb-2">Upstream Services</h6>
                            ${(errorItem.knowledge_analysis.dependencies.upstream_services || []).map(service => `
                                <div class="text-sm text-blue-700">• ${service}</div>
                            `).join('')}
                            ${!errorItem.knowledge_analysis.dependencies.upstream_services || errorItem.knowledge_analysis.dependencies.upstream_services.length === 0 ? 
                                '<div class="text-sm text-gray-500">None</div>' : ''}
                        </div>
                        <div class="bg-green-50 p-3 rounded">
                            <h6 class="font-medium text-green-900 mb-2">Service</h6>
                            <div class="text-sm font-medium text-green-700">${errorItem.alert_info.service_name}</div>
                            <div class="text-xs text-gray-600">Endpoint: ${errorItem.alert_info.endpoint || 'N/A'}</div>
                        </div>
                        <div class="bg-orange-50 p-3 rounded">
                            <h6 class="font-medium text-orange-900 mb-2">Downstream Services</h6>
                            ${(errorItem.knowledge_analysis.dependencies.downstream_services || []).map(service => `
                                <div class="text-sm text-orange-700">• ${service}</div>
                            `).join('')}
                            ${!errorItem.knowledge_analysis.dependencies.downstream_services || errorItem.knowledge_analysis.dependencies.downstream_services.length === 0 ? 
                                '<div class="text-sm text-gray-500">None</div>' : ''}
                        </div>
                    </div>
                </div>
                
                ${errorItem.knowledge_analysis.past_incidents && errorItem.knowledge_analysis.past_incidents.length > 0 ? `
                    <div>
                        <h5 class="font-medium text-gray-900 mb-2">Past Incidents</h5>
                        <div class="space-y-3">
                            ${errorItem.knowledge_analysis.past_incidents.map(incident => `
                                <div class="border rounded-lg p-3 bg-yellow-50">
                                    <div class="flex justify-between items-start mb-2">
                                        <h6 class="font-medium text-yellow-900">${incident.incident_id}</h6>
                                        <span class="text-xs text-yellow-600">${this.formatTimestamp(incident.timestamp)}</span>
                                    </div>
                                    <p class="text-sm text-yellow-800 mb-1"><strong>Error Type:</strong> ${incident.error_type}</p>
                                    <p class="text-sm text-yellow-800 mb-1"><strong>Root Cause:</strong> ${incident.root_cause}</p>
                                    <p class="text-sm text-yellow-800 mb-1"><strong>Resolution:</strong> ${incident.resolution}</p>
                                    <p class="text-sm text-yellow-600"><strong>Impact:</strong> ${incident.impact}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${errorItem.rca_summary.cause_of_error ? `
                    <div>
                        <h5 class="font-medium text-gray-900 mb-2">RCA Analysis</h5>
                        <div class="border rounded-lg p-3 bg-red-50">
                            <p class="text-sm text-red-800 mb-2"><strong>Root Cause:</strong> ${errorItem.rca_summary.cause_of_error}</p>
                            <p class="text-sm text-red-800 mb-2"><strong>Error Pattern:</strong> ${errorItem.rca_summary.error_pattern || 'N/A'}</p>
                            <p class="text-sm text-red-800 mb-2"><strong>Business Impact:</strong> ${errorItem.dashboard_data.business_impact}</p>
                            <p class="text-sm text-red-800 mb-2"><strong>Recommended Actions:</strong></p>
                            <ul class="list-disc list-inside text-sm text-red-800">
                                ${(errorItem.rca_summary.action_taken || []).map(action => `
                                    <li>${action}</li>
                                `).join('')}
                            </ul>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        document.getElementById('errorModal').classList.remove('hidden');
    }

    closeErrorModal() {
        document.getElementById('errorModal').classList.add('hidden');
    }

    formatTimestamp(timestamp) {
        return new Date(timestamp).toLocaleString();
    }

    updateLastRefreshTime() {
        document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
    }

    showLoading() {
        // Add loading indicators
        document.getElementById('errorTimeline').innerHTML = `
            <div class="text-center text-gray-500 py-8">
                <i class="fas fa-spinner fa-spin text-4xl mb-4"></i>
                <p>Loading error data...</p>
            </div>
        `;
        
        document.getElementById('serviceFlow').innerHTML = `
            <div class="text-center text-gray-500 py-8">
                <i class="fas fa-spinner fa-spin text-4xl mb-4"></i>
                <p>Loading service flow data...</p>
            </div>
        `;
    }

    hideLoading() {
        // Loading indicators will be replaced by actual content
    }

    showError(message) {
        const errorHTML = `
            <div class="text-center text-red-500 py-8">
                <i class="fas fa-exclamation-triangle text-4xl mb-4"></i>
                <p>${message}</p>
            </div>
        `;
        
        document.getElementById('errorTimeline').innerHTML = errorHTML;
        document.getElementById('serviceFlow').innerHTML = errorHTML;
    }

    async refreshData() {
        await this.loadErrorData();
    }
}

// Global functions for onclick handlers
function refreshData() {
    dashboard.refreshData();
}

function applyFilters() {
    dashboard.applyFilters();
}

function closeErrorModal() {
    dashboard.closeErrorModal();
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new ErrorDashboard();
});

// Auto-refresh every 30 seconds
setInterval(() => {
    if (dashboard) {
        dashboard.refreshData();
    }
}, 30000);
