"""QR Code service for kabadiwala validation"""

import uuid
import io
import base64
from typing import Optional
from datetime import datetime, timedelta

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


class QRCodeService:
    """Service for QR code generation and validation"""

    @staticmethod
    def generate_kabadiwala_qr(
        user_id: str,
        user_name: str,
        include_timestamp: bool = True
    ) -> dict:
        """
        Generate a QR code for kabadiwala verification.

        Args:
            user_id: The kabadiwala's user ID
            user_name: The kabadiwala's name
            include_timestamp: Whether to include timestamp in QR data

        Returns:
            dict with qr_code_url (base64), qr_data, expires_at
        """
        # Build QR data string
        timestamp = datetime.utcnow().isoformat() if include_timestamp else ""
        qr_data = f"kabadiwala:{user_id}:{timestamp}:verify"

        if not QR_AVAILABLE:
            # Return mock data if qrcode library not installed
            return {
                "qr_code_url": f"data:image/png;base64,MOCK_QR_CODE_{user_id}",
                "qr_data": qr_data,
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat() if include_timestamp else None
            }

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            "qr_code_url": f"data:image/png;base64,{base64_image}",
            "qr_data": qr_data,
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat() if include_timestamp else None
        }

    @staticmethod
    def generate_transaction_qr(
        transaction_id: str,
        listing_id: str,
        amount: float
    ) -> dict:
        """
        Generate a QR code for transaction verification.

        Args:
            transaction_id: The transaction ID
            listing_id: The listing ID
            amount: Transaction amount

        Returns:
            dict with qr_code_url (base64), qr_data
        """
        qr_data = f"transaction:{transaction_id}:{listing_id}:{amount}:confirm"

        if not QR_AVAILABLE:
            return {
                "qr_code_url": f"data:image/png;base64,MOCK_QR_CODE_TXN_{transaction_id}",
                "qr_data": qr_data,
                "expires_at": None
            }

        qr = qrcode.QRCode(
            version=1,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            "qr_code_url": f"data:image/png;base64,{base64_image}",
            "qr_data": qr_data,
            "expires_at": None
        }

    @staticmethod
    def parse_qr_data(qr_data: str) -> Optional[dict]:
        """
        Parse QR code data string.

        Args:
            qr_data: The scanned QR data string

        Returns:
            Parsed data dict or None if invalid
        """
        try:
            parts = qr_data.split(':')

            if len(parts) < 3:
                return None

            qr_type = parts[0]

            if qr_type == "kabadiwala":
                return {
                    "type": "kabadiwala",
                    "user_id": parts[1],
                    "timestamp": parts[2] if len(parts) > 2 and parts[2] else None,
                    "action": parts[3] if len(parts) > 3 else "verify"
                }

            elif qr_type == "transaction":
                return {
                    "type": "transaction",
                    "transaction_id": parts[1],
                    "listing_id": parts[2],
                    "amount": float(parts[3]) if len(parts) > 3 else 0,
                    "action": parts[4] if len(parts) > 4 else "confirm"
                }

            return None

        except Exception:
            return None


# Singleton instance
_qr_service: Optional[QRCodeService] = None


def get_qr_service() -> QRCodeService:
    """Get or create QR code service singleton"""
    global _qr_service
    if _qr_service is None:
        _qr_service = QRCodeService()
    return _qr_service
