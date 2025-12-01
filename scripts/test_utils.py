"""
Unit tests for duplicate detection and EXIF extraction utilities.
"""

import io
import unittest
from datetime import datetime, timedelta

from PIL import Image

from app.utils.duplicate_detection import (
    encode_geohash,
    decode_geohash,
    get_geohash_neighbors,
    check_geohash_proximity,
    is_potential_duplicate_location,
    generate_temporal_hash,
    check_temporal_proximity,
    generate_location_time_fingerprint,
    is_potential_duplicate,
)
from app.utils.exif_extraction import (
    extract_gps_coordinates,
    extract_timestamp,
    extract_device_info,
    extract_image_metadata,
    extract_metadata_from_bytes,
    compare_metadata,
)


class TestGeohashing(unittest.TestCase):
    """Tests for geohashing functions."""
    
    def setUp(self):
        """Set up test data."""
        # Dhaka coordinates
        self.lat = 23.7461
        self.lng = 90.3742
    
    def test_encode_geohash(self):
        """Test geohash encoding."""
        gh = encode_geohash(self.lat, self.lng, precision=8)
        self.assertEqual(len(gh), 8)
        self.assertTrue(gh.startswith("wh0r"))  # Dhaka area prefix
    
    def test_decode_geohash(self):
        """Test geohash decoding."""
        gh = encode_geohash(self.lat, self.lng, precision=8)
        decoded = decode_geohash(gh)
        # Decoded values should be close to original
        self.assertAlmostEqual(decoded[0], self.lat, places=3)
        self.assertAlmostEqual(decoded[1], self.lng, places=3)
    
    def test_get_geohash_neighbors(self):
        """Test getting geohash neighbors."""
        gh = encode_geohash(self.lat, self.lng, precision=6)
        neighbors = get_geohash_neighbors(gh)
        self.assertIn("top", neighbors)
        self.assertIn("bottom", neighbors)
        self.assertIn("left", neighbors)
        self.assertIn("right", neighbors)
    
    def test_check_geohash_proximity_same_location(self):
        """Test proximity check for same location."""
        gh1 = encode_geohash(self.lat, self.lng, precision=8)
        gh2 = encode_geohash(self.lat + 0.0001, self.lng + 0.0001, precision=8)
        self.assertTrue(check_geohash_proximity(gh1, gh2, precision_level=6))
    
    def test_check_geohash_proximity_different_location(self):
        """Test proximity check for different locations."""
        gh1 = encode_geohash(self.lat, self.lng, precision=8)
        gh2 = encode_geohash(24.0, 91.0, precision=8)  # Far away
        self.assertFalse(check_geohash_proximity(gh1, gh2, precision_level=6))
    
    def test_is_potential_duplicate_location_true(self):
        """Test potential duplicate location detection - positive case."""
        existing_gh = encode_geohash(self.lat, self.lng, precision=8)
        result = is_potential_duplicate_location(
            self.lat + 0.0001, self.lng + 0.0001,
            existing_gh, proximity_precision=6
        )
        self.assertTrue(result)
    
    def test_is_potential_duplicate_location_false(self):
        """Test potential duplicate location detection - negative case."""
        existing_gh = encode_geohash(self.lat, self.lng, precision=8)
        result = is_potential_duplicate_location(
            24.0, 91.0,  # Far away
            existing_gh, proximity_precision=6
        )
        self.assertFalse(result)


class TestTemporalHashing(unittest.TestCase):
    """Tests for temporal hashing functions."""
    
    def setUp(self):
        """Set up test data."""
        self.now = datetime(2024, 1, 15, 10, 30, 0)
    
    def test_generate_temporal_hash_same_bucket(self):
        """Test that timestamps in the same bucket produce the same hash."""
        hash1 = generate_temporal_hash(self.now, bucket_minutes=60)
        hash2 = generate_temporal_hash(self.now + timedelta(minutes=20), bucket_minutes=60)
        self.assertEqual(hash1, hash2)
    
    def test_generate_temporal_hash_different_bucket(self):
        """Test that timestamps in different buckets produce different hashes."""
        hash1 = generate_temporal_hash(self.now, bucket_minutes=60)
        hash2 = generate_temporal_hash(self.now + timedelta(minutes=90), bucket_minutes=60)
        self.assertNotEqual(hash1, hash2)
    
    def test_check_temporal_proximity_within_tolerance(self):
        """Test temporal proximity check - within tolerance."""
        result = check_temporal_proximity(
            self.now, self.now + timedelta(minutes=20),
            tolerance_minutes=30
        )
        self.assertTrue(result)
    
    def test_check_temporal_proximity_outside_tolerance(self):
        """Test temporal proximity check - outside tolerance."""
        result = check_temporal_proximity(
            self.now, self.now + timedelta(minutes=40),
            tolerance_minutes=30
        )
        self.assertFalse(result)


