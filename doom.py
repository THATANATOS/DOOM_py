"""
██████╗  ██████╗  ██████╗ ███╗   ███╗   ██████╗ ██╗   ██╗
██╔══██╗██╔═══██╗██╔═══██╗████╗ ████║   ██╔══██╗╚██╗ ██╔╝
██║  ██║██║   ██║██║   ██║██╔████╔██║   ██████╔╝ ╚████╔╝
██║  ██║██║   ██║██║   ██║██║╚██╔╝██║   ██╔═══╝   ╚██╔╝
██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║   ██║        ██║
╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝   ╚═╝        ╚═╝

A DOOM-inspired raycasting FPS — 100% Python & Pygame

Controls:
  W / S        Move forward / backward
  A / D        Strafe left / right
  ← →          Rotate camera
  Mouse        Look (captured)
  SPACE / LMB  Shoot
  R            Reload (refill ammo)
  ESC          Quit

Requirements:  pip install pygame
"""

import pygame
import math
import random
import sys

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
SW, SH       = 1280, 720
HALF_H       = SH // 2
FOV          = math.pi / 3          # 60°
HALF_FOV     = FOV / 2
RAYS         = SW // 2              # one ray per 2 px  → very fast
SCALE        = SW // RAYS           # strip width in pixels
DELTA_ANGLE  = FOV / RAYS
PROJ_DIST    = RAYS / (2 * math.tan(HALF_FOV))
MAX_DEPTH    = 20                   # tiles
TILE         = 64
FPS          = 60

# Palette
SKY_TOP      = (10,  5,  15)
SKY_BOT      = (30, 10,  25)
FLOOR_TOP    = (35, 25,  10)
FLOOR_BOT    = (18, 12,   5)
HUD_BG       = (12,  6,   4)
WHITE        = (255, 255, 255)
RED          = (220,  30,  30)
ORANGE       = (255, 140,   0)
YELLOW       = (255, 215,   0)
GREEN        = ( 30, 200,  30)
DGRAY        = ( 45,  45,  45)

# Wall colours  (N/S face vs E/W face — different brightness for depth feel)
WALL_NS = [
    (180, 120,  80),   # map tile 1 – brick
    (100, 140, 180),   # map tile 2 – stone/blue
    (180,  80,  80),   # map tile 3 – blood brick
]
WALL_EW = [
    (130,  85,  55),
    ( 70, 100, 130),
    (130,  55,  55),
]

# ─────────────────────────────────────────────────────────────────────────────
#  MAP   (# = wall-type-1, @ = wall-type-2, % = wall-type-3, . = floor)
# ─────────────────────────────────────────────────────────────────────────────
MAP_DATA = [
    "#####################",
    "#...................#",
    "#.##.##...@@@@.##...#",
    "#..#.........#......#",
    "#..#..%%%%...#......#",
    "#....#....#.........#",
    "#....#....#..####...#",
    "#.........#.........#",
    "#....####.....#.....#",
    "#.............#.....#",
    "#..####.......#.....#",
    "#....#.........#....#",
    "#....#...###...#....#",
    "#................@..#",
    "#...@@@.@...........#",
    "#..................##",
    "##..####............#",
    "#..........#####....#",
    "#...................#",
    "#####################",
]
MAP_W = len(MAP_DATA[0])
MAP_H = len(MAP_DATA)

SPAWN_X = 1.5 * TILE
SPAWN_Y = 1.5 * TILE

ENEMY_SPAWNS = [
    (3, 3), (7, 2), (12, 4), (5, 8),
    (15, 3),(10, 7),(17, 10),(3, 13),
    (12,14),(8, 17),(18, 17),(5, 15),
]

# ─────────────────────────────────────────────────────────────────────────────
#  MAP HELPERS
# ─────────────────────────────────────────────────────────────────────────────
CHAR_TO_TYPE = {'#': 1, '@': 2, '%': 3}

