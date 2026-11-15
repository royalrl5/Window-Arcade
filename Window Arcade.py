"""
WINDOW ARCADE - classic games played with real windows on your Windows desktop.
Every bird, pipe, ghost, dot, spike, paddle and ball is its own window.

Games:  Flappy Windows | Window-Man (Pac-Man) | Geometry Dash | Window Pong
Keys:   SPACE / UP / W = jump (start / restart)      W A S D or arrows = move
        ESC = quit.  The Controls window has MENU and END GAME buttons.
Run:    python window_arcade.py      (Python 3 for Windows; tkinter is built in)
"""
import ctypes
import math
import random
import time
import tkinter as tk

try:  # real screen pixels on high-DPI displays
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

TRANSPARENT = "#ff00ff"
KEYMAP = {"jump": (0x20, 0x26, 0x57), "up": (0x26, 0x57), "down": (0x28, 0x53),
          "left": (0x25, 0x41), "right": (0x27, 0x44)}  # Space/Up/W, arrows + WASD


def key_down(vk):
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


def set_console(cmd):  # 6 = minimize, 9 = restore (cmd, PowerShell or Windows Terminal)
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            hwnd = ctypes.windll.user32.GetAncestor(hwnd, 3) or hwnd
            ctypes.windll.user32.ShowWindow(hwnd, cmd)
    except Exception:
        pass


class Input:
    def __init__(self):
        self.cur = {k: False for k in KEYMAP}
        self.new = dict(self.cur)
        self.clicked = False

    def click(self):
        self.clicked = True

    def poll(self):
        for k, vks in KEYMAP.items():
            d = any(key_down(v) for v in vks)
            self.new[k] = d and not self.cur[k]
            self.cur[k] = d
        if self.clicked:
            self.new["jump"] = True
            self.clicked = False

    def held(self, k):
        return self.cur[k]

    def hit(self, k):
        return self.new[k]


