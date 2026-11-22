import sys
import math
import random
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QGroupBox, QGridLayout, QFrame,
    QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient, QPainterPath
)

WORLD_W, WORLD_H = 800, 600
CELL = 60
GW = WORLD_W // CELL + 2
GH = WORLD_H // CELL + 2
MAX_C, MAX_F, MAX_P = 500, 350, 80
INIT_C, INIT_F, INIT_P = 60, 120, 8
FOOD_NUT = 25
PREY_NUT = 60
SP_THR = 75
HIST_INT = 20
MAX_HIST = 500
SEASON_LEN = 600
MATE_RANGE = 80
SUPER_FOOD_CHANCE = 0.08

SEASONS = {
    0: ("Spring", QColor(30, 50, 30), 2.0),
    1: ("Summer", QColor(45, 45, 30), 1.0),
    2: ("Autumn", QColor(50, 38, 25), 0.5),
    3: ("Winter", QColor(30, 30, 45), 0.15),
}

BG = QColor(15, 15, 22)
PBG = QColor(22, 22, 32)
CBG = QColor(30, 30, 42)
TP = QColor(220, 220, 230)
TS = QColor(140, 140, 160)
ACC = QColor(80, 200, 130)
GRC = QColor(28, 28, 38)
BRC = QColor(45, 45, 60)


class Gene:
    __slots__ = ("speed", "size", "vision", "efficiency",
                 "r", "g", "b", "repro_th", "lifespan")

    BOUNDS = {
        "speed": (0.5, 7.0), "size": (2.0, 14.0),
        "vision": (10.0, 300.0), "efficiency": (0.2, 2.5),
        "repro_th": (40, 200), "lifespan": (300, 4000),
    }
    NUM_ATTRS = ("speed", "size", "vision", "efficiency", "repro_th", "lifespan")
    COL_ATTRS = ("r", "g", "b")

    def __init__(self, **kw):
        self.speed = kw.get("speed", random.uniform(1.5, 3.5))
        self.size = kw.get("size", random.uniform(3.0, 7.0))
        self.vision = kw.get("vision", random.uniform(40.0, 120.0))
        self.efficiency = kw.get("efficiency", random.uniform(0.6, 1.2))
        self.r = max(30, min(255, kw.get("r", random.randint(40, 255))))
        self.g = max(30, min(255, kw.get("g", random.randint(40, 255))))
        self.b = max(30, min(255, kw.get("b", random.randint(40, 255))))
        self.repro_th = kw.get("repro_th", random.uniform(70, 110))
        self.lifespan = kw.get("lifespan", random.uniform(800, 2000))

    def mutate(self, rate=0.2, st=0.15):
        n = Gene(**{a: getattr(self, a) for a in
                    list(self.NUM_ATTRS) + list(self.COL_ATTRS)})
        for a in self.NUM_ATTRS:
            if random.random() < rate:
                lo, hi = self.BOUNDS[a]
                setattr(n, a, max(lo, min(hi,
                    getattr(n, a) + random.gauss(0, getattr(n, a) * st))))
        for a in self.COL_ATTRS:
            if random.random() < rate:
                setattr(n, a, max(30, min(255,
                    int(getattr(n, a) + random.gauss(0, 30)))))
        return n

    @staticmethod
    def crossover(g1, g2):
        c = Gene()
        for a in Gene.NUM_ATTRS:
            v = getattr(g1, a) if random.random() < 0.5 else getattr(g2, a)
            if random.random() < 0.1:
                v = (getattr(g1, a) + getattr(g2, a)) / 2
            setattr(c, a, v)
        for a in Gene.COL_ATTRS:
            v = getattr(g1, a) if random.random() < 0.5 else getattr(g2, a)
            if random.random() < 0.15:
                v = max(30, min(255, int((getattr(g1, a) + getattr(g2, a)) / 2)))
            setattr(c, a, v)
        return c

    def color(self):
        return QColor(int(self.r), int(self.g), int(self.b))


class PredatorGene:
    __slots__ = ("speed", "vision", "size", "efficiency")
    BOUNDS = {"speed": (1.5, 6.0), "vision": (30, 250),
              "size": (3.0, 12.0), "efficiency": (0.3, 2.0)}

    def __init__(self, **kw):
        self.speed = kw.get("speed", random.uniform(2.5, 4.0))
        self.vision = kw.get("vision", random.uniform(80, 160))
        self.size = kw.get("size", random.uniform(5.0, 9.0))
        self.efficiency = kw.get("efficiency", random.uniform(0.7, 1.3))

    def mutate(self, rate=0.2, st=0.15):
        n = PredatorGene(**{a: getattr(self, a) for a in self.BOUNDS})
        for a in self.BOUNDS:
            if random.random() < rate:
                lo, hi = self.BOUNDS[a]
                setattr(n, a, max(lo, min(hi,
                    getattr(n, a) + random.gauss(0, getattr(n, a) * st))))
        return n


class Food:
    __slots__ = ("x", "y", "nutrition", "alive", "pulse", "super")

    def __init__(self, x=None, y=None):
        self.x = x if x is not None else random.uniform(0, WORLD_W)
        self.y = y if y is not None else random.uniform(0, WORLD_H)
        self.super = random.random() < SUPER_FOOD_CHANCE
        self.nutrition = FOOD_NUT * (2.5 if self.super else 1.0) + random.uniform(-3, 3)
        self.alive = True
        self.pulse = random.uniform(0, math.tau)


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "life", "sz")

    def __init__(self, x, y, color, sz=2.0, spd=1.5):
        self.x, self.y = x, y
        a = random.uniform(0, math.tau)
        s = random.uniform(0.3, spd)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.color = QColor(color)
        self.life = 1.0
        self.sz = sz


