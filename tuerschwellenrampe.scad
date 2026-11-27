// Türschwellenrampe für Saugroboter – anpassbar (OpenSCAD-Customizer)
// Idee, Design und Umsetzung: Simon Kaiser
// Veröffentlicht von Stefan J. Kaiser DM5CQ / OE8KKS
// Lizenz: CC BY-NC-SA 4.0 (siehe LICENSE.md)
//
// In OpenSCAD: Fenster > Customizer einblenden, Werte eintragen, "teil" wählen,
// F6 (Rendern) und Datei > Exportieren > STL. Für jeden Teiltyp einmal exportieren.
// Die Stückliste (Anzahl und Breite der Segmente) steht in der Konsole.

/* [Tür und Schwelle] */
// Gesamtbreite der Rampe = lichte Türbreite (mm)
gesamtbreite = 790; // [100:1:2500]
// Höhe der Schwelle (mm)
schwellenhoehe = 20; // [5:0.5:60]

/* [Rampe] */
// Steigungswinkel in Grad (die meisten Roboter schaffen 12–15°)
steigung = 12; // [5:0.5:20]
// Rampenlänge (mm); 0 = aus Höhe und Steigung berechnen
tiefe_manuell = 0; // [0:1:400]
// Dicke der vorderen Auflaufkante (mm)
vorderkante = 1; // [0.4:0.1:3]

/* [Drucker und Steckverbindung] */
// Größte Segmentbreite – an das Druckbett anpassen (mm)
max_segmentbreite = 200; // [60:1:400]
// Länge des Schwalbenschwanzes (mm)
zapfen_laenge = 12; // [6:0.5:25]
// Spiel je Flanke zwischen Zapfen und Nut (mm)
spiel = 0.3; // [0.1:0.05:0.6]

/* [Ausgabe] */
// Welches Teil soll erzeugt werden?
teil = "alle"; // [alle:Alle Teile nebeneinander, anfang:Anfangsteil (nur Zapfen), mitte:Mittelteil (Nut + Zapfen), ende:Endteil (nur Nut), einzel:Einzelteil (ohne Verbindung)]

/* [Hidden] */
$fn = 32;
tiefe  = tiefe_manuell > 0 ? tiefe_manuell : (schwellenhoehe - vorderkante) / tan(steigung);
anzahl = max(1, ceil(gesamtbreite / max_segmentbreite - 1e-9));
seg    = gesamtbreite / anzahl;
// Schwalbenschwanz im hinteren, dicken Teil der Rampe (bewährt bei 90 mm Tiefe: Wurzel 52–72, Spitze 47–77 mm)
xc = 0.6889 * tiefe;
r1 = xc - 0.2222 * tiefe / 2;  r2 = xc + 0.2222 * tiefe / 2;   // Wurzel
t1 = xc - 0.3333 * tiefe / 2;  t2 = xc + 0.3333 * tiefe / 2;   // Spitze
k  = (r1 - t1) / zapfen_laenge;                                  // Flankenneigung je mm

echo(str("Stückliste: ", anzahl, " Segmente à ", seg, " mm – Rampe ", tiefe, " mm tief, ",
         atan((schwellenhoehe - vorderkante) / tiefe), " Grad"));
if (anzahl == 1) echo("Drucken: 1 x Einzelteil");
else echo(str("Drucken: 1 x Anfangsteil, ", anzahl - 2, " x Mittelteil, 1 x Endteil"));

// Keil: Querschnitt der Rampe, entlang y (Breite) beliebig lang
module keil() {
    translate([0, 5000, 0]) rotate([90, 0, 0])
        linear_extrude(10000)
            polygon([[0, 0], [tiefe, 0], [tiefe, schwellenhoehe], [0, vorderkante]]);
}

module zapfen_2d() {
    polygon([[r1, 0], [r2, 0], [t2, zapfen_laenge], [t1, zapfen_laenge]]);
}

module nut_2d() {
    // Flanken nach unten verlängert, damit an der Teilekante kein Grat stehen bleibt
    offset(delta = spiel)
        polygon([[r1 + k, -1], [r2 - k, -1], [t2, zapfen_laenge], [t1, zapfen_laenge]]);
}

module grundriss(nut, zapfen) {
    difference() {
        union() {
            square([tiefe, seg]);
            if (zapfen) translate([0, seg]) zapfen_2d();
        }
        if (nut) nut_2d();
    }
}

module segment(nut, zapfen) {
    intersection() {
        keil();
        linear_extrude(schwellenhoehe + 1) grundriss(nut, zapfen);
    }
}

abstand = tiefe + 15;
if (teil == "anfang")      segment(false, true);
else if (teil == "mitte")  segment(true, true);
else if (teil == "ende")   segment(true, false);
else if (teil == "einzel") segment(false, false);
else {
    if (anzahl == 1) segment(false, false);
    else {
        segment(false, true);
        translate([abstand, 0, 0]) segment(true, true);
        translate([2 * abstand, 0, 0]) segment(true, false);
    }
}
