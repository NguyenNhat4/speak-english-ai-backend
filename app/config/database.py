# Import the MongoClient class from pymongo to interact with MongoDB
from pymongo import MongoClient
# Import the centralized configuration
from app.config.settings import settings

# Create a MongoDB client instance using the centralized configuration
# This establishes a connection to the MongoDB server
client = MongoClient(settings.get_database_url())

# Access the specific database using the configuration
# 'db' will be the object we use to perform operations (e.g., insert, find) on this database
db = client[settings.database_name]