class Base:
    name, desc = "", ""

    def __init__(self, app):
        self.app, self.sw, self.sh, self.s = app, app.sw, app.sh, app.s
        self.reset()

    def reset(self):
        self.wins, self.state, self.score, self.dead_t = [], "ready", 0, 0
        self.setup()
        self.app.set_score(0)
        self.app.set_info(f"Press SPACE or W to start\nBest: {self.best()}")

    def restart(self):
        self.cleanup()
        self.reset()

    def best(self):
        return self.app.best.get(self.name, 0)

    def info(self):
        self.app.set_info(f"Best: {self.best()}")

    def mk(self, w, h, x, y, color=None, alpha=None):
        win = tk.Toplevel(self.app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        if color is None:
            color = TRANSPARENT
            try:
                win.attributes("-transparentcolor", TRANSPARENT)
            except tk.TclError:
                pass
        if alpha:
            win.attributes("-alpha", alpha)
        win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
        c = tk.Canvas(win, width=int(w), height=int(h), bg=color, highlightthickness=0)
        c.pack()
        c.bind("<Button-1>", lambda e: self.app.K.click())
        win.canvas = c
        self.wins.append(win)
        return win

    def arena(self, x, y, w, h):
        win = self.mk(w, h, x, y, "#0a1128", 0.5)
        win.canvas.create_rectangle(2, 2, w - 2, h - 2, outline="#4fc3f7", width=4)
        self.backdrop = win
        if not self.app.overlay.get():  # background overlay setting is OFF
            win.withdraw()
        return win

    def move(self, win, x, y):
        win.geometry(f"+{int(x)}+{int(y)}")

    def kill(self, win):
        win.destroy()
        if win in self.wins:
            self.wins.remove(win)

    def cleanup(self):
        for w in self.wins:
            try:
                w.destroy()
            except Exception:
                pass
        self.wins = []

    def add(self, n):
        self.score += n
        self.app.set_score(self.score)

    def over(self):
        self.state, self.dead_t = "dead", time.perf_counter()
        self.app.best[self.name] = max(self.best(), self.score)
        self.app.set_info(f"Game over!  Best: {self.best()}\nSPACE or W to retry")

    def update(self, dt, K):
        now = time.perf_counter()
        if self.state == "ready":
            self.idle(dt, now)
            if K.hit("jump"):
                self.state = "play"
                self.info()
                self.on_start()
        elif self.state == "play":
            self.tick(dt, K)
        else:
            self.fall(dt)
            if K.hit("jump") and now - self.dead_t > 0.6:
                self.restart()

    def idle(self, dt, now): pass
    def on_start(self): pass
    def fall(self, dt): pass


# --------------------------------------------------------------------------- FLAPPY
class Flappy(Base):
    name, desc = "Flappy Windows", "Flap the bird window through the pipe windows."

    def setup(self):
        s = self.s
        self.g, self.fv, self.sp = 0.55 * s, -9.5 * s, 5 * s
        self.gap, self.pw, self.space = int(250 * s), int(120 * s), int(480 * s)
        self.bw, self.bh, self.bx = int(80 * s), int(60 * s), int(self.sw * 0.25)
        self.floor, self.rim = self.sh - int(50 * s), int(36 * s)
        self.by, self.vy, self.pipes = self.sh / 2 - self.bh / 2, 0.0, []
        self.bird = self.mk(self.bw, self.bh, self.bx, self.by)
        self.draw_bird()

    def draw_bird(self, dead=False):
        c, w, h = self.bird.canvas, self.bw, self.bh
        c.delete("all")
        c.create_oval(2, 4, w - 14, h - 4, fill="#e8453c" if dead else "#ffd23f", outline="#7a5b00", width=3)
        c.create_oval(w * .12, h * .38, w * .5, h * .82, fill="#fff3b0", outline="#7a5b00", width=2)
        c.create_oval(w * .55, h * .12, w * .8, h * .44, fill="white", outline="black", width=2)
        if dead:
            c.create_line(w * .6, h * .18, w * .6 + 12, h * .18 + 12, width=3)
            c.create_line(w * .6 + 12, h * .18, w * .6, h * .18 + 12, width=3)
        else:
            c.create_oval(w * .67, h * .2, w * .76, h * .36, fill="black")
        c.create_polygon(w - 16, h * .4, w, h * .5, w - 16, h * .62, fill="#ff7a1a", outline="#7a3500", width=2)

    def make_pipe(self):
        s, w, rim = self.s, self.pw, self.rim
        gy = random.randint(int(110 * s), self.floor - self.gap - int(110 * s))
        by = gy + self.gap
        top, bot = self.mk(w, gy, self.sw, 0, "#5cbf2a"), self.mk(w, self.sh - by, self.sw, by, "#5cbf2a")
        top.canvas.create_rectangle(0, gy - rim, w - 1, gy - 1, fill="#73d02f", outline="#2d5a12", width=3)
        top.canvas.create_rectangle(3, 0, w - 4, gy - rim, fill="#5cbf2a", outline="#2d5a12", width=3)
        bot.canvas.create_rectangle(0, 1, w - 1, rim, fill="#73d02f", outline="#2d5a12", width=3)
        bot.canvas.create_rectangle(3, rim, w - 4, self.sh - by, fill="#5cbf2a", outline="#2d5a12", width=3)
        self.pipes.append({"x": float(self.sw), "gy": gy, "top": top, "bot": bot, "done": False})

    def idle(self, dt, now):
        self.by = self.sh / 2 - self.bh / 2 + math.sin(now * 5) * 12
        self.move(self.bird, self.bx, self.by)

    def on_start(self):
        self.vy = self.fv

    def tick(self, dt, K):
        if K.hit("jump"):
            self.vy = self.fv
        self.vy += self.g * dt
        self.by += self.vy * dt
        if self.by < 0:
            self.by = self.vy = 0
        if not self.pipes or self.pipes[-1]["x"] <= self.sw - self.space:
            self.make_pipe()
        m = int(8 * self.s)
        for p in self.pipes:
            p["x"] -= self.sp * dt
            self.move(p["top"], p["x"], 0)
            self.move(p["bot"], p["x"], p["gy"] + self.gap)
            if not p["done"] and p["x"] + self.pw < self.bx:
                p["done"] = True
                self.add(1)
            if (p["x"] < self.bx + self.bw - m and p["x"] + self.pw > self.bx + m and
                    (self.by + m < p["gy"] or self.by + self.bh - m > p["gy"] + self.gap)):
                self.die()
        while self.pipes and self.pipes[0]["x"] + self.pw < -20:
            p = self.pipes.pop(0)
            self.kill(p["top"])
            self.kill(p["bot"])
        if self.by + self.bh >= self.floor:
            self.by = self.floor - self.bh
            self.die()
        self.move(self.bird, self.bx, self.by)

    def die(self):
        if self.state == "play":
            self.over()
            self.draw_bird(True)
            self.vy = self.fv * 0.6

    def fall(self, dt):
        self.vy += self.g * dt
        self.by = min(self.by + self.vy * dt, self.floor - self.bh)
        self.move(self.bird, self.bx, self.by)


# --------------------------------------------------------------------------- PAC-MAN
class PacMan(Base):
    name, desc = "Window-Man", "Eat every dot, dodge the ghost windows. Big dots make ghosts edible."
    COLORS = ["#ff3b3b", "#ff9ad5", "#35e0e0", "#ffa733"]
    ANG = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}

    def setup(self):
        s = self.s
        self.ax, self.ay, self.aw, self.ah = int(self.sw * .2), int(self.sh * .14), int(self.sw * .6), int(self.sh * .72)
        self.arena(self.ax, self.ay, self.aw, self.ah)
        self.ps = self.gs = int(58 * s)
        self.level, self.lives, self.fright, self.safe, self.mt = 1, 3, 0, 0, 0
        self.pac = self.mk(self.ps, self.ps, 0, 0)
        self.dots, self.ghosts = [], []
        self.new_level()

    def info(self):
        self.app.set_info(f"Level {self.level}   Lives {self.lives}\nBest: {self.best()}")

    def corner(self, i):
        return [(self.ax, self.ay), (self.ax + self.aw - self.gs, self.ay),
                (self.ax, self.ay + self.ah - self.gs), (self.ax + self.aw - self.gs, self.ay + self.ah - self.gs)][i % 4]

    def home(self, g, i):
        g["x"], g["y"] = self.corner(i)
        g["t"] = 0
        self.move(g["win"], g["x"], g["y"])

    def center_pac(self):
        self.px, self.py = self.ax + self.aw / 2 - self.ps / 2, self.ay + self.ah / 2 - self.ps / 2
        self.dirv = (1, 0)
        self.draw_pac()
        self.move(self.pac, self.px, self.py)

    def new_level(self):
        for g in self.ghosts:
            self.kill(g["win"])
        for d in self.dots:
            self.kill(d["win"])
        self.dots, self.ghosts = [], []
        for i in range(16):
            big = i < 2
            d = int((38 if big else 18) * self.s)
            x = random.uniform(self.ax + 20, self.ax + self.aw - d - 20)
            y = random.uniform(self.ay + 20, self.ay + self.ah - d - 20)
            w = self.mk(d, d, x, y)
            w.canvas.create_oval(2, 2, d - 2, d - 2, fill="#ffffff" if big else "#ffe9a8",
                                 outline="#ffb300" if big else "#ffe9a8", width=3)
            self.dots.append({"win": w, "x": x, "y": y, "d": d, "big": big})
        for i in range(min(1 + self.level, 4)):
            g = {"win": self.mk(self.gs, self.gs, 0, 0), "c": self.COLORS[i], "dir": (0, 0), "f": None}
            self.home(g, i)
            self.draw_ghost(g)
            self.ghosts.append(g)
        self.center_pac()

    def draw_pac(self):
        c, n = self.pac.canvas, self.ps
        m = 6 + 34 * abs(math.sin(self.mt * .5))
        c.delete("all")
        c.create_arc(2, 2, n - 2, n - 2, start=self.ANG[self.dirv] + m, extent=360 - 2 * m,
                     fill="#ffd400", outline="#7a5b00", width=3, style=tk.PIESLICE)

    def draw_ghost(self, g, fr=False, flash=False):
        if g["f"] == (fr, flash):
            return
        g["f"] = (fr, flash)
        c, n = g["win"].canvas, self.gs
        col = "#ffffff" if flash else "#2a3cff" if fr else g["c"]
        c.delete("all")
        c.create_arc(2, 2, n - 2, n - 2, start=0, extent=180, fill=col, outline=col)
        c.create_rectangle(2, n / 2, n - 2, n - 8, fill=col, outline=col)
        for i in range(3):
            c.create_polygon(2 + i * (n - 4) / 3, n - 8, 2 + (i + .5) * (n - 4) / 3, n - 1,
                             2 + (i + 1) * (n - 4) / 3, n - 8, fill=col, outline=col)
        for ex in (n * .28, n * .56):
            if fr:
                c.create_oval(ex + 4, n * .3, ex + 12, n * .3 + 8, fill="white", outline="white")
            else:
                c.create_oval(ex, n * .25, ex + n * .18, n * .5, fill="white", outline="white")
                c.create_oval(ex + 4, n * .33, ex + n * .13, n * .47, fill="#1a237e", outline="#1a237e")

    def tick(self, dt, K):
        now, s = time.perf_counter(), self.s
        for n, v in (("up", (0, -1)), ("down", (0, 1)), ("left", (-1, 0)), ("right", (1, 0))):
            if K.hit(n):
                self.dirv = v
        sp = 6.5 * s * dt
        self.px = min(max(self.px + self.dirv[0] * sp, self.ax), self.ax + self.aw - self.ps)
        self.py = min(max(self.py + self.dirv[1] * sp, self.ay), self.ay + self.ah - self.ps)
        self.mt += dt
        self.draw_pac()
        self.move(self.pac, self.px, self.py)
        pcx, pcy = self.px + self.ps / 2, self.py + self.ps / 2
        for d in self.dots[:]:
            if abs(d["x"] + d["d"] / 2 - pcx) < self.ps * .45 and abs(d["y"] + d["d"] / 2 - pcy) < self.ps * .45:
                self.kill(d["win"])
                self.dots.remove(d)
                self.add(1)
                if d["big"]:
                    self.fright = now + 7
        if not self.dots:
            self.level += 1
            self.add(10)
            self.new_level()
            self.info()
            return
        fr = now < self.fright
        gsp = (3.2 + .5 * self.level) * s * (0.6 if fr else 1) * dt
        for g in self.ghosts:
            g["t"] -= dt
            if g["t"] <= 0:
                g["t"] = random.randint(12, 30)
                dx, dy = pcx - (g["x"] + self.gs / 2), pcy - (g["y"] + self.gs / 2)
                if fr:
                    dx, dy = -dx, -dy
                horiz = (abs(dx) > abs(dy)) == (random.random() < .75)
                g["dir"] = (1 if dx > 0 else -1, 0) if horiz else (0, 1 if dy > 0 else -1)
                if random.random() < .15:
                    g["dir"] = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            nx, ny = g["x"] + g["dir"][0] * gsp, g["y"] + g["dir"][1] * gsp
            cx = min(max(nx, self.ax), self.ax + self.aw - self.gs)
            cy = min(max(ny, self.ay), self.ay + self.ah - self.gs)
            if (cx, cy) != (nx, ny):
                g["t"] = 0
            g["x"], g["y"] = cx, cy
            self.move(g["win"], cx, cy)
            self.draw_ghost(g, fr, fr and self.fright - now < 2 and int(now * 5) % 2 == 0)
            if abs(cx - self.px) < self.ps * .7 and abs(cy - self.py) < self.ps * .7:
                if fr:
                    self.add(5)
                    self.home(g, random.randrange(4))
                elif now > self.safe:
                    self.lives -= 1
                    if self.lives <= 0:
                        self.over()
                    else:
                        for i, o in enumerate(self.ghosts):
                            self.home(o, i)
                        self.center_pac()
                        self.safe = now + 2
                        self.info()
                    return


