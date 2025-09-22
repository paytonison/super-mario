import os
import json
import time
from flask import Flask, request, jsonify, send_from_directory
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

app = Flask(__name__, static_folder="public", static_url_path="")
PORT = int(os.environ.get("PORT", "3000"))

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None

# Reuse a single Assistant (Agents/Assistants API)
ASSISTANT_ID = os.environ.get("OPENAI_ASSISTANT_ID")
ASSISTANT_MODEL = os.environ.get("OPENAI_AGENT_MODEL", "gpt-4o-mini")

ASSISTANT_INSTRUCTIONS = """
You are a game-playing agent for a 2D platformer like Mario.
Output ONLY strict JSON: {"action":"<one of: idle,left,right,jump,left_jump,right_jump>"} with no extra text.
You receive {"state": {...}} with:
- player: { x, y, vx, vy, onGround }
- nearGrid: 5x9 grid of 0/1, nearGrid[row][col], where row 0 is the feet level, rows increase upward (1..4). col 0 is current x; columns increase to the right toward the goal.
- goal: { x } world x position of the goal flag.

Policy:
- Always move right toward the goal.
- Treat "obstacle ahead" as any solid tile in columns 1 or 2 within rows 0..2 (nearGrid[r][1] or nearGrid[r][2] == 1 for r in 0,1,2). This detects low platforms/pillars one tile above ground, not just at feet level.
- Treat "gap here/soon" as nearGrid[0][0] == 0 (no floor under feet) OR nearGrid[0][1] == 0 OR nearGrid[0][2] == 0 (no floor ahead within two tiles).
- If onGround and (obstacle ahead OR gap here/soon), choose right_jump.
- If airborne (onGround == false), keep moving right (right); do not jump while airborne.
- Otherwise choose right.
Remember: Output strict JSON only.
""".strip()


def ensure_assistant():
    global ASSISTANT_ID
    if not client:
        return None
    if ASSISTANT_ID:
        return ASSISTANT_ID
    # Create once per process if not provided
    try:
        a = client.beta.assistants.create(
            name="Mario Agent",
            instructions=ASSISTANT_INSTRUCTIONS,
            model=ASSISTANT_MODEL,
        )
        ASSISTANT_ID = a.id
        return ASSISTANT_ID
    except Exception as e:
        print("Failed to create assistant, falling back to heuristic:", e)
        return None


def strip_to_json(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if t.startswith("```"):
        # Remove code fences if present
        t = t.strip("`")
        i = t.find("{")
        j = t.rfind("}")
        if i != -1 and j != -1 and j > i:
            return t[i:j+1]
        return ""
    return t


def valid_action(a: str) -> str:
    a = (a or "").lower()
    return a if a in {"idle", "left", "right", "jump", "left_jump", "right_jump"} else ""


def _gval(grid, r, c):
    try:
        return 1 if grid[r][c] == 1 else 0
    except Exception:
        return 0


def heuristic(state) -> str:
    g = (state or {}).get("nearGrid") or []
    on_ground = bool(((state or {}).get("player") or {}).get("onGround"))

    # Detect low platforms/pillars up to 2 tiles high in the next two columns
    obstacle_ahead = any(_gval(g, r, c) == 1 for r in (0, 1, 2) for c in (1, 2))
    # Detect missing floor now or within two tiles
    gap_here = _gval(g, 0, 0) == 0
    gap_ahead = any(_gval(g, 0, c) == 0 for c in (1, 2))

    if on_ground and (obstacle_ahead or gap_here or gap_ahead):
        return "right_jump"
    return "right"


def decide_action_with_agents(state) -> str:
    if not client:
        return heuristic(state)
    assistant_id = ensure_assistant()
    if not assistant_id:
        return heuristic(state)

    # One-shot thread per request to avoid cross-talk
    try:
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=json.dumps({"state": state}, separators=(",", ":")),
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )

        # Poll for completion (simple loop)
        deadline = time.time() + float(os.environ.get("OPENAI_AGENT_TIMEOUT", "6"))
        status = run.status
        while status in ("queued", "in_progress"):
            if time.time() > deadline:
                raise TimeoutError("agent_timeout")
            time.sleep(0.2)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            status = run.status

        if status != "completed":
            return heuristic(state)

        msgs = client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=1)
        if not msgs.data:
            return heuristic(state)
        msg = msgs.data[0]
        content_chunks = msg.content or []
        text = ""
        for c in content_chunks:
            if getattr(c, "type", "") == "text" and hasattr(c, "text") and hasattr(c.text, "value"):
                text = c.text.value
                break
        if not text:
            return heuristic(state)

        raw = strip_to_json(text)
        parsed = json.loads(raw)
        act = valid_action(parsed.get("action"))
        return act or heuristic(state)
    except Exception as e:
        print("Agents error; using heuristic:", getattr(e, "message", str(e)))
        return heuristic(state)


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/agent/act", methods=["POST"])
def act():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        state = payload.get("state")
        action = decide_action_with_agents(state)
        return jsonify({"action": action})
    except Exception as e:
        return jsonify({"error": "agent_error", "message": str(e)}), 500


if __name__ == "__main__":
    print(f"Server running: http://localhost:{PORT}")
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY not set; using heuristic policy.")
    app.run(host="0.0.0.0", port=PORT)
