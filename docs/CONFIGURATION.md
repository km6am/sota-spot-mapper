# Configuration Reference

This document provides detailed information about configuring the SOTA Propagation Map system.

## Configuration File

The main configuration file is `config.json` located in the application root directory (`/opt/sota-matcher/` for production deployments).

## Configuration Structure

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

## Database Configuration

### `database` Section

Controls the MySQL/MariaDB database connection.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | `"localhost"` | Database server hostname or IP address |
| `port` | integer | `3306` | Database server port |
| `user` | string | Required | Database username |
| `password` | string | Required | Database password |
| `database` | string | Required | Database name |

**Example:**
```json
"database": {
    "host": "db.example.com",
    "port": 3306,
    "user": "sota_user",
    "password": "secure_password_123",
    "database": "sota_matcher"
}
```

**Security Notes:**
- Use strong passwords
- Limit database user privileges to only the required database
- Consider using SSL connections for remote databases

## QRZ.com Integration

### `qrz` Section

Configures QRZ.com API access for callsign location lookup.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Yes | QRZ.com username |
| `password` | string | Yes | QRZ.com password |

**Example:**
```json
"qrz": {
    "username": "your_callsign",
    "password": "your_qrz_password"
}
```

**Notes:**
- QRZ.com account required for location lookups
- Free accounts have rate limits
- Premium accounts recommended for production use

## SOTA API Configuration

### `sota` Section

Configures SOTA (Summits on the Air) API access.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_url` | string | `"https://api2.sota.org.uk/api"` | SOTA API base URL |
| `cache_duration` | integer | `86400` | Location cache duration in seconds (24 hours) |

**Example:**
```json
"sota": {
    "api_url": "https://api2.sota.org.uk/api",
    "cache_duration": 86400
}
```

**Notes:**
- SOTA API is free and public
- Cache duration should be reasonable to avoid excessive API calls
- 86400 seconds = 24 hours (recommended)

## Matching Service Configuration

### `matching` Section

Controls the SOTA-RBN matching behavior.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interval_minutes` | integer | `1` | How often to run matching (minutes) |
| `enhancement_batch_size` | integer | `200` | Number of matches to enhance per batch |
| `max_distance_km` | integer | `20000` | Maximum distance for valid matches (km) |

**Example:**
```json
"matching": {
    "interval_minutes": 1,
    "enhancement_batch_size": 200,
    "max_distance_km": 20000
}
```

**Performance Tuning:**
- `interval_minutes`: Lower values = more frequent matching, higher CPU usage
- `enhancement_batch_size`: Higher values = fewer API calls, more memory usage
- `max_distance_km`: Set based on expected propagation distances

## Logging Configuration

### `logging` Section

Controls logging behavior.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | string | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `file` | string | `"/var/log/sota-matcher.log"` | Log file path |

**Example:**
```json
"logging": {
    "level": "INFO",
    "file": "/var/log/sota-matcher.log"
}
```

**Log Levels:**
- `DEBUG`: Detailed information for debugging
- `INFO`: General information about program execution
- `WARNING`: Warning messages for potential issues
- `ERROR`: Error messages for serious problems

## Environment-Specific Configurations

### Development Environment

```json
{
    "database": {
        "host": "localhost",
        "port": 3306,
        "user": "dev_user",
        "password": "dev_password",
        "database": "sota_matcher_dev"
    },
    "qrz": {
        "username": "dev_callsign",
        "password": "dev_qrz_password"
    },
    "sota": {
        "api_url": "https://api2.sota.org.uk/api",
        "cache_duration": 3600
    },
    "matching": {
        "interval_minutes": 5,
        "enhancement_batch_size": 50,
        "max_distance_km": 20000
    },
    "logging": {
        "level": "DEBUG",
        "file": "./logs/sota-matcher.log"
    }
}
```

### Production Environment

```json
{
    "database": {
        "host": "db.example.com",
        "port": 3306,
        "user": "sota_prod_user",
        "password": "very_secure_production_password",
        "database": "sota_matcher_prod"
    },
    "qrz": {
        "username": "production_callsign",
        "password": "production_qrz_password"
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

## Web Interface Configuration

The web interface can be configured through environment variables or by modifying the HTML file directly.

### API Endpoint Configuration

In `propagation_map_interactive.html`, update the API endpoint:

```javascript
const API_ENDPOINT = '/api_propagation_paths.php';
```

### Default Time Range

The default time range can be changed in the HTML:

```html
<option value="10" selected>Last 10 minutes</option>
```

### Frequency Band Definitions

Frequency bands are defined in both the frontend and backend:

**Frontend (HTML):**
```html
<option value="20m">20m (14.0-14.35 MHz)</option>
```

**Backend (PHP):**
```php
case '20m':
    $query .= " AND s.frequency BETWEEN 14000 AND 14350";
    break;