# --------------------------------------------------------------------------- GEOMETRY DASH
class GeoDash(Base):
    name, desc = "Geometry Dash", "Hold SPACE / W to jump spikes and land on blocks."

    def setup(self):
        s = self.s
        self.cs, self.cx, self.gy = int(60 * s), int(self.sw * .2), int(self.sh * .78)
        self.D = int(self.cs * 1.5)
        self.g, self.jv, self.sp = 1.0 * s, -17 * s, 7.5 * s
        self.cy, self.vy, self.rot, self.ground = self.gy - self.cs, 0.0, 0.0, True
        self.obs, self.gap_need = [], 0
        gl = self.mk(self.sw, int(10 * s), 0, self.gy, "#00e5ff")
        self.cube = self.mk(self.D, self.D, 0, 0)
        self.draw_cube()
        self.place_cube()

    def place_cube(self):
        off = (self.D - self.cs) / 2
        self.move(self.cube, self.cx - off, self.cy - off)

    def draw_cube(self, dead=False):
        c, D, h, a = self.cube.canvas, self.D, self.cs / 2, math.radians(self.rot)
        co, si = math.cos(a), math.sin(a)
        P = lambda x, y: (D / 2 + x * co - y * si, D / 2 + x * si + y * co)
        sq = lambda x0, y0, x1, y1, f: c.create_polygon(P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1),
                                                        fill=f, outline="#222", width=3 if f == "#ffe600" or f == "#ff5a4d" else 1)
        c.delete("all")
        sq(-h, -h, h, h, "#ff5a4d" if dead else "#ffe600")
        sq(-h * .35 - h * .2, -h * .45, -h * .35 + h * .2, -h * .05, "#111")
        sq(h * .35 - h * .2, -h * .45, h * .35 + h * .2, -h * .05, "#111")
        sq(-h * .5, h * .3, h * .5, h * .55, "#111")

    def spike(self, x):
        ss = int(52 * self.s)
        w = self.mk(ss, ss, x, self.gy - ss)
        w.canvas.create_polygon(3, ss - 2, ss / 2, 3, ss - 3, ss - 2, fill="#111", outline="#ff3b6b", width=3)
        self.obs.append({"k": "s", "win": w, "x": x, "y": self.gy - ss, "w": ss, "h": ss, "done": False})

    def block(self, x, n):
        bs = int(60 * self.s)
        w = self.mk(bs * n, bs, x, self.gy - bs)
        for i in range(n):
            w.canvas.create_rectangle(i * bs + 2, 2, (i + 1) * bs - 2, bs - 2, fill="#101820", outline="#00e5ff", width=3)
        self.obs.append({"k": "b", "win": w, "x": x, "y": self.gy - bs, "w": bs * n, "h": bs, "done": False})

    def spawn(self):
        x, ss = self.sw + 20, int(52 * self.s)
        r = random.choice(["s", "s", "ss", "b", "bbb", "sb"])
        if r == "s": self.spike(x)
        elif r == "ss": self.spike(x); self.spike(x + ss)
        elif r == "b": self.block(x, 1)
        elif r == "bbb": self.block(x, 3)
        else: self.spike(x); self.block(x + int(200 * self.s), 2)
        self.gap_need = random.uniform(1.05, 1.7) * 32 * self.sp

    def tick(self, dt, K):
        s = self.s
        self.sp = min(7.5 + self.score * .12, 11) * s
        if self.ground and (K.held("jump") or K.hit("jump")):
            self.vy, self.ground = self.jv, False
        pb = self.cy + self.cs
        self.vy += self.g * dt
        self.cy += self.vy * dt
        cb, land, dead = self.cy + self.cs, False, False
        if cb >= self.gy:
            self.cy, land = self.gy - self.cs, True
        m = int(8 * s)
        cl, cr = self.cx + m, self.cx + self.cs - m
        if not self.obs or self.obs[-1]["x"] + self.obs[-1]["w"] < self.sw - self.gap_need:
            self.spawn()
        for o in self.obs:
            o["x"] -= self.sp * dt
            self.move(o["win"], o["x"], o["y"])
            if o["k"] == "b":
                if o["x"] < cr and o["x"] + o["w"] > cl:
                    if pb <= o["y"] + 8 * s and cb >= o["y"]:
                        self.cy, land = o["y"] - self.cs, True
                    elif self.cy + self.cs > o["y"] + 2 * s:
                        dead = True
            elif (o["x"] + o["w"] * .25 < cr and o["x"] + o["w"] * .75 > cl
                  and self.cy + self.cs - m > o["y"] + o["h"] * .35):
                dead = True
            if not o["done"] and o["x"] + o["w"] < self.cx:
                o["done"] = True
                self.add(1)
        for o in [o for o in self.obs if o["x"] + o["w"] < -50]:
            self.kill(o["win"])
            self.obs.remove(o)
        if land:
            self.vy, self.ground = 0, True
            self.rot = round(self.rot / 90) * 90 % 360
        else:
            self.ground = False
            self.rot += 5.6 * dt
        self.draw_cube()
        self.place_cube()
        if dead:
            self.over()
            self.draw_cube(True)