class Creature:
    _n = 0

    def __init__(self, x, y, genes=None, gen=0):
        Creature._n += 1
        self.id = Creature._n
        self.x, self.y = x, y
        self.genes = genes or Gene()
        self.gen = gen
        self.energy = 50.0
        self.max_e = 180.0
        self.age = 0
        self.dir = random.uniform(0, math.tau)
        self.alive = True
        self.sp_id = 0
        self.children = 0
        self.rcd = 0

    def update(self, fg, pred_pos):
        if not self.alive:
            return
        self.age += 1
        if self.rcd > 0:
            self.rcd -= 1
        if self.age > self.genes.lifespan:
            self.alive = False
            return

        fdx, fdy, fleeing = 0.0, 0.0, False
        for px, py in pred_pos:
            dx = self.x - px
            if dx > WORLD_W / 2: dx -= WORLD_W
            elif dx < -WORLD_W / 2: dx += WORLD_W
            dy = self.y - py
            if dy > WORLD_H / 2: dy -= WORLD_H
            elif dy < -WORLD_H / 2: dy += WORLD_H
            d2 = dx * dx + dy * dy
            vr2 = (self.genes.vision * 0.7) ** 2
            if d2 < vr2 and d2 > 0.1:
                d = math.sqrt(d2)
                fdx += dx / d / d
                fdy += dy / d / d
                fleeing = True

        if fleeing:
            fl = math.sqrt(fdx * fdx + fdy * fdy)
            if fl > 0:
                fa = math.atan2(fdy, fdx)
                diff = fa - self.dir
                while diff > math.pi: diff -= math.tau
                while diff < -math.pi: diff += math.tau
                self.dir += diff * 0.35
                self.x = (self.x + math.cos(self.dir) * self.genes.speed * 1.2) % WORLD_W
                self.y = (self.y + math.sin(self.dir) * self.genes.speed * 1.2) % WORLD_H
                self.energy -= 0.18
                return

        vsq = self.genes.vision ** 2
        vc = int(self.genes.vision / CELL) + 1
        cx, cy = int(self.x / CELL), int(self.y / CELL)
        bf, bdsq = None, vsq
        bdx = bdy = 0.0
        for dx in range(-vc, vc + 1):
            gx = (cx + dx) % GW
            for dy in range(-vc, vc + 1):
                gy = (cy + dy) % GH
                for f in fg.get((gx, gy)):
                    fx = f.x - self.x
                    if fx > WORLD_W / 2: fx -= WORLD_W
                    elif fx < -WORLD_W / 2: fx += WORLD_W
                    fy = f.y - self.y
                    if fy > WORLD_H / 2: fy -= WORLD_H
                    elif fy < -WORLD_H / 2: fy += WORLD_H
                    dsq = fx * fx + fy * fy
                    if dsq < bdsq:
                        bdsq, bf = dsq, f
                        bdx, bdy = fx, fy

        if bf:
            t = math.atan2(bdy, bdx)
            diff = t - self.dir
            while diff > math.pi: diff -= math.tau
            while diff < -math.pi: diff += math.tau
            self.dir += diff * 0.2
        else:
            self.dir += random.gauss(0, 0.4)

        self.x = (self.x + math.cos(self.dir) * self.genes.speed) % WORLD_W
        self.y = (self.y + math.sin(self.dir) * self.genes.speed) % WORLD_H

        cost = (0.12 + self.genes.speed * 0.06 +
                self.genes.size * 0.025 + self.genes.vision * 0.0005)
        self.energy -= cost

        if bf and math.sqrt(bdsq) < self.genes.size + 4:
            self.energy = min(self.max_e, self.energy + bf.nutrition * self.genes.efficiency)
            bf.alive = False

        if self.energy <= 0:
            self.alive = False


class Predator:
    _n = 0

    def __init__(self, x, y, genes=None, gen=0):
        Predator._n += 1
        self.id = Predator._n
        self.x, self.y = x, y
        self.genes = genes or PredatorGene()
        self.gen = gen
        self.energy = 80.0
        self.max_e = 250.0
        self.age = 0
        self.dir = random.uniform(0, math.tau)
        self.alive = True
        self.lifespan = random.uniform(1200, 2500)
        self.children = 0
        self.hcd = 0
        self.kills = 0

    def update(self, cg):
        if not self.alive:
            return
        self.age += 1
        if self.hcd > 0:
            self.hcd -= 1
        if self.age > self.lifespan:
            self.alive = False
            return

        vsq = self.genes.vision ** 2
        vc = int(self.genes.vision / CELL) + 1
        cx, cy = int(self.x / CELL), int(self.y / CELL)
        bf, bdsq = None, vsq
        bdx = bdy = 0.0
        for dx in range(-vc, vc + 1):
            gx = (cx + dx) % GW
            for dy in range(-vc, vc + 1):
                gy = (cy + dy) % GH
                for c in cg.get((gx, gy)):
                    if not c.alive:
                        continue
                    fx = c.x - self.x
                    if fx > WORLD_W / 2: fx -= WORLD_W
                    elif fx < -WORLD_W / 2: fx += WORLD_W
                    fy = c.y - self.y
                    if fy > WORLD_H / 2: fy -= WORLD_H
                    elif fy < -WORLD_H / 2: fy += WORLD_H
                    dsq = fx * fx + fy * fy
                    if dsq < bdsq:
                        bdsq, bf = dsq, c
                        bdx, bdy = fx, fy

        if bf:
            t = math.atan2(bdy, bdx)
            diff = t - self.dir
            while diff > math.pi: diff -= math.tau
            while diff < -math.pi: diff += math.tau
            self.dir += diff * 0.15
        else:
            self.dir += random.gauss(0, 0.3)

        self.x = (self.x + math.cos(self.dir) * self.genes.speed) % WORLD_W
        self.y = (self.y + math.sin(self.dir) * self.genes.speed) % WORLD_H

        cost = 0.2 + self.genes.speed * 0.08 + self.genes.size * 0.03 + self.genes.vision * 0.0008
        self.energy -= cost

        if bf and math.sqrt(bdsq) < self.genes.size + bf.genes.size and self.hcd <= 0:
            self.energy = min(self.max_e, self.energy + PREY_NUT * self.genes.efficiency)
            bf.alive = False
            self.hcd = 20
            self.kills += 1

        if self.energy <= 0:
            self.alive = False


