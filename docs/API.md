# API Documentation

This document describes the RESTful API endpoints provided by the SOTA Propagation Map system.

## Base URL

The API is accessible at:
```
http://your-server-ip/api_propagation_paths.php
```

## Authentication

Currently, the API does not require authentication. In production environments, consider implementing API key authentication or IP whitelisting.

## Endpoints

### GET /api_propagation_paths.php

Retrieves propagation path matches with optional filtering.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `minutes` | integer | No | Time range in minutes (default: 10) |
| `frequency` | string | No | Frequency band filter |
| `callsign` | string | No | Callsign filter (partial matching) |
| `summit` | string | No | Summit filter (partial matching) |
| `timezone_offset` | integer | No | Client timezone offset in minutes |

#### Frequency Band Values

| Value | Frequency Range | Description |
|-------|----------------|-------------|
| `160m` | 1.8-2.0 MHz | 160 meters |
| `80m` | 3.5-4.0 MHz | 80 meters |
| `60m` | 5.3-5.4 MHz | 60 meters |
| `40m` | 7.0-7.3 MHz | 40 meters |
| `30m` | 10.1-10.15 MHz | 30 meters |
| `20m` | 14.0-14.35 MHz | 20 meters |
| `17m` | 18.068-18.168 MHz | 17 meters |
| `15m` | 21.0-21.45 MHz | 15 meters |
| `12m` | 24.89-24.99 MHz | 12 meters |
| `10m` | 28.0-29.7 MHz | 10 meters |
| `6m` | 50.0-54.0 MHz | 6 meters |
| `2m` | 144.0-148.0 MHz | 2 meters |
| `1.25m` | 222.0-225.0 MHz | 1.25 meters |
| `70cm` | 420.0-450.0 MHz | 70 centimeters |
| `33cm` | 902.0-928.0 MHz | 33 centimeters |
| `23cm` | 1240.0-1300.0 MHz | 23 centimeters |

#### Example Requests

```bash
# Get last 10 minutes of matches
curl "http://your-server/api_propagation_paths.php?minutes=10"

# Filter by 20m band
curl "http://your-server/api_propagation_paths.php?minutes=60&frequency=20m"

# Filter by callsign
curl "http://your-server/api_propagation_paths.php?minutes=30&callsign=KX0R"

# Filter by summit
curl "http://your-server/api_propagation_paths.php?minutes=120&summit=W0C"

# Multiple filters
curl "http://your-server/api_propagation_paths.php?minutes=60&frequency=20m&callsign=KX0R"
```

#### Response Format

```json
{
    "success": true,
    "matches": [
        {
            "id": 12345,
            "sota_callsign": "KX0R",
            "sota_summit": "W0C/SR-035",
            "sota_frequency": 14.230,
            "sota_mode": "CW",
            "sota_timestamp": "2025-01-15 14:30:25",
            "rbn_spotter": "W1AW",
            "rbn_spotted": "KX0R",
            "rbn_frequency": 14.230,
            "rbn_snr": 15,
            "rbn_mode": "CW",
            "rbn_timestamp": "2025-01-15 14:30:20",
            "match_timestamp": "2025-01-15 14:30:30",
            "enhanced": true,
            "sota_lat": 39.7392,
            "sota_lon": -104.9903,
            "rbn_lat": 41.7658,
            "rbn_lon": -72.6734,
            "distance_km": 2650.5
        }
    ],
    "count": 1,
    "timestamp": "2025-01-15 14:35:00",
    "filters": {
        "minutes": "10",
        "frequency": null,
        "callsign": null,
        "summit": null,
        "timezone_offset": "-420"
    }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates if the request was successful |
| `matches` | array | Array of propagation path matches |
| `count` | integer | Number of matches returned |
| `timestamp` | string | Server timestamp when response was generated |
| `filters` | object | Applied filters and their values |

#### Match Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique match identifier |
| `sota_callsign` | string | SOTA activator callsign |
| `sota_summit` | string | SOTA summit reference |
| `sota_frequency` | float | SOTA frequency in MHz |
| `sota_mode` | string | SOTA operating mode |
| `sota_timestamp` | string | SOTA spot timestamp (UTC) |
| `rbn_spotter` | string | RBN spotter callsign |
| `rbn_spotted` | string | Spotted callsign |
| `rbn_frequency` | float | RBN frequency in MHz |
| `rbn_snr` | integer | Signal-to-noise ratio |
| `rbn_mode` | string | RBN operating mode |
| `rbn_timestamp` | string | RBN spot timestamp (UTC) |
| `match_timestamp` | string | When the match was created |
| `enhanced` | boolean | Whether location data is available |
| `sota_lat` | float | SOTA summit latitude (if enhanced) |
| `sota_lon` | float | SOTA summit longitude (if enhanced) |
| `rbn_lat` | float | RBN spotter latitude (if enhanced) |
| `rbn_lon` | float | RBN spotter longitude (if enhanced) |
| `distance_km` | float | Distance between points in kilometers |

#### Error Responses

```json
{
    "success": false,
    "error": "Database connection failed",
    "timestamp": "2025-01-15 14:35:00"
}
```

Common error messages:
- `"Database connection failed"`
- `"Invalid parameter value"`
- `"No data available"`
- `"Internal server error"`

## Rate Limiting

The API does not currently implement rate limiting. Consider implementing rate limiting in production environments to prevent abuse.

## Caching

The API implements server-side caching for location data:
- SOTA summit locations are cached for 24 hours
- RBN spotter locations are cached for 24 hours
- Database queries are optimized with proper indexing

## Timezone Handling

The API handles timezone conversion for filtering:
- RBN spot timestamps are stored in UTC
- The `timezone_offset` parameter allows client-side timezone filtering
- All response timestamps are in UTC

## Performance Considerations

### Database Optimization

The API uses optimized SQL queries with:
- Proper indexing on timestamp, frequency, and callsign columns
- LIMIT clauses to prevent large result sets
- Efficient JOIN operations

### Response Size

- Default limit: 1000 matches per request
- Large result sets are automatically limited
- Consider implementing pagination for very large datasets

## Example Usage

### JavaScript/Frontend

```javascript
// Fetch recent matches
async function fetchMatches(minutes = 10, frequency = null) {
    const params = new URLSearchParams();
    params.append('minutes', minutes);
    if (frequency) params.append('frequency', frequency);
    params.append('timezone_offset', new Date().getTimezoneOffset());
    
    try {
        const response = await fetch(`/api_propagation_paths.php?${params}`);
        const data = await response.json();
        
        if (data.success) {
            return data.matches;
        } else {
            console.error('API Error:', data.error);
            return [];
        }
    } catch (error) {
        console.error('Fetch Error:', error);
        return [];
    }
}

