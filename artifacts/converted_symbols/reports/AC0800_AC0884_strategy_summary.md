# Strategien-Auswertung (AC0800..AC0884)

Diese Übersicht kategorisiert Logzeilen in erfolgreiche/erfolglose/fixierte bzw. anpassbare Schritte.

## Strategiematrix

| Strategie | Erfolgreich | Erfolglos | Fix geregelt | Anpassbar (neutral) |
|---|---:|---:|---:|---:|
| center_diagonal_update | 0 | 313 | 0 | 231 |
| color_bracketing | 0 | 0 | 135 | 0 |
| geometry_sync | 0 | 0 | 0 | 92 |
| joint_multistart | 2 | 287 | 0 | 0 |
| length_bracketing | 65 | 150 | 0 | 0 |
| radius_bracketing | 215 | 74 | 0 | 0 |
| width_bracketing | 30 | 107 | 534 | 0 |

## Interpretation für Skript-Verbesserungen

- **center_diagonal_update**: Status **kritisch** (success=0, failed=313, fixed=0).
  - Negativbeispiel: `circle: Mittelpunkt/Diagonale-Update verworfen (Fehler 49.369->56.487)`
- **color_bracketing**: Status **kritisch** (success=0, failed=0, fixed=135).
  - Hinweis: enthält fixierte Randbedingungen (aktuell nicht dynamisch).
- **geometry_sync**: Status **kritisch** (success=0, failed=0, fixed=0).
- **joint_multistart**: Status **kritisch** (success=2, failed=287, fixed=0).
  - Negativbeispiel: `circle: Joint-Multistart keine relevante Änderung (cx=15.000, cy=15.000, r=13.500, best_err=4040.000)`
  - Positivbeispiel: `circle: Joint-Multistart cx 32.500->32.500, cy 12.500->12.500, r 9.500->10.000 (best_err=16799.000)`
- **length_bracketing**: Status **kritisch** (success=65, failed=150, fixed=0).
  - Negativbeispiel: `stem: Längen-Bracketing keine relevante Änderung (stem_len: 22.000); Kandidaten=14.500->53.016, 22.000->46.476, 29.500->66.283, 37.500->85.671, 45.000->101.351`
  - Positivbeispiel: `stem: Längen-Bracketing stem_len 10.500->12.000; Kandidaten=7.500->82.600, 10.500->56.389, 12.000->53.111, 16.000->69.600, 20.500->90.780, 25.000->110.191`
- **radius_bracketing**: Status **erfolgreich** (success=215, failed=74, fixed=0).
  - Negativbeispiel: `circle: Radius-Bracketing keine relevante Änderung (r: 6.500, best_err=2009.000); Kandidaten=6.000->5165.000, 6.500->2009.000, 7.000->2181.000`
  - Positivbeispiel: `circle: Radius-Bracketing r 13.701->13.500 (best_err=4040.000); Kandidaten=10.500->22179.000, 13.500->4040.000, 14.000->8560.000, 14.500->16999.000`
- **width_bracketing**: Status **kritisch** (success=30, failed=107, fixed=534).
  - Negativbeispiel: `text: Breiten-Bracketing keine relevante Änderung (co2_font_scale: 0.903); Kandidaten=0.865->188.955, 0.903->177.996, 0.941->179.506, 0.992->181.359, 1.038->181.359, 1.043->181.359, 1.082->181.359, 1.120->181.359`
  - Positivbeispiel: `text: Breiten-Bracketing co2_font_scale 0.940->0.903; Kandidaten=0.865->188.955, 0.903->179.875, 0.940->181.416, 0.941->181.362, 0.992->181.359, 1.043->181.359, 1.081->181.359, 1.082->181.359, 1.120->181.359`
  - Hinweis: enthält fixierte Randbedingungen (aktuell nicht dynamisch).

## Was ist fix geregelt vs. anpassbar?

- **Fix geregelt**: Zeilen mit `übersprungen`, `Farben gesperrt` oder `Range=min..max` mit identischen Grenzen.
- **Anpassbar**: Bracketing-/Korrektur-/Update-Schritte ohne Sperre.

## Verbesserungsansätze

1. Bei Strategien mit vielen `keine relevante Änderung` Suchraum/Startwerte adaptiv erweitern.
2. Für `verworfen`-Meldungen Box-Check-Schwellen dynamisch an Symbolgröße koppeln.
3. Für häufig fixierte Strategien (v. a. Farbe/Breite) optionalen `unlock`-Modus pro Referenz erlauben.
4. Strategien mit häufigem Erfolg als erste Stufe priorisieren, um Iterationen zu sparen.
