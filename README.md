# SOTA RBN Matcher

A Python application that monitors SOTA (Summits on the Air) and RBN (Reverse Beacon Network) clusters to find propagation matches and generate interactive propagation maps.

## Features

- **Real-time Monitoring**: Connects to SOTA and RBN cluster servers to monitor spots
- **Propagation Analysis**: Matches SOTA activations with RBN spots to analyze propagation paths
- **Interactive Maps**: Generates HTML maps showing propagation paths with Leaflet.js
- **QRZ Integration**: Uses QRZ.com XML API for accurate operator location data
- **Database Storage**: Stores spots and matches in SQLite or MySQL database
- **Configurable**: All settings managed through JSON configuration file
- **Debug Support**: Comprehensive logging and debug output options

## Installation

### Prerequisites

- Python 3.7 or higher
- Internet connection for cluster access and QRZ.com API
- SQLite (included with Python) or MySQL server

### Required Python Packages

Install the required packages:

```bash
pip install requests pymysql
```

**Note**: For the SQLite version, only `requests` is required. For the MySQL version, both `requests` and `pymysql` are needed.

### Database Setup

#### SQLite (Default)
No additional setup required - SQLite database will be created automatically.

#### MySQL (Optional)
1. Install MySQL server
2. Create a database (e.g., `spots`)
3. Create a user with appropriate permissions
4. Configure database settings in `config.json`

## Configuration

1. Copy the example configuration file:
   ```bash
   cp config.example.json config.json
   ```

2. Edit `config.json` with your settings:
   ```json
   {
     "callsigns": {
       "my_callsign": "YOUR_CALLSIGN",
       "cluster_callsign": "YOUR_CALLSIGN"
     },
     "credentials": {
       "qrz": {
         "username": "YOUR_QRZ_USERNAME",
         "password": "YOUR_QRZ_PASSWORD"
       }
     },
     "debug": {
       "enabled": false
     }
   }
   ```

See [CONFIG_README.md](CONFIG_README.md) for detailed configuration options.

## Usage

### Basic Usage

Run the application:

```bash
# SQLite version (default)
python sota_rbn_matcher_mapped_qrz.py

# MySQL version
python sota_rbn_matcher_mysql.py
```

### What the Application Does

1. **Connects to Clusters**: Establishes connections to SOTA and RBN cluster servers
2. **Monitors Spots**: Continuously receives and parses spot data
3. **Stores Data**: Saves spots to database with location information
4. **Finds Matches**: Identifies SOTA activations that appear in RBN spots
5. **Generates Maps**: Creates interactive HTML maps showing propagation paths
6. **Displays Statistics**: Shows propagation statistics and recent activity

### Output Files

- **`propagation_map.html`**: Interactive map showing propagation paths
- **`spots.db`** (SQLite) or MySQL database: Stores all spot and match data

### Interactive Map Features

- **SOTA Summit Markers**: Red markers showing activated summits
- **RBN Spotter Markers**: Blue markers showing RBN spotters
- **Propagation Lines**: Colored lines showing propagation paths
- **Clickable Popups**: Click markers for detailed information and links
- **Auto-refresh**: Map updates every minute
- **Frequency Color Coding**: Different colors for different bands
- **SNR-based Line Weight**: Thicker lines for stronger signals

## Configuration Options

### Essential Settings

- **`my_callsign`**: Your callsign to track in RBN spots
- **`cluster_callsign`**: Callsign to use for cluster login
- **`qrz_username/password`**: QRZ.com credentials for location lookups

### Timing Settings

- **`refresh_interval_seconds`**: How often to refresh statistics (default: 60)
- **`history_window_hours`**: Statistics analysis window (default: 1)
- **`map_window_minutes`**: Map data window (default: 15)
- **`recent_spots_minutes`**: Recent spots display window (default: 60)

### Debug Options

- **`debug.enabled`**: Enable debug logging and verbose output

## Troubleshooting

### Common Issues

1. **Connection Errors**: Check internet connection and cluster server status
2. **QRZ Authentication**: Verify QRZ.com credentials in config.json
3. **Database Errors**: Ensure database permissions and connection settings
4. **No Spots**: Check if your callsign is being spotted on RBN

### Debug Mode

Enable debug mode in `config.json`:
```json
{
  "debug": {
    "enabled": true
  }
}
```

This will show:
- Raw spot data from clusters
- Parsed spot objects
- Detailed error messages
- Connection status information

### Log Files

The application logs to console with timestamps. Debug mode provides additional detail.

## File Structure

```
sota_matcher/
├── sota_rbn_matcher_mapped_qrz.py    # Main SQLite version
├── sota_rbn_matcher_mysql.py         # MySQL version
├── config.json                       # Your configuration (create from example)
├── config.example.json               # Example configuration
├── CONFIG_README.md                  # Detailed configuration guide
├── README.md                         # This file
├── propagation_map.html              # Generated map (created at runtime)
└── spots.db                          # SQLite database (created at runtime)
```

## API Integration

### QRZ.com XML API

The application uses QRZ.com's XML API for accurate operator location data:
- Automatic login and session management
- Callsign lookup with location information
- Caching to minimize API calls
- Fallback to prefix-based location estimation

### Cluster Servers

- **SOTA Cluster**: `cluster.sota.org.uk:7300`
- **RBN Cluster**: `telnet.reversebeacon.net:7000`

## Development

### Adding New Features

The codebase is modular with separate classes for:
- `DatabaseManager`: Database operations
- `SOTAClusterClient`: SOTA cluster monitoring
- `RBNClusterClient`: RBN cluster monitoring
- `QRZLookup`: QRZ.com API integration
- `SpotMatcher`: Main coordination logic

### Testing

Test configuration loading:
```bash
python3 -c "from sota_rbn_matcher_mapped_qrz import load_config; print(load_config())"
```

## License

This project is open source. Please respect the terms of service for:
- QRZ.com API usage
- SOTA cluster server usage
- RBN cluster server usage

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Enable debug mode for detailed logging
3. Review configuration settings
4. Check cluster server status

## Version History

- **v1.0**: Initial release with SQLite support
- **v1.1**: Added MySQL support
- **v1.2**: Added configuration file system
- **v1.3**: Enhanced map features with SOTL.as and QRZ links
