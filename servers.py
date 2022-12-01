from datetime import datetime, timedelta
from os import environ

from bson.objectid import ObjectId
from pymongo.database import Database

from boards import BoardManager


class ServerManager:
    def __init__(self, db: Database, board_manager: BoardManager):
        self.board_manager = board_manager

        self.collection = db["servers"]
        # In-memory cache of servers to avoid DB calls
        self.cache = list(self.collection.find({}))
        print(self.cache)

    def add_server(self, name, author):
        # Check if server is already there (same name and author)
        found = self.collection.find_one({"name": name, "author": author})

        # If it is, we just return the ID for that one; no need to create a new database entry
        if found:
            return str(found["_id"])

        # If not found, we create a new one and add it to the database
        pg = {
            "name": name,
            "author": author,
            "timeout_time": datetime.utcnow()  # Ensures the PG can immediately write
        }

        # Insert to DB
        id = str(self.collection.insert_one(pg).inserted_id)

        # Add to cache
        self.cache.append(pg)

        return id

    def remove_server(self, id):
        # Remove server from cache
        obj_id = ObjectId(id)
        self.cache = [x for x in self.cache if x["_id"] == obj_id]
        # Delete the server in the database
        self.collection.delete_one({"_id": ObjectId(id)})

    def use_server(self, id):
        obj_id = ObjectId(id)

        # Get the server from the cache
        found = next((x for x in self.cache if x["_id"] == obj_id), None)

        # If the server isn't in the cache, check the DB
        if not found:
            # Get the server (checking if it's in the database)
            found = self.collection.find_one({"_id": obj_id})

        # If the server isn't registered, return -1 (error)
        if not found:
            return -1

        # If the timeout hasn't passed yet, return time needed
        now = datetime.utcnow()
        if found["timeout_time"] > now:
            return (found["timeout_time"] - now).total_seconds()

        # Update the timeout_time and return 0 (no time needed)
        # In cache
        next_time = now + \
            timedelta(milliseconds=self.board_manager.get_pixel_rate())
        found["timeout_time"] = next_time
        # In DB
        self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"timeout_time": next_time}}
        )
        return 0

    def get_servers(self):

        return self.cache
