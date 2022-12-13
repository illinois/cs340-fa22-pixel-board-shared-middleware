from os import getenv
import os
import json

from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, jsonify, make_response, render_template, request, send_file
from flask_socketio import SocketIO

from servers import ServerManager
from boards import BoardManager

# Load the environment variables
load_dotenv()

# Connect to the database
mongo_client = MongoClient(getenv("MONGO_HOST") or "127.0.0.1")
db = mongo_client["project-pixel"]

# Create the server manager (manages PGs) and board manager (manages pixel boards)
board_manager = BoardManager(db)
server_manager = ServerManager(db, board_manager)

# Gather secrets
if os.path.exists("secrets.txt"):
    with open("secrets.txt") as f:
        secrets = f.readlines()
    secrets = set([secret.strip() for secret in secrets])
else:
    secrets = None

# Get app context
app = Flask(__name__)
app.config['SECRET_KEY'] = getenv("SECRET_KEY") or "This is not secret."

# Create a SocketIO app for
sio = SocketIO(app, cors_allowed_origins="*")

# Serving Frontend


@app.route('/', methods=['GET'])
def GET_index():
    '''Route for "/" (frontend)'''
    return render_template("index.html")

@app.route('/admin/', methods=['GET'])
def GET_admin():
    return render_template("admin.html")


# Middleware Methods
@app.route('/register-pg', methods=['PUT'])
def PUT_register_pg():
    # Check if all required fields are present
    for requiredField in ["name", "author", "secret"]:
        if requiredField not in request.json:
            resp = make_response(jsonify({
                "success": False,
                "error": f"Required field `{requiredField}` not present.",
            }))
            resp.status_code = 400
            print(resp)
            return resp

    # Ensure that secret is in the list of secrets
    if secrets and request.json["secret"] not in secrets:
        resp = make_response(jsonify({
            "success": False,
            "error": f"Secret was not in list of valid secrets!",
        }))
        resp.status_code = 401
        print(resp)
        return resp

    # Add the server and return the id
    id = server_manager.add_server(request.json["name"], request.json["author"], request.json["secret"])
    return jsonify({"id": id})


VALIDATE_PG_REQUEST_FOR_PIXEL_UPDATE = 1
VALIDATE_PG_REQUEST_FOR_BOARD = 2

def validate_PG_request(requestFor, requestJSON):
    if requestFor == VALIDATE_PG_REQUEST_FOR_PIXEL_UPDATE:
        requiredFields = ["row", "col", "color", "id"]
    else:
        requiredFields = ["id"]

    # Check if all required fields are present
    for requiredField in requiredFields:
        if requiredField not in requestJSON:
            resp = make_response(jsonify({
                "success": False,
                "error": f"Required field `{requiredField}` not present.",
            }))
            resp.status_code = 400
            return resp
    
    # Check if the server is available to use
    if requestFor == VALIDATE_PG_REQUEST_FOR_PIXEL_UPDATE:
        server_timeout = server_manager.use_server(requestJSON["id"])
    else:
        server_timeout = server_manager.use_server(requestJSON["id"], updateTimeout=False)

    # If the server isn't found, we reject the update
    if server_timeout < 0:
        resp = make_response(jsonify({
            "success": False,
            "error": "401 Unauthorized",
        }))
        resp.status_code = 401
        return resp

    # If the server is still in cooldown, we reject the update
    elif server_timeout != 0:
        resp = make_response(jsonify({
            "success": False,
            "error": "429 Too Many Requests",
            "rate": board_manager.get_pixel_rate(),
            "timeoutRemaining": server_timeout,
        }))
        resp.headers["Retry-After"] = server_timeout
        resp.status_code = 429
        return resp

    return None



