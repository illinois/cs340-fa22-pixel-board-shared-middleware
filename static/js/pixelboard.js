var _settings = undefined;
var _canvas = undefined;
var _sio = undefined;
var _middlewareID = undefined;
var _enableToken = undefined;
var _colorChoice = 0;
var _previousChoice = 0;
let _frontend_timeout = 0;
var _pixels = undefined;
var _authors = undefined;

const ZOOM_SCALE = 6;

// Fetch the settings:
fetch("/settings")
.then((response) => response.json())
.then((settings) => {
  _settings = settings;
  initBoard();
})

// Save secret:
var _frontend_token = localStorage.getItem('frontend-token');
if (_frontend_token) {
  document.getElementById("pg_secret").value = _frontend_token;
}

let _lastEvent = undefined;
let mouseoverEvent = function(e) {
  function getCursorPosition(canvas, event) {
    var elemLeft = canvas.offsetLeft + canvas.clientLeft;
    var elemTop = canvas.offsetTop + canvas.clientTop;
    x = parseInt((event.pageX - elemLeft) / ZOOM_SCALE);
    y = parseInt((event.pageY - elemTop) / ZOOM_SCALE);
    return [x, y];
  }

  if (e) {
    e.preventDefault();
    _lastEvent = e;
  } else {
    e = _lastEvent;
  }
  var [col,row] = getCursorPosition(canvas, e);
  const hidden = document.getElementById('mouse_over');
  hidden.style.visibility = 'visible';
  var tmpcol = e.clientX + 15;
  var tmprow = e.clientY + 15;
  hidden.style.position = "absolute";
  hidden.style.left = `${tmpcol}px`;
  hidden.style.top = `${tmprow}px`;

  let getRowHTML = function(row, col) {
    html = `<div class="g1">`;
    if (row < 0 || row >= _settings.height) {
      html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      html += `<div class="g4" style="background-color: white;">&mdash;</div>`;          
    } else {
      if (col > 1) {
        html += `<div class="g4" style="background-color: ${_settings.palette[_pixels[row][col - 2]]};">&nbsp;</div>`;
      } else {
        html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      }

      if (col > 0) {
        html += `<div class="g4" style="background-color: ${_settings.palette[_pixels[row][col - 1]]};">&nbsp;</div>`;
      } else {
        html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      }

      html += `<div class="g4" style="background-color: ${_settings.palette[_pixels[row][col]]};">&nbsp;</div>`;

      if (col + 1 < _settings.width) {
        html += `<div class="g4" style="background-color: ${_settings.palette[_pixels[row][col + 1]]};">&nbsp;</div>`;
      } else {
        html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      }

      if (col + 2 < _settings.width) {
        html += `<div class="g4" style="background-color: ${_settings.palette[_pixels[row][col + 2]]};">&nbsp;</div>`;
      } else {
        html += `<div class="g4" style="background-color: white;">&mdash;</div>`;
      }      
    }
    html += `</div>`;
    return html;
  }

  let html = `<div class="grid">`;
  html += getRowHTML(row - 2, col);
  html += getRowHTML(row - 1, col);
  html += getRowHTML(row, col);
  html += getRowHTML(row + 1, col);
  html += getRowHTML(row + 2, col);
  html += `</div>`;


  hidden.innerHTML =`
  ${html}
  Pixel Color: ${_settings.palette[_pixels[row][col]]}
  <div class="small">Row: ${row}, Column: ${col}</div>
  <div class="small">${_authors[row][col]}</div>
  `;
  /*
  fetch(`/getPixelAuthor/${col}/${row}`)
  .then((response) => response.json())
  .then((data) => {

  })
  */
}


// Initialize the canvas:
let initBoard = function() {
  _canvas = document.createElement("canvas");
  _canvas.height = (_settings.height - 1) * ZOOM_SCALE;
  _canvas.width = (_settings.width - 1) * ZOOM_SCALE;
  _canvas.id = "canvas"
  _canvas.getContext("2d").scale(ZOOM_SCALE, ZOOM_SCALE);

  document.getElementById("pixelboard").appendChild(_canvas);

  // Load the current board edits onto this instance of the canvas:
  fetch("/frontend-pixels")
  .then((response) => response.json())
  .then((data) => {
    let ctx = _canvas.getContext("2d");
    let pixels = _pixels = data.pixels;
    _authors = data.authors;

    for (let y = 0; y < pixels.length; y++) {
      for (let x = 0; x < pixels[y].length; x++) {
        const paletteIndex = pixels[y][x];
        const color = _settings.palette[paletteIndex];

        ctx.fillStyle = color;
        ctx.fillRect(x, y, 1, 1);
      }
    }

    // Future updates are via SocketIO
    _sio = io(`ws://${window.location.host}`) //Initialized WS client

    // Automatically updates pixel data upon receiving message from server
    _sio.on('pixel update', function(msg){
      const x = msg['col'];
      const y = msg['row'];
      const color_idx = +msg['color'];
      const author = msg['author'];

      _pixels[y][x] = color_idx;
      _authors[y][x] = author;
      const color = _settings.palette[color_idx];

      let ctx = _canvas.getContext("2d");
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 1, 1);

      const hidden = document.getElementById('mouse_over');
      if (hidden.style.visibility != 'hidden') {
        mouseoverEvent();
      }

      document.getElementById("statsDisplay").innerHTML = `${msg["pixels"]} pixels generated (${msg["unnecessaryPixels"]} unnecessary, ${(100 * msg["unnecessaryPixels"] / msg["pixels"]).toFixed(2)}%)`
    })

    // Hover: 
    const canvas = document.getElementById('canvas')

    canvas.addEventListener('mousemove', mouseoverEvent);
    canvas.addEventListener('mouseout', (event) => {
      const hidden = document.getElementById('mouse_over');
      hidden.style.visibility = 'hidden';
    });
  })
};

