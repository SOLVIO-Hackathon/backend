"""
EXIF metadata extraction utility for image verification.
Extracts GPS coordinates, timestamps, and other metadata from images.
"""

import io
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def _get_exif_data(image: Image.Image) -> Dict[str, Any]:
    """
    Extract raw EXIF data from a PIL Image object.
    
    Args:
        image: PIL Image object
    
    Returns:
        Dictionary of EXIF tag names to values
    """
    exif_data = {}
    
    try:
        raw_exif = image._getexif()
        if raw_exif is None:
            return exif_data
        
        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_data[tag_name] = value
    except (AttributeError, KeyError, IndexError):
        pass
    
    return exif_data


def _convert_to_degrees(value: tuple) -> float:
    """
    Convert GPS coordinates from EXIF format to decimal degrees.
    
    EXIF stores GPS as ((degrees, 1), (minutes, 1), (seconds, 100))
    
    Args:
        value: Tuple of (degrees, minutes, seconds) in EXIF format
    
    Returns:
        Decimal degrees as float
    """
    try:
        # Handle different formats of EXIF GPS data
        if isinstance(value, tuple) and len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    
    return 0.0


def _extract_gps_info(exif_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract GPS information from EXIF data.
    
    Args:
        exif_data: Dictionary of EXIF data
    
    Returns:
        Dictionary with GPS information or None if not available
    """
    gps_info = exif_data.get("GPSInfo")
    if not gps_info:
        return None
    
    gps_data = {}
    
    # Parse GPS tags
    for tag_id, value in gps_info.items():
        tag_name = GPSTAGS.get(tag_id, tag_id)
        gps_data[tag_name] = value
    
    return gps_data


def extract_gps_coordinates(image: Image.Image) -> Optional[Tuple[float, float]]:
    """
    Extract GPS coordinates (latitude, longitude) from an image.
    
    Args:
        image: PIL Image object
    
    Returns:
        Tuple of (latitude, longitude) in decimal degrees, or None if not available
    """
    exif_data = _get_exif_data(image)
    gps_data = _extract_gps_info(exif_data)
    
    if not gps_data:
        return None
    
    try:
        lat = gps_data.get("GPSLatitude")
        lat_ref = gps_data.get("GPSLatitudeRef", "N")
        lng = gps_data.get("GPSLongitude")
        lng_ref = gps_data.get("GPSLongitudeRef", "E")
        
        if lat is None or lng is None:
            return None
        
        latitude = _convert_to_degrees(lat)
        longitude = _convert_to_degrees(lng)
        
        # Apply reference direction
        if lat_ref == "S":
            latitude = -latitude
        if lng_ref == "W":
            longitude = -longitude
        
        return (latitude, longitude)
    except (KeyError, TypeError, ValueError):
        return None


def extract_timestamp(image: Image.Image) -> Optional[datetime]:
    """
    Extract the original capture timestamp from an image.
    
    Args:
        image: PIL Image object
    
    Returns:
        datetime object or None if not available
    """
    exif_data = _get_exif_data(image)
    
    # Try different timestamp tags in order of preference
    timestamp_tags = [
        "DateTimeOriginal",
        "DateTimeDigitized",
        "DateTime"
    ]
    
    for tag in timestamp_tags:
        timestamp_str = exif_data.get(tag)
        if timestamp_str:
            try:
                # EXIF format: "YYYY:MM:DD HH:MM:SS"
                return datetime.strptime(timestamp_str, "%Y:%m:%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
    
    return None


def extract_device_info(image: Image.Image) -> Dict[str, Optional[str]]:
    """
    Extract device/camera information from image EXIF data.
    
    Args:
        image: PIL Image object
    
    Returns:
        Dictionary with device information
    """
    exif_data = _get_exif_data(image)
    
    return {
        "make": exif_data.get("Make"),
        "model": exif_data.get("Model"),
        "software": exif_data.get("Software"),
        "orientation": exif_data.get("Orientation")
    }


def extract_image_metadata(image: Image.Image) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from an image.
    
    Args:
        image: PIL Image object
    
    Returns:
        Dictionary containing all extracted metadata
    """
    metadata = {
        "has_exif": False,
        "gps_coordinates": None,
        "timestamp": None,
        "device_info": None,
        "image_dimensions": {
            "width": image.width,
            "height": image.height
        },
        "format": image.format,
        "mode": image.mode
    }
    
    exif_data = _get_exif_data(image)
    metadata["has_exif"] = bool(exif_data)
    
    # Extract GPS coordinates
    gps_coords = extract_gps_coordinates(image)
    if gps_coords:
        metadata["gps_coordinates"] = {
            "latitude": gps_coords[0],
            "longitude": gps_coords[1]
        }
    
    # Extract timestamp
    timestamp = extract_timestamp(image)
    if timestamp:
        metadata["timestamp"] = timestamp.isoformat()
    
    # Extract device info
    device_info = extract_device_info(image)
    if any(device_info.values()):
        metadata["device_info"] = device_info
    
    return metadata


def extract_metadata_from_bytes(image_bytes: bytes) -> Dict[str, Any]:
    """
    Extract metadata from image bytes.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Dictionary containing all extracted metadata
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return extract_image_metadata(image)
    except Exception as e:
        return {
            "has_exif": False,
            "error": str(e)
        }


def extract_metadata_from_file(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from an image file.
    
    Args:
        file_path: Path to the image file
    
    Returns:
        Dictionary containing all extracted metadata
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "has_exif": False,
                "error": "File not found"
            }
        
        image = Image.open(file_path)
        return extract_image_metadata(image)
    except Exception as e:
        return {
            "has_exif": False,
            "error": str(e)
        }


def compare_metadata(
    before_metadata: Dict[str, Any],
    after_metadata: Dict[str, Any],
    gps_tolerance_meters: float = 100.0,
    time_tolerance_minutes: int = 30
) -> Dict[str, Any]:
    """
    Compare metadata from before and after images for verification.
    
    Args:
        before_metadata: Metadata from the 'before' image
        after_metadata: Metadata from the 'after' image
        gps_tolerance_meters: Maximum allowed distance between GPS coordinates
        time_tolerance_minutes: Maximum allowed time difference in minutes
    
    Returns:
        Dictionary with comparison results
    """
    result = {
        "location_match": None,
        "time_valid": None,
        "same_device": None,
        "verification_flags": [],
        "details": {}
    }
    
    # Check GPS coordinates
    before_gps = before_metadata.get("gps_coordinates")
    after_gps = after_metadata.get("gps_coordinates")
    
    if before_gps and after_gps:
        # Calculate approximate distance using Haversine formula
        from math import radians, sin, cos, sqrt, atan2
        
        lat1 = radians(before_gps["latitude"])
        lon1 = radians(before_gps["longitude"])
        lat2 = radians(after_gps["latitude"])
        lon2 = radians(after_gps["longitude"])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        # Earth's radius in meters
        distance_meters = 6371000 * c
        
        result["location_match"] = distance_meters <= gps_tolerance_meters
        result["details"]["distance_meters"] = round(distance_meters, 2)
        
        if not result["location_match"]:
            result["verification_flags"].append(
                f"Location mismatch: {round(distance_meters, 2)}m apart"
            )
    else:
        result["verification_flags"].append("Missing GPS data in one or both images")
    
    # Check timestamps
    before_time_str = before_metadata.get("timestamp")
    after_time_str = after_metadata.get("timestamp")
    
    if before_time_str and after_time_str:
        try:
            before_time = datetime.fromisoformat(before_time_str)
            after_time = datetime.fromisoformat(after_time_str)
            
            time_diff_minutes = abs((after_time - before_time).total_seconds()) / 60
            
            # After photo should be taken after the before photo
            is_after_later = after_time > before_time
            within_tolerance = time_diff_minutes <= time_tolerance_minutes
            
            result["time_valid"] = is_after_later and within_tolerance
            result["details"]["time_difference_minutes"] = round(time_diff_minutes, 2)
            result["details"]["after_is_later"] = is_after_later
            
            if not is_after_later:
                result["verification_flags"].append(
                    "After photo appears to be taken before the before photo"
                )
            if not within_tolerance:
                result["verification_flags"].append(
                    f"Time difference too large: {round(time_diff_minutes, 2)} minutes"
                )
        except (ValueError, TypeError):
            result["verification_flags"].append("Invalid timestamp format")
    else:
        result["verification_flags"].append("Missing timestamp in one or both images")
    
    # Check device info
    before_device = before_metadata.get("device_info")
    after_device = after_metadata.get("device_info")
    
    if before_device and after_device:
        same_make = before_device.get("make") == after_device.get("make")
        same_model = before_device.get("model") == after_device.get("model")
        result["same_device"] = same_make and same_model
        
        if not result["same_device"]:
            result["verification_flags"].append(
                "Different device used for before and after photos"
            )
    
    return result
