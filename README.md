# SOTA Propagation Map

A real-time interactive web application that visualizes SOTA (Summits on the Air) propagation paths by matching SOTA activations with RBN (Reverse Beacon Network) spots. The system creates an interactive map showing radio propagation paths between SOTA summits and RBN spotters.

## Features

- **Real-time Propagation Visualization**: Interactive map showing live propagation paths
- **Amateur Radio Band Support**: Full support for all amateur radio bands (160m through 23cm)
- **Advanced Filtering**: Filter by frequency band, time range, callsign, and summit
- **Modern Web Interface**: Clean, responsive design with glass morphism effects
- **Automatic Data Enhancement**: Fetches and caches location data for summits and spotters
- **Timezone Aware**: Converts UTC timestamps to local time for filtering
- **RESTful API**: Clean API endpoints for data access

## Quick Start

1. **Clone and Configure**:
   ```bash
   git clone <repository-url>
   cd sota-propagation-map
   cp config.example.json config.json
   # Edit config.json with your database and API settings
   ```

2. **Deploy to Server**:
   ```bash
   chmod +x install.sh
   sudo ./install.sh
   ```

3. **Access the Application**:
   - Web Interface: `http://your-server-ip/`
   - API Endpoint: `http://your-server-ip/api_propagation_paths.php`

## Project Structure

```
sota-propagation-map/
├── README.md                    # This file
├── config.example.json          # Example configuration file
├── config.json                  # Your configuration file (create from example)
├── install.sh                   # Installation script
├── daemon/                      # Backend services
│   ├── sota_rbn_matcher_mysql.py    # Main matching service
│   ├── sota-matcher-daemon.py       # Daemon wrapper
│   └── sota-rbn-matcher.service     # Systemd service file
├── web/                         # Web interface
│   ├── propagation_map_interactive.html  # Main web application
│   └── api_propagation_paths.php        # API endpoint
└── docs/                        # Documentation
    ├── DEPLOYMENT.md            # Server setup guide
    ├── CONFIGURATION.md         # Configuration reference
    └── API.md                   # API documentation
```

## System Requirements

- **Operating System**: Debian 12 (Bookworm) or Ubuntu 22.04+
- **Web Server**: Nginx with PHP 8.2+
- **Database**: MySQL 8.0+ or MariaDB 10.6+
- **Python**: Python 3.9+ with required packages
- **Memory**: Minimum 2GB RAM
- **Storage**: 10GB+ free space

## Key Components

### Backend Services
- **SOTA RBN Matcher**: Python service that matches SOTA activations with RBN spots
- **Location Enhancement**: Fetches coordinates from SOTA API and QRZ.com
- **Database Management**: Stores matches, locations, and cached data

### Web Interface
- **Interactive Map**: Leaflet-based map with real-time propagation paths
- **Filtering System**: Advanced filtering by band, time, callsign, and summit
- **Modern UI**: Clean design with glass morphism and smooth animations
- **Responsive Design**: Works on desktop and mobile devices

### API
- **RESTful Endpoints**: Clean API for data access
- **JSON Responses**: Structured data with metadata
- **Filtering Support**: Server-side filtering for performance

## Configuration

The system is configured via `config.json`. Start by copying the example configuration:

```bash
cp config.example.json config.json
```

Then edit `config.json` with your specific settings:

- **Database Connection**: MySQL/MariaDB connection parameters
- **QRZ.com Credentials**: Username and password for location lookup
- **Service Settings**: Matching intervals and batch sizes
- **Logging**: Log levels and file locations

**Required Configuration:**
1. Update database credentials (host, user, password, database name)
2. Add your QRZ.com username and password for callsign location lookup
3. Adjust matching parameters as needed

See [CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

## Deployment

For detailed deployment instructions, see [DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Quick Deployment
```bash
# Install dependencies and configure services
sudo ./install.sh

# Start the matching service
sudo systemctl start sota-rbn-matcher
sudo systemctl enable sota-rbn-matcher

# Check service status
sudo systemctl status sota-rbn-matcher
```

## Usage

### Web Interface
1. Open your web browser to the server URL
2. The map will load with the last 10 minutes of propagation data
3. Use the filters to narrow down results:
   - **Frequency Band**: Select specific amateur radio bands
   - **Time Range**: Choose from 5 minutes to 24 hours
   - **Callsign**: Filter by specific callsigns (partial matching)
   - **Summit**: Filter by summit references (partial matching)
4. Click on propagation paths to see detailed information
5. Use legend buttons to quickly filter by band

### API Usage
```bash
# Get recent matches (last 10 minutes)
curl "http://your-server/api_propagation_paths.php?minutes=10"

# Filter by frequency band
curl "http://your-server/api_propagation_paths.php?minutes=60&frequency=20m"

# Filter by callsign
curl "http://your-server/api_propagation_paths.php?minutes=30&callsign=KX0R"
```

## Frequency Bands

The system supports all major amateur radio bands:

| Band | Frequency Range | Color |
|------|----------------|-------|
| 160m | 1.8-2.0 MHz | Dark Red |
| 80m | 3.5-4.0 MHz | Red |
| 60m | 5.3-5.4 MHz | Orange Red |
| 40m | 7.0-7.3 MHz | Dark Orange |
| 30m | 10.1-10.15 MHz | Orange |
| 20m | 14.0-14.35 MHz | Gold |
| 17m | 18.068-18.168 MHz | Yellow |
| 15m | 21.0-21.45 MHz | Green Yellow |
| 12m | 24.89-24.99 MHz | Lime |
| 10m | 28.0-29.7 MHz | Spring Green |
| 6m | 50.0-54.0 MHz | Cyan |
| 2m | 144.0-148.0 MHz | Blue |
| 70cm | 420.0-450.0 MHz | Purple |

## Troubleshooting

### Common Issues

1. **No propagation paths showing**:
   - Check if the matching service is running: `sudo systemctl status sota-rbn-matcher`
   - Verify database connection in `config.json`
   - Check service logs: `sudo journalctl -u sota-rbn-matcher -f`

2. **Web interface not loading**:
   - Verify Nginx is running: `sudo systemctl status nginx`
   - Check web server logs: `sudo tail -f /var/log/nginx/error.log`
   - Ensure PHP-FPM is running: `sudo systemctl status php8.2-fpm`

3. **Database connection errors**:
   - Verify MySQL/MariaDB is running: `sudo systemctl status mysql`
   - Check database credentials in `config.json`
   - Ensure database and tables exist

### Log Files
- **Service Logs**: `sudo journalctl -u sota-rbn-matcher -f`
- **Nginx Logs**: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`
- **PHP Logs**: `/var/log/php8.2-fpm.log`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation in the `docs/` directory
- Review the troubleshooting section above

## Acknowledgments

- **SOTA (Summits on the Air)**: For the summit database and API
- **RBN (Reverse Beacon Network)**: For the spot data
- **QRZ.com**: For callsign location lookup
- **Leaflet**: For the interactive mapping library