let initializeColorSelector = function() {
  // Initialize the color selector
  var colorSelect = document.getElementById("colorSelector");

  for(var i = 0; i < _settings.palette.length; i++) {
    var option = document.createElement("div")
    option.style.backgroundColor = _settings.palette[i]
    option.setAttribute('value', i)
    option.style.height = '20px'
    option.style.width = '42px'
    option.style.marginLeft = '2px'
    option.style.marginRight = '2px'
    option.style.display = 'inline-block'
    if (i == _colorChoice) {
      option.style.outline = "solid blue 3px";
      _previousChoice = option;
    }

    option.addEventListener('click', function(event) {
      if(_previousChoice !== undefined) {
        _previousChoice.style.outline = '';
      }

      _colorChoice = event.target.getAttribute("value")
      event.target.style.outline = "solid blue 3px";
      _previousChoice = event.target;
    })
    colorSelect.append(option)
  }

  colorSelect.style.display = "inline-block";
}

let initializeSecret = function() {
  _canvas.addEventListener('click', canvasListener, false);
}

let updateFrontendTimeout = function() {
  _frontend_timeout -= 100;
  if (_frontend_timeout <= 0) {
    document.getElementById("timeoutDisplay").style.display = "none";
    _frontend_timeout = 0;
  } else {
    document.getElementById("timeoutDisplay").style.display = "block";
    document.getElementById("timeoutDisplay").innerHTML = `${(_frontend_timeout / 1000).toFixed(1)}s Until Next Pixel...`;
    setTimeout(updateFrontendTimeout, 100);
  }
};

let canvasListener = function(event) {
  document.getElementById("timeoutDisplay").style.display = "block";
  document.getElementById("timeoutDisplay").innerHTML = `Sending Pixel...`;
  var elem = document.getElementById('canvas'),
  elemLeft = elem.offsetLeft + elem.clientLeft,
  elemTop = elem.offsetTop + elem.clientTop,
  col = parseInt((event.pageX - elemLeft) / ZOOM_SCALE),
  row = parseInt((event.pageY - elemTop) / ZOOM_SCALE);
  fetch(`/update-pixel`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ "id": _middlewareID, "row": row, "col": col, "color": _colorChoice})
  })
  .then((response) => {
    if(response.status === 429) {
      alert("Too many requests!", "danger");
      document.getElementById("timeoutDisplay").style.display = "none";
    } else {
      return response.json();
    }
  })
  .then((json) => {
    if (json["currentlyDisabled"]) {
      document.getElementById("disabledDisplay").innerHTML = `Your pixel was sent but this pixel board was disabled at the time you sent your pixel.`;
      document.getElementById("disabledDisplay").style.display = "block";
    } else {
      document.getElementById("disabledDisplay").style.display = "none";
    }

    _frontend_timeout = json["rate"] + 100;
    updateFrontendTimeout();
  })
  .catch((err) => {
    console.log(err);
    document.getElementById("timeoutDisplay").style.display = "none";
  });
};

let showInvalidSecret = () => {
  document.getElementById("enableFrontendEditModal_error").innerHTML = `
  <div class="alert alert-danger alert-dismissible fade show" role="alert">
    <div>Invalid Secret</div>
    <button type="button" class="btn-close" data-dismiss="alert" aria-label="Close" ></button>
  </div>`;  
}

let enableFrontend = function(event) {
  let secret = document.getElementById("pg_secret").value;

  let netid = "Unknown";
  split = secret.split('+');
  if (split.length == 3 && split[0] == "Frontend") {
    netid = atob(split[1]);
  } 

  fetch("/register-pg", {
    method: "PUT",
    body: JSON.stringify({
      "name": netid,
      "author": "Frontend",
      "secret": secret
    }),
    headers: { 'Content-Type': 'application/json' }
  })
  .then((response) => {
    if(response.status != "200") {
      document.getElementById("enableFrontendEditModal_error").innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
          <div>Invalid Secret</div>
          <button type="button" class="btn-close" data-dismiss="alert" aria-label="Close" ></button>
        </div>
      `;
    } else {
      return response.json();
    }
  })
  .then((json) => {
    _middlewareID = json["id"];
    localStorage.setItem('frontend-token', secret);
    console.log(`Frontend Enabled (Secret=${secret} => Id=${_middlewareID})`)

    // Remove "Enable" button:
    document.getElementById("enableFrontendEditButton").remove();
    initializeColorSelector();
    initializeSecret();
    
    // Close Modal:
    let modal = document.getElementById("enableFrontendEditModal");
    bootstrap.Modal.getInstance(modal).hide();
  })
  .catch((err) => console.log(err));
}