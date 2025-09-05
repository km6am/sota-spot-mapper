# Deployment Guide

This guide covers deploying the SOTA Propagation Map to a Debian 12 server with Nginx.

## Prerequisites

- **Server**: Debian 12 (Bookworm) or Ubuntu 22.04+
- **Root Access**: Administrative privileges required
- **Network**: Internet connectivity for package installation
- **Domain/IP**: Server accessible via HTTP/HTTPS

## System Requirements

- **CPU**: 2+ cores recommended
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 10GB+ free space
- **Network**: Stable internet connection

## Step 1: System Preparation

### Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
```

### Install Essential Packages
```bash
sudo apt install -y curl wget git unzip software-properties-common
```

## Step 2: Database Setup

### Install MySQL/MariaDB
```bash
# Install MariaDB (recommended)
sudo apt install -y mariadb-server mariadb-client

# Or install MySQL
# sudo apt install -y mysql-server mysql-client
```

### Secure Database Installation
```bash
sudo mysql_secure_installation
```

Follow the prompts to:
- Set root password
- Remove anonymous users
- Disable root login remotely
- Remove test database
- Reload privilege tables

### Create Database and User
```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE sota_matcher;
CREATE USER 'sota_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON sota_matcher.* TO 'sota_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Create Database Tables
```bash
mysql -u sota_user -p sota_matcher
```

```sql
-- SOTA spots table
CREATE TABLE sota_spots (
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
CREATE TABLE rbn_spots (
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
CREATE TABLE matches (
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
CREATE TABLE sota_locations (
    summit VARCHAR(50) PRIMARY KEY,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_coordinates (latitude, longitude)
);

-- RBN locations cache
CREATE TABLE rbn_locations (
    callsign VARCHAR(20) PRIMARY KEY,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_coordinates (latitude, longitude)
);
```

## Step 3: Web Server Setup

### Install Nginx
```bash
sudo apt install -y nginx
```

### Install PHP
```bash
sudo apt install -y php8.2-fpm php8.2-mysql php8.2-json php8.2-mbstring php8.2-xml php8.2-curl
```

### Configure PHP-FPM
```bash
sudo nano /etc/php/8.2/fpm/php.ini
```

Update these settings:
```ini
upload_max_filesize = 64M
post_max_size = 64M
max_execution_time = 300
memory_limit = 256M
```

Restart PHP-FPM:
```bash
sudo systemctl restart php8.2-fpm
```

### Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/sota-matcher
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP
    
    root /var/www/sota-matcher;
    index index.html index.php;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.2-fpm.sock;
    }
    
    location ~ /\.ht {
        deny all;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/sota-matcher /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## Step 4: Python Environment Setup

### Install Python Dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv python3-requests python3-pymysql
```

### Create Application Directory
```bash
sudo mkdir -p /var/www/sota-matcher
sudo chown -R www-data:www-data /var/www/sota-matcher
```

## Step 5: Application Deployment

### Copy Application Files
```bash
# Copy web files
sudo cp web/* /var/www/sota-matcher/

# Copy daemon files
sudo mkdir -p /opt/sota-matcher
sudo cp daemon/* /opt/sota-matcher/
sudo chmod +x /opt/sota-matcher/*.py

# Copy configuration
sudo cp config.json /opt/sota-matcher/
```

### Set File Permissions
```bash
sudo chown -R www-data:www-data /var/www/sota-matcher
sudo chown -R root:root /opt/sota-matcher
sudo chmod 644 /opt/sota-matcher/config.json
```

## Step 6: Configuration

### Create Configuration File
```bash
sudo nano /opt/sota-matcher/config.json
```

Example configuration:
```json
{
    "database": {
        "host": "localhost",
        "port": 3306,
        "user": "sota_user",
        "password": "your_secure_password",
        "database": "sota_matcher"
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
```

## Step 7: Service Setup

### Install Systemd Service
```bash
sudo cp /opt/sota-matcher/sota-rbn-matcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sota-rbn-matcher
```

### Start Services
```bash
sudo systemctl start sota-rbn-matcher
sudo systemctl start nginx
sudo systemctl start php8.2-fpm
```

## Step 8: Verification

### Check Service Status
```bash
sudo systemctl status sota-rbn-matcher
sudo systemctl status nginx
sudo systemctl status php8.2-fpm
```

### Test Web Interface
```bash
curl http://your-server-ip/
```

### Check Logs
```bash
sudo journalctl -u sota-rbn-matcher -f
sudo tail -f /var/log/nginx/access.log
```

## Step 9: SSL/HTTPS Setup (Optional but Recommended)

### Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### Obtain SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com
```

### Auto-renewal
```bash
sudo crontab -e
```

Add this line:
```
0 12 * * * /usr/bin/certbot renew --quiet
```

## Troubleshooting

### Common Issues

1. **Service won't start**:
   ```bash
   sudo journalctl -u sota-rbn-matcher -n 50
   ```

2. **Database connection errors**:
   ```bash
   mysql -u sota_user -p sota_matcher
   ```

3. **Web interface not loading**:
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

4. **Permission issues**:
   ```bash
   sudo chown -R www-data:www-data /var/www/sota-matcher
   ```

### Log Locations
- **Service Logs**: `sudo journalctl -u sota-rbn-matcher`
- **Nginx Logs**: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **PHP Logs**: `/var/log/php8.2-fpm.log`
- **Application Logs**: `/var/log/sota-matcher.log`

## Maintenance

### Regular Updates
```bash
sudo apt update && sudo apt upgrade -y
```

### Database Backup
```bash
mysqldump -u sota_user -p sota_matcher > backup_$(date +%Y%m%d).sql
```

### Log Rotation
```bash
sudo nano /etc/logrotate.d/sota-matcher
```

Add:
```
/var/log/sota-matcher.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
```

## Security Considerations

1. **Firewall**: Configure UFW or iptables
2. **Database**: Use strong passwords and limit access
3. **SSL**: Always use HTTPS in production
4. **Updates**: Keep system and packages updated
5. **Monitoring**: Set up log monitoring and alerts

## Performance Optimization

1. **Database Indexing**: Ensure proper indexes on frequently queried columns
2. **Caching**: Consider Redis for session and data caching
3. **CDN**: Use a CDN for static assets
4. **Monitoring**: Set up monitoring for system resources

## Support

For deployment issues:
1. Check the troubleshooting section above
2. Review log files for error messages
3. Verify all services are running
4. Test database connectivity
5. Check file permissions
