"""
Base Repository Pattern Implementation

This module provides a base repository class with common CRUD operations
that can be inherited by specific repository classes.
"""

import logging
from typing import Dict, Any, Optional, List, TypeVar, Generic, Type
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.config.database import db

logger = logging.getLogger(__name__)

# Generic type for model classes
T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Base repository class providing common database operations.
    
    This class implements the Repository pattern to centralize database
    operations and provide a consistent interface for data access.
    """
    
    def __init__(self, collection_name: str, model_class: Type[T]):
        """
        Initialize the repository with a collection name and model class.
        
        Args:
            collection_name: Name of the MongoDB collection
            model_class: The model class this repository handles
        """
        self.collection_name = collection_name
        self.collection = getattr(db, collection_name)
        self.model_class = model_class
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new document in the collection.
        
        Args:
            data: Dictionary containing document data
            
        Returns:
            Created document with generated ID
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            self.logger.info(f"Creating new {self.collection_name} document")
            
            # Add timestamps if not present
            if "created_at" not in data:
                data["created_at"] = datetime.utcnow()
            if "updated_at" not in data:
                data["updated_at"] = datetime.utcnow()
            
            # Insert document
            result = self.collection.insert_one(data)
            
            # Fetch and return the created document
            created_doc = self.collection.find_one({"_id": result.inserted_id})
            
            self.logger.info(f"Successfully created {self.collection_name} with ID: {result.inserted_id}")
            return created_doc
            
        except Exception as e:
            self.logger.error(f"Error creating {self.collection_name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create {self.collection_name}: {str(e)}"
            )
    
    def find_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a document by its ID.
        
        Args:
            document_id: String representation of the document ID
            
        Returns:
            Document if found, None otherwise
            
        Raises:
            HTTPException: If ID is invalid or query fails
        """
        try:
            # Convert string ID to ObjectId
            obj_id = ObjectId(document_id)
            
            self.logger.debug(f"Finding {self.collection_name} by ID: {document_id}")
            
            document = self.collection.find_one({"_id": obj_id})
            
            if document:
                self.logger.debug(f"Found {self.collection_name} with ID: {document_id}")
            else:
                self.logger.debug(f"No {self.collection_name} found with ID: {document_id}")
            
            return document
            
        except Exception as e:
            self.logger.error(f"Error finding {self.collection_name} by ID {document_id}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {self.collection_name} ID or query failed: {str(e)}"
            )
    
    def find_all(self, filter_dict: Optional[Dict[str, Any]] = None, 
                 skip: int = 0, limit: Optional[int] = None,
                 sort: Optional[List[tuple]] = None) -> List[Dict[str, Any]]:
        """
        Find all documents matching the filter criteria.
        
        Args:
            filter_dict: MongoDB filter dictionary
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            sort: List of sort criteria tuples (field, direction)
            
        Returns:
            List of matching documents
            
        Raises:
            HTTPException: If query fails
        """
        try:
            if filter_dict is None:
                filter_dict = {}
            
            self.logger.debug(f"Finding {self.collection_name} documents with filter: {filter_dict}")
            
            # Build query
            cursor = self.collection.find(filter_dict)
            
            # Apply sorting if provided
            if sort:
                cursor = cursor.sort(sort)
            
            # Apply pagination
            if skip > 0:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            
            documents = list(cursor)
            
            self.logger.debug(f"Found {len(documents)} {self.collection_name} documents")
            return documents
            
        except Exception as e:
            self.logger.error(f"Error finding {self.collection_name} documents: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve {self.collection_name} documents: {str(e)}"
            )
    
    def update(self, document_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update a document by its ID.
        
        Args:
            document_id: String representation of the document ID
            update_data: Dictionary containing fields to update
            
        Returns:
            Updated document if found, None otherwise
            
        Raises:
            HTTPException: If ID is invalid or update fails
        """
        try:
            # Convert string ID to ObjectId
            obj_id = ObjectId(document_id)
            
            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            self.logger.info(f"Updating {self.collection_name} with ID: {document_id}")
            
            # Update document
            result = self.collection.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                self.logger.warning(f"No {self.collection_name} found with ID: {document_id}")
                return None
            
            # Fetch and return updated document
            updated_doc = self.collection.find_one({"_id": obj_id})
            
            self.logger.info(f"Successfully updated {self.collection_name} with ID: {document_id}")
            return updated_doc
            
        except Exception as e:
            self.logger.error(f"Error updating {self.collection_name} with ID {document_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update {self.collection_name}: {str(e)}"
            )
    
    def delete(self, document_id: str) -> bool:
        """
        Delete a document by its ID.
        
        Args:
            document_id: String representation of the document ID
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            HTTPException: If ID is invalid or deletion fails
        """
        try:
            # Convert string ID to ObjectId
            obj_id = ObjectId(document_id)
            
            self.logger.info(f"Deleting {self.collection_name} with ID: {document_id}")
            
            # Delete document
            result = self.collection.delete_one({"_id": obj_id})
            
            if result.deleted_count == 0:
                self.logger.warning(f"No {self.collection_name} found with ID: {document_id}")
                return False
            
            self.logger.info(f"Successfully deleted {self.collection_name} with ID: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting {self.collection_name} with ID {document_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete {self.collection_name}: {str(e)}"
            )
    
    def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents matching the filter criteria.
        
        Args:
            filter_dict: MongoDB filter dictionary
            
        Returns:
            Number of matching documents
            
        Raises:
            HTTPException: If count fails
        """
        try:
            if filter_dict is None:
                filter_dict = {}
            
            count = self.collection.count_documents(filter_dict)
            
            self.logger.debug(f"Counted {count} {self.collection_name} documents")
            return count
            
        except Exception as e:
            self.logger.error(f"Error counting {self.collection_name} documents: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to count {self.collection_name} documents: {str(e)}"
            )
    
    def exists(self, filter_dict: Dict[str, Any]) -> bool:
        """
        Check if a document exists matching the filter criteria.
        
        Args:
            filter_dict: MongoDB filter dictionary
            
        Returns:
            True if document exists, False otherwise
        """
        try:
            document = self.collection.find_one(filter_dict)
            return document is not None
            
        except Exception as e:
            self.logger.error(f"Error checking {self.collection_name} existence: {str(e)}")
            return False 