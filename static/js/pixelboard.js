var _settings = undefined;
var _canvas = undefined;
var _sio = undefined;
var _middlewareID = undefined;
var _enableToken = undefined;
var _colorChoice = 0;
var _previousChoice = 0;

// Fetch the settings:
fetch("/settings")
.then((response) => response.json())
.then((settings) => {
  _settings = settings;
  initBoard();
})

// Initialize the canvas:
let initBoard = function() {
  _canvas = document.createElement("canvas");
  _canvas.height = _settings.height * 3;
  _canvas.width = _settings.width * 3;
  _canvas.id = "canvas"
  _canvas.getContext("2d").scale(3, 3);

  document.getElementById("pixelboard").appendChild(_canvas);

  // Load the current board edits onto this instance of the canvas:
  fetch("/pixels")
  .then((response) => response.json())
  .then((data) => {
    let ctx = _canvas.getContext("2d");
    let pixels = data.pixels;
    console.log(pixels);

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
      const color_idx = msg['color'];

      const color = _settings.palette[color_idx];

      let ctx = _canvas.getContext("2d");
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 1, 1);
    })

    // Hover: 
    const canvas = document.getElementById('canvas')
    function getCursorPosition(canvas, event) {
      var elemLeft = canvas.offsetLeft + canvas.clientLeft;
      var elemTop = canvas.offsetTop + canvas.clientTop;
      x = parseInt((event.pageX - elemLeft) / 3);
      y = parseInt((event.pageY - elemTop) / 3);
      return [x, y];
    }
    canvas.addEventListener('mousemove', function(e) {
      e.preventDefault();
      var [col,row] = getCursorPosition(canvas, e);
      const hidden = document.getElementById('mouse_over');
      hidden.style.visibility = 'visible';
      var tmpcol = e.clientX + 20;
      var tmprow = e.clientY + 20;
      hidden.style.position = "absolute";
      hidden.style.left = `${tmpcol}px`;
      hidden.style.top = `${tmprow}px`;
      
      fetch(`/getPixelAuthor/${col}/${row}`)
      .then((response) => response.json())
      .then((data) => {
        hidden.innerHTML =`
        Pixel Color: ${_settings.palette[+data.color]}
        <div class="small">${data.author}</div>
        `;
      })
    })
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

let canvasListener = function(event) {
  var elem = document.getElementById('canvas'),
  elemLeft = elem.offsetLeft + elem.clientLeft,
  elemTop = elem.offsetTop + elem.clientTop,
  col = parseInt((event.pageX - elemLeft) / 3),
  row = parseInt((event.pageY - elemTop) / 3);
  fetch(`/update-pixel`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ "id": _middlewareID, "row": row, "col": col, "color": _colorChoice})
  })
  .then((response) => {
    if(response.status === 429) {
      alert("Too many requests!", "danger")
    }
  })
  .catch((err) => console.log(err));
};

let enableFrontend = function(event) {
  let secret = document.getElementById("pg_secret").value;
  fetch("/register-pg", {
    method: "PUT",
    body: JSON.stringify({
      "name": "Frontend",
      "author": "N/A",
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