class Simulation:
    def __init__(self):
        self.creatures = []
        self.predators = []
        self.foods = []
        self.particles = []
        self.tick = 0
        self.species = {}
        self.pop_hist = []
        self.trait_hist = []
        self.pred_hist = []
        self.total_born = self.total_died = 0
        self.total_pred_born = self.total_pred_died = 0
        self.total_killed = 0
        self.mut_rate = 0.20
        self.food_rate = 3
        self.paused = False
        self.speed_mult = 1
        self.show_vis = False
        self.selected = None
        self.births_window = []
        self.deaths_window = []
        self.reset()

    def reset(self):
        self.creatures.clear()
        self.predators.clear()
        self.foods.clear()
        self.particles.clear()
        self.tick = 0
        self.species = {}
        self.pop_hist.clear()
        self.trait_hist.clear()
        self.pred_hist.clear()
        self.total_born = self.total_died = 0
        self.total_pred_born = self.total_pred_died = 0
        self.total_killed = 0
        self.selected = None
        self.births_window.clear()
        self.deaths_window.clear()
        Creature._n = 0
        Predator._n = 0

        colors = [(220, 60, 60), (60, 110, 230), (60, 210, 80),
                  (230, 200, 50), (200, 60, 220)]
        per = INIT_C // len(colors)
        mx, my = WORLD_W / 2, WORLD_H / 2
        for i, (cr, cg, cb) in enumerate(colors):
            a = math.tau * i / len(colors)
            gx = mx + math.cos(a) * 160
            gy = my + math.sin(a) * 130
            for _ in range(per):
                g = Gene(r=cr + random.randint(-25, 25),
                         g=cg + random.randint(-25, 25),
                         b=cb + random.randint(-25, 25))
                self.creatures.append(Creature(
                    (gx + random.gauss(0, 40)) % WORLD_W,
                    (gy + random.gauss(0, 40)) % WORLD_H, g, 0))
        while len(self.creatures) < INIT_C:
            self.creatures.append(Creature(
                random.uniform(0, WORLD_W), random.uniform(0, WORLD_H), Gene(), 0))
        for _ in range(INIT_F):
            self.foods.append(Food())
        for _ in range(INIT_P):
            self.predators.append(Predator(
                random.uniform(0, WORLD_W), random.uniform(0, WORLD_H)))

    @property
    def season(self):
        return SEASONS[(self.tick // SEASON_LEN) % 4]

    @property
    def season_progress(self):
        return (self.tick % SEASON_LEN) / SEASON_LEN

    @property
    def max_gen(self):
        return max((c.gen for c in self.creatures), default=0)

    @property
    def avg_traits(self):
        if not self.creatures:
            return {t: 0 for t in Gene.NUM_ATTRS}
        n = len(self.creatures)
        return {t: sum(getattr(c.genes, t) for c in self.creatures) / n
                for t in Gene.NUM_ATTRS}

    @property
    def avg_age(self):
        if not self.creatures:
            return 0
        return sum(c.age for c in self.creatures) / len(self.creatures)

    @property
    def birth_rate(self):
        if len(self.births_window) < 10:
            return 0
        return sum(self.births_window[-100:]) / min(len(self.births_window), 100)

    @property
    def death_rate(self):
        if len(self.deaths_window) < 10:
            return 0
        return sum(self.deaths_window[-100:]) / min(len(self.deaths_window), 100)

    def update(self):
        if self.paused:
            return
        for _ in range(self.speed_mult):
            self._step()

    def _step(self):
        self.tick += 1
        _, _, food_mult = self.season

        fg = defaultdict(list)
        for f in self.foods:
            if f.alive:
                fg[(int(f.x / CELL) % GW, int(f.y / CELL) % GH)].append(f)

        cg = defaultdict(list)
        for c in self.creatures:
            if c.alive:
                cg[(int(c.x / CELL) % GW, int(c.y / CELL) % GH)].append(c)

        pred_pos = [(p.x, p.y) for p in self.predators if p.alive]

        for c in self.creatures:
            c.update(fg, pred_pos)
        for p in self.predators:
            p.update(cg)

        babies = []
        pop = len(self.creatures)
        sp_map = defaultdict(list)
        for c in self.creatures:
            if c.alive:
                sp_map[c.sp_id].append(c)

        for c in self.creatures:
            if (c.alive and c.energy > c.genes.repro_th
                    and c.rcd <= 0 and pop + len(babies) < MAX_C):
                mate = None
                for other in sp_map.get(c.sp_id, []):
                    if other is c or not other.alive or other.rcd > 0:
                        continue
                    dx = other.x - c.x
                    if dx > WORLD_W / 2: dx -= WORLD_W
                    elif dx < -WORLD_W / 2: dx += WORLD_W
                    dy = other.y - c.y
                    if dy > WORLD_H / 2: dy -= WORLD_H
                    elif dy < -WORLD_H / 2: dy += WORLD_H
                    if dx * dx + dy * dy < MATE_RANGE * MATE_RANGE:
                        mate = other
                        break

                if mate:
                    child_g = Gene.crossover(c.genes, mate.genes).mutate(self.mut_rate)
                    mx2 = (c.x + mate.x) / 2
                    my2 = (c.y + mate.y) / 2
                    child = Creature(
                        (mx2 + random.gauss(0, 8)) % WORLD_W,
                        (my2 + random.gauss(0, 8)) % WORLD_H,
                        child_g, max(c.gen, mate.gen) + 1)
                    child.energy = c.energy * 0.3 + mate.energy * 0.15
                    c.energy *= 0.55
                    mate.energy *= 0.85
                    mate.rcd = 30
                else:
                    child_g = c.genes.mutate(self.mut_rate * 1.3)
                    child = Creature(
                        (c.x + random.gauss(0, 10)) % WORLD_W,
                        (c.y + random.gauss(0, 10)) % WORLD_H,
                        child_g, c.gen + 1)
                    child.energy = c.energy * 0.45
                    c.energy *= 0.45

                c.rcd = 40
                c.children += 1
                self.total_born += 1
                self.births_window.append(1)
                babies.append(child)
                for _ in range(5):
                    self.particles.append(
                        Particle(child.x, child.y, child_g.color(), 2.0, 2.0))

        self.creatures.extend(babies)

        pbabies = []
        ppop = len(self.predators)
        for p in self.predators:
            if (p.alive and p.energy > 140
                    and ppop + len(pbabies) < MAX_P):
                pg = p.genes.mutate(self.mut_rate)
                child = Predator(
                    (p.x + random.gauss(0, 15)) % WORLD_W,
                    (p.y + random.gauss(0, 15)) % WORLD_H, pg, p.gen + 1)
                child.energy = p.energy * 0.4
                p.energy *= 0.4
                p.children += 1
                self.total_pred_born += 1
                pbabies.append(child)
                for _ in range(3):
                    self.particles.append(
                        Particle(child.x, child.y, QColor(255, 80, 80), 1.5, 1.0))

        self.predators.extend(pbabies)

        for c in self.creatures:
            if not c.alive:
                self.total_died += 1
                self.deaths_window.append(1)
                for _ in range(6):
                    self.particles.append(
                        Particle(c.x, c.y, c.genes.color(), 1.5, 1.0))

        for p in self.predators:
            if not p.alive:
                self.total_pred_died += 1
                for _ in range(5):
                    self.particles.append(
                        Particle(p.x, p.y, QColor(255, 50, 50), 1.2, 0.8))

        if self.selected and not self.selected.alive:
            self.selected = None

        self.creatures = [c for c in self.creatures if c.alive]
        self.predators = [p for p in self.predators if p.alive]
        self.foods = [f for f in self.foods if f.alive]

        if len(self.creatures) < 5:
            for _ in range(12):
                self.creatures.append(Creature(
                    random.uniform(0, WORLD_W),
                    random.uniform(0, WORLD_H), Gene(), 0))

        n_food = max(1, int(self.food_rate * food_mult))
        for _ in range(n_food):
            if len(self.foods) < MAX_F:
                self.foods.append(Food())

        for f in self.foods:
            f.pulse += 0.06

        for pt in self.particles:
            pt.x += pt.vx
            pt.y += pt.vy
            pt.life -= 0.05
        self.particles = [p for p in self.particles if p.life > 0]

        if len(self.births_window) > 500:
            self.births_window = self.births_window[-500:]
        if len(self.deaths_window) > 500:
            self.deaths_window = self.deaths_window[-500:]

        if self.tick % 30 == 0:
            self._id_species()
        if self.tick % HIST_INT == 0:
            self._record()

    def _id_species(self):
        if not self.creatures:
            self.species = {}
            return
        ordered = sorted(self.creatures,
                         key=lambda c: (c.genes.r, c.genes.g, c.genes.b))
        centers = {}
        nxt = 1
        for c in ordered:
            g = c.genes
            bid, bd = None, SP_THR
            for sid, (sr, sg, sb, cnt) in centers.items():
                d = math.sqrt((g.r - sr) ** 2 + (g.g - sg) ** 2 + (g.b - sb) ** 2)
                if d < bd:
                    bd, bid = d, sid
            if bid is None:
                bid = nxt
                nxt += 1
                centers[bid] = [float(g.r), float(g.g), float(g.b), 1]
            else:
                sc = centers[bid]
                n = sc[3]
                sc[0] = (sc[0] * n + g.r) / (n + 1)
                sc[1] = (sc[1] * n + g.g) / (n + 1)
                sc[2] = (sc[2] * n + g.b) / (n + 1)
                sc[3] += 1
            c.sp_id = bid

        agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0])
        for c in self.creatures:
            a = agg[c.sp_id]
            a[0] += 1
            a[1] += c.genes.speed
            a[2] += c.genes.size
            a[3] += c.genes.vision
            a[4] += c.genes.efficiency
            a[5] += c.gen
            a[6] += c.genes.lifespan

        self.species = {}
        for sid, (sr, sg, sb, _) in centers.items():
            a = agg[sid]
            n = a[0]
            if n == 0:
                continue
            self.species[sid] = {
                "color": QColor(int(sr), int(sg), int(sb)),
                "count": n,
                "avg_speed": a[1] / n, "avg_size": a[2] / n,
                "avg_vision": a[3] / n, "avg_efficiency": a[4] / n,
                "avg_gen": a[5] / n, "avg_lifespan": a[6] / n,
            }

    def _record(self):
        pop = {}
        for c in self.creatures:
            pop[c.sp_id] = pop.get(c.sp_id, 0) + 1
        self.pop_hist.append(pop)
        self.pred_hist.append(len(self.predators))
        if len(self.pop_hist) > MAX_HIST:
            self.pop_hist.pop(0)
            self.pred_hist.pop(0)
        if self.creatures:
            n = len(self.creatures)
            self.trait_hist.append(tuple(
                sum(getattr(c.genes, t) for c in self.creatures) / n
                for t in Gene.NUM_ATTRS))
            if len(self.trait_hist) > MAX_HIST:
                self.trait_hist.pop(0)

    def catastrophe(self):
        kill = max(1, len(self.creatures) * 7 // 10)
        victims = random.sample(self.creatures, min(kill, len(self.creatures)))
        for c in victims:
            c.alive = False
            self.total_died += 1
            self.deaths_window.append(1)
            for _ in range(8):
                self.particles.append(
                    Particle(c.x, c.y, QColor(255, 200, 50), 2.5, 3.0))
        kill_p = max(1, len(self.predators) * 5 // 10)
        victims_p = random.sample(self.predators, min(kill_p, len(self.predators)))
        for p in victims_p:
            p.alive = False
            self.total_pred_died += 1
            for _ in range(6):
                self.particles.append(
                    Particle(p.x, p.y, QColor(255, 100, 50), 2.0, 2.0))
        if self.selected and not self.selected.alive:
            self.selected = None
        self.creatures = [c for c in self.creatures if c.alive]
        self.predators = [p for p in self.predators if p.alive]

    def select_at(self, x, y):
        best, bd = None, 400
        for c in self.creatures:
            d = (c.x - x) ** 2 + (c.y - y) ** 2
            if d < bd:
                bd, best = d, c
        for p in self.predators:
            d = (p.x - x) ** 2 + (p.y - y) ** 2
            if d < bd:
                bd, best = d, p
        self.selected = best


class SimCanvas(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedSize(WORLD_W, WORLD_H)
        self.setMouseTracking(True)
        self._hover = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.sim.select_at(e.position().x(), e.position().y())

    def mouseMoveEvent(self, e):
        x, y = e.position().x(), e.position().y()
        self._hover = None
        bd = 225
        for c in self.sim.creatures:
            d = (c.x - x) ** 2 + (c.y - y) ** 2
            if d < bd:
                bd, self._hover = d, c
        for p in self.sim.predators:
            d = (p.x - x) ** 2 + (p.y - y) ** 2
            if d < bd:
                bd, self._hover = d, p

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        sname, sclr, _ = self.sim.season
        bg = QColor(BG)
        bg.setRed(min(255, bg.red() + sclr.red() - 15))
        bg.setGreen(min(255, bg.green() + sclr.green() - 15))
        bg.setBlue(min(255, bg.blue() + sclr.blue() - 15))
        p.fillRect(self.rect(), bg)

        p.setPen(QPen(GRC, 1))
        for x in range(0, WORLD_W, 40):
            p.drawLine(x, 0, x, WORLD_H)
        for y in range(0, WORLD_H, 40):
            p.drawLine(0, y, WORLD_W, y)

        p.setPen(Qt.NoPen)
        for f in self.sim.foods:
            r = 2.5 + math.sin(f.pulse) * 0.8
            if f.super:
                alpha = 190 + int(math.sin(f.pulse) * 60)
                p.setBrush(QBrush(QColor(255, 220, 50, alpha)))
                p.drawEllipse(QPointF(f.x, f.y), r * 1.4, r * 1.4)
                g = QRadialGradient(QPointF(f.x, f.y), r * 2.5)
                g.setColorAt(0, QColor(255, 220, 50, 30))
                g.setColorAt(1, QColor(255, 220, 50, 0))
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(f.x, f.y), r * 2.5, r * 2.5)
            else:
                alpha = 160 + int(math.sin(f.pulse) * 50)
                p.setBrush(QBrush(QColor(80, 255, 120, alpha)))
                p.drawEllipse(QPointF(f.x, f.y), r, r)

        sv = self.sim.show_vis

        for c in self.sim.creatures:
            col = c.genes.color()
            sz = c.genes.size
            er = max(0.3, min(1.0, c.energy / 80))
            col.setAlpha(int(255 * er))

            if sv and c.genes.vision > 20:
                vc = QColor(col)
                vc.setAlpha(10)
                p.setBrush(QBrush(vc))
                p.drawEllipse(QPointF(c.x, c.y), c.genes.vision, c.genes.vision)

            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(c.x, c.y), sz, sz)

            dx = math.cos(c.dir) * sz * 1.6
            dy = math.sin(c.dir) * sz * 1.6
            p.setPen(QPen(col, max(1.0, sz * 0.3)))
            p.drawLine(QPointF(c.x, c.y), QPointF(c.x + dx, c.y + dy))
            p.setPen(Qt.NoPen)

            if c.energy > 110:
                g = QRadialGradient(QPointF(c.x, c.y), sz * 2.5)
                gc = QColor(col)
                gc.setAlpha(30)
                g.setColorAt(0, gc)
                gc.setAlpha(0)
                g.setColorAt(1, gc)
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(c.x, c.y), sz * 2.5, sz * 2.5)

        for pr in self.sim.predators:
            sz = pr.genes.size
            er = max(0.3, min(1.0, pr.energy / 100))
            a = int(220 * er)
            col = QColor(255, 60, 60, a)
            path = QPainterPath()
            angle = pr.dir
            tip_x = pr.x + math.cos(angle) * sz * 1.5
            tip_y = pr.y + math.sin(angle) * sz * 1.5
            l_x = pr.x + math.cos(angle + 2.5) * sz
            l_y = pr.y + math.sin(angle + 2.5) * sz
            r_x = pr.x + math.cos(angle - 2.5) * sz
            r_y = pr.y + math.sin(angle - 2.5) * sz
            path.moveTo(tip_x, tip_y)
            path.lineTo(l_x, l_y)
            path.lineTo(r_x, r_y)
            path.closeSubpath()
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor(255, 120, 120, a // 2), 1))
            p.drawPath(path)
            p.setPen(Qt.NoPen)
            ex = pr.x + math.cos(angle) * sz * 0.4
            ey = pr.y + math.sin(angle) * sz * 0.4
            p.setBrush(QBrush(QColor(255, 255, 100, a)))
            p.drawEllipse(QPointF(ex, ey), 1.5, 1.5)
            if sv:
                vc = QColor(255, 60, 60, 8)
                p.setBrush(QBrush(vc))
                p.drawEllipse(QPointF(pr.x, pr.y), pr.genes.vision, pr.genes.vision)

        for pt in self.sim.particles:
            pc = QColor(pt.color)
            pc.setAlpha(int(180 * pt.life))
            p.setBrush(QBrush(pc))
            p.drawEllipse(QPointF(pt.x, pt.y), pt.sz * pt.life, pt.sz * pt.life)

        sel = self.sim.selected
        if sel and sel.alive:
            if isinstance(sel, Creature):
                p.setPen(QPen(QColor(255, 255, 255, 180), 2, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(sel.x, sel.y), sel.genes.size + 6, sel.genes.size + 6)
                p.setPen(QPen(QColor(255, 255, 255, 60), 1))
                p.drawEllipse(QPointF(sel.x, sel.y), sel.genes.vision, sel.genes.vision)
            elif isinstance(sel, Predator):
                p.setPen(QPen(QColor(255, 255, 100, 180), 2, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(sel.x, sel.y), sel.genes.size + 6, sel.genes.size + 6)

        p.setPen(QPen(QColor(255, 255, 255, 100)))
        p.setFont(QFont("Segoe UI", 10))
        season_icons = {"Spring": "\U0001F331", "Summer": "\u2600\uFE0F",
                        "Autumn": "\U0001F342", "Winter": "\u2744\uFE0F"}
        p.drawText(10, 20, f"{season_icons.get(sname, '')} {sname}")
        p.drawText(10, 36, f"Tick {self.sim.tick}")

        if self.sim.paused:
            p.setPen(QPen(QColor(255, 255, 255, 180)))
            p.setFont(QFont("Segoe UI", 28, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, "\u23F8  PAUSED")

        if self._hover and self._hover.alive:
            h = self._hover
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, 180)))
            tx, ty = int(h.x) + 15, int(h.y) - 10
            if isinstance(h, Creature):
                txt = f"Sp.{h.sp_id} Gen:{h.gen} E:{h.energy:.0f} Age:{h.age}"
            else:
                txt = f"Predator Gen:{h.gen} E:{h.energy:.0f} Kills:{h.kills}"
            p.setFont(QFont("Segoe UI", 8))
            tw = p.fontMetrics().horizontalAdvance(txt) + 10
            tx = min(tx, WORLD_W - tw - 5)
            ty = max(ty, 5)
            p.drawRoundedRect(tx, ty, tw, 18, 3, 3)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(tx + 5, ty + 13, txt)

        p.setPen(QPen(BRC, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, WORLD_W - 1, WORLD_H - 1)
        p.end()


class PopGraph(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedHeight(155)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), CBG)
        hist = self.sim.pop_hist
        phist = self.sim.pred_hist
        if len(hist) < 2:
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Collecting data\u2026")
            p.end()
            return
        max_pop = 1
        all_sp = set()
        for pop in hist:
            for sid, cnt in pop.items():
                if cnt > max_pop:
                    max_pop = cnt
                all_sp.add(sid)
        if phist:
            max_pop = max(max_pop, max(phist))

        ml, mr, mt, mb = 38, 8, 22, 22
        gw2, gh2 = w - ml - mr, h - mt - mb
        p.setPen(TP)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(ml, 15, "Population Over Time")
        p.setPen(QPen(TS, 1))
        p.drawLine(ml, mt, ml, h - mb)
        p.drawLine(ml, h - mb, w - mr, h - mb)
        p.setFont(QFont("Segoe UI", 7))
        for i in range(5):
            y = mt + gh2 * i / 4
            p.setPen(TS)
                        p.drawText(2, int(y) + 4, str(int(max_pop * (1 - i / 4))))
            p.setPen(QPen(QColor(40, 40, 55), 1, Qt.DotLine))
            p.drawLine(ml, int(y), w - mr, int(y))

        n = len(hist)
        dx = gw2 / max(1, n - 1)
        for sid in all_sp:
            col = self.sim.species.get(sid, {}).get("color", QColor(100, 100, 100))
            col.setAlpha(200)
            p.setPen(QPen(col, 1.5))
            path = QPainterPath()
            started = False
            for i, pop in enumerate(hist):
                cnt = pop.get(sid, 0)
                x = ml + i * dx
                y = mt + gh2 * (1 - cnt / max_pop)
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            if started:
                p.drawPath(path)

        if phist:
            p.setPen(QPen(QColor(255, 80, 80, 180), 1.5))
            path = QPainterPath()
            for i, cnt in enumerate(phist):
                x = ml + i * dx
                y = mt + gh2 * (1 - cnt / max_pop)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.drawPath(path)

        lx = ml + 4
        p.setFont(QFont("Segoe UI", 7))
        for sid in sorted(all_sp)[:5]:
            col = self.sim.species.get(sid, {}).get("color", QColor(100, 100, 100))
            p.setPen(QPen(col, 2))
            p.drawLine(lx, h - 8, lx + 10, h - 8)
            p.setPen(TS)
            p.drawText(lx + 13, h - 4, f"Sp.{sid}")
            lx += 48
        if phist:
            p.setPen(QPen(QColor(255, 80, 80), 2))
            p.drawLine(lx, h - 8, lx + 10, h - 8)
            p.setPen(TS)
            p.drawText(lx + 13, h - 4, "Pred")
        p.end()


class TraitGraph(QWidget):
    NAMES = ["Speed", "Size", "Vision", "Effic.", "ReproTh", "Life"]
    COLORS = [QColor(255, 100, 100), QColor(100, 200, 255),
              QColor(255, 255, 100), QColor(100, 255, 200),
              QColor(200, 150, 255), QColor(255, 180, 120)]
    MAXES = [7.0, 14.0, 300.0, 2.5, 200.0, 4000.0]

    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedHeight(130)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), CBG)
        hist = self.sim.trait_hist
        if len(hist) < 2:
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Collecting data\u2026")
            p.end()
            return
        ml, mr, mt, mb = 8, 8, 20, 20
        gw2, gh2 = w - ml - mr, h - mt - mb
        n = len(hist)
        dx = gw2 / max(1, n - 1)
        p.setPen(TP)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(ml, 14, "Average Traits Over Time")
        for ti in range(min(6, len(Gene.NUM_ATTRS))):
            p.setPen(QPen(self.COLORS[ti], 1.2))
            path = QPainterPath()
            for i, traits in enumerate(hist):
                x = ml + i * dx
                y = mt + gh2 * (1 - traits[ti] / self.MAXES[ti])
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.drawPath(path)
        p.setFont(QFont("Segoe UI", 6))
        lx = ml + 2
        for name, col in zip(self.NAMES[:6], self.COLORS[:6]):
            p.setPen(QPen(col, 2))
            p.drawLine(lx, h - 7, lx + 8, h - 7)
            p.setPen(TS)
            p.drawText(lx + 10, h - 3, name)
            lx += 52
        p.end()