@app.route('/update-pixel', methods=['PUT'])
def PUT_update_pixel():
    # Get pixel update
    update = request.json

    # Validate the PG is valid and can update the pixel:
    validationFailure = validate_PG_request(VALIDATE_PG_REQUEST_FOR_PIXEL_UPDATE, update)
    if validationFailure:
        print(validationFailure)
        return validationFailure

    # Otherwise, we apply to the board, emit the update to frontend users, and let the user know of its success
    row = int(update["row"])
    col = int(update["col"])
    color = int(update["color"])
    id = update["id"]
    author = server_manager.get_author_by_id(id)

    # Validate a valid color index:
    if color < 0 or color >= len(board_manager.get_palette()):
        resp = make_response(jsonify({
            "success": False,
            "error": "Invalid Color",
        }))
        resp.status_code = 400
        return resp

    stats = board_manager.update_current_board(row, col, color, author, server_manager, id)
    
    # Notify all socket connections of update:
    if stats:
        sio.emit('pixel update', {
            'row': row,
            'col': col,
            'color': color,
            'pixels': stats["pixels"],
            'unnecessaryPixels': stats["unnecessaryPixels"],
            'author': author
        })

        # Return success:
        return jsonify({
            "success": True,
            "rate": board_manager.get_pixel_rate()
        }), 200
    else:
        # Return success:
        return jsonify({
            "success": True,
            "currentlyDisabled": True,
            "rate": board_manager.get_pixel_rate()
        }), 200


@app.route('/settings', methods=['GET'])
def GET_settings():
    # Get the current board
    board = board_manager.get_current_board()
    # Return the settings data
    return jsonify({
        "width": board["width"],
        "height": board["height"],
        "palette": board["palette"],
        "enabled": board_manager.get_enabled_state(),
        "stats": board_manager.get_stats(),
        "currentPixelRate": board_manager.get_pixel_rate(),
    })


def return_board():
    # Get the current board and return just the pixels
    board = board_manager.get_current_board()
    resp = make_response(jsonify({ "pixels": board["pixels"] }))
    return resp


@app.route('/pixels', methods=['GET'])
def GET_pixels():
    # Validate the PG is valid and can update the pixel:
    validationFailure = validate_PG_request(VALIDATE_PG_REQUEST_FOR_BOARD, request.json)
    if validationFailure:
        return validationFailure

    return return_board()

@app.route('/frontend-pixels', methods=['GET'])
def GET_frontend_pixels():
    board = board_manager.get_current_board()
    return make_response(jsonify({
        "pixels": board["pixels"],
        "authors": board["lastModify"]
    }))


# @app.route('/timelapse', methods=['GET'])
# def GET_timelapse():
#     # Get the timelapse
#     timelapse_path = board_manager.generate_gif()
#     # Serve the file here
#     return send_file(timelapse_path), 200

@app.route('/servers', methods=['GET'])
def GET_servers():
    # Route for render server page
    servers = server_manager.cache
    sort_servers = sorted(servers, key=lambda e: e['author'])

    return render_template('server.html', data={"servers": sort_servers})


@app.route('/changePixelRate', methods=['POST'])
def POST_change_pixel_rate():
    # Check required field
    for requiredField in ["new_rate", "token"]:
        if requiredField not in request.json:
            resp = make_response(jsonify({
                "success": False,
                "error": f"Required field `{requiredField}` not present.",
            }))
            resp.status_code = 400
            print(resp)
            return resp

    # Check token
    if getenv("ADMIN_TOKEN") == request.json['token']:
        board_manager.change_pixel_rate(int(request.json['new_rate']))
        return "Success", 200
    else:
        return "Unauthorized", 401


@app.route('/enableBoard', methods=['POST'])
def POST_enableBoard():
    # Allow enable only with ADMIN_TOKEN
    if getenv("ADMIN_TOKEN") and getenv("ADMIN_TOKEN") == request.json['token']:
        board_manager.set_enabled_state(True)
        return "Success", 200
    else:
        return "Unauthorized", 401


if __name__ == '__main__':
    sio.run(app, getenv("HOST") or "127.0.0.1",
            getenv("PORT") or 5000, debug=True)
