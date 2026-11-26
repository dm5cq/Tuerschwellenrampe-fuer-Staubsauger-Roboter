#!/usr/bin/env python3
"""
Tuerschwellenrampe fuer Staubsauger-/Saugroboter – Generator fuer druckfertige STL-Dateien
Autor: Stefan J. Kaiser DM5CQ / OE8KKS
Lizenz: CC BY-NC-SA 4.0 (siehe LICENSE.md)

Die Rampe besteht aus gleich breiten Segmenten, die ueber eine Schwalbenschwanz-Verbindung
von oben zusammengesteckt werden:

  Anfangsteil  – nur Zapfen, die andere Seite ist glatt
  Mittelteil   – Nut auf der einen, Zapfen auf der anderen Seite (beliebig oft druckbar)
  Endteil      – nur Nut, die andere Seite ist glatt
  Einzelteil   – nur wenn die ganze Rampe auf das Druckbett passt (keine Verbindung)

Aufruf (nur Python 3, keine Zusatzpakete noetig):

  python3 rampe_gen.py --breite 790 --hoehe 20
  python3 rampe_gen.py --breite 900 --hoehe 25 --steigung 10 --max-segment 220 --ausgabe stl_900x25

Alle Masse in mm. Das Programm berechnet Anzahl und Breite der Segmente selbst und
schreibt pro Teiltyp eine STL-Datei sowie eine Stueckliste (stueckliste.txt).
"""
import argparse
import math
import os
import struct
import sys

# ----------------------------------------------------------------- Standardwerte
BREITE       = 790.0   # Gesamtbreite der Rampe = lichte Tuerbreite
HOEHE        = 20.0    # Hoehe der Schwelle
STEIGUNG     = 12.0    # Steigungswinkel in Grad (die meisten Roboter schaffen 12–15°)
TIEFE        = 0.0     # Rampenlaenge; 0 = aus Hoehe und Steigung berechnen
VORDERKANTE  = 1.0     # Dicke der vorderen Auflaufkante (duenner franst beim Druck aus)
MAX_SEGMENT  = 200.0   # groesste Segmentbreite (Druckbett minus Rand und Zapfen)
ZAPFEN_L     = 12.0    # Laenge des Schwalbenschwanzes
SPIEL        = 0.3     # Spiel je Flanke zwischen Zapfen und Nut
# Lage des Schwalbenschwanzes als Anteil der Rampentiefe (bewaehrt bei 90 mm Tiefe:
# Wurzel 52–72 mm, Spitze 47–77 mm – also im hinteren, dicken Teil der Rampe)
ZAPFEN_MITTE = 0.6889  # 62 / 90
ZAPFEN_WURZEL= 0.2222  # 20 / 90  Breite an der Wurzel
ZAPFEN_SPITZE= 0.3333  # 30 / 90  Breite an der Spitze


