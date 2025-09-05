<?php
/**
 * Corrected API endpoint for propagation paths
 * This version works with the actual database schema from the examination
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Load database configuration
$config = json_decode(file_get_contents('config.json'), true);
$db_config = $config['credentials']['mysql'];

try {
    // Connect to MySQL
    $pdo = new PDO(
        "mysql:host={$db_config['host']};port={$db_config['port']};dbname={$db_config['database']};charset=utf8mb4",
        $db_config['user'],
        $db_config['password'],
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
        ]
    );
    
    // Get parameters
    $minutes = $_GET['minutes'] ?? 60;
    $frequency_band = $_GET['frequency'] ?? null;
    $min_snr = $_GET['min_snr'] ?? null;
    $max_distance = $_GET['max_distance'] ?? null;
    $callsign = $_GET['callsign'] ?? null;
    $summit = $_GET['summit'] ?? null;
    
    // Build the query using the ACTUAL database schema from the examination
    // The matches table has: id, sota_id, rbn_id, sota_spotter, rbn_spotter, time_diff_seconds, freq_diff_hz, match_timestamp, etc.
    $query = "
        SELECT 
            m.id,
            s.callsign,
            s.summit,
            s.frequency,
            r.snr,
            m.sota_spotter,
            m.rbn_spotter,
            m.time_diff_seconds,
            m.freq_diff_hz,
            m.match_timestamp,
            m.sota_summit_lat as summit_lat,
            m.sota_summit_lon as summit_lon,
            COALESCE(m.sota_summit_name, s.summit) as summit_name,
            m.rbn_spotter_lat as spotter_lat,
            m.rbn_spotter_lon as spotter_lon,
            COALESCE(m.rbn_spotter_name, m.rbn_spotter) as spotter_name
        FROM matches m
        JOIN sota_spots s ON m.sota_id = s.id
        JOIN rbn_spots r ON m.rbn_id = r.id
        WHERE r.timestamp >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL ? MINUTE)
    ";
    
    $params = [$minutes];
    
    // Add frequency band filter
    if ($frequency_band) {
        switch ($frequency_band) {
            case '160m':
                $query .= " AND s.frequency BETWEEN 1800 AND 2000";
                break;
            case '80m':
                $query .= " AND s.frequency BETWEEN 3500 AND 4000";
                break;
            case '60m':
                $query .= " AND s.frequency BETWEEN 5300 AND 5400";
                break;
            case '40m':
                $query .= " AND s.frequency BETWEEN 7000 AND 7300";
                break;
            case '30m':
                $query .= " AND s.frequency BETWEEN 10100 AND 10150";
                break;
            case '20m':
                $query .= " AND s.frequency BETWEEN 14000 AND 14350";
                break;
            case '17m':
                $query .= " AND s.frequency BETWEEN 18068 AND 18168";
                break;
            case '15m':
                $query .= " AND s.frequency BETWEEN 21000 AND 21450";
                break;
            case '12m':
                $query .= " AND s.frequency BETWEEN 24890 AND 24990";
                break;
            case '10m':
                $query .= " AND s.frequency BETWEEN 28000 AND 29700";
                break;
            case '6m':
                $query .= " AND s.frequency BETWEEN 50000 AND 54000";
                break;
            case '2m':
                $query .= " AND s.frequency BETWEEN 144000 AND 148000";
                break;
            case '1.25m':
                $query .= " AND s.frequency BETWEEN 222000 AND 225000";
                break;
            case '70cm':
                $query .= " AND s.frequency BETWEEN 420000 AND 450000";
                break;
            case '33cm':
                $query .= " AND s.frequency BETWEEN 902000 AND 928000";
                break;
            case '23cm':
                $query .= " AND s.frequency BETWEEN 1240000 AND 1300000";
                break;
        }
    }
    
    // Add SNR filter
    if ($min_snr !== null) {
        $query .= " AND r.snr >= ?";
        $params[] = $min_snr;
    }
    
    // Add callsign filter
    if ($callsign) {
        $query .= " AND s.callsign LIKE ?";
        $params[] = "%$callsign%";
    }
    
    // Add summit filter
    if ($summit) {
        $query .= " AND s.summit LIKE ?";
        $params[] = "%$summit%";
    }
    
    // Order by location_data_enhanced DESC first (enhanced matches first), then by match_timestamp DESC
    $query .= " ORDER BY m.location_data_enhanced DESC, m.match_timestamp DESC";
    
    $stmt = $pdo->prepare($query);
    $stmt->execute($params);
    $matches = $stmt->fetchAll();
    
    $paths = [];
    foreach ($matches as $match) {
        // Calculate distance if coordinates are available
        $distance = 0;
        if ($match['summit_lat'] && $match['summit_lon'] && $match['spotter_lat'] && $match['spotter_lon']) {
            $distance = calculateDistance(
                $match['summit_lat'], $match['summit_lon'],
                $match['spotter_lat'], $match['spotter_lon']
            );
        }
        
        // Apply distance filter
        if ($max_distance && $distance > $max_distance) {
            continue;
        }
        
        $path = [
            'id' => $match['id'],
            'callsign' => $match['callsign'],
            'summit' => $match['summit'],
            'summit_name' => $match['summit_name'],
            'frequency' => (float)$match['frequency'],
            'snr' => (int)$match['snr'],
            'spotter' => $match['rbn_spotter'],
            'spotter_name' => $match['spotter_name'],
            'distance' => round($distance, 1),
            'summit_lat' => (float)$match['summit_lat'],
            'summit_lon' => (float)$match['summit_lon'],
            'spotter_lat' => (float)$match['spotter_lat'],
            'spotter_lon' => (float)$match['spotter_lon'],
            'timestamp' => $match['match_timestamp']
        ];
        $paths[] = $path;
    }
    
    echo json_encode([
        'success' => true,
        'matches' => $paths,
        'count' => count($paths),
        'filters' => [
            'minutes' => $minutes,
            'frequency' => $frequency_band,
            'min_snr' => $min_snr,
            'max_distance' => $max_distance,
            'callsign' => $callsign,
            'summit' => $summit
        ]
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}

/**
 * Calculate distance between two points using Haversine formula
 */
function calculateDistance($lat1, $lon1, $lat2, $lon2) {
    $earthRadius = 6371; // Earth's radius in kilometers
    
    $dLat = deg2rad($lat2 - $lat1);
    $dLon = deg2rad($lon2 - $lon1);
    
    $a = sin($dLat/2) * sin($dLat/2) + cos(deg2rad($lat1)) * cos(deg2rad($lat2)) * sin($dLon/2) * sin($dLon/2);
    $c = 2 * atan2(sqrt($a), sqrt(1-$a));
    
    return $earthRadius * $c;
}
?>