def tile_type(px, py):
    """Return wall type (1-3) if wall, 0 if floor, -1 if out of bounds."""
    mx = int(px / TILE)
    my = int(py / TILE)
    if 0 <= mx < MAP_W and 0 <= my < MAP_H:
        c = MAP_DATA[my][mx]
        return CHAR_TO_TYPE.get(c, 0)
    return -1

def is_wall(px, py):
    return tile_type(px, py) != 0

# ─────────────────────────────────────────────────────────────────────────────
#  PLAYER
# ─────────────────────────────────────────────────────────────────────────────
class Player:
    SPEED     = 160.0   # px/s
    ROT_SPEED = 2.2     # rad/s
    RADIUS    = 14      # collision margin

    def __init__(self):
        self.x          = SPAWN_X
        self.y          = SPAWN_Y
        self.angle      = 0.0
        self.health     = 100
        self.max_health = 100
        self.ammo       = 50
        self.max_ammo   = 50
        self.kills      = 0
        self.shoot_cd   = 0.0   # seconds until can shoot again
        self.flash       = 0.0   # muzzle flash timer

    def move(self, dt, keys):
        sin_a = math.sin(self.angle)
        cos_a = math.cos(self.angle)
        dx = dy = 0

        spd = self.SPEED * dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += cos_a * spd;  dy += sin_a * spd
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= cos_a * spd;  dy -= sin_a * spd
        if keys[pygame.K_a]:
            dx += sin_a * spd;  dy -= cos_a * spd
        if keys[pygame.K_d]:
            dx -= sin_a * spd;  dy += cos_a * spd

        r = self.RADIUS
        if not is_wall(self.x + dx + math.copysign(r, dx), self.y):
            self.x += dx
        if not is_wall(self.x, self.y + dy + math.copysign(r, dy)):
            self.y += dy

        rot = 0
        if keys[pygame.K_LEFT]:  rot -= self.ROT_SPEED * dt
        if keys[pygame.K_RIGHT]: rot += self.ROT_SPEED * dt
        self.angle = (self.angle + rot) % (2 * math.pi)

    def shoot(self, enemies):
        if self.shoot_cd > 0 or self.ammo <= 0:
            return
        self.ammo    -= 1
        self.shoot_cd = 0.22
        self.flash    = 0.12

        # hit scan – find closest enemy in crosshair cone
        best_dist   = float('inf')
        best_enemy  = None
        for e in enemies:
            if not e.alive: continue
            dx = e.x - self.x
            dy = e.y - self.y
            dist = math.hypot(dx, dy)
            ang  = math.atan2(dy, dx)
            diff = (ang - self.angle + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) < 0.08 and dist < best_dist:
                best_dist  = dist
                best_enemy = e

        if best_enemy:
            dmg = random.randint(15, 35)
            best_enemy.take_damage(dmg)
            if not best_enemy.alive:
                self.kills += 1

    def reload(self):
        self.ammo = self.max_ammo

# ─────────────────────────────────────────────────────────────────────────────
#  ENEMY
# ─────────────────────────────────────────────────────────────────────────────
class Enemy:
    SPEED       = 55.0
    ATTACK_DIST = 52
    SIGHT_DIST  = 600

    def __init__(self, tx, ty):
        self.x          = tx * TILE + TILE // 2
        self.y          = ty * TILE + TILE // 2
        self.health     = 40
        self.alive      = True
        self.attack_cd  = 0.0
        self.anim_t     = random.random()   # offset so they don't all pulse together
        self.dist       = 9999.0
        self.screen_ang = 0.0

    def take_damage(self, dmg):
        self.health -= dmg
        if self.health <= 0:
            self.alive = False

    def update(self, dt, player):
        self.anim_t += dt
        dx = player.x - self.x
        dy = player.y - self.y
        self.dist = math.hypot(dx, dy)

        if self.dist > self.SIGHT_DIST:
            return

        # Chase
        if self.dist > self.ATTACK_DIST:
            spd  = self.SPEED * dt
            step = spd / max(self.dist, 1)
            nx   = self.x + dx * step
            ny   = self.y + dy * step
            if not is_wall(nx, self.y): self.x = nx
            if not is_wall(self.x, ny): self.y = ny

        # Attack
        self.attack_cd -= dt
        if self.dist <= self.ATTACK_DIST and self.attack_cd <= 0:
            dmg = random.randint(6, 14)
            player.health = max(0, player.health - dmg)
            self.attack_cd = 1.2

