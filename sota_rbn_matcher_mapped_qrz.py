#!/usr/bin/env python3
"""
SOTA and RBN Spot Matcher with QRZ Integration
Pulls spots from SOTA cluster and RBN, stores in database, finds matches, and creates maps
"""

import socket
import sqlite3
import threading
import time
import re
import logging
import traceback
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import queue
import requests
import json
import math
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

def load_config(config_file: str = "config.json") -> Dict:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found. Using default values.")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file {config_file}: {e}")
        return {}

# Configure logging
def configure_logging(debug: bool = False):
    """Configure logging level based on debug flag"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

# Default to INFO level
configure_logging(debug=False)
logger = logging.getLogger(__name__)

@dataclass
class Location:
    latitude: float
    longitude: float
    name: str = ""
    
    def distance_to(self, other: 'Location') -> float:
        """Calculate distance in kilometers using Haversine formula"""
        R = 6371  # Earth's radius in km
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

@dataclass
class PropagationPath:
    sota_summit: str
    sota_location: Location
    rbn_spotter: str
    rbn_location: Location
    frequency: float
    distance_km: float
    timestamp: datetime
    snr: int
    callsign: str

@dataclass
class SOTASpot:
    callsign: str
    frequency: float
    summit: str
    comment: str
    timestamp: datetime
    spotter: str
    
@dataclass
class RBNSpot:
    callsign: str
    frequency: float
    snr: int
    timestamp: datetime
    spotter: str
    mode: str = "CW"  # RBN is primarily CW

class QRZLookup:
    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password
        self.session_key = None
        self.last_login = None
        self.session_timeout = 3600  # 1 hour
        self.base_url = "https://xmldata.qrz.com/xml/current/"
        
    def _login(self) -> bool:
        """Login to QRZ and get session key"""
        if not self.username or not self.password:
            logger.warning("QRZ username/password not provided - will use callsign prefix estimation")
            return False
            
        try:
            params = {
                'username': self.username,
                'password': self.password,
                'agent': 'sota-rbn-matcher'
            }
            """<ns0:QRZDatabase xmlns:ns0="http://xmldata.qrz.com" version="1.36">
  <ns0:Session>
    <ns0:Key>5aefaf4bbe82e5d001ce8a2d79e5635e</ns0:Key>
    <ns0:Count>0</ns0:Count>
    <ns0:SubExp>Sat Aug 29 05:14:38 2026</ns0:SubExp>
    <ns0:GMTime>Sat Aug 30 05:50:44 2025</ns0:GMTime>
    <ns0:Remark>cpu: 0.013s</ns0:Remark>
  </ns0:Session>
