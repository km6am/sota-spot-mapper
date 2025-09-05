#!/bin/bash

# SOTA Propagation Map Installation Script
# This script automates the deployment of the SOTA Propagation Map system
# on Debian 12 with Nginx, PHP, and MySQL/MariaDB

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WEB_ROOT="/var/www/sota-matcher"
APP_ROOT="/opt/sota-matcher"
SERVICE_NAME="sota-rbn-matcher"
DB_NAME="sota_matcher"
DB_USER="sota_user"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Function to check if running on Debian/Ubuntu
check_os() {
    if [[ ! -f /etc/debian_version ]]; then
        print_error "This script is designed for Debian/Ubuntu systems"
        exit 1
    fi
    
    print_success "Detected Debian/Ubuntu system"
}

# Function to update system packages
update_system() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    print_success "System packages updated"
}

# Function to install required packages
install_packages() {
    print_status "Installing required packages..."
    
    # Essential packages
    apt install -y curl wget git unzip software-properties-common
    
    # Web server and PHP
    apt install -y nginx php8.2-fpm php8.2-mysql php8.2-json php8.2-mbstring php8.2-xml php8.2-curl
    
    # Database
    apt install -y mariadb-server mariadb-client
    
    # Python and dependencies
    apt install -y python3 python3-pip python3-venv python3-requests python3-pymysql
    
    print_success "Required packages installed"
}

# Function to configure PHP
configure_php() {
    print_status "Configuring PHP..."
    
    # Update PHP configuration
    sed -i 's/upload_max_filesize = 2M/upload_max_filesize = 64M/' /etc/php/8.2/fpm/php.ini
    sed -i 's/post_max_size = 8M/post_max_size = 64M/' /etc/php/8.2/fpm/php.ini
    sed -i 's/max_execution_time = 30/max_execution_time = 300/' /etc/php/8.2/fpm/php.ini
    sed -i 's/memory_limit = 128M/memory_limit = 256M/' /etc/php/8.2/fpm/php.ini
    
    # Restart PHP-FPM
    systemctl restart php8.2-fpm
    
    print_success "PHP configured"
}

# Function to configure database
configure_database() {
    print_status "Configuring database..."
    
    # Start and enable MariaDB
    systemctl start mariadb
    systemctl enable mariadb
    
    # Generate random password for database user
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Create database and user
    mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME};"
    mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';"
    mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
    mysql -e "FLUSH PRIVILEGES;"
    
    # Create database tables
    mysql ${DB_NAME} << EOF
-- SOTA spots table
CREATE TABLE IF NOT EXISTS sota_spots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    callsign VARCHAR(20) NOT NULL,
    summit VARCHAR(50) NOT NULL,
    frequency DECIMAL(10,3) NOT NULL,
    mode VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp),
    INDEX idx_callsign (callsign),
    INDEX idx_summit (summit),
    INDEX idx_frequency (frequency)
);

-- RBN spots table
CREATE TABLE IF NOT EXISTS rbn_spots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    spotter VARCHAR(20) NOT NULL,
    spotted VARCHAR(20) NOT NULL,
    frequency DECIMAL(10,3) NOT NULL,
    snr INT NOT NULL,
    mode VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp),
    INDEX idx_spotter (spotter),
    INDEX idx_spotted (spotted),
    INDEX idx_frequency (frequency)
);

-- Matches table
CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sota_id INT NOT NULL,
    rbn_id INT NOT NULL,
    match_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enhanced BOOLEAN DEFAULT FALSE,
    sota_lat DECIMAL(10, 8),
    sota_lon DECIMAL(11, 8),
    rbn_lat DECIMAL(10, 8),
    rbn_lon DECIMAL(11, 8),
    distance_km DECIMAL(8, 2),
    FOREIGN KEY (sota_id) REFERENCES sota_spots(id),
    FOREIGN KEY (rbn_id) REFERENCES rbn_spots(id),
    UNIQUE KEY unique_match (sota_id, rbn_id),
    INDEX idx_match_timestamp (match_timestamp),
    INDEX idx_enhanced (enhanced)
);

-- SOTA locations cache
CREATE TABLE IF NOT EXISTS sota_locations (
    summit VARCHAR(50) PRIMARY KEY,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_coordinates (latitude, longitude)
);

-- RBN locations cache
CREATE TABLE IF NOT EXISTS rbn_locations (
    callsign VARCHAR(20) PRIMARY KEY,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_coordinates (latitude, longitude)
);
EOF
    
    print_success "Database configured"
    print_warning "Database password: ${DB_PASSWORD}"
    print_warning "Please save this password securely!"
}

