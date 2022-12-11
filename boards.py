from os import getenv, path, makedirs, environ
from datetime import datetime
import hashlib
import random

from bson.objectid import ObjectId
from pymongo.database import Database
from dotenv import load_dotenv
import numpy as np

# Load the environment variables, with default fallback values
load_dotenv()
INITIAL_WIDTH = int(getenv("INITIAL_WIDTH") or 100)
INITIAL_HEIGHT = int(getenv("INITIAL_HEIGHT") or 100)

if getenv("INITIAL_PALETTE"):
    INITIAL_PALETTE = ["#" + x for x in getenv("INITIAL_PALETTE").split(",")]
else:
    INITIAL_PALETTE = random.choice([
        ["#a7f542", "#7EA7DF", "#f3bcf5", "#6F6E69",
            "#F8F075", "#9ff5ec", "#E5E5E5"],
        ["#B3E2E2", "#7EA7DF", "#F0A099", "#6F6E69",
            "#F8F075", "#FFFFFF", "#E5E5E5"],
        ["#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF"],
        ["#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FF69B4", "#FFFF00", "#FFA500", "#FFC0CB",  "#800080", "#000000", "#808080",
            "#FF00FF", "#00FFFF", "#40E0D0", "#ADD8E6", "#90EE90", "#FFB6C1", "#FFFFE0", "#D3D3D3", "#AA7A6F", "#BA648C", "#164F82"],

        # Reddit r/place in 2022:
        ["#ffffff", "#d4d7d9", "#898d90", "#000000", "#9c6926", "#ff99aa", "#b44ac0", "#811e9f",
            "#51e9f4", "#3690ea", "#2450a4", "#7eed56", "#00a368", "#ffd635", "#ffa800", "#ff4500"],
    ])

TEMP_DIR = getenv("TEMP_DIR") or "tmp"
makedirs(TEMP_DIR, exist_ok=True)

PIXEL_RATE = int(getenv("PIXEL_RATE") or random.randint(100, 1000))

BOARD_DISABLED = False
if getenv("START_DISABLED"):
    BOARD_DISABLED = True

class BoardManager:
    def __init__(self, db: Database):
        self.board = db["boards"]
        self.updates = db["updates"]
        self.hash = hashlib.md5()

        self.statsDB = db["stats"]
        self.stats = self.statsDB.find_one({}) or {"pixels": 0, "unnecessaryPixels": 0}

        # If we don't have a board, create an empty one
        current_board = self.board.find_one({"current": True})
        if not current_board:
            current_board = self.initialize_new_board(INITIAL_WIDTH,
                                                      INITIAL_HEIGHT,
                                                      INITIAL_PALETTE)

        # In-memory cache of the current board state
        self.cache = current_board

    def get_pixel_rate(self):
        return PIXEL_RATE

    def get_current_board(self):
        # Return the current board
        if self.cache:
            # From cache
            return self.cache
        else:
            # From DB
            return self.board.find_one({"current": True})

    # Updates = [{row: int, col: int, color: int}]
    def update_current_board_by_list(self, updates, serverManager, id):
        # Update cache if we need to
        if not self.cache:
            self.cache = self.board.find_one({"current": True})

        if BOARD_DISABLED:
            return None

        # Collect statistics:
        for update in updates:
            self.stats["pixels"] = self.stats["pixels"] + 1
            if self.cache["pixels"][update["row"]][update["col"]] == update["color"]:
                serverManager.update_pixel_count(id, necessaryPixel=False)
                self.stats["unnecessaryPixels"] = self.stats["unnecessaryPixels"] + 1
            else:
                serverManager.update_pixel_count(id, necessaryPixel=True)

            self.statsDB.update_one({}, {"$set": self.stats})

        # Apply pixel updates
        for update in updates:
            self.cache["pixels"][update["row"]][update["col"]] = update["color"]
            self.cache["lastModify"][update["row"]][update["col"]] = update["author"]

        # Update board in database
        self.board.update_one(
            {"current": True}, {"$set": {"pixels": self.cache["pixels"],"lastModify":self.cache["lastModify"]}}
        )

        # Update the board hash
        self.update_hash(self.cache["palette"], self.cache["pixels"])
        self.cache["hash"] = self.hash.hexdigest()

        # Add board updates to database collection
        now = datetime.utcnow()
        for update in updates:
            update["time"] = now
        self.updates.insert_many(updates)

        return self.stats

    def update_current_board(self, row, col, color, author, serverManager, id):
        return self.update_current_board_by_list(
            [{"row": row, "col": col, "color": color, "author": author}],
            serverManager,
            id
        )

    def initialize_new_board(self, width, height, palette):
        # Create a blank board
        board = {
            "current": True,
            "width": width,
            "height": height,
            "palette": palette,
            "pixels": [[0 for _ in range(width)] for _ in range(height)],
            "lastModify": [["" for _ in range(width)] for _ in range(height)]
        }
        # Hash the empty board
        self.update_hash(palette, board["pixels"])
        board["hash"] = self.hash.hexdigest()

        # Insert to DB
        self.board.insert_one(board)

        # Return the board (for the cache to use)
        return board

    def update_hash(self, palette, pixels):
        palette_string = ''.join(palette)
        pixels_strings = [''.join(map(str, row)) for row in pixels]
        pixel_string = ''.join(pixels_strings)
        self.hash.update((palette_string + pixel_string).encode())

    def generate_gif(self):
        from PIL import Image
        pixels = np.array(
            [[self.__get_rgb_color(0) for _ in range(INITIAL_WIDTH)]
             for _ in range(INITIAL_HEIGHT)],
            dtype=np.uint8
        )

        im = Image.fromarray(pixels)
        frames = []

        # Get the list of updates from the database
        updates = self.updates.find({}).sort("time")
        for update in updates:
            pixels[update["row"], update["col"]
                   ] = self.__get_rgb_color(update["color"])
            frame = Image.fromarray(pixels)
            frames.append(frame)

        # Now create the GIF and save it to a temp file, returning the path
        temp_path = path.join(TEMP_DIR, "timelapse.gif")
        im.save(temp_path, save_all=True,
                append_images=frames, duration=10, loop=0)
        return temp_path

    def __get_rgb_color(self, index):
        hex_color = INITIAL_PALETTE[index]
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return (r, g, b)

    def change_pixel_rate(self, new_rate: int):
        global PIXEL_RATE
        PIXEL_RATE = new_rate
        return PIXEL_RATE

    def set_enabled_state(self, is_enabled):
        global BOARD_DISABLED

        if is_enabled:
            BOARD_DISABLED = False
        else:
            BOARD_DISABLED = True

        return BOARD_DISABLED

    def get_enabled_state(self):
        global BOARD_DISABLED
        return not BOARD_DISABLED

    def get_stats(self):
        return self.stats
