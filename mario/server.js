// server.js
import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import OpenAI from 'openai';

const app = express();
const port = process.env.PORT || 3000;

// CORS: lock down in prod if you have a known origin
app.use(cors());
app.use(express.json({ limit: '256kb' }));
app.use(express.static('public'));

const openaiKey = process.env.OPENAI_API_KEY;
const openai = openaiKey ? new OpenAI({ apiKey: openaiKey }) : null;

// Allowed actions enum
const ACTIONS = new Set(['idle','left','right','jump','left_jump','right_jump']);

// System prompt: keep it terse, force strict JSON
const systemPrompt = `
You are a game-playing agent for a 2D platformer like Mario.
Output ONLY strict JSON: {"action":"<one of: idle,left,right,jump,left_jump,right_jump>"}
No comments. No code fences. No prose.
You receive {"state": {...}} with:
- player: { x, y, vx, vy, onGround }
- nearGrid: 5x9 grid of 0/1, nearGrid[row][col], where:
  row 0 = tiles at the player's feet level, rows increase upward (1..4)
  col 0 = tile at player's current x, columns increase to the right toward the goal.
  1 = solid, 0 = empty.
- goal: { x } world x position of the goal.

Policy:
- Move right toward the goal.
- If onGround and (wall ahead: nearGrid[0][1]==1 or nearGrid[0][2]==1) OR a gap at feet (nearGrid[0][0]==0), choose right_jump.
- If airborne (onGround==false), keep moving right (right). Do not issue jump.
- Otherwise choose right.

Remember: Output strict JSON only.
`.trim();

// Health + readiness
app.get('/healthz', (_req, res) => {
  res.json({
    ok: true,
    openaiConfigured: !!openai,
    model: 'gpt-4o-mini',
  });
});

// Main action endpoint
app.post('/agent/act', async (req, res) => {
  try {
    const { state } = req.body || {};
    const validated = validateState(state);
    const action = await decideAction(validated);
    res.json({ action });
  } catch (e) {
    console.error('[agent_error]', e);
    res.status(400).json({ error: 'agent_error', message: e.message || 'Bad request' });
  }
});

function validateState(state) {
  if (!state || typeof state !== 'object') throw new Error('Missing state');
  const p = state.player || {};
  if (typeof p.onGround !== 'boolean') throw new Error('player.onGround must be boolean');
  if (!Array.isArray(state.nearGrid)) throw new Error('nearGrid must be an array');
  // Expect 5 rows x 9 cols; tolerate bigger but require at least that much
  if (state.nearGrid.length < 5) throw new Error('nearGrid needs >= 5 rows');
  for (let r = 0; r < 5; r++) {
    if (!Array.isArray(state.nearGrid[r]) || state.nearGrid[r].length < 9) {
      throw new Error(`nearGrid row ${r} needs >= 9 cols`);
    }
  }
  return state;
}

async function decideAction(state) {
  // Heuristic fallback covers API not configured or any failure
  if (!openai) return heuristic(state);

  // Short fuse so the game loop doesn’t stall
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort('timeout'), 2500);

  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0,
      max_tokens: 16,
      // Let the server do the JSON tightening
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: JSON.stringify({ state }) },
      ],
      signal: ac.signal,
    });

    const raw = completion.choices?.[0]?.message?.content ?? '{}';
    const jsonText = stripFences(raw);
    const parsed = JSON.parse(jsonText);
    const a = String(parsed.action || '').toLowerCase();

    if (ACTIONS.has(a)) return a;
    return heuristic(state);
  } catch (err) {
    // On timeout, abort, etc. go safe
    return heuristic(state);
  } finally {
    clearTimeout(t);
  }
}

// Fence stripper just in case the model ever tries to be “helpful”
function stripFences(s) {
  if (typeof s !== 'string') return '{}';
  return s.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
}

// Simple local policy fallback so gameplay never blocks
function heuristic(state) {
  const g = state?.nearGrid || [];
  const onGround = !!state?.player?.onGround;
  const obstacleAhead = (g[0]?.[1] === 1) || (g[0]?.[2] === 1);
  const gapHere = (g[0]?.[0] === 0);
  if (onGround && (obstacleAhead || gapHere)) return 'right_jump';
  return 'right';
}

app.listen(port, () => {
  console.log(`Mario agent server running: http://localhost:${port}`);
});