# ----------------------------------------------------------------- Geometrie
class Rampe:
    def __init__(self, a):
        self.breite, self.hoehe, self.vk = a.breite, a.hoehe, a.vorderkante
        if a.hoehe <= a.vorderkante:
            sys.exit("Fehler: --hoehe muss groesser als --vorderkante sein.")
        self.tiefe = a.tiefe if a.tiefe > 0 else (a.hoehe - a.vorderkante) / math.tan(math.radians(a.steigung))
        self.winkel = math.degrees(math.atan((a.hoehe - a.vorderkante) / self.tiefe))
        self.n = max(1, math.ceil(a.breite / a.max_segment - 1e-9))
        self.seg = a.breite / self.n
        self.L, self.spiel = a.zapfen_laenge, a.spiel
        T = self.tiefe
        xc = ZAPFEN_MITTE * T
        self.r1, self.r2 = xc - ZAPFEN_WURZEL * T / 2, xc + ZAPFEN_WURZEL * T / 2   # Wurzel
        self.t1, self.t2 = xc - ZAPFEN_SPITZE * T / 2, xc + ZAPFEN_SPITZE * T / 2   # Spitze

    def z(self, x):
        """Oberkante der Rampe an der Stelle x (0 = vordere Kante, tiefe = Schwelle)."""
        return self.vk + (self.hoehe - self.vk) * x / self.tiefe

    def _nut_punkte(self):
        """Nut = Zapfen-Trapez, an jeder Flanke um 'spiel' nach aussen versetzt."""
        L, c = self.L, self.spiel

        def flanke(p, q, aussen):
            # Gerade p->q um c nach aussen (Richtung 'aussen' in x) parallel verschieben
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(dx, dy)
            nx, ny = dy / ln, -dx / ln
            if nx * aussen < 0:
                nx, ny = -nx, -ny
            p2 = (p[0] + nx * c, p[1] + ny * c)

            def x_bei(y):
                return p2[0] + dx * (y - p2[1]) / dy
            return x_bei
        links = flanke((self.r1, 0.0), (self.t1, L), -1)
        rechts = flanke((self.r2, 0.0), (self.t2, L), +1)
        Ln = L + c
        return [(links(0.0), 0.0), (links(Ln), Ln), (rechts(Ln), Ln), (rechts(0.0), 0.0)]

    def umriss(self, nut, zapfen):
        """Grundriss eines Segments (x = Tiefe, y = Breite), gegen den Uhrzeigersinn."""
        T, W, L = self.tiefe, self.seg, self.L
        pts = [(0.0, 0.0)]
        if nut:
            pts += self._nut_punkte()
        pts += [(T, 0.0), (T, W)]
        if zapfen:
            pts += [(self.r2, W), (self.t2, W + L), (self.t1, W + L), (self.r1, W)]
        pts += [(0.0, W)]
        return pts

    def dreiecke(self, nut, zapfen):
        """Geschlossenes Dreiecksnetz: Grundriss-Prisma, oben von der Rampenebene begrenzt."""
        poly = self.umriss(nut, zapfen)
        tris2d = ohr_triangulierung(poly)
        out = []
        for a, b, c in tris2d:                                   # Boden (Normale nach unten)
            out.append(((a[0], a[1], 0.0), (c[0], c[1], 0.0), (b[0], b[1], 0.0)))
        for a, b, c in tris2d:                                   # Rampenflaeche (eben, da z linear in x)
            out.append(((a[0], a[1], self.z(a[0])), (b[0], b[1], self.z(b[0])), (c[0], c[1], self.z(c[0]))))
        for i in range(len(poly)):                               # senkrechte Seitenwaende
            p, q = poly[i], poly[(i + 1) % len(poly)]
            p0, q0 = (p[0], p[1], 0.0), (q[0], q[1], 0.0)
            p1, q1 = (p[0], p[1], self.z(p[0])), (q[0], q[1], self.z(q[0]))
            out.append((p0, q0, q1))
            out.append((p0, q1, p1))
        return out


def ohr_triangulierung(poly):
    """Einfache Ohr-Abschneide-Triangulierung fuer ein einfaches Polygon (gegen Uhrzeigersinn)."""
    def kreuz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def innen(p, a, b, c):
        return kreuz(a, b, p) >= -1e-12 and kreuz(b, c, p) >= -1e-12 and kreuz(c, a, p) >= -1e-12

    idx = list(range(len(poly)))
    tris = []
    while len(idx) > 3:
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if kreuz(a, b, c) <= 1e-12:
                continue
            if any(innen(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2) and poly[j] not in (a, b, c)):
                continue
            tris.append((a, b, c))
            idx.pop(k)
            break
        else:
            raise RuntimeError("Triangulierung fehlgeschlagen – Parameter pruefen")
    tris.append(tuple(poly[i] for i in idx))
    return tris


def pruefe_dicht(tris):
    """Jede Kante muss genau zweimal (gegenlaeufig) vorkommen."""
    kanten = {}
    r = lambda p: tuple(round(v, 6) for v in p)
    for t in tris:
        for i in range(3):
            a, b = r(t[i]), r(t[(i + 1) % 3])
            kanten[(a, b)] = kanten.get((a, b), 0) + 1
    return all(kanten.get((b, a), 0) == n for (a, b), n in kanten.items())