# ─────────────────────────────────────────────────────────────────────────────
#  RAYCASTING
# ─────────────────────────────────────────────────────────────────────────────
def cast_rays(player):
    """DDA raycasting. Returns list of (depth, wall_type, is_ns_face)."""
    results = []
    angle = player.angle - HALF_FOV + DELTA_ANGLE * 0.5

    ox, oy = player.x, player.y

    for _ in range(RAYS):
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)

        # ── horizontal grid intersections ─────────────────────────────────
        dh = MAX_DEPTH * TILE
        wh = 0
        if sin_a != 0:
            if sin_a > 0:
                y0 = (int(oy / TILE) + 1) * TILE
                dy_h = TILE
            else:
                y0 = int(oy / TILE) * TILE - 1e-5
                dy_h = -TILE
            tan_inv = cos_a / sin_a if sin_a else 1e15
            x0 = ox + (y0 - oy) * tan_inv
            dx_h = dy_h * tan_inv
            for _ in range(MAX_DEPTH):
                wt = tile_type(x0, y0)
                if wt:
                    dh = math.hypot(x0 - ox, y0 - oy)
                    wh = wt
                    break
                x0 += dx_h
                y0 += dy_h

        # ── vertical grid intersections ───────────────────────────────────
        dv = MAX_DEPTH * TILE
        wv = 0
        if cos_a != 0:
            if cos_a > 0:
                x0 = (int(ox / TILE) + 1) * TILE
                dx_v = TILE
            else:
                x0 = int(ox / TILE) * TILE - 1e-5
                dx_v = -TILE
            tan_a = sin_a / cos_a if cos_a else 1e15
            y0 = oy + (x0 - ox) * tan_a
            dy_v = dx_v * tan_a
            for _ in range(MAX_DEPTH):
                wt = tile_type(x0, y0)
                if wt:
                    dv = math.hypot(x0 - ox, y0 - oy)
                    wv = wt
                    break
                x0 += dx_v
                y0 += dy_v

        if dh < dv:
            depth, wtype, ns = dh, wh, True
        else:
            depth, wtype, ns = dv, wv, False

        # fix fish-eye
        depth *= math.cos(player.angle - angle)
        depth  = max(depth, 0.1)

        results.append((depth, wtype, ns))
        angle += DELTA_ANGLE

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def draw_sky(surf):
    """Gradient sky + floor."""
    for y in range(HALF_H):
        t = y / HALF_H
        c = lerp_color(SKY_TOP, SKY_BOT, t)
        pygame.draw.line(surf, c, (0, y), (SW, y))
    for y in range(HALF_H, SH):
        t = (y - HALF_H) / HALF_H
        c = lerp_color(FLOOR_TOP, FLOOR_BOT, t)
        pygame.draw.line(surf, c, (0, y), (SW, y))


def draw_walls(surf, ray_data):
    z_buf = []
    for i, (depth, wtype, ns) in enumerate(ray_data):
        if wtype == 0:
            z_buf.append(depth)
            continue

        proj_h = int(PROJ_DIST * TILE / depth)
        proj_h = min(proj_h, SH * 3)

        base  = (WALL_NS if ns else WALL_EW)[wtype - 1]
        fog   = max(0.0, 1.0 - depth / (MAX_DEPTH * TILE * 0.9))
        wall_c = shade(base, fog * 0.9 + 0.1)

        x = i * SCALE
        y = HALF_H - proj_h // 2
        pygame.draw.rect(surf, wall_c, (x, y, SCALE, proj_h))
        z_buf.append(depth)

    return z_buf


