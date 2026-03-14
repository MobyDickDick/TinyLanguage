# Konkreter Umbauplan: JPEG → SVG mit hoher Qualität

## Zielbild

Die aktuelle Pipeline ist stark auf binäre Flächen und wenige Primitive (Kreis/Ellipse) ausgelegt. Für JPEG-Quellen führt das zu hoher Abweichung. Ziel ist eine mehrstufige, robuste Pipeline mit messbarer Qualitätssteigerung.

## Ausgangslage (Ist)

- Frühzeitige harte Binarisierung (`threshold=220`) zerstört Kanten-/Tonwertinformation.
- Komponenten werden nur aus Binärmaske segmentiert.
- Geometrie ist überwiegend auf Kreis/Ellipse beschränkt.
- Die Optimierung variiert primär Parameter bestehender Primitive, nicht die Primitive selbst.

## Umbau in 3 Ausbaustufen

### Stufe 1 (klein, 1–2 Tage): Qualitätsgewinn ohne Architekturbruch

1. **Adaptive Schwellwertbildung statt globalem Threshold**
   - Neue Option in `load_binary_image`: `mode={global,otsu,adaptive}`.
   - Standard für JPEG: Otsu oder adaptive Kachel-Schwellen.
2. **Vorverarbeitung für JPEG-Artefakte**
   - Leichte Glättung (Median/Gauss klein) vor Segmentierung.
   - Optional Morphology Open/Close gegen Blockartefakte.
3. **Parameter je Bild automatisch wählen**
   - Kleines Raster an Parametern testen, bestes nach MAE/IoU übernehmen.
4. **Messbarkeit absichern**
   - Bestehende Roundtrip-Metriken als Gate: MAE/RMSE/Exact Pixel.

**Erwartung:** deutliche Verbesserung bei gezackten Konturen und kleinen Flecken; schneller, risikoarmer Gewinn.

### Stufe 2 (mittel, 3–5 Tage): Primitive-Vokabular erweitern

1. **Neue Primitive einführen**
   - `rect`, `rounded_rect`, `line`, `polyline` zusätzlich zu `circle`/`ellipse`.
2. **Konturbasierte Kandidatenerzeugung**
   - Aus Komponenten Außenkontur ableiten und passende Primitive vorschlagen.
3. **Mehrziel-Scoring**
   - Kombinierte Zielfunktion: IoU + Konturtreue + Flächenabweichung.
4. **Lokale Feinoptimierung pro Primitive-Typ**
   - Typ-spezifische Nachbarschaftsschritte, nicht nur `(cx, cy, w, h)`.

**Erwartung:** große Verbesserung bei nicht-runden Symbolteilen und Kantenqualität.

### Stufe 3 (größer, 1–2 Wochen): Kontur-/Pfadfokus für hohe Treue

1. **Pfadbasierte Vektorisierung**
   - Konturen in Polygone/Pfade überführen, dann glätten/vereinfachen.
2. **Kurvenanpassung**
   - Bezier-Segmente dort einsetzen, wo Polygone zu eckig sind.
3. **Layering & Reordering**
   - Primitive/Pfade nach Überdeckung sortieren, um visuelle Logik zu erhalten.
4. **Qualitätsmodus mit Budget**
   - CLI-Profile: `fast`, `balanced`, `high_quality`.

**Erwartung:** bestes Qualitätsniveau, dafür höhere Rechenzeit und Komplexität.

## Konkrete Code-Eingriffspunkte

- `load_binary_image(...)`: neue Modi + JPEG-spezifische Vorverarbeitung.
- `find_elements(...)`: robustere Segmentierung für verrauschte Ränder.
- `Candidate`/`candidate_to_svg(...)`: Typen um `rect`/`line`/`polyline` erweitern.
- `score_candidate(...)`: zusammengesetzte Metrik statt reinem IoU-Fokus.
- CLI (`argparse`): Qualitätsprofile, Auto-Parametrisierung, Debug-Outputs.

## Test- und Messplan

1. **Unit-Tests erweitern**
   - Neue Primitive in Render-/Scoring-Tests.
   - Vorverarbeitungsmodi deterministisch testen.
2. **Roundtrip-Benchmark fixieren**
   - Reproduzierbarer Satz JPEGs + feste Seeds.
   - Vergleich vor/nach Umbau als Tabelle.
3. **Abnahmekriterien (Vorschlag)**
   - Durchschnittlicher Exact-Pixel-Anteil mindestens +15 Prozentpunkte.
   - Keine Verschlechterung in bestehenden SVG→Raster→SVG-Checks.

## Reihenfolge-Empfehlung

1. Stufe 1 vollständig + Metrikreport aktualisieren.
2. Stufe 2 für 2–3 priorisierte Primitive (`rect`, `line`, `polyline`).
3. Stufe 3 nur, wenn Qualitätsziel nach Stufe 2 nicht erreicht wird.

## Pragmatic Fallback

Falls bestimmte JPEGs weiterhin schwer zu vektorisieren sind:

- Hybrid-SVG erlauben (eingebettetes Raster für problematische Teilflächen).
- Diese Fälle im Report kennzeichnen, statt stillschweigend schlechte Vektoren zu liefern.