</ns0:QRZDatabase>"""
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            ET.indent(root)

            # Convert to string and print
            print(ET.tostring(root, encoding='utf-8').decode('utf-8'))
            
            # Use namespace for finding Session element
            session = root.find('.//ns0:Session', namespaces={'ns0': 'http://xmldata.qrz.com'})
            if session is not None:
                print(ET.tostring(session, encoding='utf-8').decode('utf-8'))
                key_elem = session.find('ns0:Key', namespaces={'ns0': 'http://xmldata.qrz.com'})
                if key_elem is not None:
                    self.session_key = key_elem.text
                    self.last_login = datetime.now()
                    logger.info("Successfully logged into QRZ XML API")
                    return True
                    
            # Check for error with namespace
            error = root.find('.//ns0:Error', namespaces={'ns0': 'http://xmldata.qrz.com'})
            if error is not None:
                logger.error(f"QRZ login error: {error.text}")
            else:
                logger.error("QRZ login failed - no session key received")
                
        except Exception as e:
            logger.error(f"QRZ login exception: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
        return False
    
    def _is_session_valid(self) -> bool:
        """Check if current session is still valid"""
        if not self.session_key or not self.last_login:
            return False
            
        elapsed = (datetime.now() - self.last_login).total_seconds()
        return elapsed < self.session_timeout
    
    def lookup_callsign(self, callsign: str) -> Optional[Dict]:
        """Lookup callsign details from QRZ"""
        if not self._is_session_valid():
            if not self._login():
                return None
        
        # Clean callsign (remove /P, /M, etc.)
        clean_callsign = callsign.split('/')[0].upper().strip()
        
        try:
            params = {
                's': self.session_key,
                'callsign': clean_callsign
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            callsign_data = root.find('.//ns0:Callsign', namespaces={'ns0': 'http://xmldata.qrz.com'})
            
            if callsign_data is not None:
                data = {}
                for elem in callsign_data:
                    # Remove namespace prefix from tag name
                    tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    data[tag_name.lower()] = elem.text
                
                # Extract location data
                result = {
                    'callsign': data.get('call', clean_callsign),
                    'name': data.get('fname', '') + ' ' + data.get('name', ''),
                    'address': data.get('addr2', ''),
                    'city': data.get('addr2', ''),
                    'state': data.get('state', ''),
                    'country': data.get('country', ''),
                    'grid': data.get('grid', ''),
                    'latitude': None,
                    'longitude': None
                }
                
                # Try to get coordinates
                if 'lat' in data and 'lon' in data:
                    try:
                        result['latitude'] = float(data['lat'])
                        result['longitude'] = float(data['lon'])
                    except (ValueError, TypeError):
                        pass
                
                # If no lat/lon but we have grid square, convert it
                if not result['latitude'] and result['grid']:
                    lat, lon = self._grid_to_coordinates(result['grid'])
                    if lat and lon:
                        result['latitude'] = lat
                        result['longitude'] = lon
                
                return result
            
            # Check for error with namespace
            error = root.find('.//ns0:Error', namespaces={'ns0': 'http://xmldata.qrz.com'})
            if error is not None:
                logger.debug(f"QRZ lookup error for {clean_callsign}: {error.text}")
                
        except Exception as e:
            logger.debug(f"QRZ lookup exception for {clean_callsign}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
        return None
    
    def _grid_to_coordinates(self, grid: str) -> Tuple[Optional[float], Optional[float]]:
        """Convert Maidenhead grid square to lat/lon coordinates"""
        if not grid or len(grid) < 4:
            return None, None
            
        try:
            grid = grid.upper()
            
            # Extract field, square, and subsquare
            field_lon = ord(grid[0]) - ord('A')
            field_lat = ord(grid[1]) - ord('A') 
            square_lon = int(grid[2])
            square_lat = int(grid[3])
            
            # Calculate base coordinates (SW corner of square)
            lon = -180 + (field_lon * 20) + (square_lon * 2)
            lat = -90 + (field_lat * 10) + (square_lat * 1)
            
            # Add offset to get center of square
            if len(grid) >= 6:
                # Have subsquare, use center of subsquare
                subsq_lon = ord(grid[4]) - ord('A')
                subsq_lat = ord(grid[5]) - ord('A')
                lon += (subsq_lon * 2/24) + (1/24)  # Center of subsquare
                lat += (subsq_lat * 1/24) + (1/48)  # Center of subsquare
            else:
                # No subsquare, use center of square
                lon += 1  # Center of 2-degree square
                lat += 0.5  # Center of 1-degree square
            
            return lat, lon
            
        except (ValueError, IndexError):
            return None, None

class DatabaseManager:
    def __init__(self, db_path: str = "spots.db", my_callsign: str = "", qrz_username: str = "", qrz_password: str = ""):
        self.db_path = db_path
        self.my_callsign = my_callsign.upper()
        self.qrz = QRZLookup(qrz_username, qrz_password)
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # SOTA spots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sota_spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                callsign TEXT NOT NULL,
                frequency REAL NOT NULL,
                summit TEXT NOT NULL,
                comment TEXT,
                timestamp DATETIME NOT NULL,
                spotter TEXT NOT NULL,
                UNIQUE(callsign, frequency, summit, timestamp, spotter)
            )
        """)
        
        # RBN spots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbn_spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                callsign TEXT NOT NULL,
                frequency REAL NOT NULL,
                snr INTEGER NOT NULL,
                timestamp DATETIME NOT NULL,
                spotter TEXT NOT NULL,
                mode TEXT DEFAULT 'CW',
                is_my_callsign BOOLEAN DEFAULT 0,
                is_sota_matched BOOLEAN DEFAULT 0,
                keep_permanent BOOLEAN DEFAULT 0,
                UNIQUE(callsign, frequency, timestamp, spotter)
            )
        """)
        
        # Matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sota_id INTEGER,
                rbn_id INTEGER,
                sota_spotter TEXT,
                rbn_spotter TEXT,
                time_diff_seconds INTEGER,
                freq_diff_hz INTEGER,
                match_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sota_id) REFERENCES sota_spots (id),
                FOREIGN KEY (rbn_id) REFERENCES rbn_spots (id)
            )
        """)
        
        # Locations table for SOTA summits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sota_locations (
                summit_ref TEXT PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                name TEXT,
                region TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Locations table for RBN spotters
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbn_locations (
                spotter TEXT PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                name TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                grid TEXT,
                source TEXT DEFAULT 'unknown',
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def insert_sota_spot(self, spot: SOTASpot) -> Optional[int]:
        """Insert SOTA spot into database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO sota_spots 
                (callsign, frequency, summit, comment, timestamp, spotter)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (spot.callsign, spot.frequency, spot.summit, spot.comment, 
                  spot.timestamp, spot.spotter))
            
            spot_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return spot_id
        except Exception as e:
            logger.error(f"Error inserting SOTA spot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def is_sota_spot_recent(self, spot: SOTASpot, max_age_hours: int = 1) -> bool:
        """Check if a SOTA spot is recent enough to insert (not from initial connection dump)"""
        try:
            now = datetime.now(timezone.utc)
            spot_age = now - spot.timestamp
            
            # If spot is older than max_age_hours, it's likely from initial connection dump
            if spot_age.total_seconds() > max_age_hours * 3600:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking spot age: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return True  # Default to allowing insertion if there's an error
    
    def insert_rbn_spot(self, spot: RBNSpot) -> Optional[int]:
        """Insert RBN spot into database with callsign matching logic"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if this is my callsign or has callsign variations
            is_my_callsign = self._is_my_callsign(spot.callsign)
            keep_permanent = is_my_callsign  # Always keep my callsign spots
            
            cursor.execute("""
                INSERT OR IGNORE INTO rbn_spots 
                (callsign, frequency, snr, timestamp, spotter, mode, is_my_callsign, keep_permanent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (spot.callsign, spot.frequency, spot.snr, 
                  spot.timestamp, spot.spotter, spot.mode, is_my_callsign, keep_permanent))
            
            spot_id = cursor.lastrowid if cursor.rowcount > 0 else None
            
            # If we inserted a new spot and it's my callsign, log it specially
            if spot_id and is_my_callsign:
                logger.info(f"MY CALLSIGN spotted: {spot.callsign} {spot.frequency:.1f}kHz "
                           f"{spot.snr}dB by {spot.spotter}")
            
            conn.commit()
            conn.close()
            return spot_id
        except Exception as e:
            logger.error(f"Error inserting RBN spot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _is_my_callsign(self, callsign: str) -> bool:
        """Check if callsign matches my callsign (including common variations)"""
        if not self.my_callsign:
            return False
            
        callsign = callsign.upper().strip()
        my_call = self.my_callsign.upper().strip()
        
        # Exact match
        if callsign == my_call:
            return True
            
        # Common variations (/P, /M, /QRP, etc.)
        base_call = callsign.split('/')[0]  # Remove suffix
        my_base = my_call.split('/')[0]     # Remove suffix from my call too
        
        if base_call == my_base or base_call == my_call or callsign == my_base:
            return True
            
        return False
    
    def find_matches(self, spot_rbn_max_time_diff: int = 30, freq_tolerance_hz: int = 10000):
        """Find matches between SOTA and RBN spots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing matches (we'll rebuild them)
        cursor.execute("DELETE FROM matches")
        
        # Find matches within time and frequency windows
        cursor.execute("""
            SELECT 
                s.id as sota_id, 
                r.id as rbn_id,
                s.callsign,
                s.frequency as sota_freq,
                r.frequency as rbn_freq,
                s.timestamp as sota_time,
                r.timestamp as rbn_time,
                s.summit,
                s.spotter as sota_spotter,
                r.spotter as rbn_spotter
            FROM sota_spots s
            JOIN rbn_spots r ON s.callsign = r.callsign
            WHERE 
                ABS(julianday(s.timestamp) - julianday(r.timestamp)) * 24 * 60 <= ?
                AND ABS(s.frequency - r.frequency) <= ?
            ORDER BY s.timestamp DESC
        """, (spot_rbn_max_time_diff, freq_tolerance_hz / 1000.0))  # Convert Hz to kHz
        
        matches = cursor.fetchall()
        matched_rbn_ids = []
        
        # Insert matches and collect matched RBN IDs
        for match in matches:
            sota_id, rbn_id, callsign, sota_freq, rbn_freq, sota_time, rbn_time, summit, sota_spotter, rbn_spotter = match
            
            # Calculate differences
            sota_dt = datetime.fromisoformat(sota_time.replace('Z', '+00:00'))
            rbn_dt = datetime.fromisoformat(rbn_time.replace('Z', '+00:00'))
            time_diff = int((rbn_dt - sota_dt).total_seconds())
            freq_diff = int((rbn_freq - sota_freq) )  # Convert to Hz
            
            cursor.execute("""
                INSERT INTO matches 
                (sota_id, rbn_id, sota_spotter, rbn_spotter, time_diff_seconds, freq_diff_hz, match_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sota_id, rbn_id, sota_spotter, rbn_spotter, time_diff, freq_diff, rbn_dt))
            
            matched_rbn_ids.append(rbn_id)
            
            logger.debug(f"Match found: {callsign} on {summit}, "
                       f"SOTA: {sota_freq:.3f}kHz at {sota_time} by {sota_spotter}, "
                       f"RBN: {rbn_freq:.3f}kHz at {rbn_time} by {rbn_spotter}, "
                       f"Δt: {time_diff}s, Δf: {freq_diff}kHz")
        
        # Mark matched RBN spots as SOTA-matched and permanent
        if matched_rbn_ids:
            placeholders = ','.join(['?' for _ in matched_rbn_ids])
            cursor.execute(f"""
                UPDATE rbn_spots 
                SET is_sota_matched = 1, keep_permanent = 1
                WHERE id IN ({placeholders})
            """, matched_rbn_ids)
            
            logger.info(f"Marked {len(matched_rbn_ids)} RBN spots as SOTA-matched")
        
        conn.commit()
        conn.close()
        return len(matches)
    
    def cleanup_old_rbn_spots(self):
        """Remove RBN spots older than 24 hours that aren't marked for permanent keeping"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete old unmatched spots that aren't my callsign or SOTA-matched
            cursor.execute("""
                DELETE FROM rbn_spots 
                WHERE timestamp < datetime('now', '-24 hours')
                AND keep_permanent = 0
            """)
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old unmatched RBN spots")
            
            conn.commit()
            conn.close()
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old RBN spots: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0
    
    def get_my_callsign_spots(self, minutes: int = 1440) -> List[Tuple]:
        """Get RBN spots of my callsign from the last N minutes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                callsign,
                frequency,
                snr,
                timestamp,
                spotter,
                mode
            FROM rbn_spots
            WHERE is_my_callsign = 1
            AND timestamp > datetime('now', '-{} minutes')
            ORDER BY timestamp DESC
        """.format(minutes))
        
        spots = cursor.fetchall()
        conn.close()
        return spots
    
    def get_sota_location(self, summit_ref: str) -> Optional[Location]:
        """Get SOTA summit location from database or fetch from API"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try to get from database first
        cursor.execute("""
            SELECT latitude, longitude, name FROM sota_locations 
            WHERE summit_ref = ?
        """, (summit_ref,))
        
        result = cursor.fetchone()
        if result:
            conn.close()
            return Location(result[0], result[1], result[2] or summit_ref)
        
        # Fetch from SOTA API
        try:
            # SOTA API endpoint (this is a simplified example - actual SOTA API may differ)
            url = f"https://api2.sota.org.uk/api/summits/{summit_ref}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data.get('latitude', 0))
                    lon = float(data.get('longitude', 0))
                    name = data.get('name', summit_ref)
                    region = data.get('region', '')
                    
                    # Store in database
                    cursor.execute("""
                        INSERT OR REPLACE INTO sota_locations 
                        (summit_ref, latitude, longitude, name, region)
                        VALUES (?, ?, ?, ?, ?)
                    """, (summit_ref, lat, lon, name, region))
                    conn.commit()
                    
                    conn.close()
                    return Location(lat, lon, name)
        except Exception as e:
            logger.warning(f"Failed to fetch SOTA location for {summit_ref}: {e}")
            logger.warning(f"Traceback: {traceback.format_exc()}")
        
        conn.close()
        return None
    
    def get_rbn_location(self, spotter: str) -> Optional[Location]:
        """Get RBN spotter location from database, QRZ, or estimate from callsign"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clean spotter callsign (remove -# suffix)
        clean_spotter = spotter.split('-')[0].upper()
        
        # Try to get from database first (check if recent)
        cursor.execute("""
            SELECT latitude, longitude, name, source, last_updated FROM rbn_locations 
            WHERE spotter = ?
        """, (clean_spotter,))
        
        result = cursor.fetchone()
        if result:
            lat, lon, name, source, last_updated = result
            # If from QRZ and less than 30 days old, use it
            last_update_dt = datetime.fromisoformat(last_updated)
            if source == 'qrz' or (datetime.now() - last_update_dt).days < 30:
                conn.close()
                return Location(lat, lon, name or clean_spotter)
        
        # Try QRZ lookup
        logger.debug(f"Looking up {clean_spotter} in QRZ...")
        qrz_data = self.qrz.lookup_callsign(clean_spotter)
        
        if qrz_data and qrz_data.get('latitude') and qrz_data.get('longitude'):
            # Got coordinates from QRZ
            lat = qrz_data['latitude']
            lon = qrz_data['longitude']
            name = qrz_data.get('name', '').strip()
            city = qrz_data.get('city', '')
            state = qrz_data.get('state', '')
            country = qrz_data.get('country', '')
            grid = qrz_data.get('grid', '')
            
            # Create display name
            location_parts = [part for part in [city, state, country] if part]
            display_name = name if name else clean_spotter
            if location_parts:
                display_name += f" ({', '.join(location_parts)})"
            
            # Store in database
            cursor.execute("""
                INSERT OR REPLACE INTO rbn_locations 
                (spotter, latitude, longitude, name, city, state, country, grid, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'qrz')
            """, (clean_spotter, lat, lon, display_name, city, state, country, grid))
            conn.commit()
            
            logger.info(f"QRZ lookup successful: {clean_spotter} -> {display_name}")
            conn.close()
            return Location(lat, lon, display_name)
        
        # Fallback to prefix estimation if QRZ fails
        logger.debug(f"QRZ lookup failed for {clean_spotter}, using prefix estimation")
        location = self._estimate_location_from_callsign(clean_spotter)
        
        if location:
            cursor.execute("""
                INSERT OR REPLACE INTO rbn_locations 
                (spotter, latitude, longitude, name, source)
                VALUES (?, ?, ?, ?, 'prefix')
            """, (clean_spotter, location.latitude, location.longitude, 
                  location.name))
            conn.commit()
            logger.debug(f"Using prefix location for {clean_spotter}: {location.name}")
        
        conn.close()
        return location
    
    def _estimate_location_from_callsign(self, callsign: str) -> Optional[Location]:
        """Rough location estimation based on callsign prefix"""
        # This is a simplified mapping - in practice you'd want a more complete database
        prefix_locations = {
            'W1': Location(42.3601, -71.0589, 'New England'),
            'W2': Location(40.7128, -74.0060, 'New York/New Jersey'),
            'W3': Location(39.9526, -75.1652, 'Pennsylvania/Delaware'),
            'W4': Location(33.7490, -84.3880, 'Southeast US'),
            'W5': Location(32.7767, -96.7970, 'South Central US'),
            'W6': Location(34.0522, -118.2437, 'California'),
            'W7': Location(47.6062, -122.3321, 'Pacific Northwest'),
            'W8': Location(41.4993, -81.6944, 'Great Lakes'),
            'W9': Location(41.8781, -87.6298, 'Midwest'),
            'W0': Location(39.7391, -104.9847, 'Mountain/Plains'),
            'VE1': Location(44.6488, -63.5752, 'Nova Scotia'),
            'VE2': Location(45.5017, -73.5673, 'Quebec'),
            'VE3': Location(43.6532, -79.3832, 'Ontario'),
            'VE4': Location(49.8951, -97.1384, 'Manitoba'),
            'VE5': Location(52.1332, -106.6700, 'Saskatchewan'),
            'VE6': Location(51.0447, -114.0719, 'Alberta'),
            'VE7': Location(49.2827, -123.1207, 'British Columbia'),
            'G': Location(51.5074, -0.1278, 'England'),
            'GM': Location(55.9533, -3.1883, 'Scotland'),
            'GW': Location(51.4816, -3.1791, 'Wales'),
            'EI': Location(53.3498, -6.2603, 'Ireland'),
            'ON': Location(50.8503, 4.3517, 'Belgium'),
            'PA': Location(52.3676, 4.9041, 'Netherlands'),
            'DL': Location(52.5200, 13.4050, 'Germany'),
            'F': Location(48.8566, 2.3522, 'France'),
            'JA': Location(35.6762, 139.6503, 'Japan'),
            'HL': Location(37.5665, 126.9780, 'South Korea'),
            'VK': Location(-33.8688, 151.2093, 'Australia'),
        }
        
        # Find matching prefix
        for prefix, location in prefix_locations.items():
            if callsign.startswith(prefix):
                return location
        
        # Try single letter prefixes for US
        if len(callsign) >= 2 and callsign[0] in 'NKWA':
            region = callsign[1]
            if region in '123456789':
                us_regions = {
                    '1': Location(42.3601, -71.0589, 'New England'),
                    '2': Location(40.7128, -74.0060, 'New York/New Jersey'),
                    '3': Location(39.9526, -75.1652, 'Pennsylvania/Delaware'),
                    '4': Location(33.7490, -84.3880, 'Southeast US'),
                    '5': Location(32.7767, -96.7970, 'South Central US'),
                    '6': Location(34.0522, -118.2437, 'California'),
                    '7': Location(47.6062, -122.3321, 'Pacific Northwest'),
                    '8': Location(41.4993, -81.6944, 'Great Lakes'),
                    '9': Location(41.8781, -87.6298, 'Midwest'),
                    '0': Location(39.7391, -104.9847, 'Mountain/Plains'),
                }
                return us_regions.get(region)
        
        return None
    
    def get_propagation_paths(self, minutes: int = 1440) -> List[PropagationPath]:
        """Get propagation paths from recent matches"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.callsign,
                s.summit,
                s.frequency as sota_freq,
                r.frequency as rbn_freq,
                r.spotter,
                r.snr,
                m.match_timestamp
            FROM matches m
            JOIN sota_spots s ON m.sota_id = s.id
            JOIN rbn_spots r ON m.rbn_id = r.id
            WHERE m.match_timestamp > datetime('now', '-{} minutes')
            ORDER BY m.match_timestamp DESC
        """.format(minutes))
        
        matches = cursor.fetchall()
        conn.close()
        
        paths = []
        for match in matches:
            callsign, summit, sota_freq, rbn_freq, spotter, snr, timestamp = match
            
            # Get locations
            sota_loc = self.get_sota_location(summit)
            rbn_loc = self.get_rbn_location(spotter)
            
            if sota_loc and rbn_loc:
                distance = sota_loc.distance_to(rbn_loc)
                
                path = PropagationPath(
                    sota_summit=summit,
                    sota_location=sota_loc,
                    rbn_spotter=spotter,
                    rbn_location=rbn_loc,
                    frequency=rbn_freq,
                    distance_km=distance,
                    timestamp=datetime.fromisoformat(timestamp),
                    snr=snr,
                    callsign=callsign
                )
                paths.append(path)
        
        return paths
    
    def generate_propagation_map(self, minutes: int = 1440, output_file: str = "propagation_map.html"):
        """Generate an interactive HTML map showing propagation paths"""
        paths = self.get_propagation_paths(minutes)
        
        if not paths:
            logger.warning("No propagation paths found for mapping")
            return None
        
        # Create HTML map
        html_content = self._create_map_html(paths)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Propagation map saved to {output_file} with {len(paths)} paths")
        return output_file
    
    def _create_map_html(self, paths: List[PropagationPath]) -> str:
        """Create HTML content for the propagation map"""
        # Calculate map center
        if not paths:
            center_lat, center_lon = 40.0, -100.0  # Default to center of US
        else:
            all_lats = [p.sota_location.latitude for p in paths] + [p.rbn_location.latitude for p in paths]
            all_lons = [p.sota_location.longitude for p in paths] + [p.rbn_location.longitude for p in paths]
            center_lat = sum(all_lats) / len(all_lats)
            center_lon = sum(all_lons) / len(all_lons)
        
        # Generate path data for JavaScript
        paths_js = []
        for i, path in enumerate(paths):
            path_data = {
                'id': i,
                'callsign': path.callsign,
                'summit': path.sota_summit,
                'summit_name': path.sota_location.name,
                'summit_lat': path.sota_location.latitude,
                'summit_lon': path.sota_location.longitude,
                'spotter': path.rbn_spotter,
                'spotter_name': path.rbn_location.name,
                'spotter_lat': path.rbn_location.latitude,
                'spotter_lon': path.rbn_location.longitude,
                'frequency': path.frequency,
                'distance': round(path.distance_km, 1),
                'snr': path.snr,
                'timestamp': path.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            paths_js.append(path_data)
        
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SOTA-RBN Propagation Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 100vh; }}
        .info-panel {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            max-width: 300px;
        }}
        .path-info {{
            margin-bottom: 10px;
            padding: 8px;
            border-left: 4px solid #3388ff;
            background: #f8f9fa;
        }}
        .legend {{
            position: absolute;
            bottom: 30px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 3px;
            margin-right: 10px;
        }}
        .legend-circle {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="info-panel">
        <h3>SOTA-RBN Propagation Paths</h3>
        <div id="stats">
            <strong>Paths: {len(paths)}</strong><br>
            <span id="selected-info">Click a path for details</span>
        </div>
    </div>
    
    <div class="legend">
        <h4>Legend</h4>
        <div class="legend-item">
            <div class="legend-circle" style="background: #ff4444; border-color: #ff0000;"></div>
            <span>🏔️ SOTA Summit</span>
        </div>
        <div class="legend-item">
            <div class="legend-circle" style="background: #4444ff; border-color: #0000ff;"></div>
            <span>📡 RBN Spotter</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff2222;"></div>
            <span>📶 40m & below</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff8844;"></div>
            <span>📶 20m</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ffff44;"></div>
            <span>📶 15m</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #44ff44;"></div>
            <span>📶 12/10m</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #4444ff;"></div>
            <span>📶 6m & above</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Initialize map
        var map = L.map('map').setView([{center_lat}, {center_lon}], 4);
        
        // Add tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Path data
        var paths = {json.dumps(paths_js)};
        
        // Track layers for cleanup
        var pathLayers = [];
        
                // Function to get line color based on frequency
        function getFrequencyColor(freq) {{
            if (freq < 7500) return '#ff2222';      // 40m and below - red
            if (freq < 14500) return '#ff8844';     // 20m - orange  
            if (freq < 21500) return '#ffff44';     // 15m - yellow
            if (freq < 29000) return '#44ff44';     // 12/10m - green
            return '#4444ff';                      // 6m and above - blue
        }}
        
        // Function to get line weight based on SNR
        function getLineWeight(snr) {{
            if (snr < 5) return 1;
            if (snr < 10) return 2;
            if (snr < 15) return 3;
            if (snr < 20) return 4;
            if (snr < 25) return 5;
            if (snr < 30) return 6;
            if (snr < 35) return 7;
            return 8;
        }}
        
        // Function to calculate great circle points between two coordinates
        function getGreatCirclePoints(lat1, lon1, lat2, lon2, numPoints = 50) {{
            var points = [];
            var lat1Rad = lat1 * Math.PI / 180;
            var lon1Rad = lon1 * Math.PI / 180;
            var lat2Rad = lat2 * Math.PI / 180;
            var lon2Rad = lon2 * Math.PI / 180;
            
            var d = Math.acos(Math.sin(lat1Rad) * Math.sin(lat2Rad) + 
                             Math.cos(lat1Rad) * Math.cos(lat2Rad) * Math.cos(lon2Rad - lon1Rad));
            
            for (var i = 0; i <= numPoints; i++) {{
                var f = i / numPoints;
                var a = Math.sin((1 - f) * d) / Math.sin(d);
                var b = Math.sin(f * d) / Math.sin(d);
                
                var x = a * Math.cos(lat1Rad) * Math.cos(lon1Rad) + b * Math.cos(lat2Rad) * Math.cos(lon2Rad);
                var y = a * Math.cos(lat1Rad) * Math.sin(lon1Rad) + b * Math.cos(lat2Rad) * Math.sin(lon2Rad);
                var z = a * Math.sin(lat1Rad) + b * Math.sin(lat2Rad);
                
                var lat = Math.atan2(z, Math.sqrt(x * x + y * y)) * 180 / Math.PI;
                var lon = Math.atan2(y, x) * 180 / Math.PI;
                
                points.push([lat, lon]);
            }}
            
            return points;
        }}
        
        // Add paths to map
        paths.forEach(function(path) {{
            // SOTA summit marker
            var summitMarker = L.circleMarker([path.summit_lat, path.summit_lon], {{
                radius: 4,
                color: '#ff0000',
                fillColor: '#ff4444',
                fillOpacity: 0.8
            }}).addTo(map);
            
            summitMarker.bindPopup(`
                <strong>🏔️ SOTA Summit</strong><br>
                <strong>${{path.summit}}</strong><br>
                ${{path.summit_name}}<br>
                <em>Activated by ${{path.callsign}}</em><br>
                <br>
                <a href="https://sotl.as/summits/${{path.summit}}" target="_blank">📋 View on SOTL.AS</a><br>
                <a href="https://sotl.as/activators/${{path.callsign}}" target="_blank">SOTL.as Activator Profile</a>
            `);
            
            // RBN spotter marker
            var spotterMarker = L.circleMarker([path.spotter_lat, path.spotter_lon], {{
                radius: 3,
                color: '#0000ff',
                fillColor: '#4444ff',
                fillOpacity: 0.8
            }}).addTo(map);
            
            spotterMarker.bindPopup(`
                <strong>📡 RBN Spotter</strong><br>
                <strong>${{path.spotter}}</strong><br>
                ${{path.spotter_name}}<br>
                SNR: ${{path.snr}} dB
            `);
            
            // Propagation path line (great circle)
            var greatCirclePoints = getGreatCirclePoints(
                path.summit_lat, path.summit_lon,
                path.spotter_lat, path.spotter_lon
            );
            var pathLine = L.polyline(greatCirclePoints, {{
                color: getFrequencyColor(path.frequency),
                weight: getLineWeight(path.snr),
                opacity: 0.7
            }}).addTo(map);
            
            // Add click handler for path info
            pathLine.on('click', function() {{
                document.getElementById('selected-info').innerHTML = `
                    <div class="path-info">
                        <strong>${{path.callsign}}</strong> on <strong>${{path.summit}}</strong><br>
                        📡 Heard by: ${{path.spotter}}<br>
                        📶 Frequency: ${{path.frequency.toFixed(1)}} kHz<br>
                        📏 Distance: ${{path.distance}} km<br>
                        📊 SNR: ${{path.snr}} dB<br>
                        🕐 Time: ${{path.timestamp}}
                    </div>
                `;
            }});
            
            pathLine.bindTooltip(`
                ${{path.callsign}} → ${{path.spotter}}<br>
                ${{path.frequency.toFixed(1)}} kHz, ${{path.distance}} km<br>
                ${{path.snr}} dB
            `);
        }});
        
        // Fit map to show all points
        if (paths.length > 0) {{
            var group = new L.featureGroup();
            paths.forEach(function(path) {{
                group.addLayer(L.marker([path.summit_lat, path.summit_lon]));
                group.addLayer(L.marker([path.spotter_lat, path.spotter_lon]));
            }});
            map.fitBounds(group.getBounds().pad(0.1));
        }}
    </script>
</body>
</html>
        """
        
        return html_template

class ClusterConnection:
    def __init__(self, host: str, port: int, callsign: str, timeout: int, long_connection: bool = False):
        self.host = host
        self.port = port
        self.callsign = callsign
        self.socket = None
        self.connected = False
        self.timeout = timeout
        self.long_connection = long_connection  # For connections that need to stay open for hours
        
    def connect(self):
        """Connect to cluster"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # For long connections (like SOTA), don't set a socket timeout
            # This allows the connection to stay open for hours without data
            if not self.long_connection:
                self.socket.settimeout(self.timeout)
            else:
                # Set a very long timeout for long connections (24 hours)
                self.socket.settimeout(24 * 60 * 60)
                
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            # Send callsign
            self.socket.send(f"{self.callsign}\r\n".encode())
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from cluster"""
        if self.socket:
            self.socket.close()
        self.connected = False
    
    def read_line(self) -> Optional[str]:
        """Read a line from the cluster"""
        if not self.connected:
            return None
            
        try:
            buffer = b""
            while b"\n" not in buffer:
                data = self.socket.recv(1)
                if not data:
                    return None
                buffer += data
            return buffer.decode('utf-8', errors='ignore').strip()
        except socket.timeout:
            # For long connections, timeout is expected and not an error
            if self.long_connection:
                return None  # Return None to indicate no data, but don't log as error
            else:
                logger.error(f"Socket timeout reading from {self.host}:{self.port}")
                return None
        except Exception as e:
            logger.error(f"Error reading from cluster: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

def create_datetime(spot_time):
    """Convert spot time in hhmm format to datetime with date from now and time in last 24 hours"""
    now = datetime.now(timezone.utc)
    
    # Parse hhmm format (e.g., "1430" -> 14:30)
    try:
        hour = int(spot_time[:2])
        minute = int(spot_time[2:])
        
        # Create datetime for today with the parsed time
        spot_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the spot time is in the future (e.g., it's 10 AM but spot says 2 PM),
        # it means the spot is from yesterday
        if spot_datetime > now:
            spot_datetime = spot_datetime - timedelta(days=1)
        
        return spot_datetime
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing spot time '{spot_time}': {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return now


class SOTAClusterClient:
    def __init__(self, db_manager: DatabaseManager, callsign: str, debug: bool = False):
        self.db_manager = db_manager
        self.callsign = callsign
        self.debug = debug
        self.connection = ClusterConnection("cluster.sota.org.uk", 7300, callsign, timeout=15*60, long_connection=True)
        self.running = False
        
    def parse_sota_spot(self, line: str) -> Optional[SOTASpot]:
        """Parse SOTA spot line"""
        if self.debug:
            logger.debug(f"SOTA spot line: {line}")
        try:
            # SOTA format: DX de G0ABC: 14.062 W4G/NG-001 CW QSL
            match = re.search(r'DX de (\S+):\s+([\d.]+)\s+(\S+)\s+([\S\d/-]+)\s+([\d]+)Z', line)
            if not match:
                return None
            
            spotter = match.group(1)
            frequency = float(match.group(2))
            callsign = match.group(3)
            summit = match.group(4)
            spot_time = match.group(5).strip()

            timestamp = create_datetime(spot_time)

            spot = SOTASpot(
                callsign=callsign,
                frequency=frequency,
                summit=summit,
                comment="comment",
                timestamp=timestamp,
                spotter=spotter
            )
            
            # Print SOTASpot if debug flag is True
            if self.debug:
                print(f"DEBUG SOTASpot: {spot}")
            
            return spot
        except Exception as e:
            logger.error(f"Error parsing SOTA spot '{line}': {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def start(self):
        """Start SOTA cluster monitoring"""
        self.running = True
        thread = threading.Thread(target=self._monitor_cluster)
        thread.daemon = True
        thread.start()
        return thread
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.connection.disconnect()
    
    def _monitor_cluster(self):
        """Monitor SOTA cluster"""
        last_activity = time.time()
        while self.running:
            if not self.connection.connected:
                if not self.connection.connect():
                    time.sleep(30)
                    continue
            
            line = self.connection.read_line()
            if line is None:
                # For long connections, no data is normal - don't disconnect
                # Only disconnect if we haven't received any data for 24 hours
                current_time = time.time()
                if current_time - last_activity > 24 * 60 * 60:  # 24 hours
                    logger.warning("SOTA connection inactive for 24 hours, reconnecting...")
                    self.connection.connected = False
                continue
            
            # We got data, update last activity time
            last_activity = time.time()
                
            spot = self.parse_sota_spot(line)
            if spot:
                # Check if spot is recent enough to insert (not from initial connection dump)
                if self.db_manager.is_sota_spot_recent(spot):
                    spot_id = self.db_manager.insert_sota_spot(spot)
                    if spot_id:
                        logger.info(f"SOTA spot {spot_id}: {spot.callsign} on {spot.summit} "
                                   f"{spot.frequency:.3f}kHz")
                else:
                        logger.info(f"Skipping old SOTA spot: {spot.callsign} on {spot.summit} "
                                   f"{spot.frequency:.3f}kHz (age: {datetime.now(timezone.utc) - spot.timestamp})")

class RBNClusterClient:
    def __init__(self, db_manager: DatabaseManager, callsign: str, debug: bool = False):
        self.db_manager = db_manager
        self.callsign = callsign
        self.debug = debug
        self.connection = ClusterConnection("telnet.reversebeacon.net", 7000, callsign, timeout=1*60)
        self.running = False
        
    def parse_rbn_spot(self, line: str) -> Optional[RBNSpot]:
        """Parse RBN spot line"""
        try:
            # RBN format: DX de W3LPL-#: 14025.0 K1ABC CW 22 dB 23 WPM CQ 1200Z
            if self.debug:
                logger.info(f"RBN spot line: {line}")
            # Try the full pattern with time first
            match = re.search(r'DX de (\S+):\s+([\d.]+)\s+(\S+)\s+(\w+)\s+([-\d]+)\s+dB\s+[\d]+\s+WPM\s+(\S+)\s+(\d{4})Z', line)
            if match:
                spot_time = match.group(7)
            else:
                return None
            
            spotter = match.group(1)
            frequency = float(match.group(2))
            callsign = match.group(3)
            mode = match.group(4)
            snr = int(match.group(5))
            spot_time = match.group(7)
            
            timestamp = create_datetime(spot_time)
            
            spot = RBNSpot(
                callsign=callsign,
                frequency=frequency,
                snr=snr,
                timestamp=timestamp,
                spotter=spotter,
                mode=mode
            )
            
            # Print RBNSpot if debug flag is True
            if self.debug:
                print(f"DEBUG RBNSpot: {spot}")
            
            return spot
        except Exception as e:
            logger.error(f"Error parsing RBN spot '{line}': {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def start(self):
        """Start RBN cluster monitoring"""
        self.running = True
        thread = threading.Thread(target=self._monitor_cluster)
        thread.daemon = True
        thread.start()
        return thread
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.connection.disconnect()
    
    def _monitor_cluster(self):
        """Monitor RBN cluster"""
        last_activity = time.time()
        while self.running:
            if not self.connection.connected:
                if self.debug:
                    logger.debug("Attempting to connect to RBN cluster...")
                if not self.connection.connect():
                    if self.debug:
                        logger.debug("Failed to connect to RBN cluster, retrying in 30 seconds...")
                    time.sleep(30)
                    continue
                else:
                    if self.debug:
                        logger.debug("Successfully connected to RBN cluster")
            
            line = self.connection.read_line()
            if line is None:
                # For RBN, no data might mean timeout - don't immediately disconnect
                # Only disconnect if we haven't received any data for 5 minutes
                current_time = time.time()
                if current_time - last_activity > 5 * 60:  # 5 minutes
                    if self.debug:
                        logger.debug("RBN connection inactive for 5 minutes, reconnecting...")
                    self.connection.connected = False
                continue
            
            # We got data, update last activity time
            last_activity = time.time()
            
            if self.debug:
                logger.debug(f"RBN raw line: {line}")
                
            spot = self.parse_rbn_spot(line)
            if spot:
                spot_id = self.db_manager.insert_rbn_spot(spot)
                if spot_id and self.debug:
                    logger.debug(f"RBN spot {spot_id}: {spot.callsign} {spot.frequency:.1f}kHz "
                               f"{spot.snr}dB by {spot.spotter}")
            else:
                if self.debug and line.strip():
                    logger.debug(f"RBN line did not parse as spot: {line}")

class SpotMatcher:
    def __init__(self, callsign: str = "N0CALL", my_callsign: str = "", qrz_username: str = "", qrz_password: str = "", debug: bool = False):
        self.callsign = callsign
        self.my_callsign = my_callsign.upper() if my_callsign else callsign.upper()
        self.debug = debug
        self.db_manager = DatabaseManager(my_callsign=self.my_callsign, 
                                        qrz_username=qrz_username, 
                                        qrz_password=qrz_password)
        self.sota_client = SOTAClusterClient(self.db_manager, callsign, debug=debug)
        self.rbn_client = RBNClusterClient(self.db_manager, callsign, debug=debug)
        self.running = False
    
    def start(self):
        """Start monitoring both clusters"""
        logger.info("Starting SOTA and RBN spot matcher")
        self.running = True
        
        # Start cluster clients
        sota_thread = self.sota_client.start()
        rbn_thread = self.rbn_client.start()
        
        # Start matching thread
        match_thread = threading.Thread(target=self._match_loop)
        match_thread.daemon = True
        match_thread.start()
        
        return sota_thread, rbn_thread, match_thread
    
    def stop(self):
        """Stop all monitoring"""
        logger.info("Stopping spot matcher")
        self.running = False
        self.sota_client.stop()
        self.rbn_client.stop()
    
    def _match_loop(self):
        """Periodically run matching algorithm and cleanup"""
        cleanup_counter = 0
        while self.running:
            time.sleep(60)  # Run every minute
            try:
                # Run matching algorithm
                matches = self.db_manager.find_matches()
                if matches > 0:
                    logger.info(f"Found {matches} new matches")
                
                # Run cleanup every 30 minutes (30 * 60 second cycles)
                cleanup_counter += 1
                if cleanup_counter >= 30:
                    cleanup_counter = 0
                    deleted = self.db_manager.cleanup_old_rbn_spots()
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old RBN spots")
                        
            except Exception as e:
                logger.error(f"Error in matching/cleanup loop: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
    
    def get_my_recent_spots(self, minutes: int = 1440) -> List[Tuple]:
        """Get my callsign's recent RBN spots"""
        return self.db_manager.get_my_callsign_spots(minutes)
    
    def get_recent_matches(self, minutes: int = 60) -> List[Tuple]:
        """Get recent matches from database"""
        conn = sqlite3.connect(self.db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.callsign,
                s.summit,
                s.frequency as sota_freq,
                r.frequency as rbn_freq,
                s.timestamp as sota_time,
                r.timestamp as rbn_time,
                m.time_diff_seconds,
                m.freq_diff_hz,
                r.snr,
                m.sota_spotter,
                m.rbn_spotter
            FROM matches m
            JOIN sota_spots s ON m.sota_id = s.id
            JOIN rbn_spots r ON m.rbn_id = r.id
            WHERE m.match_timestamp > datetime('now', '-{} minutes')
            ORDER BY m.match_timestamp DESC
        """.format(minutes))
        
        matches = cursor.fetchall()
        conn.close()
        return matches
    
    def generate_map(self, minutes: int = 60) -> str:
        """Generate propagation map and return filename"""
        return self.db_manager.generate_propagation_map(minutes)
    
    def get_propagation_stats(self, minutes: int = 24) -> Dict:
        """Get propagation statistics"""
        paths = self.db_manager.get_propagation_paths(minutes)
        
        if not paths:
            return {"total_paths": 0}
        
        stats = {
            "total_paths": len(paths),
            "unique_summits": len(set(p.sota_summit for p in paths)),
            "unique_spotters": len(set(p.rbn_spotter for p in paths)),
            "avg_distance_km": sum(p.distance_km for p in paths) / len(paths),
            "max_distance_km": max(p.distance_km for p in paths),
            "min_distance_km": min(p.distance_km for p in paths),
            "avg_snr_db": sum(p.snr for p in paths) / len(paths),
            "frequency_bands": {}
        }
        
        # Analyze frequency distribution
        for path in paths:
            freq = path.frequency
            if freq < 7.5:
                band = "40m and below"
            elif freq < 14.5:
                band = "20m"
            elif freq < 21.5:
                band = "15m"
            elif freq < 29.0:
                band = "12m/10m"
            else:
                band = "6m and above"
            
            stats["frequency_bands"][band] = stats["frequency_bands"].get(band, 0) + 1
        
        return stats

def main():
    # Load configuration from file
    config = load_config()
    
    # Extract configuration values with defaults
    my_callsign = config.get("callsigns", {}).get("my_callsign", "")
    cluster_callsign = config.get("callsigns", {}).get("cluster_callsign", "")
    
    # QRZ credentials (optional but recommended for accurate locations)
    qrz_username = config.get("credentials", {}).get("qrz", {}).get("username", "")
    qrz_password = config.get("credentials", {}).get("qrz", {}).get("password", "")
    
    # Debug flag - set to True to print SOTASpot objects and enable debug logging
    debug = config.get("debug", {}).get("enabled", False)
    refresh_interval = config.get("timing", {}).get("refresh_interval_seconds", 60)
    history_window = config.get("timing", {}).get("history_window_minutes", 60)
    map_window = config.get("timing", {}).get("map_window_minutes", 15)
    recent_spots_window = config.get("timing", {}).get("recent_spots_minutes", 60)
    
    # Configure logging level based on debug flag
    configure_logging(debug=debug)
    
    matcher = SpotMatcher(
        callsign=cluster_callsign, 
        my_callsign=my_callsign,
        qrz_username=qrz_username,
        qrz_password=qrz_password,
        debug=debug
    )
    
    try:
        threads = matcher.start()
        logger.info(f"Monitoring for spots of: {my_callsign}")
        logger.info("Location lookup priority:")
        logger.info("1. QRZ.com XML database (most accurate)")
        logger.info("2. Cached database entries")  
        logger.info("3. Callsign prefix estimation (fallback)")
        logger.info("")
        logger.info("RBN spot retention policy:")
        logger.info(f"- Spots matching '{my_callsign}': PERMANENT")
        logger.info("- Spots matching SOTA activations: PERMANENT")
        logger.info("- Other RBN spots: Deleted after 24 hours")
        
        # Run for a while
        while 1:
            

            # Show propagation statistics
            stats = matcher.get_propagation_stats(history_window)  # Last hour
            print(f"\n=== Propagation Statistics (Last {history_window} Minutes(s)) ===")
            print(f"Total propagation paths: {stats.get('total_paths', 0)}")
            if stats.get('total_paths', 0) > 0:
                print(f"Unique SOTA summits: {stats.get('unique_summits', 0)}")
                print(f"Unique RBN spotters: {stats.get('unique_spotters', 0)}")
                print(f"Average distance: {stats.get('avg_distance_km', 0):.1f} km")
                print(f"Distance range: {stats.get('min_distance_km', 0):.1f} - {stats.get('max_distance_km', 0):.1f} km")
                print(f"Average SNR: {stats.get('avg_snr_db', 0):.1f} dB")

                print("\nFrequency band distribution:")
                for band, count in stats.get('frequency_bands', {}).items():
                    print(f"  {band}: {count} paths")

                # Generate interactive map
                map_file = matcher.generate_map(map_window)  # Configurable window
                if map_file:
                    print(f"\n📍 Interactive propagation map saved as: {map_file}")
                    print("Open this file in your web browser to view the map!")

            # Show my recent spots
            my_spots = matcher.get_my_recent_spots(recent_spots_window)  # Configurable window
            if my_spots:
                print(f"\nMy callsign ({my_callsign}) heard in the last {recent_spots_window} minutes:")
                for spot in my_spots[:10]:  # Show first 10
                    callsign, freq, snr, timestamp, spotter, mode = spot
                    print(f"  {callsign} {freq:.1f}kHz {snr}dB {mode} by {spotter} at {timestamp}")
            else:
                print(f"\nNo spots of {my_callsign} in the last {recent_spots_window} minutes")

            # Show recent SOTA matches
            matches = matcher.get_recent_matches(history_window)  # Configurable window
            if matches:
                print(f"\nFound {len(matches)} SOTA/RBN matches in the last {history_window} minutes(s):")
                for match in matches[:10]:  # Show first 10
                    callsign, summit, sota_freq, rbn_freq, sota_time, rbn_time, time_diff, freq_diff, snr, sota_spotter, rbn_spotter = match
                    print(f"  {callsign} on {summit}: SOTA {sota_freq:.3f}MHz (by {sota_spotter}) -> RBN {rbn_freq:.1f}kHz (by {rbn_spotter}) "
                          f"({time_diff}s, {freq_diff}Hz, {snr}dB)")
            else:
                print(f"\nNo SOTA/RBN matches in the last {history_window} hour(s)")
            time.sleep(refresh_interval)  # Run for 5 minutes as example
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        matcher.stop()

if __name__ == "__main__":
    main()