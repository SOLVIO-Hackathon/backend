"""Routing service using OpenStreetMap/OSRM for waste disposal routing"""

import httpx
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class RouteStep:
    """A step in the route"""
    instruction: str
    distance_meters: float
    duration_seconds: float
    maneuver: Optional[str] = None


@dataclass
class RouteResult:
    """Result from routing calculation"""
    distance_km: float
    duration_minutes: float
    route_geometry: str  # Encoded polyline
    steps: List[RouteStep]


class RoutingService:
    """Service for routing using OpenStreetMap/OSRM"""

    # Public OSRM demo server (use your own for production)
    OSRM_BASE_URL = "https://router.project-osrm.org"

    @staticmethod
    async def get_route(
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        profile: str = "driving"
    ) -> Optional[RouteResult]:
        """
        Get routing directions from origin to destination.

        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            profile: Routing profile (driving, walking, cycling)

        Returns:
            RouteResult or None if routing fails
        """
        # OSRM uses lng,lat order
        coordinates = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        url = f"{RoutingService.OSRM_BASE_URL}/route/v1/{profile}/{coordinates}"

        params = {
            "overview": "full",
            "geometries": "polyline",
            "steps": "true"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    logger.warning("OSRM routing failed with status: %d", response.status_code)
                    return None

                data = response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    return None

                route = data["routes"][0]

                # Parse steps
                steps = []
                for leg in route.get("legs", []):
                    for step in leg.get("steps", []):
                        steps.append(RouteStep(
                            instruction=step.get("maneuver", {}).get("instruction", ""),
                            distance_meters=step.get("distance", 0),
                            duration_seconds=step.get("duration", 0),
                            maneuver=step.get("maneuver", {}).get("type")
                        ))

                return RouteResult(
                    distance_km=route["distance"] / 1000,
                    duration_minutes=route["duration"] / 60,
                    route_geometry=route["geometry"],
                    steps=steps
                )

        except Exception as e:
            logger.error("Routing error: %s", e)
            return None

    @staticmethod
    async def get_distance_matrix(
        origin: Tuple[float, float],
        destinations: List[Tuple[float, float]]
    ) -> Optional[List[dict]]:
        """
        Get distances from origin to multiple destinations.

        Args:
            origin: (latitude, longitude) tuple
            destinations: List of (latitude, longitude) tuples

        Returns:
            List of dicts with distance_km and duration_minutes
        """
        if not destinations:
            return []

        # Build coordinates string for OSRM table service
        coords = [f"{origin[1]},{origin[0]}"]  # lng,lat
        for dest in destinations:
            coords.append(f"{dest[1]},{dest[0]}")

        coordinates = ";".join(coords)
        url = f"{RoutingService.OSRM_BASE_URL}/table/v1/driving/{coordinates}"

        params = {
            "sources": "0",  # Origin is first coordinate
            "annotations": "distance,duration"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return None

                data = response.json()

                if data.get("code") != "Ok":
                    return None

                distances = data.get("distances", [[]])[0]
                durations = data.get("durations", [[]])[0]

                results = []
                # Skip first element (origin to itself)
                for i in range(1, len(distances)):
                    results.append({
                        "distance_km": distances[i] / 1000 if distances[i] else None,
                        "duration_minutes": durations[i] / 60 if durations[i] else None
                    })

                return results

        except Exception as e:
            logger.error("Distance matrix error: %s", e)
            return None

    @staticmethod
    def decode_polyline(polyline: str) -> List[Tuple[float, float]]:
        """
        Decode a polyline string into coordinates.

        Args:
            polyline: Encoded polyline string

        Returns:
            List of (latitude, longitude) tuples
        """
        coordinates = []
        index = 0
        lat = 0
        lng = 0

        while index < len(polyline):
            # Decode latitude
            shift = 0
            result = 0
            while True:
                b = ord(polyline[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat

            # Decode longitude
            shift = 0
            result = 0
            while True:
                b = ord(polyline[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng

            coordinates.append((lat / 1e5, lng / 1e5))

        return coordinates


# Singleton instance
_routing_service: Optional[RoutingService] = None


def get_routing_service() -> RoutingService:
    """Get or create routing service singleton"""
    global _routing_service
    if _routing_service is None:
        _routing_service = RoutingService()
    return _routing_service
