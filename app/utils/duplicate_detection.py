"""
Duplicate detection utilities using geohashing and temporal hashing.
Used to detect and prevent duplicate quest reports based on location and time.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pygeohash as geohash


def encode_geohash(latitude: float, longitude: float, precision: int = 8) -> str:
    """
    Encode latitude and longitude coordinates into a geohash string.
    
    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        precision: Geohash precision level (1-12, default 8)
                   - Precision 5: ~4.89km x 4.89km
                   - Precision 6: ~1.22km x 0.61km
                   - Precision 7: ~153m x 153m
                   - Precision 8: ~38m x 19m (default)
                   - Precision 9: ~4.8m x 4.8m
    
    Returns:
        Geohash string
    """
    return geohash.encode(latitude, longitude, precision=precision)


def decode_geohash(gh: str) -> Tuple[float, float]:
    """
    Decode a geohash string back to latitude and longitude coordinates.
    
    Args:
        gh: Geohash string
    
    Returns:
        Tuple of (latitude, longitude)
    """
    return geohash.decode(gh)


def get_geohash_neighbors(gh: str) -> dict:
    """
    Get all neighboring geohashes for a given geohash.
    
    Args:
        gh: Geohash string
    
    Returns:
        Dictionary with keys: 'top', 'bottom', 'left', 'right'
    """
    # pygeohash uses 'get_adjacent' function with specific direction names
    direction_map = {
        'top': 'top',       # north
        'bottom': 'bottom', # south
        'right': 'right',   # east
        'left': 'left',     # west
    }
    neighbors = {}
    for key, direction in direction_map.items():
        neighbors[key] = geohash.get_adjacent(gh, direction)
    return neighbors


def check_geohash_proximity(
    geohash1: str,
    geohash2: str,
    precision_level: int = 6
) -> bool:
    """
    Check if two geohashes are within proximity based on shared prefix.
    
    Two locations are considered proximate if their geohashes share
    a common prefix up to the specified precision level.
    
    Args:
        geohash1: First geohash string
        geohash2: Second geohash string
        precision_level: Minimum common prefix length to consider proximate (default 6)
                        - Precision 6: ~1.22km x 0.61km
    
    Returns:
        True if locations are within proximity, False otherwise
    """
    # Truncate both geohashes to the precision level and compare
    prefix1 = geohash1[:precision_level]
    prefix2 = geohash2[:precision_level]
    return prefix1 == prefix2


def is_potential_duplicate_location(
    new_lat: float,
    new_lng: float,
    existing_geohash: str,
    proximity_precision: int = 6
) -> bool:
    """
    Check if a new location is potentially a duplicate of an existing location.
    
    Args:
        new_lat: Latitude of the new location
        new_lng: Longitude of the new location
        existing_geohash: Geohash of the existing location
        proximity_precision: Geohash precision level for proximity check (default 6)
    
    Returns:
        True if the new location is within proximity of the existing location
    """
    new_geohash = encode_geohash(new_lat, new_lng, precision=len(existing_geohash))
    return check_geohash_proximity(new_geohash, existing_geohash, proximity_precision)


def generate_temporal_hash(
    timestamp: datetime,
    bucket_minutes: int = 60
) -> str:
    """
    Generate a temporal hash for a given timestamp.
    
    Timestamps within the same time bucket will produce the same hash,
    useful for detecting submissions that occur within a similar time window.
    
    Args:
        timestamp: The datetime to hash
        bucket_minutes: Time bucket size in minutes (default 60)
    
    Returns:
        Hexadecimal hash string representing the time bucket
    """
    # Normalize timestamp to UTC if it has timezone info
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)
    
    # Calculate the bucket start time
    total_minutes = int(timestamp.timestamp() / 60)
    bucket_start = (total_minutes // bucket_minutes) * bucket_minutes
    
    # Create a deterministic string representation
    bucket_str = str(bucket_start)
    
    # Generate SHA256 hash and return first 16 characters
    return hashlib.sha256(bucket_str.encode()).hexdigest()[:16]


def check_temporal_proximity(
    timestamp1: datetime,
    timestamp2: datetime,
    tolerance_minutes: int = 30
) -> bool:
    """
    Check if two timestamps are within a tolerance window.
    
    Args:
        timestamp1: First timestamp
        timestamp2: Second timestamp
        tolerance_minutes: Maximum difference in minutes to consider proximate (default 30)
    
    Returns:
        True if timestamps are within the tolerance window
    """
    # Normalize timestamps (remove timezone info for comparison)
    if timestamp1.tzinfo is not None:
        timestamp1 = timestamp1.replace(tzinfo=None)
    if timestamp2.tzinfo is not None:
        timestamp2 = timestamp2.replace(tzinfo=None)
    
    time_diff = abs((timestamp1 - timestamp2).total_seconds())
    return time_diff <= (tolerance_minutes * 60)


def generate_location_time_fingerprint(
    latitude: float,
    longitude: float,
    timestamp: datetime,
    geohash_precision: int = 6,
    time_bucket_minutes: int = 60
) -> str:
    """
    Generate a combined fingerprint based on location and time.
    
    This creates a unique identifier for submissions that occur in 
    approximately the same place and time.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        timestamp: Submission timestamp
        geohash_precision: Precision for location grouping (default 6)
        time_bucket_minutes: Time bucket size in minutes (default 60)
    
    Returns:
        Combined fingerprint hash string
    """
    location_hash = encode_geohash(latitude, longitude, precision=geohash_precision)
    time_hash = generate_temporal_hash(timestamp, bucket_minutes=time_bucket_minutes)
    
    # Combine location and time hashes
    combined = f"{location_hash}:{time_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def is_potential_duplicate(
    new_lat: float,
    new_lng: float,
    new_timestamp: datetime,
    existing_geohash: str,
    existing_timestamp: datetime,
    location_precision: int = 6,
    time_tolerance_minutes: int = 30
) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive check if a new submission is a potential duplicate.
    
    Checks both location proximity and temporal proximity to determine
    if a submission might be a duplicate.
    
    Args:
        new_lat: Latitude of the new submission
        new_lng: Longitude of the new submission
        new_timestamp: Timestamp of the new submission
        existing_geohash: Geohash of an existing submission
        existing_timestamp: Timestamp of the existing submission
        location_precision: Geohash precision for proximity check (default 6)
        time_tolerance_minutes: Time tolerance in minutes (default 30)
    
    Returns:
        Tuple of (is_duplicate: bool, reason: Optional[str])
    """
    # Check location proximity
    location_match = is_potential_duplicate_location(
        new_lat, new_lng, existing_geohash, location_precision
    )
    
    # Check temporal proximity
    time_match = check_temporal_proximity(
        new_timestamp, existing_timestamp, time_tolerance_minutes
    )
    
    if location_match and time_match:
        return True, "Duplicate detected: Same location and time window"
    elif location_match:
        return True, "Potential duplicate: Same location, different time"
    
    return False, None