```

## Database Schema Configuration

### Table Creation

The system creates several tables automatically. Key tables include:

- `sota_spots`: SOTA activation spots
- `rbn_spots`: RBN (Reverse Beacon Network) spots
- `matches`: Matched propagation paths
- `sota_locations`: Cached SOTA summit locations
- `rbn_locations`: Cached RBN spotter locations

### Index Optimization

For better performance, ensure these indexes exist:

```sql
-- SOTA spots indexes
CREATE INDEX idx_sota_timestamp ON sota_spots(timestamp);
CREATE INDEX idx_sota_callsign ON sota_spots(callsign);
CREATE INDEX idx_sota_frequency ON sota_spots(frequency);

-- RBN spots indexes
CREATE INDEX idx_rbn_timestamp ON rbn_spots(timestamp);
CREATE INDEX idx_rbn_spotter ON rbn_spots(spotter);
CREATE INDEX idx_rbn_frequency ON rbn_spots(frequency);

-- Matches indexes
CREATE INDEX idx_matches_timestamp ON matches(match_timestamp);
CREATE INDEX idx_matches_enhanced ON matches(enhanced);
```

## Security Configuration

### File Permissions

```bash
# Configuration file
chmod 600 /opt/sota-matcher/config.json
chown root:root /opt/sota-matcher/config.json

# Web files
chmod 644 /var/www/sota-matcher/*
chown www-data:www-data /var/www/sota-matcher/*

# Log files
chmod 644 /var/log/sota-matcher.log
chown root:root /var/log/sota-matcher.log
```

### Database Security

```sql
-- Create dedicated user with limited privileges
CREATE USER 'sota_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON sota_matcher.* TO 'sota_user'@'localhost';
FLUSH PRIVILEGES;
```

### Web Server Security

```nginx
# Hide sensitive files
location ~ /\.(ht|env|git) {
    deny all;
}

# Limit file uploads
client_max_body_size 1M;

# Security headers
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
```

## Performance Tuning

### Database Optimization

```sql
-- Increase buffer pool size
SET GLOBAL innodb_buffer_pool_size = 1G;

-- Optimize query cache
SET GLOBAL query_cache_size = 64M;
SET GLOBAL query_cache_type = ON;
```

### Application Optimization

```json
{
    "matching": {
        "interval_minutes": 2,
        "enhancement_batch_size": 500,
        "max_distance_km": 15000
    }
}
```

### Web Server Optimization

```nginx
# Enable gzip compression
gzip on;
gzip_types text/plain text/css application/json application/javascript;

# Enable caching
location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Monitoring Configuration

### Log Monitoring

```bash
# Monitor logs in real-time
tail -f /var/log/sota-matcher.log

# Check for errors
grep ERROR /var/log/sota-matcher.log

# Monitor service status
systemctl status sota-rbn-matcher
```

### Database Monitoring

```sql
-- Check table sizes
SELECT 
    table_name,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.tables
WHERE table_schema = 'sota_matcher'
ORDER BY (data_length + index_length) DESC;

-- Check query performance
SHOW PROCESSLIST;
```

## Backup Configuration

### Database Backup

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -u sota_user -p sota_matcher > backup_${DATE}.sql
gzip backup_${DATE}.sql
```

### Configuration Backup

```bash
# Backup configuration
cp /opt/sota-matcher/config.json /opt/sota-matcher/config.json.backup
```

## Troubleshooting Configuration Issues

### Common Configuration Problems

1. **Database Connection Errors**:
   - Verify credentials in `config.json`
   - Check database server status
   - Ensure user has proper privileges

2. **API Rate Limiting**:
   - Increase `cache_duration` for SOTA API
   - Reduce `enhancement_batch_size`
   - Check QRZ.com account limits

3. **Performance Issues**:
   - Increase `enhancement_batch_size`
   - Reduce `interval_minutes`
   - Optimize database indexes

4. **Log File Issues**:
   - Check file permissions
   - Ensure directory exists
   - Verify disk space

### Configuration Validation

```python
import json
import sys

def validate_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        required_sections = ['database', 'qrz', 'sota', 'matching', 'logging']
        for section in required_sections:
            if section not in config:
                print(f"Missing required section: {section}")
                return False
        
        # Validate database section
        db_required = ['host', 'port', 'user', 'password', 'database']
        for field in db_required:
            if field not in config['database']:
                print(f"Missing database field: {field}")
                return False
        
        print("Configuration is valid")
        return True
        
    except Exception as e:
        print(f"Configuration error: {e}")
        return False

if __name__ == "__main__":
    validate_config(sys.argv[1] if len(sys.argv) > 1 else 'config.json')
```