# Function to configure Nginx
configure_nginx() {
    print_status "Configuring Nginx..."
    
    # Create Nginx configuration
    cat > /etc/nginx/sites-available/sota-matcher << EOF
server {
    listen 80;
    server_name _;
    
    root ${WEB_ROOT};
    index index.html index.php;
    
    location / {
        try_files \$uri \$uri/ =404;
    }
    
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.2-fpm.sock;
    }
    
    location ~ /\.ht {
        deny all;
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Enable gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
EOF
    
    # Enable the site
    ln -sf /etc/nginx/sites-available/sota-matcher /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    nginx -t
    
    # Restart Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    print_success "Nginx configured"
}

# Function to create application directories
create_directories() {
    print_status "Creating application directories..."
    
    # Create web directory
    mkdir -p ${WEB_ROOT}
    
    # Create application directory
    mkdir -p ${APP_ROOT}
    
    # Set permissions
    chown -R www-data:www-data ${WEB_ROOT}
    chown -R root:root ${APP_ROOT}
    
    print_success "Application directories created"
}

# Function to deploy application files
deploy_files() {
    print_status "Deploying application files..."
    
    # Copy web files
    cp web/* ${WEB_ROOT}/
    
    # Copy daemon files
    cp daemon/* ${APP_ROOT}/
    
    # Make Python scripts executable
    chmod +x ${APP_ROOT}/*.py
    
    # Set permissions
    chown -R www-data:www-data ${WEB_ROOT}
    chown -R root:root ${APP_ROOT}
    
    print_success "Application files deployed"
}

# Function to create configuration file
create_config() {
    print_status "Creating configuration file..."
    
    # Get server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # Create configuration file
    cat > ${APP_ROOT}/config.json << EOF
{
    "database": {
        "host": "localhost",
        "port": 3306,
        "user": "${DB_USER}",
        "password": "${DB_PASSWORD}",
        "database": "${DB_NAME}"
    },
    "qrz": {
        "username": "your_qrz_username",
        "password": "your_qrz_password"
    },
    "sota": {
        "api_url": "https://api2.sota.org.uk/api",
        "cache_duration": 86400
    },
    "matching": {
        "interval_minutes": 1,
        "enhancement_batch_size": 200,
        "max_distance_km": 20000
    },
    "logging": {
        "level": "INFO",
        "file": "/var/log/sota-matcher.log"
    }
}
EOF
    
    # Set secure permissions
    chmod 600 ${APP_ROOT}/config.json
    chown root:root ${APP_ROOT}/config.json
    
    print_success "Configuration file created"
    print_warning "Please update QRZ.com credentials in ${APP_ROOT}/config.json"
}

# Function to install systemd service
install_service() {
    print_status "Installing systemd service..."
    
    # Copy service file
    cp ${APP_ROOT}/sota-rbn-matcher.service /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable ${SERVICE_NAME}
    
    print_success "Systemd service installed"
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Start and enable services
    systemctl start ${SERVICE_NAME}
    systemctl start nginx
    systemctl start php8.2-fpm
    systemctl start mariadb
    
    # Enable services
    systemctl enable nginx
    systemctl enable php8.2-fpm
    systemctl enable mariadb
    
    print_success "Services started"
}

# Function to check service status
check_services() {
    print_status "Checking service status..."
    
    # Check service status
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        print_success "SOTA matcher service is running"
    else
        print_error "SOTA matcher service is not running"
        systemctl status ${SERVICE_NAME}
    fi
    
    if systemctl is-active --quiet nginx; then
        print_success "Nginx is running"
    else
        print_error "Nginx is not running"
    fi
    
    if systemctl is-active --quiet php8.2-fpm; then
        print_success "PHP-FPM is running"
    else
        print_error "PHP-FPM is not running"
    fi
    
    if systemctl is-active --quiet mariadb; then
        print_success "MariaDB is running"
    else
        print_error "MariaDB is not running"
    fi
}

# Function to display installation summary
show_summary() {
    print_success "Installation completed successfully!"
    echo
    echo "=========================================="
    echo "SOTA Propagation Map Installation Summary"
    echo "=========================================="
    echo
    echo "Web Interface: http://${SERVER_IP}/"
    echo "API Endpoint:  http://${SERVER_IP}/api_propagation_paths.php"
    echo
    echo "Configuration: ${APP_ROOT}/config.json"
    echo "Web Root:      ${WEB_ROOT}"
    echo "Log File:      /var/log/sota-matcher.log"
    echo
    echo "Database:"
    echo "  Name:        ${DB_NAME}"
    echo "  User:        ${DB_USER}"
    echo "  Password:    ${DB_PASSWORD}"
    echo
    echo "Service Commands:"
    echo "  Status:      systemctl status ${SERVICE_NAME}"
    echo "  Start:       systemctl start ${SERVICE_NAME}"
    echo "  Stop:        systemctl stop ${SERVICE_NAME}"
    echo "  Restart:     systemctl restart ${SERVICE_NAME}"
    echo "  Logs:        journalctl -u ${SERVICE_NAME} -f"
    echo
    echo "Next Steps:"
    echo "1. Update QRZ.com credentials in ${APP_ROOT}/config.json"
    echo "2. Test the web interface at http://${SERVER_IP}/"
    echo "3. Check service logs: journalctl -u ${SERVICE_NAME} -f"
    echo "4. Configure firewall if needed"
    echo
    print_warning "Please save the database password securely!"
    echo
}

# Function to handle errors
handle_error() {
    print_error "Installation failed at step: $1"
    print_error "Check the logs above for details"
    exit 1
}

# Main installation function
main() {
    echo "=========================================="
    echo "SOTA Propagation Map Installation Script"
    echo "=========================================="
    echo
    
    # Check prerequisites
    check_root
    check_os
    
    # Installation steps
    update_system || handle_error "System update"
    install_packages || handle_error "Package installation"
    configure_php || handle_error "PHP configuration"
    configure_database || handle_error "Database configuration"
    configure_nginx || handle_error "Nginx configuration"
    create_directories || handle_error "Directory creation"
    deploy_files || handle_error "File deployment"
    create_config || handle_error "Configuration creation"
    install_service || handle_error "Service installation"
    start_services || handle_error "Service startup"
    check_services || handle_error "Service verification"
    
    # Show summary
    show_summary
}

# Run main function
main "$@"
