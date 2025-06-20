"""
ObjectId utility functions for MongoDB operations.

This module centralizes ObjectId conversion and validation to eliminate
duplication across repositories and services.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


def str_to_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    """
    Convert string to ObjectId with proper error handling.
    
    Args:
        id_str: String representation of ObjectId
        field_name: Name of the field for error messages
        
    Returns:
        ObjectId instance
        
    Raises:
        HTTPException: If conversion fails
    """
    if not id_str:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} cannot be empty"
        )
    
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format"
        )


def validate_object_ids(ids: List[str], field_name: str = "ID") -> List[ObjectId]:
    """
    Validate and convert multiple string IDs to ObjectIds.
    
    Args:
        ids: List of string IDs
        field_name: Name of the field for error messages
        
    Returns:
        List of ObjectId instances
        
    Raises:
        HTTPException: If any conversion fails
    """
    result = []
    for id_str in ids:
        result.append(str_to_object_id(id_str, field_name))
    return result


def mongo_doc_to_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB document to dictionary with string ID.
    
    Args:
        doc: MongoDB document
        
    Returns:
        Dictionary with _id converted to string id
    """
    if not doc:
        return doc
    
    # Create a copy to avoid modifying original
    result = dict(doc)
    
    # Convert _id to string id
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    
    return result


def mongo_docs_to_dicts(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert list of MongoDB documents to dictionaries with string IDs.
    
    Args:
        docs: List of MongoDB documents
        
    Returns:
        List of dictionaries with _id converted to string id
    """
    return [mongo_doc_to_dict(doc) for doc in docs]


def mongo_doc_to_schema(doc: Dict[str, Any], schema_cls: Type[T]) -> T:
    """
    Convert MongoDB document to Pydantic schema instance.
    
    Args:
        doc: MongoDB document
        schema_cls: Pydantic model class
        
    Returns:
        Schema instance
        
    Raises:
        HTTPException: If conversion fails
    """
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )
    
    try:
        # Convert MongoDB doc to dict with string ID
        doc_dict = mongo_doc_to_dict(doc)
        return schema_cls(**doc_dict)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert document to schema: {str(e)}"
        )


def prepare_update_data(update_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data by converting string IDs to ObjectIds where needed.
    
    Args:
        update_dict: Dictionary containing update data
        
    Returns:
        Dictionary with appropriate ObjectId conversions
    """
    result = dict(update_dict)
    
    # Common ID fields that should be converted to ObjectId
    id_fields = ["user_id", "conversation_id", "audio_id", "feedback_id", "target_id"]
    
    for field in id_fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = ObjectId(result[field])
            except Exception:
                # Keep as string if conversion fails - let validation handle it
                pass
    
    return result


def ensure_object_id(value: Union[str, ObjectId]) -> ObjectId:
    """
    Ensure value is an ObjectId, converting from string if necessary.
    
    Args:
        value: String or ObjectId
        
    Returns:
        ObjectId instance
        
    Raises:
        ValueError: If conversion fails
    """
    if isinstance(value, ObjectId):
        return value
    
    if isinstance(value, str):
        try:
            return ObjectId(value)
        except Exception as e:
            raise ValueError(f"Invalid ObjectId format: {value}") from e
    
    raise ValueError(f"Cannot convert {type(value)} to ObjectId")


def is_valid_object_id(id_str: str) -> bool:
    """
    Check if string is a valid ObjectId format.
    
    Args:
        id_str: String to validate
        
    Returns:
        True if valid ObjectId format, False otherwise
    """
    try:
        ObjectId(id_str)
        return True
    except Exception:
        return False 