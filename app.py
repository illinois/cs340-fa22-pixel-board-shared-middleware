from os import getenv

from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, jsonify, make_response, render_template, request, send_file
from flask_socketio import SocketIO

from servers import ServerManager
from boards import BoardManager
from FrontendManager import FrontendManager

# Load the environment variables
load_dotenv()

# Connect to the database
mongo_client = MongoClient(getenv("MONGO_HOST") or "127.0.0.1")
db = mongo_client["project-pixel"]

# Create the server manager (manages PGs) and board manager (manages pixel boards)
board_manager = BoardManager(db)
server_manager = ServerManager(db, board_manager)
frontend_manager = FrontendManager(board=board_manager)
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
            return resp

    # Add the server and return the id
    id = server_manager.add_server(
        request.json["name"], request.json["author"])
    return jsonify({
        "id": id
    })


@app.route('/remove-pg', methods=['DELETE'])
def DELETE_remove_pg():
    server_manager.remove_server(request.json["id"])
    return jsonify({"success": True}), 200


@app.route('/update-pixel', methods=['PUT'])
def PUT_update_pixel():
    # Get pixel update
    update = request.json

    # Check if all required fields are present
    for requiredField in ["row", "col", "color", "id"]:
        if requiredField not in update:
            resp = make_response(jsonify({
                "success": False,
                "error": f"Required field `{requiredField}` not present.",
            }))
            resp.status_code = 400
            return resp

    # Check if the server is available to use
    server_timeout = server_manager.use_server(update["id"])

    # If the server isn't found, we reject the update
    if server_timeout < 0:
        resp = make_response(jsonify({
            "success": False,
            "error": "401 Unauthorized",
        }))
        resp.status_code = 401
        return resp

    # If the server isn't, we reject the update
    elif server_timeout != 0:
        resp = make_response(jsonify({
            "success": False,
            "error": "429 Too Many Requests",
            "rate": board_manager.get_pixel_rate()
        }))
        resp.headers["Retry-After"] = server_timeout
        resp.status_code = 429
        return resp

    # Otherwise, we apply to the board, emit the update to frontend users, and let the user know of its success
    row = update["row"]
    col = update["col"]
    color = update["color"]

    board_manager.update_current_board(row, col, color)
    sio.emit('pixel update', {
        'row': row,
        'col': col,
        'color': color
    })

    return jsonify({
        "success": True
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
        "pixel_rate": board_manager.get_pixel_rate()
    })


@app.route('/pixels', methods=['GET'])
def GET_pixels():
    # Get the current board and return just the pixels
    board = board_manager.get_current_board()
    # Check if the client has this cached
    if request.if_none_match.contains(board["hash"]):
        return "", 304
    resp = make_response(jsonify({
        "pixels": board["pixels"]
    }))
    # Add the etag
    resp.headers["ETag"] = board["hash"]
    return resp


@app.route('/timelapse', methods=['GET'])
def GET_timelapse():
    # Get the timelapse
    timelapse_path = board_manager.generate_gif()
    # Serve the file here
    return send_file(timelapse_path), 200


@app.route('/changeByClick', methods=['POST'])
def changeByClick():
    body = request.json
    # If no json file return 401
    if not body:
        return "No json file", 401

    # If requested fields are not privided return 402
    for required in ['row', 'col', 'color', 'id']:
        if body[required] == None:
            return f'{required} is missed in body', 402

    row = int(body['row'])
    col = int(body['col'])
    color = int(body['color'])
    id = body['id']

    # Pass to frontend_manager
    result = frontend_manager.updateChange(
        id=id, row=row, col=col, color=color)

    # If update is successful, trigger an event
    if result[1] == 200:
        sio.emit('pixel update', {
            'row': row,
            'col': col,
            'color': color
        })
    return result


@app.route('/servers', methods=['GET'])
def getServers():
    # Route for render server page
    servers = server_manager.cache
    sort_servers = sorted(servers, key=lambda e: e['author'])

    return render_template('server.html', data={"servers": sort_servers})


if __name__ == '__main__':
    sio.run(app, getenv("HOST") or "127.0.0.1",
            getenv("PORT") or 5000, debug=True)