def volumen(tris):
    v = 0.0
    for a, b, c in tris:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return v


def schreibe_stl(pfad, tris, name):
    with open(pfad, "wb") as f:
        f.write(name.encode("ascii", "replace")[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / ln, ny / ln, nz / ln, *a, *b, *c, 0))


def fmt(v):
    return f"{v:.1f}".replace(".", ",")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tuerschwellenrampe fuer Saugroboter – STL-Generator")
    ap.add_argument("--breite", type=float, default=BREITE, help="Gesamtbreite = Tuerbreite in mm (Standard 790)")
    ap.add_argument("--hoehe", type=float, default=HOEHE, help="Schwellenhoehe in mm (Standard 20)")
    ap.add_argument("--steigung", type=float, default=STEIGUNG, help="Steigungswinkel in Grad (Standard 12)")
    ap.add_argument("--tiefe", type=float, default=TIEFE, help="Rampenlaenge in mm; 0 = aus Steigung berechnen")
    ap.add_argument("--vorderkante", type=float, default=VORDERKANTE, help="Dicke der vorderen Kante (Standard 1)")
    ap.add_argument("--max-segment", dest="max_segment", type=float, default=MAX_SEGMENT,
                    help="groesste Segmentbreite fuer dein Druckbett (Standard 200)")
    ap.add_argument("--zapfen-laenge", dest="zapfen_laenge", type=float, default=ZAPFEN_L, help="Standard 12")
    ap.add_argument("--spiel", type=float, default=SPIEL, help="Spiel je Flanke in mm (Standard 0,3)")
    ap.add_argument("--ausgabe", default=None, help="Ausgabeordner (Standard: stl_<breite>x<hoehe>)")
    a = ap.parse_args(argv)

    r = Rampe(a)
    out = a.ausgabe or f"stl_{a.breite:g}x{a.hoehe:g}mm"
    os.makedirs(out, exist_ok=True)

    if r.n == 1:
        teile = [("Einzelteil", False, False, 1)]
    else:
        teile = [("Anfangsteil", False, True, 1), ("Mittelteil", True, True, r.n - 2), ("Endteil", True, False, 1)]

    hz = r.z(r.t1)
    zeilen = [
        "Tuerschwellenrampe fuer Saugroboter – Stueckliste",
        "=" * 50,
        f"Gesamtbreite : {fmt(r.breite)} mm",
        f"Schwelle     : {fmt(r.hoehe)} mm hoch",
        f"Rampe        : {fmt(r.tiefe)} mm tief, Steigung {fmt(r.winkel)} Grad, Vorderkante {fmt(r.vk)} mm",
        f"Segmente     : {r.n} x {fmt(r.seg)} mm" + ("" if r.n == 1 else f"  (+ {fmt(r.L)} mm Zapfen ueberstehend)"),
        "",
    ]
    for name, nut, zapfen, anzahl in teile:
        if anzahl <= 0:
            continue
        tris = r.dreiecke(nut, zapfen)
        if not pruefe_dicht(tris):
            sys.exit(f"Fehler: Netz fuer {name} ist nicht geschlossen.")
        datei = f"rampe_{name.lower()}.stl"
        schreibe_stl(os.path.join(out, datei), tris, f"Tuerschwellenrampe {name} DM5CQ CC BY-NC-SA 4.0")
        zeilen.append(f"{anzahl:>3} x  {datei:<26} {fmt(volumen(tris) / 1000)} cm3")
    zeilen += ["", "Pro Tuerseite einmal drucken. Soll der Roboter von beiden Seiten ueber die Schwelle,",
               "alles doppelt drucken. Teile flach mit der Unterseite aufs Bett legen, kein Stuetzmaterial."]
    if r.n > 1 and hz < 5:
        zeilen += ["", f"WARNUNG: Der Zapfen ist vorne nur {fmt(hz)} mm hoch – Steigung verringern oder Tiefe erhoehen."]
    with open(os.path.join(out, "stueckliste.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    print(f"\nSTL-Dateien in: {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