class TraitHistogram(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedHeight(105)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), CBG)
        p.setPen(TP)
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(8, 14, "Trait Distribution")
        creatures = self.sim.creatures
        if len(creatures) < 5:
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(self.rect(), Qt.AlignCenter, "Need more creatures\u2026")
            p.end()
            return
        traits_info = [
            ("Speed", "speed", QColor(255, 100, 100), 0.5, 7.0, 10),
            ("Size", "size", QColor(100, 200, 255), 2.0, 14.0, 10),
            ("Vision", "vision", QColor(255, 255, 100), 10, 300, 10),
        ]
        ml, mr, mt, mb = 8, 8, 20, 16
        gw2 = (w - ml - mr) / len(traits_info)
        gh2 = h - mt - mb
        for ti, (name, attr, col, lo, hi, bins) in enumerate(traits_info):
            ox = ml + ti * gw2
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(int(ox + gw2 / 2 - 15), h - 3, name)
            vals = [getattr(c.genes, attr) for c in creatures]
            bw = (hi - lo) / bins
            counts = [0] * bins
            for v in vals:
                b = int((v - lo) / bw)
                b = max(0, min(bins - 1, b))
                counts[b] += 1
            mx = max(counts) if max(counts) > 0 else 1
            bar_w = (gw2 - 4) / bins
            for bi, cnt in enumerate(counts):
                bh = (cnt / mx) * gh2 * 0.85
                bx = ox + 2 + bi * bar_w
                by = mt + gh2 - bh
                c = QColor(col)
                c.setAlpha(180)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(c))
                p.drawRoundedRect(int(bx), int(by), max(1, int(bar_w) - 1),
                                  int(bh), 1, 1)
        p.end()


