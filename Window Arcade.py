"""
WINDOW ARCADE - classic games played with real windows on your Windows desktop.
Every bird, pipe, ghost, dot, spike, paddle and ball is its own window.

Games:  Flappy | Window-Man (Pac-Man) | Geometry Dash | Pong | Galaga | Snake | Breakout | Whack-a-Window | Window Bros
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
        try:  # click-through + never activated, so Windows can't bring it above the game windows
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x80000 | 0x20 | 0x08000000 | 0x80)
        except Exception:
            pass
        win.attributes("-alpha", 0.5 if self.app.overlay.get() else 0.0)  # overlay setting
        return win

    def raise_game(self):
        """Put every game window back on top of the overlay."""
        for w in list(self.wins):
            if w is not getattr(self, "backdrop", None):
                try:
                    w.lift()
                except Exception:
                    pass

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

    def field(self):
        self.ax, self.ay = int(self.sw * .2), int(self.sh * .14)
        self.aw, self.ah = int(self.sw * .6), int(self.sh * .72)
        self.arena(self.ax, self.ay, self.aw, self.ah)

    def update(self, dt, K):
        self.K = K
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


# --------------------------------------------------------------------------- GALAGA
class Galaga(Base):
    name = "Window Galaga"
    desc = "A/D or arrows move, hold SPACE / W to fire (2 shots at once). Enemies dive-bomb you and their shots keep flying!"
    SPRITE = ["..x..x..", "...xx...", "..xxxx..", ".xx..xx.", "xxxxxxxx", "x.x..x.x"]
    COLORS = ["#ff5252", "#ffb74d", "#81c784", "#4dd0e1", "#ba68c8"]

    def setup(self):
        s = self.s
        self.field()
        self.level, self.lives, self.safe, self.cool = 1, 3, 0, 0
        self.shw, self.shh = int(64 * s), int(34 * s)
        self.sy, self.sx = self.ay + self.ah - self.shh - int(14 * s), self.ax + self.aw / 2 - int(32 * s)
        self.ship = self.mk(self.shw, self.shh, self.sx, self.sy)
        self.ship.canvas.create_polygon(self.shw / 2, 2, self.shw - 2, self.shh - 2, 2, self.shh - 2,
                                        fill="#4fc3f7", outline="#0277bd", width=3)
        self.iw = int(44 * s)
        self.ih = int(self.iw * .75)
        self.pbs, self.eb, self.en = [], [], []
        self.sway_t, self.fa, self.dn = 0, 0, 120
        self.wave()

    def info(self):
        self.app.set_info(f"Stage {self.level}   Lives {self.lives}\nBest: {self.best()}")

    def slot(self, e):
        s = self.s
        fw = 7 * int(74 * s) + self.iw
        amp = min(160 * s, (self.aw - fw) / 2 - 12)
        x = self.ax + (self.aw - fw) / 2 + math.sin(self.sway_t * .025) * amp + e["c"] * int(74 * s)
        return x, self.ay + 50 * s + e["r"] * int(58 * s)

    def wave(self):
        cw = self.iw / 8
        for r in range(min(3 + self.level, 5)):
            for c in range(8):
                e = {"r": r, "c": c, "m": "form", "t": 0, "ph": 0}
                e["x"], e["y"] = self.slot(e)
                e["win"] = self.mk(self.iw, self.ih, e["x"], e["y"])
                for j, row in enumerate(self.SPRITE):
                    for i, ch in enumerate(row):
                        if ch == "x":
                            e["win"].canvas.create_rectangle(i * cw, j * cw, (i + 1) * cw, (j + 1) * cw,
                                                             fill=self.COLORS[r], outline=self.COLORS[r])
                self.en.append(e)

    def bullet(self, x, y, w, h, col, vx, vy):
        return {"win": self.mk(w, h, x, y, col), "x": x, "y": y, "w": w, "h": h, "vx": vx, "vy": vy}

    def shoot(self, e):
        s = self.s
        bx, by = e["x"] + self.iw / 2 - 4, e["y"] + self.ih
        dx, dy = self.sx + self.shw / 2 - bx, self.sy - by
        d, sp = math.hypot(dx, dy) or 1, (5 + .5 * self.level) * s
        self.eb.append(self.bullet(bx, by, 8, 18 * s, "#ff5252", dx / d * sp, max(dy / d * sp, sp * .6)))

    def hurt(self, now):
        self.lives -= 1
        self.safe = now + 1.5
        if self.lives <= 0:
            self.over()
            return True
        self.info()
        return False

    def hits(self, ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def tick(self, dt, K):
        s, now = self.s, time.perf_counter()
        self.sx = min(max(self.sx + (K.held("right") - K.held("left")) * 9 * s * dt, self.ax + 6),
                      self.ax + self.aw - self.shw - 6)
        self.move(self.ship, self.sx, self.sy)
        self.cool -= dt
        if K.held("jump") and self.cool <= 0 and len(self.pbs) < 2:
            self.cool = 8
            self.pbs.append(self.bullet(self.sx + self.shw / 2 - 3, self.sy - 20 * s, 6, 20 * s, "#ffffff", 0, -15 * s))
        for b in self.pbs[:]:
            b["y"] += b["vy"] * dt
            self.move(b["win"], b["x"], b["y"])
            hit = next((e for e in self.en if self.hits(b["x"], b["y"], b["w"], b["h"],
                                                          e["x"], e["y"], self.iw, self.ih)), None)
            if hit:
                self.kill(hit["win"])
                self.en.remove(hit)
                self.add(1 if hit["m"] == "form" else 2)  # divers are worth double
            if hit or b["y"] < self.ay:
                self.kill(b["win"])
                self.pbs.remove(b)
        if not self.en:  # next stage - enemy shots already in the air keep flying
            self.level += 1
            self.add(10)
            self.wave()
            self.info()
        self.sway_t += dt * (1 + .12 * self.level)
        self.fa += dt
        upd = self.fa >= 3
        if upd:
            self.fa = 0
        self.dn -= dt
        forms = [e for e in self.en if e["m"] == "form"]
        if self.dn <= 0 and sum(e["m"] == "dive" for e in self.en) < min(1 + self.level, 5) and forms:
            for _ in range(1 + (self.level >= 3)):
                if forms:
                    e = forms.pop(random.randrange(len(forms)))
                    e["m"], e["t"], e["ph"] = "dive", 0, random.uniform(0, 6)
            self.dn = max(40, 150 - self.level * 16)
        for e in self.en[:]:
            if e["m"] == "form":
                if upd:
                    e["x"], e["y"] = self.slot(e)
                    self.move(e["win"], e["x"], e["y"])
                if random.random() < .004 * dt * (1 + .15 * self.level) and len(self.eb) < 6 + 2 * self.level:
                    self.shoot(e)
                continue
            if e["m"] == "dive":
                e["t"] += dt
                e["y"] += (5 + .5 * self.level) * s * dt
                e["x"] += (math.sin(e["t"] * .09 + e["ph"]) * 6 * s + (self.sx + self.shw / 2 - e["x"] - self.iw / 2) * .012) * dt
                e["x"] = min(max(e["x"], self.ax), self.ax + self.aw - self.iw)
                if random.random() < .015 * dt * (1 + .2 * self.level) and len(self.eb) < 6 + 2 * self.level:
                    self.shoot(e)
                if e["y"] > self.ay + self.ah:  # swoops off the bottom, re-enters from the top
                    e["y"], e["m"] = self.ay - self.ih, "ret"
            else:  # returning to formation
                tx, ty = self.slot(e)
                dx, dy = tx - e["x"], ty - e["y"]
                d, st = math.hypot(dx, dy) or 1, 7 * s * dt
                if d <= st:
                    e["x"], e["y"], e["m"] = tx, ty, "form"
                else:
                    e["x"] += dx / d * st
                    e["y"] += dy / d * st
            self.move(e["win"], e["x"], e["y"])
            if now > self.safe and self.hits(e["x"], e["y"], self.iw, self.ih, self.sx, self.sy, self.shw, self.shh):
                self.kill(e["win"])
                self.en.remove(e)
                if self.hurt(now):
                    return
        for b in self.eb[:]:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            self.move(b["win"], b["x"], b["y"])
            if b["y"] > self.ay + self.ah or b["x"] < self.ax or b["x"] > self.ax + self.aw:
                self.kill(b["win"])
                self.eb.remove(b)
            elif now > self.safe and self.hits(b["x"], b["y"], b["w"], b["h"], self.sx, self.sy, self.shw, self.shh):
                self.kill(b["win"])
                self.eb.remove(b)
                if self.hurt(now):
                    return


# --------------------------------------------------------------------------- SNAKE
class Snake(Base):
    name, desc = "Window Snake", "Eat the apple windows and grow. Don't hit a wall or yourself. WASD / arrows."
    HEAD, BODY = "#c6ff5a", "#4caf50"

    def setup(self):
        self.field()
        self.cell = int(40 * self.s)
        self.cols, self.rows = (self.aw - 16) // self.cell, (self.ah - 16) // self.cell
        self.ox = self.ax + (self.aw - self.cols * self.cell) // 2
        self.oy = self.ay + (self.ah - self.rows * self.cell) // 2
        cx, cy = self.cols // 2, self.rows // 2
        self.body = [(cx - i, cy) for i in range(3)]
        self.segs = [self.seg(x, y, i == 0) for i, (x, y) in enumerate(self.body)]
        self.dirv = self.nxt = (1, 0)
        self.acc, self.food, self.fc = 0, None, None
        self.place_food()

    def pos(self, x, y):
        return self.ox + x * self.cell, self.oy + y * self.cell

    def seg(self, x, y, head):
        px, py = self.pos(x, y)
        w = self.mk(self.cell - 2, self.cell - 2, px + 1, py + 1, self.HEAD if head else self.BODY)
        w.canvas.create_rectangle(1, 1, self.cell - 4, self.cell - 4, outline="#1b5e20", width=2)
        return w

    def place_food(self):
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in self.body]
        if not free:
            self.over()
            return
        if self.food:
            self.kill(self.food)
        self.fc = random.choice(free)
        px, py = self.pos(*self.fc)
        c = self.cell
        self.food = self.mk(c - 6, c - 6, px + 3, py + 3)
        self.food.canvas.create_oval(2, 2, c - 8, c - 8, fill="#ff5252", outline="#b71c1c", width=3)

    def tick(self, dt, K):
        for n, v in (("up", (0, -1)), ("down", (0, 1)), ("left", (-1, 0)), ("right", (1, 0))):
            if K.hit(n) and v != (-self.dirv[0], -self.dirv[1]):
                self.nxt = v
        self.acc += dt
        if self.acc < max(2.5, 5 - self.score * .12):
            return
        self.acc, self.dirv = 0, self.nxt
        nx, ny = self.body[0][0] + self.dirv[0], self.body[0][1] + self.dirv[1]
        eat = (nx, ny) == self.fc
        if not (0 <= nx < self.cols and 0 <= ny < self.rows) or (nx, ny) in (self.body if eat else self.body[:-1]):
            self.segs[0].canvas.config(bg="#ff5252")
            self.over()
            return
        self.body.insert(0, (nx, ny))
        self.segs[0].canvas.config(bg=self.BODY)
        if eat:
            w = self.seg(nx, ny, True)
            self.add(1)
        else:
            self.body.pop()
            w = self.segs.pop()
            w.canvas.config(bg=self.HEAD)
            px, py = self.pos(nx, ny)
            self.move(w, px + 1, py + 1)
        self.segs.insert(0, w)
        if eat:
            self.place_food()


# --------------------------------------------------------------------------- BREAKOUT
class Breakout(Base):
    name, desc = "Window Breakout", "A/D or arrows move the paddle, SPACE launches. Smash every brick window!"
    COLORS = ["#ef5350", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5"]

    def setup(self):
        s = self.s
        self.field()
        self.level, self.lives, self.spd = 1, 3, 8 * s
        self.pw, self.ph, self.bd = int(150 * s), int(24 * s), int(26 * s)
        self.py, self.px = self.ay + self.ah - int(60 * s), self.ax + self.aw / 2 - int(75 * s)
        self.pad = self.mk(self.pw, self.ph, self.px, self.py, "#4fc3f7")
        self.ball = self.mk(self.bd, self.bd, 0, 0)
        self.ball.canvas.create_oval(2, 2, self.bd - 2, self.bd - 2, fill="white", outline="#cfd8dc", width=2)
        self.bricks = []
        self.build()
        self.stick()

    def info(self):
        self.app.set_info(f"Level {self.level}   Lives {self.lives}\nBest: {self.best()}")

    def build(self):
        s, cols = self.s, 9
        bw, bh = int((self.aw - 60 * s) / cols) - 6, int(30 * s)
        for r in range(min(3 + self.level, 5)):
            for c in range(cols):
                x, y = self.ax + 30 * s + c * (bw + 6), self.ay + 40 * s + r * (bh + 6)
                w = self.mk(bw, bh, x, y, self.COLORS[r])
                w.canvas.create_rectangle(1, 1, bw - 2, bh - 2, outline="#222", width=2)
                self.bricks.append({"win": w, "x": x, "y": y, "w": bw, "h": bh})

    def mpad(self, dt):
        K = self.K
        self.px = min(max(self.px + (K.held("right") - K.held("left")) * 12 * self.s * dt, self.ax + 6),
                      self.ax + self.aw - self.pw - 6)
        self.move(self.pad, self.px, self.py)

    def stick(self):
        self.vx = self.vy = 0
        self.bx, self.by = self.px + self.pw / 2 - self.bd / 2, self.py - self.bd - 2
        self.move(self.ball, self.bx, self.by)

    def idle(self, dt, now):
        self.mpad(dt)
        self.stick()

    def on_start(self):
        a = random.uniform(-.4, .4)
        self.vx, self.vy = self.spd * math.sin(a), -self.spd * math.cos(a)

    def tick(self, dt, K):
        self.mpad(dt)
        self.bx += self.vx * dt
        self.by += self.vy * dt
        if self.bx < self.ax + 4: self.bx, self.vx = self.ax + 4, abs(self.vx)
        if self.bx + self.bd > self.ax + self.aw - 4: self.bx, self.vx = self.ax + self.aw - 4 - self.bd, -abs(self.vx)
        if self.by < self.ay + 4: self.by, self.vy = self.ay + 4, abs(self.vy)
        if (self.vy > 0 and self.by + self.bd >= self.py and self.by <= self.py + self.ph
                and self.bx + self.bd >= self.px and self.bx <= self.px + self.pw):
            off = max(-1, min(1, ((self.bx + self.bd / 2) - (self.px + self.pw / 2)) / (self.pw / 2)))
            self.vx, self.vy = self.spd * math.sin(off * 1.05), -self.spd * math.cos(off * 1.05)
            self.by = self.py - self.bd
        for b in self.bricks:
            if (self.bx < b["x"] + b["w"] and self.bx + self.bd > b["x"] and
                    self.by < b["y"] + b["h"] and self.by + self.bd > b["y"]):
                ox = min(self.bx + self.bd - b["x"], b["x"] + b["w"] - self.bx)
                oy = min(self.by + self.bd - b["y"], b["y"] + b["h"] - self.by)
                if ox < oy: self.vx = -self.vx
                else: self.vy = -self.vy
                self.kill(b["win"])
                self.bricks.remove(b)
                self.add(1)
                break
        self.move(self.ball, self.bx, self.by)
        if not self.bricks:
            self.level += 1
            self.add(10)
            self.spd *= 1.08
            self.build()
            self.state = "ready"
            self.stick()
            self.app.set_info(f"Level {self.level}   Lives {self.lives}\nPress SPACE to launch")
        elif self.by > self.ay + self.ah:
            self.lives -= 1
            if self.lives <= 0:
                self.over()
            else:
                self.state = "ready"
                self.stick()
                self.app.set_info(f"Lives {self.lives}\nPress SPACE to launch")


# --------------------------------------------------------------------------- WHACK-A-WINDOW
class Whack(Base):
    name, desc = "Whack-a-Window", "Click the mole windows before they vanish! Miss 5 and it's over."

    def setup(self):
        self.field()
        self.lives, self.moles, self.nxt, self.size = 5, [], 0, int(110 * self.s)

    def info(self):
        self.app.set_info(f"Lives {self.lives}\nBest: {self.best()}")

    def whack(self, win):
        m = next((m for m in self.moles if m["win"] is win), None)
        if m and self.state == "play":
            self.kill(win)
            self.moles.remove(m)
            self.add(1)

    def tick(self, dt, K):
        now, n = time.perf_counter(), self.size
        if now >= self.nxt and len(self.moles) < 4:
            x = random.uniform(self.ax + 10, self.ax + self.aw - n - 10)
            y = random.uniform(self.ay + 10, self.ay + self.ah - n - 10)
            w = self.mk(n, n, x, y, "#6d4c41")
            c = w.canvas
            c.create_oval(6, 6, n - 6, n - 14, fill="#8d6e63", outline="#3e2723", width=3)
            c.create_oval(n * .28, n * .25, n * .4, n * .4, fill="black")
            c.create_oval(n * .6, n * .25, n * .72, n * .4, fill="black")
            c.create_oval(n * .42, n * .45, n * .58, n * .56, fill="#ff8a80", outline="#3e2723")
            bar = c.create_rectangle(6, n - 10, n - 6, n - 4, fill="#7bd957", outline="")
            c.bind("<Button-1>", lambda e, w=w: self.whack(w), add="+")
            self.moles.append({"win": w, "bar": bar, "born": now, "die": now + max(.8, 2.2 - self.score * .04)})
            self.nxt = now + max(.35, 1.1 - self.score * .02)
        for m in self.moles[:]:
            left = (m["die"] - now) / (m["die"] - m["born"])
            m["win"].canvas.coords(m["bar"], 6, n - 10, 6 + (n - 12) * max(left, 0), n - 4)
            if left <= 0:
                self.kill(m["win"])
                self.moles.remove(m)
                self.lives -= 1
                if self.lives <= 0:
                    for o in self.moles:
                        self.kill(o["win"])
                    self.moles = []
                    self.over()
                    return
                self.info()


# --------------------------------------------------------------------------- WINDOW BROS (side-scrolling platformer)
class WindowBros(Base):
    name = "Window Bros"
    desc = "A/D run, SPACE / W jump (hold = higher). Stomp blobs, jump spikes, grab coins, reach the flag. 10 levels!"
    THEMES = {
        "day":    dict(g="#a0522d", t="#4caf50", l="#6d3a1a", b="#c0642b", p="#2e9c3a"),
        "cave":   dict(g="#37474f", t="#546e7a", l="#263238", b="#455a64", p="#00897b"),
        "night":  dict(g="#3e2f5b", t="#7e57c2", l="#2a1f40", b="#5e4a8a", p="#26a69a"),
        "castle": dict(g="#4a4a4a", t="#b71c1c", l="#2b2b2b", b="#6d6d6d", p="#8d6e63"),
        "sky":    dict(g="#e3f2fd", t="#90caf9", l="#90a4ae", b="#ce93d8", p="#ffb74d"),
    }
    # name, theme, length(tiles), pit, enemy, pipe, platform, spiky-share, seed
    LEVELS = [
        ("Sunny Plains", "day", 100, .04, .05, .04, .10, 0, 11),
        ("Pipe Valley", "day", 110, .05, .06, .12, .10, 0, 12),
        ("Gap Hills", "day", 120, .12, .06, .05, .10, 0, 13),
        ("Deep Cave", "cave", 120, .07, .09, .08, .16, 0, 14),
        ("Blob Town", "day", 130, .07, .14, .08, .12, 0, 15),
        ("Spike Fields", "night", 130, .08, .12, .06, .14, .25, 16),
        ("Cloud Run", "sky", 140, .16, .07, .03, .22, .10, 17),
        ("Dark Forest", "night", 140, .10, .15, .08, .14, .35, 18),
        ("Fire Castle", "castle", 150, .13, .15, .08, .12, .40, 19),
        ("Final Fortress", "castle", 170, .15, .18, .10, .14, .50, 20),
    ]

    def setup(self):
        s = self.s
        self.T, self.R = int(48 * s), 11
        self.oy = self.sh - int(90 * s) - self.R * self.T
        self.g = .62 * s
        self.lv, self.lives, self.coins = 0, 3, 0
        self.pw, self.ph = int(34 * s), int(44 * s)
        self.hwin = self.mk(self.pw, self.ph, -999, -999)
        self.face, self.leg, self.lt, self.drawn = 1, 0, 0, None
        self.objs, self.near, self.safe, self.clear_t, self.lastcam = [], [], 0, 0, None
        self.ground = False
        self.load(0)

    def info(self):
        self.app.set_info(f"Level {self.lv + 1}/{len(self.LEVELS)}: {self.LEVELS[self.lv][0]}\n"
                          f"Lives {self.lives}   Coins {self.coins}")

    # ---------- level generation (each level is a fixed, hand-tuned seed) ----------
    def new(self, k, x, y, w, h, **kw):
        o = {"k": k, "x": x, "y": y, "w": w, "h": h, "win": None, "st": True, "solid": False}
        o.update(kw)
        self.objs.append(o)
        return o

    def load(self, idx):
        for o in self.objs:
            if o["win"] is not None:
                self.kill(o["win"])
        T, R, s = self.T, self.R, self.s
        name, theme, n, pit, en, pipe, plat, spk, seed = self.LEVELS[idx]
        rnd, gt = random.Random(seed), (self.R - 2) * T
        self.th, self.objs, self.enl, self.coinl = self.THEMES[theme], [], [], []
        self.n, self.lastcam, self.cam = n, None, 0
        ground, last = [True] * n, -99
        for x in range(14, n - 18):                     # pits
            if x - last > 6 and rnd.random() < pit:
                w = rnd.randint(2, 3 + (idx >= 5))
                for i in range(w):
                    ground[x + i] = False
                last = x + w
        x = 0
        while x < n:                                    # ground chunks (max 8 tiles wide)
            if ground[x]:
                e = x
                while e < n and ground[e] and e - x < 8:
                    e += 1
                self.new("ground", x * T, gt, (e - x) * T, 2 * T, solid=True)
                x = e
            else:
                x += 1
        used, pc, x = set(), set(), 14
        while x < n - 18:                               # pipes and platforms
            if all(ground[x - 1:x + 5]) and not used.intersection(range(x - 1, x + 5)):
                r = rnd.random()
                if r < pipe:
                    h = rnd.randint(2, 3)
                    self.new("pipe", x * T, gt - h * T, 2 * T, h * T, solid=True)
                    used.update(range(x - 1, x + 4))
                    pc.update((x, x + 1))
                    x += 5
                    continue
                if r < pipe + plat:
                    cnt, py = rnd.randint(3, 6), gt - 3 * T
                    if not all(ground[x - 3:x + cnt + 5]) or used.intersection(range(x - 3, x + cnt + 5)):
                        x += 1  # keep head-bump platforms well away from pits
                        continue
                    kinds = ["q" if rnd.random() < .3 else "b" for _ in range(cnt)]
                    j = 0
                    while j < cnt:
                        if kinds[j] == "q":
                            self.new("q", (x + j) * T, py, T, T, solid=True, used=False)
                            j += 1
                        else:
                            k = j
                            while k < cnt and kinds[k] == "b":
                                k += 1
                            self.new("brick", (x + j) * T, py, (k - j) * T, T, solid=True)
                            j = k
                    for j in range(cnt):
                        if rnd.random() < .6:
                            c = self.new("coin", (x + j) * T + T * .2, py - T * 1.1, T * .6, T * .6)
                            self.coinl.append(c)
                    used.update(range(x - 1, x + cnt + 1))
                    x += cnt + 3
                    continue
            x += 1
        x = 1
        while x < n:                                    # coin arcs over pits
            if not ground[x] and ground[x - 1]:
                e = x
                while e < n and not ground[e]:
                    e += 1
                for i, dy in enumerate((2.2, 2.8, 2.2)):
                    cx = (x + e) / 2 + (i - 1) * .8
                    self.coinl.append(self.new("coin", cx * T, gt - dy * T, T * .6, T * .6))
                x = e
            x += 1
        last_e, eh = -99, int(T * .85)
        for x in range(12, n - 18):                     # enemies
            if (ground[x] and x not in used and all(ground[x - 3:x + 4])  # never near pits / under platforms
                    and x - last_e > 4 and rnd.random() < en):
                sp = rnd.random() < spk
                e = self.new("enemy", x * T, gt - eh, eh, eh, st=False, spike=sp,
                             vx=0.0 if sp else -(1.3 + .12 * idx) * s, vy=0.0)  # spiky ones stand still
                self.enl.append(e)
                last_e = x
        for i in range(6):                              # staircase + flag
            self.new("stair", (n - 14 + i) * T, gt - (i + 1) * T, T, (i + 1) * T, solid=True)
        self.flag = self.new("flag", (n - 5) * T + T * .3, gt - 8 * T, T * .7, 8 * T)
        self.p = {"x": 2.0 * T, "y": gt - self.ph, "w": self.pw, "h": self.ph, "vx": 0.0, "vy": 0.0}

    # ---------- drawing ----------
    def make_win(self, o):
        T, k, th = self.T, o["k"], self.th
        w, h = int(o["w"]), int(o["h"])
        col = {"ground": th["g"], "brick": th["b"], "stair": th["b"], "pipe": th["p"], "q": "#ffb300"}.get(k)
        win = self.mk(w, h, -9999, -9999, col)
        o["win"] = win
        c = win.canvas
        if k in ("ground", "brick", "stair"):
            if k == "ground":
                c.create_rectangle(0, 0, w, T * .3, fill=th["t"], outline="")
            for x in range(0, w + 1, T):
                c.create_line(x, 0, x, h, fill=th["l"], width=2)
            for y in range(0, h + 1, T):
                c.create_line(0, y, w, y, fill=th["l"], width=2)
            c.create_rectangle(1, 1, w - 1, h - 1, outline=th["l"], width=2)
        elif k == "pipe":
            c.create_rectangle(0, 0, w - 1, T * .55, fill="#5fd36e", outline="#0b3d15", width=3)
            c.create_rectangle(T * .1, T * .55, w - T * .1, h - 1, outline="#0b3d15", width=3)
        elif k == "q":
            self.draw_q(o)
        elif k == "coin":
            c.create_oval(2, 2, w - 2, h - 2, fill="#ffd700", outline="#b8860b", width=3)
            c.create_line(w / 2, h * .25, w / 2, h * .75, fill="#b8860b", width=3)
        elif k == "enemy":
            sp = o["spike"]
            if sp:
                for i in range(3):
                    c.create_polygon(w * i / 3 + 2, h * .4, w * (i + .5) / 3, 0, w * (i + 1) / 3 - 2, h * .4,
                                     fill="#eeeeee", outline="#555")
            body = "#c62828" if sp else "#8b4513"
            c.create_oval(2, h * .3, w - 2, h - 6, fill=body, outline="#2b1200", width=3)
            c.create_rectangle(w * .1, h - 9, w * .4, h - 2, fill="#2b1200", outline="")
            c.create_rectangle(w * .6, h - 9, w * .9, h - 2, fill="#2b1200", outline="")
            for ex in (w * .3, w * .58):
                c.create_oval(ex, h * .42, ex + w * .14, h * .62, fill="white", outline="black")
                c.create_oval(ex + 3, h * .48, ex + w * .1, h * .6, fill="black")
        elif k == "flag":
            c.create_rectangle(w * .4, 0, w * .5, h, fill="#cfd8dc", outline="#607d8b")
            c.create_oval(w * .33, 0, w * .57, w * .24, fill="#ffd700", outline="#b8860b")
            c.create_polygon(w * .5, h * .04, w, h * .1, w * .5, h * .16, fill="#43a047", outline="#1b5e20", width=2)
        return win

    def draw_q(self, o):
        c, w, h = o["win"].canvas, int(o["w"]), int(o["h"])
        c.delete("all")
        c.config(bg="#8d6e63" if o["used"] else "#ffb300")
        c.create_rectangle(1, 1, w - 2, h - 2, outline="#5d4037", width=3)
        if not o["used"]:
            c.create_text(w / 2, h / 2, text="?", fill="white", font=("Segoe UI", int(h * .6), "bold"))

    def draw_hero(self, pose):
        key = (self.face, pose)
        if self.drawn == key:
            return
        self.drawn = key
        c, w, h, f = self.hwin.canvas, self.pw, self.ph, self.face
        c.delete("all")
        c.create_rectangle(w * .1, 0, w * .9, h * .22, fill="#00b8a9", outline="#00695c", width=2)
        bx = w * .55 if f > 0 else 0
        c.create_rectangle(bx, h * .16, bx + w * .45, h * .26, fill="#00897b", outline="#00695c")
        c.create_rectangle(w * .15, h * .22, w * .85, h * .48, fill="#ffcc99", outline="#a1662f", width=2)
        ex = w * .6 if f > 0 else w * .28
        c.create_rectangle(ex, h * .28, ex + w * .12, h * .4, fill="black")
        c.create_rectangle(w * .1, h * .48, w * .9, h * .78, fill="#e53935", outline="#7f0000", width=2)
        off = w * .1 if pose == 1 else (w * .14 if pose == 2 else 0)
        c.create_rectangle(w * .1 - off * (pose == 2), h * .78, w * .45 + off, h, fill="#283593", outline="#101a5c", width=2)
        c.create_rectangle(w * .55 - off, h * .78, w * .9 + off * (pose == 2), h, fill="#283593", outline="#101a5c", width=2)

    # ---------- physics ----------
    @staticmethod
    def ov(a, o, ex=0, ey=0):
        return (a["x"] + ex < o["x"] + o["w"] and a["x"] + a["w"] - ex > o["x"]
                and a["y"] + ey < o["y"] + o["h"] and a["y"] + a["h"] - ey > o["y"])

    def step(self, b, dt):
        b["x"] += b["vx"] * dt
        wall = False
        for o in self.near:
            if self.ov(b, o, 0, .5):
                if b["vx"] > 0: b["x"] = o["x"] - b["w"]
                elif b["vx"] < 0: b["x"] = o["x"] + o["w"]
                wall = True
        b["vy"] = min(b["vy"] + self.g * dt, 18 * self.s)
        vy0 = b["vy"]
        b["y"] += b["vy"] * dt
        ground, bump = False, None
        for o in self.near:
            if self.ov(b, o, .5, 0):
                if vy0 >= 0:
                    b["y"], ground = o["y"] - b["h"], True
                else:
                    b["y"], bump = o["y"] + o["h"], o
                b["vy"] = 0
        return wall, ground, bump

    def sync(self):
        T, cam = self.T, int(self.cam)
        vl, vr = cam - 2 * T, cam + self.sw + 2 * T
        moved = cam != self.lastcam
        self.lastcam = cam
        near = []
        for o in self.objs:
            if vl < o["x"] + o["w"] and o["x"] < vr:
                fresh = o["win"] is None
                if fresh:
                    self.make_win(o)
                if o["solid"]:
                    near.append(o)
                if fresh or moved or not o["st"]:
                    self.move(o["win"], o["x"] - cam, self.oy + o["y"])
            elif o["win"] is not None:
                self.kill(o["win"])
                o["win"] = None
        self.near = near

    def remove(self, o):
        if o["win"] is not None:
            self.kill(o["win"])
        self.objs.remove(o)

    def show_hero(self, pose):
        self.draw_hero(pose)
        self.move(self.hwin, self.p["x"] - self.cam, self.oy + self.p["y"])

    def idle(self, dt, now):
        self.sync()
        self.show_hero(0)

    def die(self, now):
        self.lives -= 1
        if self.lives <= 0:
            self.over()
        else:
            self.load(self.lv)
            self.safe = now + 1.5
            self.info()

    def next_level(self):
        self.clear_t = 0
        self.lv += 1
        if self.lv >= len(self.LEVELS):
            self.lv = len(self.LEVELS) - 1
            self.over()
            self.app.set_info(f"YOU BEAT ALL 10 LEVELS!\nScore {self.score}  -  SPACE to replay")
        else:
            self.load(self.lv)
            self.info()

    def tick(self, dt, K):
        s, T, now, p = self.s, self.T, time.perf_counter(), self.p
        done = bool(self.clear_t)
        d = 0 if done else K.held("right") - K.held("left")
        if d:
            p["vx"] = max(-5.6 * s, min(5.6 * s, p["vx"] + d * .7 * s * dt))
            self.face = d
        else:
            p["vx"] = 0 if abs(p["vx"]) < .1 else p["vx"] * .8 ** dt
        if self.ground and K.hit("jump") and not done:
            p["vy"], self.ground = -15.5 * s, False
        elif p["vy"] < 0 and not K.held("jump"):
            p["vy"] += self.g * dt * 1.2               # release jump = shorter hop
        prevb = p["y"] + p["h"]
        vy0 = p["vy"]
        wall, self.ground, bump = self.step(p, dt)
        if bump and vy0 < 0 and bump["k"] == "q" and not bump["used"]:
            bump["used"] = True
            self.draw_q(bump)
            self.coins += 1
            self.add(1)
            self.info()
        p["x"] = min(max(p["x"], self.cam), self.n * T - p["w"])
        self.cam = max(0, min(max(self.cam, p["x"] - self.sw * .4), self.n * T - self.sw))
        if p["y"] > (self.R + 1) * T:
            self.die(now)
            return
        if self.ground and abs(p["vx"]) > .5:
            self.lt += abs(p["vx"]) * dt
        pose = 2 if not self.ground else (int(self.lt / (9 * s)) % 2 if abs(p["vx"]) > .5 else 0)
        for e in self.enl[:]:                           # enemies
            if not (self.cam - T < e["x"] < self.cam + self.sw + T):
                continue
            wall, _, _ = self.step(e, dt)
            if wall:
                e["vx"] = -e["vx"]
            if e["y"] > (self.R + 2) * T:
                self.enl.remove(e)
                self.remove(e)
                continue
            if self.ov(p, e):
                if not e["spike"] and prevb <= e["y"] + e["h"] * .55:
                    self.enl.remove(e)
                    self.remove(e)
                    self.add(2)
                    p["vy"], self.ground = (-14 if K.held("jump") else -9) * s, False
                elif now > self.safe and not done:
                    self.die(now)
                    return
        for c in self.coinl[:]:                         # coins
            if self.cam - T < c["x"] < self.cam + self.sw + T and self.ov(p, c):
                self.coinl.remove(c)
                self.remove(c)
                self.coins += 1
                self.add(1)
                if self.coins % 20 == 0:
                    self.lives += 1
                self.info()
        if not done and self.ov(p, self.flag):          # flag = level clear
            self.clear_t = now
            self.add(10)
            self.app.set_info(f"Level {self.lv + 1} complete!\nLives {self.lives}   Coins {self.coins}")
        elif done and now - self.clear_t > 1.4:
            self.next_level()
            if self.state != "play":
                return
        self.sync()
        self.show_hero(pose)


# --------------------------------------------------------------------------- APP
GAMES = [Flappy, PacMan, GeoDash, Pong, Galaga, Snake, Breakout, Whack, WindowBros]


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
        if bd is not None:
            bd.attributes("-alpha", 0.5 if self.overlay.get() else 0.0)

    def build_menu(self):
        m = self.menu = tk.Toplevel(self.root)
        m.title("Window Arcade - choose a game")
        m.configure(bg="#14202e")
        m.attributes("-topmost", True)
        rows = (len(GAMES) + 1) // 2
        h = 80 + rows * 104
        m.geometry(f"880x{h}+{self.sw // 2 - 440}+{max(20, self.sh // 2 - h // 2)}")
        m.resizable(False, False)
        m.protocol("WM_DELETE_WINDOW", self.quit_game)
        m.bind("<Escape>", lambda e: self.quit_game())
        tk.Label(m, text="What do you want to play?", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#14202e").pack(pady=(14, 6))
        grid = tk.Frame(m, bg="#14202e")
        grid.pack()
        for i, cls in enumerate(GAMES):
            f = tk.Frame(grid, bg="#14202e")
            f.grid(row=i // 2, column=i % 2, padx=14, pady=4)
            tk.Button(f, text=cls.name, font=("Segoe UI", 14, "bold"), fg="white", bg="#2f6fdb", width=26,
                      activebackground="#1f4fa8", activeforeground="white", relief="flat", cursor="hand2",
                      command=lambda c=cls: self.launch(c)).pack(fill="x", ipady=5)
            tk.Label(f, text=cls.desc, font=("Segoe UI", 9), fg="#9fb3c8", bg="#14202e",
                     wraplength=380, height=2).pack(pady=(2, 0))

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