# --------------------------------------------------------------------------- PONG
class Pong(Base):
    name, desc = "Window Pong", "W / S or arrows move your paddle. Don't let the ball past!"

    def setup(self):
        s = self.s
        self.ax, self.ay, self.aw, self.ah = int(self.sw * .2), int(self.sh * .14), int(self.sw * .6), int(self.sh * .72)
        a = self.arena(self.ax, self.ay, self.aw, self.ah)
        a.canvas.create_line(self.aw / 2, 12, self.aw / 2, self.ah - 12, fill="#4fc3f7", dash=(12, 12), width=3)
        self.pw, self.ph, self.bd = int(26 * s), int(150 * s), int(38 * s)
        self.lx, self.rx = self.ax + int(30 * s), self.ax + self.aw - int(30 * s) - self.pw
        self.ly = self.ry = self.ay + self.ah / 2 - self.ph / 2
        self.lp = self.mk(self.pw, self.ph, self.lx, self.ly, "#4fc3f7")
        self.rp = self.mk(self.pw, self.ph, self.rx, self.ry, "#ff8a65")
        self.ball = self.mk(self.bd, self.bd, 0, 0)
        self.ball.canvas.create_oval(2, 2, self.bd - 2, self.bd - 2, fill="white", outline="#cfd8dc", width=2)
        self.spd = 7 * s
        self.serve()

    def serve(self):
        a = random.uniform(-.5, .5)
        self.vx, self.vy = self.spd * math.cos(a), self.spd * math.sin(a)
        self.bx, self.by = self.ax + self.aw / 2 - self.bd / 2, self.ay + self.ah / 2 - self.bd / 2
        self.move(self.ball, self.bx, self.by)

    def bounce(self, py, d):
        off = max(-1, min(1, ((self.by + self.bd / 2) - (py + self.ph / 2)) / (self.ph / 2)))
        self.spd = min(self.spd * 1.06, 18 * self.s)
        a = off * .9
        self.vx, self.vy = d * self.spd * math.cos(a), self.spd * math.sin(a)
        self.bx = self.lx + self.pw if d == 1 else self.rx - self.bd

    def tick(self, dt, K):
        s, lo, hi = self.s, self.ay, self.ay + self.ah - self.ph
        if K.held("up"): self.ly -= 11 * s * dt
        if K.held("down"): self.ly += 11 * s * dt
        self.ly = min(max(self.ly, lo), hi)
        tgt = self.by + self.bd / 2 - self.ph / 2 if self.vx > 0 else self.ay + self.ah / 2 - self.ph / 2
        step = min(abs(tgt - self.ry), min(6 + self.score * .15, 9.5) * s * dt)
        self.ry = min(max(self.ry + (step if tgt > self.ry else -step), lo), hi)
        self.bx += self.vx * dt
        self.by += self.vy * dt
        if self.by < self.ay: self.by, self.vy = self.ay, abs(self.vy)
        if self.by + self.bd > self.ay + self.ah: self.by, self.vy = self.ay + self.ah - self.bd, -abs(self.vy)
        if (self.vx < 0 and self.bx <= self.lx + self.pw and self.bx + self.bd >= self.lx
                and self.by + self.bd >= self.ly and self.by <= self.ly + self.ph):
            self.bounce(self.ly, 1)
            self.add(1)
        elif (self.vx > 0 and self.bx + self.bd >= self.rx and self.bx <= self.rx + self.pw
              and self.by + self.bd >= self.ry and self.by <= self.ry + self.ph):
            self.bounce(self.ry, -1)
        if self.bx + self.bd < self.ax:
            self.over()
        elif self.bx > self.ax + self.aw:
            self.add(5)
            self.serve()
        self.move(self.lp, self.lx, self.ly)
        self.move(self.rp, self.rx, self.ry)
        self.move(self.ball, self.bx, self.by)