// Usage
const matches = await fetchMatches(60, '20m');
console.log(`Found ${matches.length} matches`);
```

### Python

```python
import requests
import json

def fetch_matches(minutes=10, frequency=None, callsign=None):
    url = "http://your-server/api_propagation_paths.php"
    params = {
        'minutes': minutes,
        'timezone_offset': -420  # UTC-7
    }
    
    if frequency:
        params['frequency'] = frequency
    if callsign:
        params['callsign'] = callsign
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['success']:
            return data['matches']
        else:
            print(f"API Error: {data['error']}")
            return []
    except Exception as e:
        print(f"Request Error: {e}")
        return []

# Usage
matches = fetch_matches(minutes=60, frequency='20m')
print(f"Found {len(matches)} matches")
```

### cURL Examples

```bash
# Basic request
curl "http://your-server/api_propagation_paths.php"

# With time range
curl "http://your-server/api_propagation_paths.php?minutes=30"

# With frequency filter
curl "http://your-server/api_propagation_paths.php?minutes=60&frequency=20m"

# With callsign filter
curl "http://your-server/api_propagation_paths.php?minutes=120&callsign=KX0R"

# With multiple filters
curl "http://your-server/api_propagation_paths.php?minutes=60&frequency=20m&callsign=KX0R&summit=W0C"

# Pretty print JSON response
curl "http://your-server/api_propagation_paths.php?minutes=10" | jq '.'
```

## Integration Examples

### Real-time Updates

```javascript
// Poll for updates every 30 seconds
setInterval(async () => {
    const matches = await fetchMatches(10);
    updateMap(matches);
}, 30000);
```

### Filtering Interface

```javascript
// Dynamic filtering
function applyFilters() {
    const minutes = document.getElementById('time-range').value;
    const frequency = document.getElementById('frequency-filter').value;
    const callsign = document.getElementById('callsign-filter').value;
    
    fetchMatches(minutes, frequency, callsign)
        .then(matches => {
            displayMatches(matches);
        });
}
```

### Data Export

```javascript
// Export matches to CSV
function exportMatches(matches) {
    const csv = matches.map(match => 
        `${match.sota_callsign},${match.sota_summit},${match.rbn_spotter},${match.distance_km}`
    ).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sota_matches.csv';
    a.click();
}
```

## Security Considerations

### Input Validation

The API validates all input parameters:
- Numeric parameters are validated for range
- String parameters are sanitized
- SQL injection prevention through prepared statements

### Error Handling

- Sensitive information is not exposed in error messages
- Detailed error logging for debugging
- Graceful degradation for service failures

### CORS Configuration

For cross-origin requests, configure CORS headers:

```php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
```

## Monitoring and Logging

### API Metrics

Monitor these metrics:
- Request count per endpoint
- Response times
- Error rates
- Database query performance

### Logging

API requests are logged with:
- Timestamp
- Request parameters
- Response status
- Processing time
- Error details (if any)

## Future Enhancements

Planned API improvements:
- Pagination support
- WebSocket for real-time updates
- API key authentication
- Rate limiting
- Response compression
- GraphQL endpoint
