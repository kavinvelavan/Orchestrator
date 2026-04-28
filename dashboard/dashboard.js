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
        // This would be implemented with AWS SDK or API Gateway endpoint
        // For now, return mock data
        return this.getMockErrorData(date);
    }

    getMockErrorData(date) {
        return [
            {
                application_name: "payment-service",
                alert_timestamp: `${date}T10:30:00Z`,
                dependent_services: ["auth-service", "database-service", "notification-service"],
                failed_services: [
                    {
                        service_name: "database-service",
                        error_code: "DB_CONNECTION_TIMEOUT",
                        error_message: "Failed to connect to database within timeout period",
                        timestamp: `${date}T10:29:45Z`
                    }
                ],
                service_hierarchy: [
                    { service_name: "auth-service", status: "HEALTHY", error_count: 0 },
                    { service_name: "database-service", status: "FAILED", error_count: 3 },
                    { service_name: "notification-service", status: "HEALTHY", error_count: 0 }
                ],
                processed_at: `${date}T10:30:15Z`
            },
            {
                application_name: "user-service",
                alert_timestamp: `${date}T09:15:00Z`,
                dependent_services: ["auth-service", "profile-service"],
                failed_services: [
                    {
                        service_name: "auth-service",
                        error_code: "AUTH_TOKEN_EXPIRED",
                        error_message: "Authentication token has expired",
                        timestamp: `${date}T09:14:30Z`
                    }
                ],
                service_hierarchy: [
                    { service_name: "auth-service", status: "FAILED", error_count: 5 },
                    { service_name: "profile-service", status: "HEALTHY", error_count: 0 }
                ],
                processed_at: `${date}T09:15:10Z`
            },
            {
                application_name: "order-service",
                alert_timestamp: `${date}T08:45:00Z`,
                dependent_services: ["inventory-service", "payment-service", "shipping-service"],
                failed_services: [],
                service_hierarchy: [
                    { service_name: "inventory-service", status: "HEALTHY", error_count: 0 },
                    { service_name: "payment-service", status: "HEALTHY", error_count: 0 },
                    { service_name: "shipping-service", status: "HEALTHY", error_count: 0 }
                ],
                processed_at: `${date}T08:45:05Z`
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
        const allServices = this.filteredData.flatMap(item => item.service_hierarchy);
        const failedServices = allServices.filter(service => service.status === 'FAILED').length;
        const healthyServices = allServices.filter(service => service.status === 'HEALTHY').length;
        const errorRate = totalServices > 0 ? ((failedServices / totalServices) * 100).toFixed(1) : 0;

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

        timelineContainer.innerHTML = this.filteredData.map(item => `
            <div class="flex space-x-4 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer service-card ${item.failed_services.length > 0 ? 'error-row' : 'healthy-row'}"
                 onclick="dashboard.showErrorDetails('${item.application_name}', '${item.alert_timestamp}')">
                <div class="flex-shrink-0">
                    <div class="timeline-dot ${item.failed_services.length > 0 ? 'error-dot' : ''}"></div>
                </div>
                <div class="flex-1">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="font-semibold text-gray-900">${item.application_name}</h3>
                            <p class="text-sm text-gray-500">${this.formatTimestamp(item.alert_timestamp)}</p>
                        </div>
                        <div class="text-right">
                            ${item.failed_services.length > 0 ? 
                                `<span class="error-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                    <i class="fas fa-exclamation-triangle mr-1"></i>
                                    ${item.failed_services.length} Failed
                                </span>` :
                                `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    <i class="fas fa-check-circle mr-1"></i>
                                    Healthy
                                </span>`
                            }
                        </div>
                    </div>
                    ${item.failed_services.length > 0 ? `
                        <div class="mt-2 text-sm text-red-600">
                            <i class="fas fa-times-circle mr-1"></i>
                            ${item.failed_services.map(fs => fs.service_name).join(', ')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
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

        flowContainer.innerHTML = this.filteredData.map(item => `
            <div class="border rounded-lg p-4">
                <div class="flex justify-between items-center mb-3">
                    <h3 class="font-semibold text-gray-900">${item.application_name}</h3>
                    <span class="text-sm text-gray-500">${this.formatTimestamp(item.alert_timestamp)}</span>
                </div>
                <div class="space-y-2">
                    ${item.service_hierarchy.map(service => `
                        <div class="flex items-center justify-between p-2 rounded ${service.status === 'FAILED' ? 'bg-red-50' : 'bg-green-50'}">
                            <div class="flex items-center space-x-2">
                                <i class="fas ${service.status === 'FAILED' ? 'fa-times-circle text-red-600' : 'fa-check-circle text-green-600'}"></i>
                                <span class="font-medium">${service.service_name}</span>
                            </div>
                            <div class="flex items-center space-x-4">
                                <span class="text-sm ${service.status === 'FAILED' ? 'text-red-600' : 'text-green-600'}">${service.status}</span>
                                ${service.error_count > 0 ? 
                                    `<span class="text-sm text-red-600">${service.error_count} errors</span>` : 
                                    `<span class="text-sm text-gray-500">0 errors</span>`
                                }
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }

    updateServiceFilter() {
        const serviceFilter = document.getElementById('serviceFilter');
        const allServices = new Set();
        
        this.errorData.forEach(item => {
            item.service_hierarchy.forEach(service => {
                allServices.add(service.service_name);
            });
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
            const itemDate = item.alert_timestamp.split('T')[0];
            if (dateFilter && itemDate !== dateFilter) return false;

            // Service filter
            if (serviceFilter) {
                const hasService = item.service_hierarchy.some(service => 
                    service.service_name === serviceFilter
                );
                if (!hasService) return false;
            }

            // Status filter
            if (statusFilter) {
                const hasStatus = item.service_hierarchy.some(service => 
                    service.status === statusFilter
                );
                if (!hasStatus) return false;
            }

            return true;
        });

        this.updateDashboard();
    }

    showErrorDetails(applicationName, timestamp) {
        const errorItem = this.filteredData.find(item => 
            item.application_name === applicationName && item.alert_timestamp === timestamp
        );

        if (!errorItem) return;

        const modalContent = document.getElementById('errorModalContent');
        modalContent.innerHTML = `
            <div class="space-y-4">
                <div class="border-b pb-4">
                    <h4 class="font-semibold text-gray-900 mb-2">Application: ${errorItem.application_name}</h4>
                    <p class="text-sm text-gray-600">Alert Time: ${this.formatTimestamp(errorItem.alert_timestamp)}</p>
                    <p class="text-sm text-gray-600">Processed: ${this.formatTimestamp(errorItem.processed_at)}</p>
                </div>
                
                <div>
                    <h5 class="font-medium text-gray-900 mb-2">Service Flow</h5>
                    <div class="space-y-2">
                        ${errorItem.service_hierarchy.map(service => `
                            <div class="flex items-center justify-between p-2 rounded ${service.status === 'FAILED' ? 'bg-red-50' : 'bg-green-50'}">
                                <div class="flex items-center space-x-2">
                                    <i class="fas ${service.status === 'FAILED' ? 'fa-times-circle text-red-600' : 'fa-check-circle text-green-600'}"></i>
                                    <span class="font-medium">${service.service_name}</span>
                                </div>
                                <span class="text-sm ${service.status === 'FAILED' ? 'text-red-600' : 'text-green-600'}">${service.status}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                ${errorItem.failed_services.length > 0 ? `
                    <div>
                        <h5 class="font-medium text-gray-900 mb-2">Error Details</h5>
                        <div class="space-y-3">
                            ${errorItem.failed_services.map(failedService => `
                                <div class="border rounded-lg p-3 bg-red-50">
                                    <div class="flex justify-between items-start mb-2">
                                        <h6 class="font-medium text-red-900">${failedService.service_name}</h6>
                                        <span class="text-xs text-red-600">${failedService.error_code}</span>
                                    </div>
                                    <p class="text-sm text-red-800 mb-1">${failedService.error_message}</p>
                                    <p class="text-xs text-red-600">${this.formatTimestamp(failedService.timestamp)}</p>
                                </div>
                            `).join('')}
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
