"""
Controls
--------
←/→      walk
SPACE/↑  jump
ESC      quit
"""

import os
import sys
import time
import pygame as pg
from openai import OpenAI
import re

client = OpenAI()
import json                       # ← NEW
from dataclasses import dataclass
from typing import List, Tuple
# ───────── CONFIG ─────────
SCREEN_W, SCREEN_H = 960, 480
FPS = 60
TILE = 32
GRAVITY = 0.5
JUMP_V = -11
RUN_SPEED = 4.5

COIN_VALUE = 100
ENEMY_PENALTY = 100
START_LIVES = 3
START_SCORE = 0

LEVEL = [
    "                                                           F",
    "                                                           F",
    "                  #####                                    F",
    "                             C                             F",
    "        C                      C                           F",
    "              ##########            C      C               F",
    "                      G         G        G     C    ####   F",
    "############################  ####  #######  ##########    F",
]

SOLID_TILES = {"#"}
COIN_CHR = "C"
ENEMY_CHR = "G"
FINISH_CHR = "F"

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")

# ───────── HELPERS ─────────
def load_image(name: str, fallback_color: tuple[int, int, int], size: tuple[int, int]) -> pg.Surface:
    """Load image or return simple colored Surface of given size."""
    path = os.path.join(ASSET_DIR, name)
    surf = pg.Surface(size, pg.SRCALPHA)
    if os.path.isfile(path):
        try:
            img = pg.image.load(path).convert_alpha()
            return pg.transform.scale(img, size)
        except pg.error:
            pass
    surf.fill(fallback_color)
    return surf


def extract_action(text):
    # Look for a JSON-ish action object, tolerate missing quotes/braces
    m = re.search(r'{"action":\s*"(\w+(_and_\w+)?)"}', text)
    if m:
        return m.group(1)
    # Or, just look for "action" in plain English
    m = re.search(r'action\s*[:=]\s*(\w+(_and_\w+)?)', text)
    if m:
        return m.group(1)
    # Or, common phrase in the output
    for act in ["move_right_and_jump", "move_right", "move_left", "jump", "idle"]:
        if act in text:
            return act
    return "idle"
# ───────── AI DRIVER ─────────
class OpenAIPlayer:
    """Agent that queries the OpenAI API for next action with explainability."""
    def __init__(self, model: str = "gpt-4.1-mini", interval: float = 0.25):
        self.model = model
        self.interval = interval  # seconds between API calls
        self.last_t = 0.0
        self.last_act = (False, False, False)
        self.last_reasoning = ""

    def _prompt(self, game: "MarioGame") -> str:
        """Return a system prompt with game state and clear instructions."""
        state = {
            "player": {
                "x": game.player.rect.centerx / TILE,
                "y": game.player.rect.centery / TILE,
                "vx": game.player.vx,
                "vy": game.player.vy,
                "on_ground": game.on_ground(game.player),
            },
            "coins": [
                {"x": c.rect.centerx / TILE, "y": c.rect.centery / TILE}
                for c in game.coins
            ],
            "enemies": [
                {"x": e.rect.centerx / TILE, "y": e.rect.centery / TILE}
                for e in game.enemies
            ],
            "flag_dx": (
                (game.finish.rect.centerx - game.player.rect.centerx) / TILE
                if game.finish else None
            ),
            "score": game.score,
            "lives": game.lives,
        }
        prompt = (
            "You are an expert at playing Mario. "
            "Analyze the following game state and determine the best next action for Mario. "
            "First, explain what you intend to do and why, then output a JSON object with your action as one of: "
            "\"move_left\", \"move_right\", \"jump\", \"move_right_and_jump\", or \"idle\".\n"
            "Example response:\n"
            "\"There's an enemy ahead, so I will jump over it to avoid losing a life.\"\n"
            "{\"action\": \"move_right_and_jump\"}\n"
            "Here is the game state:\n"
            f"{json.dumps(state)}"
        )
        return prompt

    def decide(self, game: "MarioGame") -> Tuple[bool, bool, bool]:
        from openai import OpenAI
        
        client = OpenAI()
        import re
        import ast

        prompt = self._prompt(game)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful and expert Mario player."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=128,
            temperature=0.2
        )
        text = response.choices[0].message.content  # (for OpenAI v1 SDK)

        reasoning = text.strip().split("\n")[0]
        self.last_reasoning = reasoning
        print("[AI Mario] " + reasoning)

        # Use the new robust action extractor:
        action = extract_action(text)
        move = {
            "move_left":    (True, False, False),
            "move_right":   (False, True, False),
            "jump":         (False, False, True),
            "move_right_and_jump": (False, True, True),
            "idle":         (False, False, False),
        }
        return move.get(action, (False, False, False))

# ───────── DATA CLASSES ─────────
@dataclass(slots=True)
class Entity:
    image: pg.Surface
    rect: pg.Rect
    vx: float = 0.0
    vy: float = 0.0

    def draw(self, screen: pg.Surface, cam_x: int):
        screen.blit(self.image, (self.rect.x - cam_x, self.rect.y))


