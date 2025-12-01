"""Firebase Storage service for image uploads"""

import uuid
import os
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class FirebaseStorageService:
    """Service for handling image uploads to Firebase Storage"""

    def __init__(self):
        """Initialize Firebase Storage service"""
        self.bucket_name = settings.FIREBASE_STORAGE_BUCKET
        self.credentials_path = settings.FIREBASE_CREDENTIALS_PATH
        self.bucket = None
        self._initialized = False

        # Only initialize if credentials are configured
        if self.credentials_path and self.bucket_name:
            self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            import firebase_admin
            from firebase_admin import credentials, storage

            if not firebase_admin._apps:
                cred = credentials.Certificate(self.credentials_path)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': self.bucket_name
                })

            self.bucket = storage.bucket()
            self._initialized = True
        except Exception as e:
            print(f"Firebase initialization failed (optional for hackathon): {e}")
            self._initialized = False

    def is_available(self) -> bool:
        """Check if Firebase storage is available"""
        return self._initialized and self.bucket is not None

    async def upload_image(
        self,
        file: UploadFile,
        folder: str = "uploads",
        user_id: Optional[str] = None
    ) -> dict:
        """
        Upload an image to Firebase Storage.

        Args:
            file: The uploaded file
            folder: Folder path in storage
            user_id: Optional user ID for organizing uploads

        Returns:
            dict with url, filename, content_type, size_bytes
        """
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file.content_type} not allowed. Allowed: {allowed_types}"
            )

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size (max 10MB)
        max_size = settings.MAX_UPLOAD_SIZE
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {max_size / (1024*1024):.1f}MB"
            )

        # Generate unique filename
        ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"{uuid.uuid4()}.{ext}"
        
        # Build storage path
        if user_id:
            storage_path = f"{folder}/{user_id}/{unique_filename}"
        else:
            storage_path = f"{folder}/{unique_filename}"

        # If Firebase is not available, return a mock URL (for hackathon/testing)
        if not self.is_available():
            mock_url = f"https://storage.example.com/{storage_path}"
            return {
                "url": mock_url,
                "filename": unique_filename,
                "content_type": file.content_type,
                "size_bytes": file_size
            }

        try:
            # Upload to Firebase Storage
            blob = self.bucket.blob(storage_path)
            blob.upload_from_string(content, content_type=file.content_type)

            # Make the file publicly accessible
            blob.make_public()

            return {
                "url": blob.public_url,
                "filename": unique_filename,
                "content_type": file.content_type,
                "size_bytes": file_size
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image: {str(e)}"
            )

    async def delete_image(self, file_path: str) -> bool:
        """
        Delete an image from Firebase Storage.

        Args:
            file_path: Path to the file in storage

        Returns:
            True if deleted successfully
        """
        if not self.is_available():
            return True  # Mock success for hackathon

        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Failed to delete image: {e}")
            return False


# Singleton instance
_storage_service: Optional[FirebaseStorageService] = None


def get_storage_service() -> FirebaseStorageService:
    """Get or create storage service singleton"""
    global _storage_service
    if _storage_service is None:
        _storage_service = FirebaseStorageService()
    return _storage_service
