# Nachweisbericht: JPEG -> SVG Konvertierungsalgorithmus

## Bewertungsbasis
- Implementierung in `src/image_composite_converter.py` (Konvertierung).
- Vergleichs-/Evaluierungs-Workflow in `tools/generate_badge_comparison_set.py`.
- Ergebnislegende `artifacts/converted_symbols/diff_legend.csv`.

## Prüfpunkte aus der Anforderung

### 1) „Er holt sich die sprachliche Beschreibung aus der Textdatei.“
**Status: Teilweise (im Dataset-/Benchmark-Generator, nicht im Kernkonverter).**

- `parse_specs(...)` liest die CSV mit den semantischen Beschreibungen und erzeugt `BadgeSpec`-Objekte.
- `detect_label(...)` und `detect_paddle(...)` extrahieren daraus Textinhalt (`"CO"`, `"CO_2"`) sowie Kellenlage (`unten/oben/links/rechts`).
- Der eigentliche JPEG->SVG-Konverter `convert_image(...)` verarbeitet nur Pixel und liest **keine** Textdatei.

### 2) „Dann extrahiert jedes Element aus der JPEG-Datei.“
**Status: Erfüllt.**

- JPEG wird in Graustufen geladen.
- Per Schwellwertverfahren (`global`, `otsu`, `adaptive`) wird binarisiert.
- `find_elements(...)` extrahiert zusammenhängende Komponenten inkl. Bounding Box.

### 3) „Er zeichnet das Element in SVG nach und variiert die SVGs.“
**Status: Erfüllt.**

- Für jedes Element wird ein Initialkandidat geschätzt (`estimate_initial_candidate`).
- In `optimize_element(...)` werden Zufalls-Nachbarn erzeugt (`random_neighbor`) und iterativ verbessert.
- Ausgabe erfolgt als `<circle>`/`<ellipse>`, bei erkannter Kelle als `<rect>` + Kreis.

### 4) „Dann wird jede Variation mit dem Ursprungsbild verglichen (im beschränkenden Rechteck).“
**Status: Erfüllt.**

- Der Vergleich geschieht über `score_candidate(...)` mittels IoU.
- Die Maske wird in der Elementgröße (lokales Bounding-Rectangle) gerendert (`render_candidate_mask(..., width, height)`).

### 5) „Zum Schluss werden die Elemente zusammengesetzt und Bedingungen eingehalten ...“
**Status: Teilweise.**

- **Zusammensetzen:** erfüllt (`parts` werden in ein finales `<svg>` geschrieben).
- **Text im Kreis, nicht berührend, horizontal/vertikal ausgerichtet:** im Generator (`svg_for_spec`, `inject_label_into_reconverted_svg`) über `text-anchor="middle"` und `dominant-baseline="middle"`; im Kernkonverter selbst gibt es keine OCR/Textrekonstruktion.
- **Kellen-Griff hinter Kreisrand und als Symmetrieachse:** heuristisch umgesetzt über `decompose_circle_with_stem(...)`, indem `<rect>` vor `<circle>` geschrieben wird (Reihenfolge => optisch „hinter“ dem Kreisrand) und bei vertikaler Kelle zentriert wird.

### 6) „Zum Schluss wird wieder ein wenig variiert.“
**Status: Nicht im Sinne eines zweiten globalen Optimierungsschritts für das Gesamtsymbol nach Komposition.**

- Es gibt Variation pro Element in `optimize_element(...)`.
- Ein zusätzlicher abschließender Variationsschritt über das zusammengesetzte Gesamtsymbol ist nicht implementiert.

### 7) Zusätzliche Messungen (Kreis/Strecke/Randdicke)
**Status: Teilweise.**

- Kreisparameter werden intern geschätzt (Zentrum, Größe/Radius-ähnlich über `w/h`).
- Randdicke wird heuristisch abgeleitet (`estimate_stroke_style(...)` -> `stroke_width`).
- Explizite, allgemeine Streckenmessung (Mittelpunkt, Orientierung, Länge) als separates Mess-API fehlt.

## Qualitätsnachweis über `diff_legend.csv`
Aus der vorhandenen Legende (35 Symbole):

- `error_mean`: **min 5.7102**, **max 12.1556**, **Mittel 7.2474**, **Median 7.0649**.
- 32/35 Symbole liegen bei `error_mean <= 10`.
- 28/35 Symbole liegen bei `error_mean <= 8`.

Interpretation: Die Rekonstruktionen sind insgesamt konsistent, mit einzelnen schwierigeren Fällen am oberen Fehlerende.

## Fazit
Der implementierte Prozess deckt den Kern „Elementsegmentierung -> zufällige Varianten -> lokaler Vergleich -> SVG-Komposition“ ab und erreicht laut `diff_legend.csv` überwiegend gute Resultate. Nicht vollständig umgesetzt sind jedoch:

1. Sprachbeschreibung direkt im Kernkonverter nutzen (aktuell nur im Generator/Benchmarkpfad).
2. Ein expliziter zweiter Variations-/Optimierungsschritt nach der finalen Komposition.
3. Vollständige geometrische Mess-APIs für Streckenparameter.
