# Configuration Guide

The SOTA RBN Matcher now uses a JSON configuration file to manage all settings. This makes it easy to customize the application without modifying the source code.

## Setup

1. Copy the example configuration file:
   ```bash
   cp config.example.json config.json
   ```

2. Edit `config.json` with your specific settings

## Configuration Options

### Callsigns
- `my_callsign`: Your amateur radio callsign (the one you want to track)
- `cluster_callsign`: Callsign to use when connecting to cluster servers

### Credentials

#### QRZ.com (Optional but recommended)
- `username`: Your QRZ.com username
- `password`: Your QRZ.com password
- Used for accurate location lookups of operators

#### MySQL Database (for MySQL version only)
- `host`: MySQL server hostname (default: localhost)
- `port`: MySQL server port (default: 3306)
- `user`: MySQL username
- `password`: MySQL password
- `database`: Database name (default: spots)

### Debug Settings
- `enabled`: Set to `true` to enable debug logging and verbose output

### Timing Settings
- `refresh_interval_seconds`: How often to refresh statistics and generate maps (default: 60)
- `history_window_hours`: How many hours of history to analyze for statistics (default: 1)
- `map_window_minutes`: How many minutes of data to include in the propagation map (default: 15)
- `recent_spots_minutes`: How many minutes of recent spots to display (default: 60)

### Cluster Servers
- `sota.host` and `sota.port`: SOTA cluster server settings
- `rbn.host` and `rbn.port`: RBN cluster server settings

## Usage

Simply run the application as usual:
```bash
python sota_rbn_matcher_mapped_qrz.py
# or
python sota_rbn_matcher_mysql.py
```

The application will automatically load settings from `config.json`. If the file doesn't exist, it will use default values and print a warning message.

## Security Note

**Important**: Never commit your `config.json` file to version control as it contains sensitive information like passwords. The `config.example.json` file is safe to commit as it contains no real credentials.
