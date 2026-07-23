#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
   A P T - M A N   ---   DebConf26 HackLab edition
============================================================

El primo trucho de Pac-Man. Sos 'apt' (C amarilla) y tenes
que comerte todos los BITS (.) del filesystem sin que te
agarren los BUGS que te persiguen:

   S = Segfault   N = NullPtr   R = RaceCond   D = Deadlock

Comé una 'o' (un 'sudo') y entras en MODO ROOT: los bugs se
asustan (se ponen azules) y por unos segundos te los podes
comer -> los reportas y vuelven al tracker (centro).

Ganas cuando te comes todos los bits: 'apt full-upgrade' OK.
Te quedan 3 vidas. Si un bug te toca sin sudo: -1 vida.

Controles:
  Flechas / WASD / HJKL  -> mover
  P                      -> pausa
  Q  o  Ctrl-C           -> salir

Requisitos: Python 3 en Linux/macOS (usa 'curses', ya incluido).
Ejecutar:   python3 debman.py
============================================================
"""

import curses
import random
import time

# ------------------------------------------------------------------
# El laberinto (verificado: todo conectado). '#' pared, '.' bit,
# 'o' power (sudo), ' ' pasillo vacio.
# ------------------------------------------------------------------
MAZE = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.###.#.###.####",
    "#......#...#......#",
    "#.####.#.#.#.####.#",
    "#....#.......#....#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.###.#.###.####",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#..#.....#.....#..#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]

PAC_SPAWN = (19, 9)
GHOST_SPAWNS = [(9, 6), (9, 8), (9, 10), (9, 12)]
GHOST_DEFS = [
    ("Segfault", "S", 1),   # color pair 1 (rojo)
    ("NullPtr",  "N", 3),   # cyan
    ("RaceCond", "R", 5),   # magenta
    ("Deadlock", "D", 7),   # verde-ghost
]

POWER_TICKS = 55  # cuanto dura el modo root

WIN_MSGS = [
    "apt full-upgrade completado. Sistema limpio!",
    "0 upgraded, 0 to remove. Todo verde, crack.",
    "dpkg: no quedan bugs. Mergeado a main.",
]
LOSE_MSGS = [
    "kernel panic - el bug te asimilo",
    "Signal SIGKILL: apt-man (core dumped)",
    "E: 3 vidas removed. Reinstalando dignidad...",
    "Los bugs cerraron TU ticket como WONTFIX",
]
EAT_GHOST_MSGS = [
    "bug reportado! +200", "reproducible! cerrado", "git bisect FTW",
    "patch mergeado", "CVE asignado, +200",
]
DEATH_MSGS = [
    "Ay. -1 vida", "te toco un bug :(", "regresion fatal",
    "race condition perdida", "deberias haber testeado",
]


def parse_maze():
    grid = [list(row) for row in MAZE]
    dots = set()
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in ".o":
                dots.add((y, x))
    # las celdas de spawn no llevan bit
    dots.discard(PAC_SPAWN)
    for g in GHOST_SPAWNS:
        dots.discard(g)
    return grid, dots


def is_wall(y, x):
    if y < 0 or y >= len(MAZE) or x < 0 or x >= len(MAZE[0]):
        return True
    return MAZE[y][x] == '#'


class Ghost:
    def __init__(self, name, char, color, spawn):
        self.name = name
        self.char = char
        self.color = color
        self.spawn = spawn
        self.reset()

    def reset(self):
        self.y, self.x = self.spawn
        self.dy, self.dx = 0, -1
        self.frightened = False

    def step(self, pac, frightened_now):
        """Movimiento simple estilo Pac-Man: elige en cada celda la
        direccion valida que acerca (o aleja, si esta asustado) a apt,
        sin dar marcha atras salvo callejon."""
        self.frightened = frightened_now
        opts = []
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = self.y + dy, self.x + dx
            if is_wall(ny, nx):
                continue
            # evitar reversa
            if (dy, dx) == (-self.dy, -self.dx):
                continue
            opts.append((dy, dx, ny, nx))
        if not opts:  # callejon: permitir reversa
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = self.y + dy, self.x + dx
                if not is_wall(ny, nx):
                    opts.append((dy, dx, ny, nx))
        if not opts:
            return

        py, px = pac

        def dist(o):
            return abs(o[2] - py) + abs(o[3] - px)

        if random.random() < 0.25:
            choice = random.choice(opts)          # un poco de caos
        elif frightened_now:
            choice = max(opts, key=dist)          # huye de apt
        else:
            choice = min(opts, key=dist)          # persigue a apt

        self.dy, self.dx, self.y, self.x = choice


def draw(stdscr, oy, ox, grid, dots, pac, pac_dir, pac_open, ghosts,
         score, lives, power, status, best):
    stdscr.erase()
    H, W = len(grid), len(grid[0])

    # paredes y bits
    for y in range(H):
        for x in range(W):
            ch = grid[y][x]
            try:
                if ch == '#':
                    stdscr.addstr(oy + y, ox + x, "#", curses.color_pair(2))
                elif (y, x) in dots:
                    if MAZE[y][x] == 'o':
                        stdscr.addstr(oy + y, ox + x, "o",
                                      curses.color_pair(4) | curses.A_BOLD)
                    else:
                        stdscr.addstr(oy + y, ox + x, ".",
                                      curses.color_pair(6))
            except curses.error:
                pass

    # fantasmas
    for g in ghosts:
        cp = curses.color_pair(8) | curses.A_BOLD if g.frightened \
            else curses.color_pair(g.color) | curses.A_BOLD
        glyph = "w" if g.frightened else g.char
        try:
            stdscr.addstr(oy + g.y, ox + g.x, glyph, cp)
        except curses.error:
            pass

    # apt-man (boca que abre/cierra segun direccion)
    if pac_open:
        mouth = {(0, 1): "C", (0, -1): ")", (-1, 0): "U", (1, 0): "n"}
        pc = mouth.get(pac_dir, "C")
    else:
        pc = "o"
    try:
        stdscr.addstr(oy + pac[0], ox + pac[1], pc,
                      curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass

    # HUD arriba
    hud = f" APT-MAN  bits: {score}  vidas: {'C' * lives}  best: {best} "
    try:
        stdscr.addstr(oy - 1, ox, hud[: W + 2],
                      curses.color_pair(2) | curses.A_BOLD)
    except curses.error:
        pass
    # estado abajo
    extra = "  [MODO ROOT]" if power > 0 else ""
    st = f" {status}{extra} "
    try:
        stdscr.addstr(oy + H, ox, st[: W + 2], curses.color_pair(3))
    except curses.error:
        pass

    stdscr.refresh()


def center_msg(stdscr, sh, sw, lines, hi_pairs):
    stdscr.erase()
    for i, m in enumerate(lines):
        x = max(0, sw // 2 - len(m) // 2)
        y = sh // 2 - len(lines) // 2 + i
        cp, attr = hi_pairs.get(i, (3, curses.A_NORMAL))
        try:
            stdscr.addstr(y, x, m, curses.color_pair(cp) | attr)
        except curses.error:
            pass
    stdscr.refresh()


def title_screen(stdscr, sh, sw, best):
    art = [
        r"    _    ____ _____      __  __    _    _   _ ",
        r"   / \  |  _ \_   _|    |  \/  |  / \  | \ | |",
        r"  / _ \ | |_) || |_____ | |\/| | / _ \ |  \| |",
        r" / ___ \|  __/ | |_____|| |  | |/ ___ \| |\  |",
        r"/_/   \_\_|    |_|      |_|  |_/_/   \_\_| \_|",
        r"          DebConf26 :: HackLab edition        ",
    ]
    stdscr.erase()
    for i, line in enumerate(art):
        x = max(0, sw // 2 - len(line) // 2)
        y = sh // 2 - 7 + i
        try:
            stdscr.addstr(y, x, line, curses.color_pair(4) | curses.A_BOLD)
        except curses.error:
            pass
    info = [
        "",
        "Sos 'apt'. Comete todos los bits (.) del sistema.",
        "Te persiguen los bugs: S N R D. Comé un 'sudo' (o) y",
        "por unos segundos te los comes a ellos (se ponen azules).",
        "",
        "Flechas/WASD/HJKL: mover   P: pausa   Q: salir",
        f"Mejor score (esta sesion): {best}",
        "",
        ">> Apreta una tecla para 'apt install apt-man' <<",
    ]
    for i, m in enumerate(info):
        x = max(0, sw // 2 - len(m) // 2)
        y = sh // 2 + i
        try:
            attr = curses.A_BOLD if m.startswith(">>") else curses.A_NORMAL
            stdscr.addstr(y, x, m, curses.color_pair(3) | attr)
        except curses.error:
            pass
    stdscr.refresh()
    stdscr.nodelay(False)
    stdscr.getch()


def play(stdscr, best):
    curses.curs_set(0)
    sh, sw = stdscr.getmaxyx()
    H, W = len(MAZE), len(MAZE[0])

    if sh < H + 3 or sw < W + 2:
        stdscr.nodelay(False)
        stdscr.erase()
        msg = f"Terminal muy chica. Necesito al menos {W+2}x{H+3}."
        try:
            stdscr.addstr(0, 0, msg)
        except curses.error:
            pass
        stdscr.getch()
        return best

    # offset para centrar el tablero
    oy = (sh - H) // 2
    ox = (sw - W) // 2

    grid, dots = parse_maze()
    total_bits = len(dots)

    pac = list(PAC_SPAWN)
    pac_dir = (0, -1)
    next_dir = (0, -1)
    pac_open = True

    ghosts = [Ghost(n, c, col, GHOST_SPAWNS[i])
              for i, (n, c, col) in enumerate(GHOST_DEFS)]

    score = 0
    lives = 3
    power = 0
    status = "Boot OK. A comerse los bits!"

    TICK = 130          # ms por frame
    frame = 0
    stdscr.nodelay(True)

    def reset_positions():
        pac[0], pac[1] = PAC_SPAWN
        for g in ghosts:
            g.reset()

    while True:
        stdscr.timeout(TICK)
        key = stdscr.getch()

        if key in (ord('q'), ord('Q')):
            return max(best, score)
        if key in (ord('p'), ord('P')):
            # pausa simple
            paused = True
            status = "PAUSA (proceso detenido)"
            draw(stdscr, oy, ox, grid, dots, pac, pac_dir, pac_open,
                 ghosts, score, lives, power, status, best)
            while paused:
                k2 = stdscr.getch()
                if k2 in (ord('p'), ord('P'), ord('q'), ord('Q')):
                    if k2 in (ord('q'), ord('Q')):
                        return max(best, score)
                    paused = False
                    status = "Reanudando..."
            continue

        if key in (curses.KEY_UP, ord('w'), ord('W'), ord('k'), ord('K')):
            next_dir = (-1, 0)
        elif key in (curses.KEY_DOWN, ord('s'), ord('S'), ord('j'), ord('J')):
            next_dir = (1, 0)
        elif key in (curses.KEY_LEFT, ord('a'), ord('A'), ord('h'), ord('H')):
            next_dir = (0, -1)
        elif key in (curses.KEY_RIGHT, ord('d'), ord('D'), ord('l'), ord('L')):
            next_dir = (0, 1)

        frame += 1

        # --- mover apt-man ---
        # intentar girar si se puede
        ny, nx = pac[0] + next_dir[0], pac[1] + next_dir[1]
        if not is_wall(ny, nx):
            pac_dir = next_dir
        # avanzar en la direccion actual si no hay pared
        ny, nx = pac[0] + pac_dir[0], pac[1] + pac_dir[1]
        if not is_wall(ny, nx):
            pac[0], pac[1] = ny, nx
            pac_open = not pac_open  # animacion de boca

        # comer bit / power
        cell = (pac[0], pac[1])
        if cell in dots:
            if MAZE[cell[0]][cell[1]] == 'o':
                power = POWER_TICKS
                status = "sudo! MODO ROOT: a cazar bugs!"
                score += 5
            else:
                score += 1
                status = "nom (bit +1)"
            dots.discard(cell)

        # --- mover fantasmas (mas lento: cada 2 frames) ---
        if frame % 2 == 0:
            for g in ghosts:
                # asustados se mueven aun mas lento (cada 3 frames)
                if power > 0 and frame % 3 == 0:
                    continue
                g.step((pac[0], pac[1]), power > 0)

        if power > 0:
            power -= 1

        # --- colisiones apt vs bugs ---
        for g in ghosts:
            if (g.y, g.x) == (pac[0], pac[1]):
                if g.frightened:
                    score += 200
                    status = random.choice(EAT_GHOST_MSGS)
                    g.reset()
                else:
                    lives -= 1
                    status = random.choice(DEATH_MSGS)
                    if lives <= 0:
                        return end_screen(stdscr, sh, sw, score,
                                          max(best, score), won=False)
                    reset_positions()
                    power = 0
                    draw(stdscr, oy, ox, grid, dots, pac, pac_dir, pac_open,
                         ghosts, score, lives, power, status, best)
                    time.sleep(0.6)
                    break

        # --- victoria ---
        if not dots:
            return end_screen(stdscr, sh, sw, score, max(best, score),
                              won=True)

        draw(stdscr, oy, ox, grid, dots, pac, pac_dir, pac_open,
             ghosts, score, lives, power, status, best)


def end_screen(stdscr, sh, sw, score, best, won):
    if won:
        head = "  >>> YOU WIN <<<  "
        msg = random.choice(WIN_MSGS)
        cp = 7
    else:
        head = "  GAME OVER  "
        msg = random.choice(LOSE_MSGS)
        cp = 1
    lines = [
        "",
        head,
        "",
        msg,
        "",
        f"Bits comidos: {score}    Best: {best}",
        "",
        "R: reintentar    Q: salir al prompt",
    ]
    hi = {1: (cp, curses.A_BOLD), 3: (cp, curses.A_BOLD)}
    stdscr.nodelay(False)
    center_msg(stdscr, sh, sw, lines, hi)
    while True:
        k = stdscr.getch()
        if k in (ord('r'), ord('R')):
            return ("retry", best)
        if k in (ord('q'), ord('Q')):
            return ("quit", best)


def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)      # Segfault / game over
    curses.init_pair(2, curses.COLOR_BLUE, -1)     # paredes
    curses.init_pair(3, curses.COLOR_CYAN, -1)     # NullPtr / textos
    curses.init_pair(4, curses.COLOR_YELLOW, -1)   # apt-man / power
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # RaceCond
    curses.init_pair(6, curses.COLOR_WHITE, -1)    # bits
    curses.init_pair(7, curses.COLOR_GREEN, -1)    # Deadlock / win
    curses.init_pair(8, curses.COLOR_BLUE, -1)     # bugs asustados

    best = 0
    while True:
        sh, sw = stdscr.getmaxyx()
        title_screen(stdscr, sh, sw, best)
        result = play(stdscr, best)
        if isinstance(result, tuple):
            action, best = result
            if action == "quit":
                break
        else:
            best = result
            break


if __name__ == "__main__":
    try:
        curses.wrapper(main)
        print("Gracias por jugar APT-MAN. sudo apt autoremove diversion")
    except KeyboardInterrupt:
        print("\nCtrl-C: SIGINT recibido. Nos vemos en la DebConf26!")
