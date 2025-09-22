const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const TILE = 32;
const LEVEL_W = 120;
const LEVEL_H = 20;
const GRAVITY = 1800;
const MOVE_ACCEL = 1800;
const MAX_SPEED_X = 220;
const JUMP_VY = -520;
const FRICTION = 0.85;

const WORLD = makeLevel();
const CAMERA = { x: 0, y: 0, w: canvas.width, h: canvas.height };

const player = {
  x: TILE * 2,
  y: TILE * 12,
  w: 26,
  h: 30,
  vx: 0,
  vy: 0,
  onGround: false,
  facing: 1 // 1 right, -1 left
};

const GOAL_X = (LEVEL_W - 3) * TILE;

const keys = Object.create(null);
let aiEnabled = true;
let lastAction = "idle";
let actionUntil = 0;

document.addEventListener("keydown", (e) => {
  if (e.repeat) return;
  if (e.code === "KeyA") {
    aiEnabled = !aiEnabled;
    document.getElementById("status").textContent = `AI: ${aiEnabled ? "ON" : "OFF"}`;
  } else if (e.code === "KeyR") {
    reset();
  } else {
    keys[e.code] = true;
  }
});

document.addEventListener("keyup", (e) => {
  keys[e.code] = false;
});

function reset() {
  player.x = TILE * 2;
  player.y = TILE * 12;
  player.vx = 0;
  player.vy = 0;
  player.onGround = false;
  player.facing = 1;
}

function makeLevel() {
  // 0 empty, 1 solid
  const lvl = Array.from({ length: LEVEL_H }, () => Array(LEVEL_W).fill(0));
  // Ground
  for (let x = 0; x < LEVEL_W; x++) {
    for (let y = LEVEL_H - 2; y < LEVEL_H; y++) lvl[y][x] = 1;
  }

  // Lowered platforms so AI can mount them (1–2 tiles above ground)
  for (let x = 10; x < 20; x++) lvl[17][x] = 1; // was 14
  for (let x = 22; x < 28; x++) lvl[16][x] = 1; // was 12
  for (let x = 35; x < 45; x++) lvl[17][x] = 1; // was 15

  // Gaps in ground
  for (let x = 48; x < 52; x++) lvl[LEVEL_H - 2][x] = 0;
  for (let x = 70; x < 74; x++) lvl[LEVEL_H - 2][x] = 0;

  // Short pillars (1 tile tall) so AI can jump over
  lvl[LEVEL_H - 3][60] = 1; // y = 17
  lvl[LEVEL_H - 3][85] = 1; // y = 17

  // Goal pillar (keep tall for flag visibility)
  for (let y = LEVEL_H - 3; y > LEVEL_H - 12; y--) lvl[y][LEVEL_W - 3] = 1;

  return lvl;
}

function isSolidTile(tx, ty) {
  if (tx < 0 || ty < 0 || tx >= LEVEL_W || ty >= LEVEL_H) return true;
  return WORLD[ty][tx] === 1;
}

function rectVsTilesMove(o, dx, dy) {
  // Horizontal move
  if (dx !== 0) {
    const sign = Math.sign(dx);
    let nx = o.x + dx;
    const ahead = sign > 0 ? nx + o.w : nx;
    const xTile = Math.floor(ahead / TILE);
    const yTop = Math.floor(o.y / TILE);
    const yBot = Math.floor((o.y + o.h - 1) / TILE);
    for (let ty = yTop; ty <= yBot; ty++) {
      if (isSolidTile(xTile, ty)) {
        nx = sign > 0 ? xTile * TILE - o.w - 0.01 : (xTile + 1) * TILE + 0.01;
        o.vx = 0;
        break;
      }
    }
    o.x = nx;
  }
  // Vertical move
  if (dy !== 0) {
    const sign = Math.sign(dy);
    let ny = o.y + dy;
    const ahead = sign > 0 ? ny + o.h : ny;
    const yTile = Math.floor(ahead / TILE);
    const xLeft = Math.floor(o.x / TILE);
    const xRight = Math.floor((o.x + o.w - 1) / TILE);
    for (let tx = xLeft; tx <= xRight; tx++) {
      if (isSolidTile(tx, yTile)) {
        ny = sign > 0 ? yTile * TILE - o.h - 0.01 : (yTile + 1) * TILE + 0.01;
        o.vy = 0;
        if (sign > 0) o.onGround = true;
        break;
      }
    }
    o.y = ny;
  }
}

