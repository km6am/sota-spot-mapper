#!/usr/bin/env python3
"""
SOTA RBN Matcher Daemon
A wrapper script to run the SOTA RBN Matcher as a system service
"""

import os
import sys
import time
import signal
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main matcher
from sota_rbn_matcher_mysql import main, load_config

# Configure logging
def setup_logging():
    """Setup logging for the daemon"""
    # Create logs directory if it doesn't exist
    log_dir = Path("/var/log/sota-matcher")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "sota-matcher.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Error log file
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "sota-matcher-error.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    return logger

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main_daemon():
    """Main daemon function"""
    logger = setup_logging()
    logger.info("Starting SOTA RBN Matcher Daemon")
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load configuration
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Validate configuration
    required_fields = ['callsigns', 'credentials']
    for field in required_fields:
        if field not in config:
            logger.error(f"Missing required configuration field: {field}")
            sys.exit(1)
    
    # Check database connectivity
    try:
        from sota_rbn_matcher_mysql import DatabaseManager
        db_config = config.get('credentials', {}).get('mysql', {})
        db_manager = DatabaseManager(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 3306),
            user=db_config.get('user', 'root'),
            password=db_config.get('password', ''),
            database=db_config.get('database', 'spots'),
            my_callsign=config['callsigns']['my_callsign'],
            qrz_username=config['credentials']['qrz']['username'],
            qrz_password=config['credentials']['qrz']['password']
        )
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    # Run the main application
    restart_count = 0
    max_restarts = 10
    restart_window = 3600  # 1 hour
    restart_times = []
    
    while True:
        try:
            logger.info(f"Starting SOTA RBN Matcher (attempt {restart_count + 1})")
            start_time = time.time()
            
            # Run the main function
            main()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
            break
        except Exception as e:
            logger.error(f"Application crashed: {e}")
            logger.error(f"Traceback: {sys.exc_info()}")
            
            # Check restart limits
            current_time = time.time()
            restart_times = [t for t in restart_times if current_time - t < restart_window]
            restart_times.append(current_time)
            
            if len(restart_times) > max_restarts:
                logger.error(f"Too many restarts in {restart_window} seconds, exiting")
                sys.exit(1)
            
            restart_count += 1
            logger.info(f"Restarting in 10 seconds... (restart {restart_count})")
            time.sleep(10)

if __name__ == "__main__":
    main_daemon()