class InspectorPanel(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedHeight(180)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), CBG)
        sel = self.sim.selected
        if not sel or not sel.alive:
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Click a creature to inspect")
            p.end()
            return

        p.setPen(TP)
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        if isinstance(sel, Creature):
            g = sel.genes
            p.drawText(10, 18, f"\U0001F9EC Creature #{sel.id}  (Sp.{sel.sp_id})")
            p.setFont(QFont("Segoe UI", 8))
            y = 36
            lines = [
                (f"Generation: {sel.gen}", TP),
                (f"Energy: {sel.energy:.1f} / {sel.max_e}", TP),
                (f"Age: {sel.age} / {g.lifespan:.0f}", TP),
                (f"Children: {sel.children}", TP),
                (f"Speed: {g.speed:.2f}  Size: {g.size:.2f}", TP),
                (f"Vision: {g.vision:.1f}  Efficiency: {g.efficiency:.2f}", TP),
                (f"Repro Threshold: {g.repro_th:.1f}", TP),
            ]
            for txt, col in lines:
                p.setPen(col)
                p.drawText(14, y, txt)
                y += 15
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g.color()))
            p.drawRoundedRect(w - 40, 8, 28, 28, 4, 4)
            p.setPen(TS)
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(w - 42, 50, "Color")
        elif isinstance(sel, Predator):
            g = sel.genes
            p.drawText(10, 18, f"\U0001F43A Predator #{sel.id}")
            p.setFont(QFont("Segoe UI", 8))
            y = 36
            lines = [
                (f"Generation: {sel.gen}", TP),
                (f"Energy: {sel.energy:.1f} / {sel.max_e}", TP),
                (f"Age: {sel.age} / {sel.lifespan:.0f}", TP),
                (f"Kills: {sel.kills}  Children: {sel.children}", TP),
                (f"Speed: {g.speed:.2f}  Size: {g.size:.2f}", TP),
                (f"Vision: {g.vision:.1f}  Efficiency: {g.efficiency:.2f}", TP),
            ]
            for txt, col in lines:
                p.setPen(col)
                p.drawText(14, y, txt)
                y += 15
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(255, 60, 60)))
            path = QPainterPath()
            cx, cy = w - 26, 22
            path.moveTo(cx, cy - 10)
            path.lineTo(cx - 8, cy + 6)
            path.lineTo(cx + 8, cy + 6)
            path.closeSubpath()
            p.drawPath(path)
        p.end()


