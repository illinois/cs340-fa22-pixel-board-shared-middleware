var _settings = undefined;
var _canvas = undefined;
var _sio = undefined;
var _middlewareID = undefined;
var _enableToken = undefined;
var _colorChoice = undefined;
var _previousChoice = undefined;

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

  initalizeSecret();
  initalizeSelector();

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

    // hoover 
    const canvas = document.getElementById('canvas')
    function getCursorPosition(canvas, event) {
      var elemLeft = canvas.offsetLeft + canvas.clientLeft;
      var elemTop = canvas.offsetTop + canvas.clientTop;
      x = parseInt((event.pageX - elemLeft) / 3);
      y = parseInt((event.pageY - elemTop) / 3);
      console.log("x: " + x + " y: " + y)
      return [x,y]
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
      function delay(time) {
        return new Promise(resolve => setTimeout(resolve, time));
      }
      delay(1000).then(() => {hidden.style.visibility = 'hidden';});
    });
  })
};

let initalizeSelector = function() {
  // Initialize the color selector
  var colorSelect = document.getElementById("selector")
  for(var i = 0; i < _settings.palette.length; i++) {
    var option = document.createElement("div")
    option.style.backgroundColor = _settings.palette[i]
    option.setAttribute('value', i)
    option.style.height = '20px'
    option.style.width = '42px'
    option.style.display = 'inline-block'
    option.addEventListener('click', function(event) {
      if(_previousChoice !== undefined) {
        _previousChoice.style.outline = ''
      }

      _colorChoice = event.target.getAttribute("value")
      event.target.style.outline = "solid blue 3px";
      _previousChoice = event.target;
    })
    colorSelect.append(option)
  }
}

let initalizeSecret = function() {
  _enableToken = document.getElementById("enable")
  _enableToken.addEventListener('click', function(event) {
    let secret = document.getElementById("secretTextBox").value;

    fetch("/register-pg", {
      method: "PUT",
      body: JSON.stringify({
        "name": "Frontend",
        "author": "N/A",
        "secret": secret
      }),
      headers: { 'Content-Type': 'application/json' }
    })
    .then((response) => response.json())
    .then((json) => _middlewareID = json["id"])
    .catch((err) => console.log(err));
  });

  _canvas.addEventListener('click', function(event) {
    if(_middlewareID === undefined || _colorChoice === undefined) {
      return;
    }
    var elem = document.getElementById('canvas'),
    elemLeft = elem.offsetLeft + elem.clientLeft,
    elemTop = elem.offsetTop + elem.clientTop,
    col = parseInt((event.pageX - elemLeft) / 3),
    row = parseInt((event.pageY - elemTop) / 3);
    fetch(`/changeByClick`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ "id": _middlewareID, "row": row, "col": col, "color": _colorChoice})
    })
  }, false);
}