# ───────── GAME CLASS ─────────
class MarioGame:
    def __init__(self):
        pg.init()
        self.scr = pg.display.set_mode((SCREEN_W, SCREEN_H))
        pg.display.set_caption("Mario-esque clone")
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont(None, 28)

        self.load_assets()
        self.autoplay = True       # ← AI ALWAYS ON
        self.ai = OpenAIPlayer()   # ← instantiate unconditionally
        self.reset()

    # ────── ASSETS ──────
    def load_assets(self):
        self.img_player = load_image("mario.png", (255, 0, 0), (TILE, int(TILE * 1.5)))
        self.img_coin = load_image("coin.png", (255, 213, 0), (TILE, TILE))
        # Create simple brown square for enemies
        self.img_enemy = pg.Surface((TILE, TILE))
        self.img_enemy.fill((139, 69, 19))
        self.img_brick = load_image("brick.png", (174, 105, 6), (TILE, TILE))
        self.img_flag = load_image("flag.png", (30, 197, 48), (TILE, TILE * 2))

    # ────── WORLD BUILD ──────
    def build_level(self):
        self.solids: List[pg.Rect] = []
        self.coins: List[Entity] = []
        self.enemies: List[Entity] = []
        self.finish: Entity | None = None
        self.pole_rect: pg.Rect | None = None

        offset_y = SCREEN_H - len(LEVEL) * TILE

        for row_idx, line in enumerate(LEVEL):
            for col_idx, ch in enumerate(line):
                x = col_idx * TILE
                y = offset_y + row_idx * TILE
                if ch in SOLID_TILES:
                    self.solids.append(pg.Rect(x, y, TILE, TILE))
                elif ch == COIN_CHR:
                    self.coins.append(
                        Entity(self.img_coin, pg.Rect(x, y, TILE, TILE))
                    )
                elif ch == ENEMY_CHR:
                    # enemies start moving left
                    self.enemies.append(
                        Entity(self.img_enemy, pg.Rect(x, y, TILE, TILE), vx=-2.0)
                    )
                elif ch == FINISH_CHR:
                    flag_rect = pg.Rect(x, y - TILE, TILE, TILE * 2)
                    self.finish = Entity(self.img_flag, flag_rect)
                    self.pole_rect = flag_rect

    # ────── UPDATE ──────
    def update(self, dt: float):
        # AI input is always active -----------------------------------------
        left, right, jump = self.ai.decide(self)
        self.player.vx = (right - left) * RUN_SPEED
        if jump and self.on_ground(self.player):
            self.player.vy = JUMP_V

        # Horizontal movement + collision
        move_x = self.player.vx * dt
        self.player.rect.x += int(round(move_x))
        self.collide_axis(self.player, axis=0)

        # Vertical movement + gravity -----------------------------
        self.player.vy += GRAVITY * dt
        self.player.rect.y += int(round(self.player.vy * dt))
        self.collide_axis(self.player, axis=1)

        # ───── FINISH LINE ─────
        # Check BEFORE coins / enemies so no life can be lost after winning.
        if self.pole_rect and self.player.rect.colliderect(self.pole_rect):
            touch_y = self.player.rect.bottom
            factor = max(0.0, min(1.0, (SCREEN_H - touch_y) / SCREEN_H))
            self.score += int(factor * 1000)
            self.level_complete = True
            # keep camera updated so the pole remains visible
            max_cam = self.level_surface.get_width() - SCREEN_W
            self.camera = max(0, min(max_cam, self.player.rect.centerx - SCREEN_W // 2))
            return  # stop further processing; course is complete

        # Collect coins ------------------------------------------
        for coin in self.coins[:]:
            if self.player.rect.colliderect(coin.rect):
                self.coins.remove(coin)
                self.score += COIN_VALUE

        # Enemy interactions (stomp / hurt) ----------------------
        for en in self.enemies[:]:
            if self.player.rect.colliderect(en.rect):
                # Determine if stomp (falling onto enemy)
                if self.player.vy > 0 and self.player.rect.bottom <= en.rect.top + TILE * 0.5:
                    self.enemies.remove(en)
                    self.player.vy = JUMP_V * 0.6
                    self.score += COIN_VALUE
                else:
                    self.handle_enemy_hit()
                break

        # ─── Enemy autonomous movement ───
        for en in self.enemies:
            # horizontal patrol
            en.rect.x += int(round(en.vx * dt))
            hit = False
            for solid in self.solids:
                if en.rect.colliderect(solid):
                    if en.vx > 0:
                        en.rect.right = solid.left
                    else:
                        en.rect.left = solid.right
                    en.vx = -en.vx  # bounce
                    hit = True
            # gravity + vertical collisions
            en.vy += GRAVITY * dt
            en.rect.y += int(round(en.vy * dt))
            for solid in self.solids:
                if en.rect.colliderect(solid):
                    if en.vy > 0:
                        en.rect.bottom = solid.top
                    else:
                        en.rect.top = solid.bottom
                    en.vy = 0

        # Duplicate flag-pole detection removed; this logic is already
        # handled earlier (see lines 208-218) before coin/enemy checks,
        # ensuring the player can’t lose a life after winning.

        # Fell below screen (only if level not complete)
        if self.player.rect.top > SCREEN_H and not self.level_complete:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over = True
                self.score = 0
            else:
                self.build_level()
                self.player.rect.topleft = (64, SCREEN_H - TILE * 3)
                self.player.vx = self.player.vy = 0
                self.camera = 0

        # Camera update - follow player horizontally
        max_cam = self.level_surface.get_width() - SCREEN_W
        self.camera = max(0, min(max_cam, self.player.rect.centerx - SCREEN_W // 2))

    # ────── EVENTS ──────
    def handle_events(self):
        """Process SDL/keyboard events."""
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                self.quit()
            elif ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE:
                    self.quit()
                # Quick reset after game-over for convenience
                if ev.key == pg.K_r and self.game_over:
                    self.reset()

    # ────── COLLISIONS ──────
    def collide_axis(self, ent: Entity, axis: int):
        for solid in self.solids:
            if ent.rect.colliderect(solid):
                if axis == 0:
                    if ent.vx > 0:
                        ent.rect.right = solid.left
                    elif ent.vx < 0:
                        ent.rect.left = solid.right
                    ent.vx = 0
                else:
                    if ent.vy > 0:
                        ent.rect.bottom = solid.top
                    elif ent.vy < 0:
                        ent.rect.top = solid.bottom
                    ent.vy = 0

    def on_ground(self, ent: Entity) -> bool:
        # Check if entity is on the ground
        rect = ent.rect.copy()
        rect.y += 1
        for solid in self.solids:
            if rect.colliderect(solid):
                return True
        return False
    def build_background(self):
        """Create and draw the static level surface (tiles only)."""
        # Determine level dimensions
        level_width = len(LEVEL[0]) * TILE
        level_height = SCREEN_H
        # Create surface and fill sky color
        self.level_surface = pg.Surface((level_width, level_height))
        self.level_surface.fill((135, 206, 235))  # light sky blue
        # Draw solid tiles
        for solid in self.solids:
            self.level_surface.blit(self.img_brick, (solid.x, solid.y))

    def reset(self):
         """Reset game to its initial state."""
         self.score = START_SCORE
         self.lives = START_LIVES
         self.game_over = False
         self.level_complete = False
         self.build_level()
         # Initialize player
         player_y = SCREEN_H - TILE * 3
         self.player = Entity(
             self.img_player,
             pg.Rect(64, player_y, TILE, int(TILE * 1.5))
         )
         self.player.vx = self.player.vy = 0
         self.camera = 0
         # ensure background + state flags exist
         self.build_background()

    def run(self):
        """Main game loop."""
        while True:
            dt = self.clock.tick(FPS) / 16.666  # scaled to 60 FPS base
            self.handle_events()
            if not self.game_over and not self.level_complete:
                self.update(dt)
            self.draw()

    def draw(self):
        # Draw background
        self.scr.blit(self.level_surface, (-self.camera, 0))
        cam = self.camera

        # Draw entities
        for coin in self.coins:
            coin.draw(self.scr, cam)
        # Draw enemies
        for en in self.enemies:
            en.draw(self.scr, cam)
        # Draw finish flag if present
        if self.finish:
            self.finish.draw(self.scr, cam)
        self.player.draw(self.scr, cam)

        # HUD ----------------------------------------------------
        hud = self.font.render(f"Score: {self.score}   Lives: {self.lives}", True, (0, 0, 0))
        self.scr.blit(hud, (10, 10))

        # Show win banner only when level is really completed
        if self.level_complete:
            win_surf = self.font.render("COURSE COMPLETE", True, (0, 0, 0), (0, 255, 0))
            win_rect = win_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 20))
            self.scr.blit(win_surf, win_rect)
            # Prompt to exit
            small_surf = self.font.render("Press ESC to quit", True, (255, 255, 255))
            small_rect = small_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 40))
            self.scr.blit(small_surf, small_rect)

        # Game-over banner --------------------------------------
        if self.game_over:
            over = self.font.render("GAME OVER", True, (255, 0, 0))
            o_rect = over.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 20))
            self.scr.blit(over, o_rect)
            info = self.font.render("Press ESC to quit", True, (255, 255, 255))
            i_rect = info.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 40))
            self.scr.blit(info, i_rect)

        pg.display.flip()

    # ────── HELPERS ──────
    def handle_enemy_hit(self):
        """Lose one life and points when colliding with an enemy."""
        self.score = max(0, self.score - ENEMY_PENALTY)
        self.lives -= 1
        if self.lives <= 0:
            self.game_over = True
            self.score = 0
        else:
            self.build_level()
            self.player.rect.topleft = (64, SCREEN_H - TILE * 3)
            self.player.vx = self.player.vy = 0
            self.camera = 0

    def center_message(self, msg: str):
        surf = self.font.render(msg, True, (0, 0, 0))
        rect = surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2))
        self.scr.blit(surf, rect)

    def quit(self):
        pg.quit()
        sys.exit()


# ───────── ENTRY ─────────
if __name__ == "__main__":
    MarioGame().run()