class StatsPanel(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setFixedWidth(315)
        self._build()

    def _gs(self):
        return (f"QGroupBox{{color:{TP.name()};border:1px solid "
                f"{BRC.name()};border-radius:6px;margin-top:10px;"
                f"padding-top:14px;font-size:11px;font-weight:bold;"
                f"background:{CBG.name()};}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;"
                f"padding:0 5px;}}")

    def _bs(self, col):
        return (f"QPushButton{{background:{col.name()};color:#1a1a2e;"
                f"border:none;border-radius:5px;padding:6px 10px;"
                f"font-weight:bold;font-size:10px;}}"
                f"QPushButton:hover{{background:{col.lighter(120).name()};}}"
                f"QPushButton:pressed{{background:{col.darker(110).name()};}}")

    def _build(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(6, 6, 6, 6)
        lo.setSpacing(4)
        title = QLabel("\U0001F9EC Evolution Simulator")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet(f"color:{ACC.name()};")
        lo.addWidget(title)

        sg = QGroupBox("Statistics")
        sg.setStyleSheet(self._gs())
        gl = QGridLayout(sg)
        gl.setSpacing(2)
        self._sl = {}
        for i, (k, n) in enumerate([
            ("tick", "Tick"), ("gen", "Max Gen"), ("pop", "Prey"),
            ("pred", "Predators"), ("food", "Food"), ("sp", "Species"),
            ("born", "Born"), ("died", "Died"), ("age", "Avg Age"),
            ("brate", "Birth/s"), ("drate", "Death/s"),
        ]):
            r, c = divmod(i, 2)
            ln = QLabel(n + ":")
            ln.setStyleSheet(f"color:{TS.name()};font-size:10px;")
            lv = QLabel("0")
            lv.setStyleSheet(f"color:{TP.name()};font-size:10px;font-weight:bold;")
            gl.addWidget(ln, r, c * 2)
            gl.addWidget(lv, r, c * 2 + 1)
            self._sl[k] = lv
        lo.addWidget(sg)

        tg = QGroupBox("Current Avg Traits")
        tg.setStyleSheet(self._gs())
        tl = QVBoxLayout(tg)
        tl.setSpacing(2)
        self._tb = {}
        for key, name, col, mx in [
            ("speed", "Speed", QColor(255, 100, 100), 7.0),
            ("size", "Size", QColor(100, 200, 255), 14.0),
            ("vision", "Vision", QColor(255, 255, 100), 300.0),
            ("efficiency", "Effic.", QColor(100, 255, 200), 2.5),
            ("repro_th", "ReproTh", QColor(200, 150, 255), 200.0),
            ("lifespan", "Lifespan", QColor(255, 180, 120), 4000.0),
        ]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)
            nl = QLabel(name)
            nl.setFixedWidth(48)
            nl.setStyleSheet(f"color:{TS.name()};font-size:9px;")
            bar_bg = QFrame()
            bar_bg.setFixedHeight(10)
            bar_bg.setStyleSheet(
                f"background:{QColor(40, 40, 55).name()};border-radius:3px;")
            bar_fg = QFrame(bar_bg)
            bar_fg.setGeometry(0, 0, 0, 10)
            bar_fg.setStyleSheet(
                f"background:{col.name()};border-radius:3px;")
            vl = QLabel("0.0")
            vl.setFixedWidth(32)
            vl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            vl.setStyleSheet(f"color:{TP.name()};font-size:9px;")
            rl.addWidget(nl)
            rl.addWidget(bar_bg, 1)
            rl.addWidget(vl)
            tl.addWidget(row)
            self._tb[key] = (bar_fg, vl, mx, bar_bg)
        lo.addWidget(tg)

        self.inspector = InspectorPanel(self.sim)
        lo.addWidget(self.inspector)
        self.pop_graph = PopGraph(self.sim)
        lo.addWidget(self.pop_graph)
        self.trait_graph = TraitGraph(self.sim)
        lo.addWidget(self.trait_graph)
        self.histogram = TraitHistogram(self.sim)
        lo.addWidget(self.histogram)

        spg = QGroupBox("Species")
        spg.setStyleSheet(self._gs())
        spl = QVBoxLayout(spg)
        spl.setSpacing(0)
        self._spc = QWidget()
        self._splo = QVBoxLayout(self._spc)
        self._splo.setContentsMargins(0, 0, 0, 0)
        self._splo.setSpacing(1)
        sa = QScrollArea()
        sa.setWidget(self._spc)
        sa.setWidgetResizable(True)
        sa.setFixedHeight(85)
        sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        spl.addWidget(sa)
        lo.addWidget(spg)

        cg = QGroupBox("Controls")
        cg.setStyleSheet(self._gs())
        cl = QGridLayout(cg)
        cl.setSpacing(4)

        def _sl2(row, label, lo_v, hi_v, init, fmt, cb):
            cl.addWidget(QLabel(label), row, 0)
            s = QSlider(Qt.Horizontal)
            s.setRange(lo_v, hi_v)
            s.setValue(init)
            cl.addWidget(s, row, 1)
            vl = QLabel(fmt(init))
            vl.setFixedWidth(30)
            cl.addWidget(vl, row, 2)
            s.valueChanged.connect(lambda v: (cb(v), vl.setText(fmt(v))))

        _sl2(0, "Speed:", 1, 10, 1, lambda v: f"{v}x",
             lambda v: setattr(self.sim, "speed_mult", v))
        _sl2(1, "Food:", 1, 10, 3, lambda v: str(v),
             lambda v: setattr(self.sim, "food_rate", v))
        _sl2(2, "Mut%:", 5, 60, 20, lambda v: f"{v}%",
             lambda v: setattr(self.sim, "mut_rate", v / 100))

        self._vc = QCheckBox("Show Vision")
        self._vc.setStyleSheet(f"color:{TS.name()};font-size:9px;")
        self._vc.toggled.connect(lambda v: setattr(self.sim, "show_vis", v))
        cl.addWidget(self._vc, 3, 0, 1, 2)

        bl = QHBoxLayout()
        self._pb = QPushButton("\u23F8 Pause")
        self._pb.clicked.connect(self._tp)
        self._pb.setStyleSheet(self._bs(ACC))
        bl.addWidget(self._pb)
        rb = QPushButton("\U0001F504 Reset")
        rb.clicked.connect(self._rs)
        rb.setStyleSheet(self._bs(QColor(200, 100, 80)))
        bl.addWidget(rb)
        cb = QPushButton("\u26A1 Catastrophe")
        cb.clicked.connect(lambda: self.sim.catastrophe())
        cb.setStyleSheet(self._bs(QColor(255, 180, 50)))
        bl.addWidget(cb)
        cl.addLayout(bl, 4, 0, 1, 3)
        lo.addWidget(cg)
        lo.addStretch()

    def _tp(self):
        self.sim.paused = not self.sim.paused
        self._pb.setText("\u25B6 Resume" if self.sim.paused else "\u23F8 Pause")

    def _rs(self):
        self.sim.reset()
        self._pb.setText("\u23F8 Pause")

    def refresh(self):
        s = self.sim
        self._sl["tick"].setText(str(s.tick))
        self._sl["gen"].setText(str(s.max_gen))
        self._sl["pop"].setText(str(len(s.creatures)))
        self._sl["pred"].setText(str(len(s.predators)))
        self._sl["food"].setText(str(len(s.foods)))
        self._sl["sp"].setText(str(len(s.species)))
        self._sl["born"].setText(str(s.total_born))
        self._sl["died"].setText(str(s.total_died))
        self._sl["age"].setText(f"{s.avg_age:.0f}")
        self._sl["brate"].setText(f"{s.birth_rate:.1f}")
        self._sl["drate"].setText(f"{s.death_rate:.1f}")

        traits = s.avg_traits
        for key, (bar, lbl, mx, bg) in self._tb.items():
            v = traits.get(key, 0)
            bar.setGeometry(0, 0, max(0, int(bg.width() * min(1, v / mx))), 10)
            if mx > 100:
                lbl.setText(f"{v:.0f}")
            else:
                lbl.setText(f"{v:.2f}")

        while self._splo.count():
            it = self._splo.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for sid, info in sorted(s.species.items(), key=lambda x: -x[1]["count"])[:8]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(2, 1, 2, 1)
            rl.setSpacing(3)
            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background:{info['color'].name()};border-radius:5px;")
            rl.addWidget(dot)
            for txt, w2, sty in [
                (f"Sp.{sid}", 26, f"color:{TP.name()};font-size:9px;"),
                (str(info["count"]), 24,
                 f"color:{TP.name()};font-size:9px;font-weight:bold;"),
                (f"G{info['avg_gen']:.0f}", 24,
                 f"color:{TS.name()};font-size:8px;"),
                (f"v{info['avg_vision']:.0f}", 26,
                 f"color:{TS.name()};font-size:8px;"),
                (f"l{info['avg_lifespan']:.0f}", 30,
                 f"color:{TS.name()};font-size:8px;"),
            ]:
                l = QLabel(txt)
                l.setFixedWidth(w2)
                l.setStyleSheet(sty)
                rl.addWidget(l)
            rl.addStretch()
            self._splo.addWidget(row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "\U0001F9EC Evolution Simulator \u2014 Predators, Seasons & Genetics")
        self.setStyleSheet(f"""
            QMainWindow {{ background: {PBG.name()}; }}
            QLabel {{ background: transparent; }}
            QSlider::groove:horizontal {{
                background: {QColor(50, 50, 65).name()};
                height: 5px; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {ACC.name()};
                width: 13px; height: 13px;
                margin: -4px 0; border-radius: 6px; }}
            QSlider::sub-page:horizontal {{
                background: {ACC.darker(130).name()};
                border-radius: 2px; }}
            QCheckBox {{ spacing: 4px; }}
            QCheckBox::indicator {{
                width: 13px; height: 13px;
                border: 1px solid {BRC.name()};
                border-radius: 3px; background: {CBG.name()}; }}
            QCheckBox::indicator:checked {{
                background: {ACC.name()}; border-color: {ACC.name()}; }}
        """)

        self.sim = Simulation()
        central = QWidget()
        hl = QHBoxLayout(central)
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(8)

        self.canvas = SimCanvas(self.sim)
        hl.addWidget(self.canvas)

        self.stats = StatsPanel(self.sim)
        scroll = QScrollArea()
        scroll.setWidget(self.stats)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(335)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{width:5px;background:transparent;}"
            "QScrollBar::handle:vertical{background:"
            f"{QColor(60, 60, 75).name()};border-radius:2px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical"
            "{height:0;}")
        hl.addWidget(scroll)
        self.setCentralWidget(central)

        self._t1 = QTimer(self)
        self._t1.timeout.connect(self._tick)
        self._t1.start(33)
        self._t2 = QTimer(self)
        self._t2.timeout.connect(self._st)
        self._t2.start(200)

    def _tick(self):
        self.sim.update()
        self.canvas.update()

    def _st(self):
        self.stats.refresh()
        self.stats.pop_graph.update()
        self.stats.trait_graph.update()
        self.stats.histogram.update()
        self.stats.inspector.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())