def draw_enemies(surf, player, enemies, z_buf):
    sprites = []
    for e in enemies:
        if not e.alive: continue
        dx = e.x - player.x
        dy = e.y - player.y
        dist = math.hypot(dx, dy)
        ang  = math.atan2(dy, dx)
        diff = (ang - player.angle + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) < HALF_FOV + 0.4:
            sprites.append((dist, diff, e))

    sprites.sort(key=lambda s: -s[0])   # far → near

    for dist, diff, e in sprites:
        if dist < 8: continue

        proj_h = int(PROJ_DIST * TILE / dist * 1.3)
        proj_h = min(proj_h, SH * 2)
        proj_w = int(proj_h * 0.7)

        sx = int((diff / FOV + 0.5) * SW) - proj_w // 2
        sy = HALF_H - proj_h // 2

        # pulse based on anim timer
        pulse = (math.sin(e.anim_t * 6) + 1) * 0.5
        hp_r  = e.health / 40.0

        # body colour: red→orange depending on health
        body_col  = lerp_color((200, 40, 20), (240, 160, 20), 1 - hp_r)
        # fog
        fog   = max(0.1, 1.0 - dist / (MAX_DEPTH * TILE * 0.8))
        body_col  = shade(body_col, fog)

        # draw column by column, respecting z-buffer
        for cx in range(max(0, sx), min(SW, sx + proj_w)):
            z_idx = min(cx // SCALE, len(z_buf) - 1)
            if dist >= z_buf[z_idx]: continue

            # determine part of sprite
            rel   = (cx - sx) / max(proj_w, 1)
            # head (top 25%), body (next 50%), legs (bottom 25%)
            for strip_sy in range(max(0, sy), min(SH, sy + proj_h)):
                rel_y = (strip_sy - sy) / max(proj_h, 1)
                if rel_y < 0.22:
                    # head – slightly lighter
                    col = lerp_color(body_col, (255,200,160), 0.35)
                elif rel_y < 0.70:
                    # body
                    col = body_col
                else:
                    # legs darker
                    col = shade(body_col, 0.6)

                # rim shading on edges
                edge = min(rel, 1 - rel) * 4
                col = shade(col, min(1.0, 0.4 + edge * 0.6))
                surf.set_at((cx, strip_sy), col)

        # eye glow
        eye_y = int(sy + proj_h * 0.14)
        eye_x = sx + proj_w // 2
        eye_r  = max(2, proj_h // 18)
        if 0 < eye_x < SW and 0 < eye_y < SH:
            glow_col = (int(255 * pulse), 30, 30)
            pygame.draw.circle(surf, glow_col, (eye_x, eye_y), eye_r)


def draw_gun(surf, player, dt):
    """Procedural gun drawn at bottom centre."""
    bx = SW // 2
    by = SH

    # sway
    sway_x = int(math.sin(pygame.time.get_ticks() * 0.002) * 4)
    sway_y = int(abs(math.sin(pygame.time.get_ticks() * 0.003)) * 3)
    bx += sway_x
    by -= sway_y

    # barrel
    pygame.draw.rect(surf, (75, 75, 75),  (bx - 12, by - 200, 24, 120), border_radius=3)
    pygame.draw.rect(surf, (55, 55, 55),  (bx -  8, by - 205, 16,  10))
    # body
    pygame.draw.rect(surf, (95, 95, 95),  (bx - 40, by - 100, 80, 60), border_radius=5)
    pygame.draw.rect(surf, (70, 70, 70),  (bx - 28, by -  55, 56, 15))
    # grip
    pygame.draw.polygon(surf, (60, 45, 30), [
        (bx - 20, by -  55),
        (bx + 20, by -  55),
        (bx + 28, by +  20),
        (bx - 28, by +  20),
    ])
    # trigger guard
    pygame.draw.arc(surf, (80, 80, 80),
                    pygame.Rect(bx - 15, by - 55, 30, 28),
                    math.pi, 2 * math.pi, 2)

    # muzzle flash
    if player.flash > 0:
        r = random.randint(18, 30)
        cx, cy = bx, by - 205
        for _ in range(8):
            ang_f = random.uniform(0, 2 * math.pi)
            lx = cx + int(math.cos(ang_f) * r)
            ly = cy + int(math.sin(ang_f) * r)
            pygame.draw.line(surf, (255, 200, 60), (cx, cy), (lx, ly), 2)
        pygame.draw.circle(surf, (255, 240, 180), (cx, cy), r // 3)


def draw_hud(surf, player, font_big, font_med, font_sm, enemies):
    hbar_h = 72
    # semi-transparent HUD bar
    hud = pygame.Surface((SW, hbar_h), pygame.SRCALPHA)
    hud.fill((8, 4, 2, 210))
    surf.blit(hud, (0, SH - hbar_h))

    # ── Health bar ──────────────────────────────────────────────────────────
    hp   = player.health / player.max_health
    hcol = lerp_color((200, 20, 20), (20, 200, 20), hp)
    lbl  = font_sm.render("HEALTH", True, (180, 180, 180))
    surf.blit(lbl, (22, SH - hbar_h + 8))
    pygame.draw.rect(surf, DGRAY,  (22, SH - hbar_h + 28, 180, 16), border_radius=4)
    pygame.draw.rect(surf, hcol,   (22, SH - hbar_h + 28, int(180 * hp), 16), border_radius=4)
    pygame.draw.rect(surf, WHITE,  (22, SH - hbar_h + 28, 180, 16), 1, border_radius=4)
    hp_n = font_med.render(str(player.health), True, WHITE)
    surf.blit(hp_n, (210, SH - hbar_h + 24))

    # ── Ammo ────────────────────────────────────────────────────────────────
    ar   = player.ammo / player.max_ammo
    acol = lerp_color((200, 80, 20), (220, 220, 20), ar)
    lbl2 = font_sm.render("AMMO", True, (180, 180, 180))
    surf.blit(lbl2, (SW // 2 - 90, SH - hbar_h + 8))
    pygame.draw.rect(surf, DGRAY,  (SW // 2 - 90, SH - hbar_h + 28, 180, 16), border_radius=4)
    pygame.draw.rect(surf, acol,   (SW // 2 - 90, SH - hbar_h + 28, int(180 * ar), 16), border_radius=4)
    pygame.draw.rect(surf, WHITE,  (SW // 2 - 90, SH - hbar_h + 28, 180, 16), 1, border_radius=4)
    am_n = font_med.render(str(player.ammo), True, WHITE)
    surf.blit(am_n, (SW // 2 + 98, SH - hbar_h + 24))

    # ── Kills ────────────────────────────────────────────────────────────────
    alive_n = sum(1 for e in enemies if e.alive)
    kl = font_sm.render(f"KILLS  {player.kills}", True, RED)
    al = font_sm.render(f"REMAINING  {alive_n}", True, ORANGE)
    surf.blit(kl, (SW - 220, SH - hbar_h + 12))
    surf.blit(al, (SW - 220, SH - hbar_h + 38))

    # ── Crosshair ───────────────────────────────────────────────────────────
    cx, cy = SW // 2, HALF_H
    col = (255, 50, 50) if player.shoot_cd > 0 else (220, 220, 220)
    pygame.draw.line(surf, col, (cx - 14, cy), (cx -  4, cy), 2)
    pygame.draw.line(surf, col, (cx +  4, cy), (cx + 14, cy), 2)
    pygame.draw.line(surf, col, (cx, cy - 14), (cx, cy -  4), 2)
    pygame.draw.line(surf, col, (cx, cy +  4), (cx, cy + 14), 2)
    pygame.draw.circle(surf, col, (cx, cy), 3, 1)


def draw_minimap(surf, player, enemies, font_sm):
    MM   = 180
    CELL = MM // max(MAP_W, MAP_H)
    mx   = SW - MM - 12
    my   = 12

    mm = pygame.Surface((MM, MM), pygame.SRCALPHA)
    mm.fill((0, 0, 0, 160))

    for row in range(MAP_H):
        for col in range(MAP_W):
            c  = MAP_DATA[row][col]
            x0 = col * CELL; y0 = row * CELL
            if c in CHAR_TO_TYPE:
                wt = CHAR_TO_TYPE[c]
                wc = WALL_NS[wt - 1]
                pygame.draw.rect(mm, wc + (220,), (x0, y0, CELL, CELL))
            pygame.draw.rect(mm, (25, 25, 25, 80), (x0, y0, CELL, CELL), 1)

    # enemies
    for e in enemies:
        if not e.alive: continue
        ex = int(e.x / TILE * CELL)
        ey = int(e.y / TILE * CELL)
        pygame.draw.circle(mm, (255, 50, 50, 255), (ex, ey), max(2, CELL // 2))

    # player dot + direction line
    px = int(player.x / TILE * CELL)
    py = int(player.y / TILE * CELL)
    lx = px + int(math.cos(player.angle) * 12)
    ly = py + int(math.sin(player.angle) * 12)
    pygame.draw.line(mm, (50, 255, 50, 255), (px, py), (lx, ly), 2)
    pygame.draw.circle(mm, (50, 255, 50, 255), (px, py), 4)

    surf.blit(mm, (mx, my))
    pygame.draw.rect(surf, (200, 200, 200), (mx, my, MM, MM), 1)
    lbl = font_sm.render("MAP", True, (200, 200, 200))
    surf.blit(lbl, (mx + 4, my + MM + 2))


def draw_screen_flash(surf, player, prev_health):
    """Red vignette when hit."""
    if player.health < prev_health:
        flash = pygame.Surface((SW, SH), pygame.SRCALPHA)
        flash.fill((180, 0, 0, 80))
        surf.blit(flash, (0, 0))


def draw_overlay(surf, font_big, font_med, msg, sub=""):
    overlay = pygame.Surface((SW, SH), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surf.blit(overlay, (0, 0))
    t = font_big.render(msg, True, YELLOW)
    surf.blit(t, (SW // 2 - t.get_width() // 2, SH // 2 - 50))
    if sub:
        s = font_med.render(sub, True, WHITE)
        surf.blit(s, (SW // 2 - s.get_width() // 2, SH // 2 + 10))


# ─────────────────────────────────────────────────────────────────────────────
#  TITLE SCREEN
# ─────────────────────────────────────────────────────────────────────────────
def title_screen(screen, clock):
    font_giant = pygame.font.SysFont("Impact", 100)
    font_big   = pygame.font.SysFont("Impact", 38)
    font_sm    = pygame.font.SysFont("Consolas", 18)

    t = 0
    while True:
        dt = clock.tick(FPS) / 1000
        t += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                return   # any other key → start game
            if event.type == pygame.MOUSEBUTTONDOWN:
                return

        # background
        screen.fill((5, 0, 0))
        for _ in range(40):
            rx = random.randint(0, SW); ry = random.randint(0, HALF_H)
            pygame.draw.circle(screen, (random.randint(60,120), 0, 0), (rx, ry), 1)

        # title
        pulse = 0.85 + 0.15 * math.sin(t * 3)
        r_col = (int(220 * pulse), int(20 * pulse), int(20 * pulse))
        title = font_giant.render("D O O M . P Y", True, r_col)
        screen.blit(title, (SW // 2 - title.get_width() // 2, 160))

        sub = font_big.render("A RAYCASTING FPS IN PURE PYTHON", True, (180, 60, 60))
        screen.blit(sub, (SW // 2 - sub.get_width() // 2, 290))

        blink = font_sm.render("PRESS ANY KEY TO PLAY", True,
                               WHITE if int(t * 2) % 2 == 0 else (100, 100, 100))
        screen.blit(blink, (SW // 2 - blink.get_width() // 2, 400))

        controls = [
            "W/S  — Move       A/D  — Strafe",
            "← →  — Turn       MOUSE — Look",
            "SPACE / LMB — Shoot        R — Reload",
            "ESC — Quit",
        ]
        for i, line in enumerate(controls):
            c = font_sm.render(line, True, (130, 130, 130))
            screen.blit(c, (SW // 2 - c.get_width() // 2, 470 + i * 24))

        pygame.display.flip()


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN GAME LOOP
# ─────────────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SW, SH))
    pygame.display.set_caption("DOOM.py  |  ESC = Quit")
    clock = pygame.time.Clock()

    font_big = pygame.font.SysFont("Impact",   52)
    font_med = pygame.font.SysFont("Impact",   30)
    font_sm  = pygame.font.SysFont("Consolas", 16, bold=True)

    title_screen(screen, clock)

    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    player  = Player()
    enemies = [Enemy(x, y) for x, y in ENEMY_SPAWNS]

    game_state   = "playing"   # "playing" | "dead" | "won"
    prev_health  = player.health
    hit_flash    = 0.0

    while True:
        dt = min(clock.tick(FPS) / 1000, 0.05)

        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_r and game_state == "playing":
                    player.reload()
                if event.key == pygame.K_SPACE and game_state == "playing":
                    player.shoot(enemies)
                if event.key == pygame.K_RETURN and game_state != "playing":
                    # restart
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                    player    = Player()
                    enemies   = [Enemy(x, y) for x, y in ENEMY_SPAWNS]
                    game_state = "playing"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game_state == "playing":
                    player.shoot(enemies)

        # ── Update ────────────────────────────────────────────────────────
        if game_state == "playing":
            # mouse look
            mx, _ = pygame.mouse.get_rel()
            player.angle = (player.angle + mx * 0.0025) % (2 * math.pi)

            keys = pygame.key.get_pressed()
            player.move(dt, keys)

            player.shoot_cd = max(0.0, player.shoot_cd - dt)
            player.flash     = max(0.0, player.flash    - dt)

            for e in enemies:
                if e.alive:
                    e.update(dt, player)

            if player.health != prev_health:
                hit_flash = 0.18
            hit_flash = max(0.0, hit_flash - dt)

            if player.health <= 0:
                game_state = "dead"
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)
            elif all(not e.alive for e in enemies):
                game_state = "won"
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

        # ── Draw ──────────────────────────────────────────────────────────
        draw_sky(screen)

        ray_data = cast_rays(player)
        z_buf    = draw_walls(screen, ray_data)
        draw_enemies(screen, player, enemies, z_buf)
        draw_gun(screen, player, dt)

        # hit vignette
        if hit_flash > 0:
            alpha = int(hit_flash / 0.18 * 100)
            vign = pygame.Surface((SW, SH), pygame.SRCALPHA)
            vign.fill((200, 0, 0, alpha))
            screen.blit(vign, (0, 0))

        draw_hud(screen, player, font_big, font_med, font_sm, enemies)
        draw_minimap(screen, player, enemies, font_sm)

        if game_state == "dead":
            draw_overlay(screen, font_big, font_med,
                         "YOU DIED", "Press ENTER to play again  |  ESC to quit")
        elif game_state == "won":
            draw_overlay(screen, font_big, font_med,
                         "YOU WIN!", f"All enemies eliminated  —  Kills: {player.kills}  |  ENTER to restart")

        # FPS counter
        fps_t = font_sm.render(f"FPS {clock.get_fps():.0f}", True, (100, 100, 100))
        screen.blit(fps_t, (12, SH - 95))

        prev_health = player.health
        pygame.display.flip()


if __name__ == "__main__":
    main()