class TestCombinedDuplicateDetection(unittest.TestCase):
    """Tests for combined duplicate detection."""
    
    def setUp(self):
        """Set up test data."""
        self.lat = 23.7461
        self.lng = 90.3742
        self.now = datetime(2024, 1, 15, 10, 30, 0)
        self.existing_gh = encode_geohash(self.lat, self.lng, precision=8)
    
    def test_generate_location_time_fingerprint(self):
        """Test fingerprint generation."""
        fp1 = generate_location_time_fingerprint(
            self.lat, self.lng, self.now
        )
        self.assertEqual(len(fp1), 32)
        
        # Same location and time bucket should produce same fingerprint
        fp2 = generate_location_time_fingerprint(
            self.lat + 0.0001, self.lng + 0.0001,
            self.now + timedelta(minutes=10)
        )
        self.assertEqual(fp1, fp2)
    
    def test_is_potential_duplicate_same_location_and_time(self):
        """Test duplicate detection - same location and time."""
        is_dup, reason = is_potential_duplicate(
            self.lat + 0.0001, self.lng + 0.0001, self.now,
            self.existing_gh, self.now - timedelta(minutes=10),
            location_precision=6, time_tolerance_minutes=30
        )
        self.assertTrue(is_dup)
        self.assertIn("Same location and time window", reason)
    
    def test_is_potential_duplicate_same_location_different_time(self):
        """Test duplicate detection - same location, different time."""
        is_dup, reason = is_potential_duplicate(
            self.lat + 0.0001, self.lng + 0.0001, self.now,
            self.existing_gh, self.now - timedelta(hours=2),
            location_precision=6, time_tolerance_minutes=30
        )
        self.assertTrue(is_dup)
        self.assertIn("Same location, different time", reason)
    
    def test_is_potential_duplicate_different_location(self):
        """Test duplicate detection - different location."""
        is_dup, reason = is_potential_duplicate(
            24.0, 91.0, self.now,  # Far away
            self.existing_gh, self.now - timedelta(minutes=10),
            location_precision=6, time_tolerance_minutes=30
        )
        self.assertFalse(is_dup)
        self.assertIsNone(reason)


class TestEXIFExtraction(unittest.TestCase):
    """Tests for EXIF metadata extraction."""
    
    def test_extract_metadata_from_bytes_no_exif(self):
        """Test extracting metadata from image without EXIF."""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        
        metadata = extract_metadata_from_bytes(buffer.getvalue())
        
        self.assertFalse(metadata["has_exif"])
        self.assertIsNone(metadata["gps_coordinates"])
        self.assertIsNone(metadata["timestamp"])
        self.assertEqual(metadata["image_dimensions"]["width"], 100)
        self.assertEqual(metadata["image_dimensions"]["height"], 100)
    
    def test_extract_metadata_invalid_bytes(self):
        """Test extracting metadata from invalid image bytes."""
        metadata = extract_metadata_from_bytes(b"not an image")
        self.assertFalse(metadata["has_exif"])
        self.assertIn("error", metadata)
    
    def test_compare_metadata_matching(self):
        """Test metadata comparison with matching data."""
        before = {
            "gps_coordinates": {"latitude": 23.7461, "longitude": 90.3742},
            "timestamp": "2024-01-15T10:00:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        after = {
            "gps_coordinates": {"latitude": 23.7462, "longitude": 90.3743},
            "timestamp": "2024-01-15T10:20:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        
        result = compare_metadata(before, after, gps_tolerance_meters=100, time_tolerance_minutes=30)
        
        self.assertTrue(result["location_match"])
        self.assertTrue(result["time_valid"])
        self.assertTrue(result["same_device"])
        self.assertEqual(result["verification_flags"], [])
    
    def test_compare_metadata_location_mismatch(self):
        """Test metadata comparison with location mismatch."""
        before = {
            "gps_coordinates": {"latitude": 23.7461, "longitude": 90.3742},
            "timestamp": "2024-01-15T10:00:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        after = {
            "gps_coordinates": {"latitude": 24.0, "longitude": 91.0},  # Far away
            "timestamp": "2024-01-15T10:20:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        
        result = compare_metadata(before, after, gps_tolerance_meters=100, time_tolerance_minutes=30)
        
        self.assertFalse(result["location_match"])
        self.assertTrue(any("Location mismatch" in flag for flag in result["verification_flags"]))
    
    def test_compare_metadata_time_mismatch(self):
        """Test metadata comparison with time mismatch."""
        before = {
            "gps_coordinates": {"latitude": 23.7461, "longitude": 90.3742},
            "timestamp": "2024-01-15T10:00:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        after = {
            "gps_coordinates": {"latitude": 23.7462, "longitude": 90.3743},
            "timestamp": "2024-01-15T12:00:00",  # 2 hours later
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        
        result = compare_metadata(before, after, gps_tolerance_meters=100, time_tolerance_minutes=30)
        
        self.assertFalse(result["time_valid"])
        self.assertTrue(any("Time difference too large" in flag for flag in result["verification_flags"]))
    
    def test_compare_metadata_after_before_timestamp(self):
        """Test metadata comparison where after photo is taken before the before photo."""
        before = {
            "gps_coordinates": {"latitude": 23.7461, "longitude": 90.3742},
            "timestamp": "2024-01-15T10:20:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        after = {
            "gps_coordinates": {"latitude": 23.7462, "longitude": 90.3743},
            "timestamp": "2024-01-15T10:00:00",  # Earlier than before
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        
        result = compare_metadata(before, after, gps_tolerance_meters=100, time_tolerance_minutes=30)
        
        self.assertFalse(result["time_valid"])
        self.assertTrue(any("taken before the before photo" in flag for flag in result["verification_flags"]))
    
    def test_compare_metadata_missing_gps(self):
        """Test metadata comparison with missing GPS data."""
        before = {
            "gps_coordinates": {"latitude": 23.7461, "longitude": 90.3742},
            "timestamp": "2024-01-15T10:00:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        after = {
            "gps_coordinates": None,  # No GPS
            "timestamp": "2024-01-15T10:20:00",
            "device_info": {"make": "Samsung", "model": "Galaxy S21"}
        }
        
        result = compare_metadata(before, after, gps_tolerance_meters=100, time_tolerance_minutes=30)
        
        self.assertIsNone(result["location_match"])
        self.assertTrue(any("Missing GPS data" in flag for flag in result["verification_flags"]))


if __name__ == "__main__":
    unittest.main()
