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

    def get_author_by_id(self, id):
        # helper function for frontend show last modification
        if id == 'no author':
            return 'no author'
        found = self.collection.find_one(ObjectId(id))
        if found:
            return found["name"] + " (" + found["author"] + ")"
        else:
            return "id not found"

    def add_server(self, name, author, secret):
        # Check if server is already there (same secret)
        found = self.collection.find_one({"secret": secret})

        # If it is, we just return the ID for that one; no need to create a new database entry
        if found:
            self.collection.update_one(
                {"secret": secret},
                {"$set": {"name": name, "author": author}}
            )

            for pg in self.cache:
                if secret == pg["secret"]:
                    pg["name"] = name
                    pg["author"] = author
                    break

            return str(found["_id"])

        # If not found, we create a new one and add it to the database
        pg = {
            "name": name,
            "author": author,
            "secret": secret,
            "pixels": 0,
            "unnecessaryPixels": 0,
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

    def fetchServerDataByID(self, id):
        obj_id = ObjectId(id)

        # Get the server from the cache
        serverData = next((x for x in self.cache if x["_id"] == obj_id), None)

        # If the server isn't in the cache, check the DB
        if not serverData:
            # Get the server (checking if it's in the database)
            serverData = self.collection.find_one({"_id": obj_id})

        # If the server isn't registered, return None
        if not serverData:
            return None
        
        # Otherwise, return the server data:
        return serverData

    def use_server(self, id, updateTimeout=True):
        serverData = self.fetchServerDataByID(id)

        # If the server isn't registered, return -1 (error)
        if not serverData:
            return -1

        # If the timeout hasn't passed yet, return time needed
        now = datetime.utcnow()
        if serverData["timeout_time"] > now:
            return (serverData["timeout_time"] - now).total_seconds()

        # Update the timeout_time when requested
        if updateTimeout:
            # In cache
            next_time = now + timedelta(milliseconds=self.board_manager.get_pixel_rate())
            serverData["timeout_time"] = next_time
            # In DB
            self.collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"timeout_time": next_time}}
            )

        # Return valid time for update (0ms)
        return 0

    def update_pixel_count(self, id, necessaryPixel=True):
        serverData = self.fetchServerDataByID(id)        
        if serverData:
            # cache update:
            if "pixels" not in serverData:
                serverData["pixels"] = 0
            if "unnecessaryPixels" not in serverData:
                serverData["unnecessaryPixels"] = 0

            serverData["pixels"] = serverData["pixels"] + 1
            if not necessaryPixel:
                serverData["unnecessaryPixels"] = serverData["unnecessaryPixels"] + 1

            # db update:
            self.collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {
                    "pixels": serverData["pixels"],
                    "unnecessaryPixels": serverData["unnecessaryPixels"],
                }}
            )

    def get_servers(self):
        return self.cache