# --------------------------------------------------------------------------- APP
GAMES = [Flappy, PacMan, GeoDash, Pong]


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.sw, self.sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.s = max(0.6, self.sh / 1080)
        self.K, self.best, self.game, self.closing = Input(), {}, None, False
        self.overlay = tk.BooleanVar(value=True)  # background overlay in Window-Man / Pong
        self.last = time.perf_counter()
        self.build_score()
        self.build_controls()
        self.build_menu()
        self.root.after(300, lambda: set_console(6))  # auto-minimize the cmd window
        self.loop()

    def build_score(self):
        r = self.root
        r.title("Window Arcade")
        r.configure(bg="#1e2a38")
        r.attributes("-topmost", True)
        r.geometry(f"300x190+{self.sw - 340}+40")
        r.resizable(False, False)
        self.score_lbl = tk.Label(r, text="0", font=("Segoe UI", 50, "bold"), fg="white", bg="#1e2a38")
        self.score_lbl.pack(pady=(2, 0))
        self.info_lbl = tk.Label(r, text="Pick a game", font=("Segoe UI", 11), fg="#cfd8e3", bg="#1e2a38")
        self.info_lbl.pack()
        r.bind("<Escape>", lambda e: self.quit_game())
        r.protocol("WM_DELETE_WINDOW", self.quit_game)

    def build_controls(self):
        c = tk.Toplevel(self.root)
        c.title("Controls")
        c.configure(bg="#1e2a38")
        c.attributes("-topmost", True)
        c.geometry(f"300x140+{self.sw - 340}+310")
        c.resizable(False, False)
        c.protocol("WM_DELETE_WINDOW", self.quit_game)
        c.bind("<Escape>", lambda e: self.quit_game())
        row = tk.Frame(c, bg="#1e2a38")
        row.pack(expand=True, fill="both")
        for text, bg, cmd in (("MENU", "#2f6fdb", self.to_menu), ("END GAME", "#d9362b", self.quit_game)):
            tk.Button(row, text=text, font=("Segoe UI", 14, "bold"), fg="white", bg=bg, activebackground=bg,
                      activeforeground="white", relief="flat", cursor="hand2", command=cmd
                      ).pack(side="left", expand=True, fill="both", padx=10, pady=(14, 6))
        tk.Checkbutton(c, text="Background overlay (Window-Man / Pong)", variable=self.overlay,
                       command=self.toggle_overlay, font=("Segoe UI", 10), fg="white", bg="#1e2a38",
                       selectcolor="#1e2a38", activebackground="#1e2a38", activeforeground="white",
                       cursor="hand2").pack(pady=(0, 8))

    def toggle_overlay(self):
        bd = getattr(self.game, "backdrop", None)
        if bd is None:
            return
        if self.overlay.get():
            bd.deiconify()
            bd.lower()  # keep it behind the game windows
        else:
            bd.withdraw()

    def build_menu(self):
        m = self.menu = tk.Toplevel(self.root)
        m.title("Window Arcade - choose a game")
        m.configure(bg="#14202e")
        m.attributes("-topmost", True)
        h = 90 + len(GAMES) * 100
        m.geometry(f"480x{h}+{self.sw // 2 - 240}+{max(20, self.sh // 2 - h // 2)}")
        m.resizable(False, False)
        m.protocol("WM_DELETE_WINDOW", self.quit_game)
        m.bind("<Escape>", lambda e: self.quit_game())
        tk.Label(m, text="What do you want to play?", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#14202e").pack(pady=(16, 8))
        for cls in GAMES:
            f = tk.Frame(m, bg="#14202e")
            f.pack(fill="x", padx=24, pady=4)
            tk.Button(f, text=cls.name, font=("Segoe UI", 14, "bold"), fg="white", bg="#2f6fdb",
                      activebackground="#1f4fa8", activeforeground="white", relief="flat", cursor="hand2",
                      command=lambda c=cls: self.launch(c)).pack(fill="x", ipady=6)
            tk.Label(f, text=cls.desc, font=("Segoe UI", 9), fg="#9fb3c8", bg="#14202e",
                     wraplength=430).pack(pady=(2, 0))

    def set_score(self, n):
        self.score_lbl.config(text=str(n))

    def set_info(self, t):
        self.info_lbl.config(text=t)

    def launch(self, cls):
        self.menu.withdraw()
        self.game = cls(self)

    def to_menu(self):
        if self.game:
            self.game.cleanup()
            self.game = None
        self.set_score(0)
        self.set_info("Pick a game")
        self.menu.deiconify()
        self.menu.lift()

    def quit_game(self):
        if self.closing:
            return
        self.closing = True
        set_console(9)  # bring the cmd window back
        self.root.destroy()

    def loop(self):
        if self.closing:
            return
        t = time.perf_counter()
        dt = min((t - self.last) * 60.0, 3.0)
        self.last = t
        self.K.poll()
        if self.game:
            self.game.update(dt, self.K)
        self.root.after(max(1, 16 - int((time.perf_counter() - t) * 1000)), self.loop)


if __name__ == "__main__":
    App().root.mainloop()