function update(dt) {
  // Apply AI action roughly every 100ms
  if (aiEnabled && performance.now() >= actionUntil) {
    requestAction().then((a) => {
      applyAction(a);
      lastAction = a;
      actionUntil = performance.now() + 120; // hold for ~120ms
    }).catch(() => {
      // ignore, keep last action
    });
  }

  // Input from player or AI-mapped keys
  let ax = 0;
  if (keys.ArrowLeft) {
    ax -= MOVE_ACCEL;
    player.facing = -1;
  }
  if (keys.ArrowRight) {
    ax += MOVE_ACCEL;
    player.facing = 1;
  }
  // Horizontal physics
  player.vx += ax * dt;
  player.vx = Math.max(Math.min(player.vx, MAX_SPEED_X), -MAX_SPEED_X);
  player.vx *= FRICTION;

  // Gravity
  player.onGround = false;
  player.vy += GRAVITY * dt;
  // Jump
  if (keys.Space || keys.KeyZ) {
    if (player.onGroundLast) {
      player.vy = JUMP_VY;
    }
  }

  // Move and collide
  rectVsTilesMove(player, player.vx * dt, 0);
  rectVsTilesMove(player, 0, player.vy * dt);

  // Camera follow
  CAMERA.x = Math.floor(player.x + player.w / 2 - CAMERA.w / 2);
  CAMERA.y = Math.floor(player.y + player.h / 2 - CAMERA.h / 2);
  CAMERA.x = Math.max(0, Math.min(CAMERA.x, LEVEL_W * TILE - CAMERA.w));
  CAMERA.y = Math.max(0, Math.min(CAMERA.y, LEVEL_H * TILE - CAMERA.h));

  // Win reset if reach goal area
  if (player.x > GOAL_X - TILE && player.y < (LEVEL_H - 3) * TILE) {
    reset();
  }

  // Track ground state for jump edge
  player.onGroundLast = player.onGround;
}

function draw() {
  // Sky
  ctx.fillStyle = "#87ceeb";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Level
  const x0 = Math.floor(CAMERA.x / TILE);
  const y0 = Math.floor(CAMERA.y / TILE);
  const x1 = Math.ceil((CAMERA.x + CAMERA.w) / TILE);
  const y1 = Math.ceil((CAMERA.y + CAMERA.h) / TILE);

  for (let ty = y0; ty < y1; ty++) {
    for (let tx = x0; tx < x1; tx++) {
      if (tx < 0 || ty < 0 || tx >= LEVEL_W || ty >= LEVEL_H) continue;
      if (WORLD[ty][tx] === 1) {
        ctx.fillStyle = "#8b4513";
        ctx.fillRect(
          Math.floor(tx * TILE - CAMERA.x),
          Math.floor(ty * TILE - CAMERA.y),
          TILE, TILE
        );
        ctx.strokeStyle = "rgba(0,0,0,0.15)";
        ctx.strokeRect(
          Math.floor(tx * TILE - CAMERA.x) + 0.5,
          Math.floor(ty * TILE - CAMERA.y) + 0.5,
          TILE - 1, TILE - 1
        );
      }
    }
  }

  // Goal flagpole
  ctx.fillStyle = "#2e8b57";
  ctx.fillRect(Math.floor(GOAL_X - CAMERA.x), Math.floor((LEVEL_H - 11) * TILE - CAMERA.y), 6, TILE * 10);
  ctx.fillStyle = "#fff";
  ctx.fillRect(Math.floor(GOAL_X - CAMERA.x + 6), Math.floor((LEVEL_H - 11) * TILE - CAMERA.y), 18, 12);

  // Player
  ctx.fillStyle = "#ff4136";
  ctx.fillRect(
    Math.floor(player.x - CAMERA.x),
    Math.floor(player.y - CAMERA.y),
    player.w, player.h
  );

  // HUD info
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.fillRect(8, canvas.height - 54, 260, 46);
  ctx.fillStyle = "#fff";
  ctx.font = "12px monospace";
  ctx.fillText(`AI: ${aiEnabled ? "ON" : "OFF"}  last: ${lastAction}`, 16, canvas.height - 32);
  ctx.fillText(`x:${(player.x/TILE).toFixed(1)} y:${(player.y/TILE).toFixed(1)}`, 16, canvas.height - 16);
}

function gameLoop(ts) {
  const now = performance.now();
  const dt = 1 / 60; // fixed step for stability
  update(dt);
  draw();
  requestAnimationFrame(gameLoop);
}
requestAnimationFrame(gameLoop);

// Map an action string to key presses for a brief duration
function applyAction(action) {
  // Clear movement keys
  keys.ArrowLeft = false;
  keys.ArrowRight = false;
  // Jump is edge-triggered
  keys.Space = false;

  switch (action) {
    case "left":
      keys.ArrowLeft = true;
      break;
    case "right":
      keys.ArrowRight = true;
      break;
    case "jump":
      if (player.onGround) keys.Space = true;
      break;
    case "left_jump":
      keys.ArrowLeft = true;
      if (player.onGround) keys.Space = true;
      break;
    case "right_jump":
      keys.ArrowRight = true;
      if (player.onGround) keys.Space = true;
      break;
    case "idle":
    default:
      break;
  }
}

// Build a compact state for the agent
function snapshotState() {
  const txFeet = Math.floor((player.x + player.w / 2) / TILE);
  const tyFeet = Math.floor((player.y + player.h) / TILE);
  const rows = 5, cols = 9;
  const nearGrid = Array.from({ length: rows }, () => Array(cols).fill(0));
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const tx = txFeet + c;
      const ty = tyFeet - r;
      nearGrid[r][c] = isSolidTile(tx, ty) ? 1 : 0;
    }
  }
  return {
    player: {
      x: Math.round(player.x),
      y: Math.round(player.y),
      vx: Math.round(player.vx),
      vy: Math.round(player.vy),
      onGround: !!player.onGround
    },
    nearGrid,
    goal: { x: GOAL_X }
  };
}

async function requestAction() {
  const state = snapshotState();
  const res = await fetch("/agent/act", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state })
  });
  if (!res.ok) throw new Error("agent HTTP " + res.status);
  const data = await res.json();
  return data.action || "right";
}
