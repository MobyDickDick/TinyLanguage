# TinyCPU in Logisim-evolution

## AP-12 release acceptance

From a fresh checkout with Eclipse Temurin 21.0.8 available, run the complete
electrical release gate with one command:

```bash
PYTHONPATH=src python src/tiny_cpu_logisim.py \
  --acceptance-output artifacts/tinycpu-ap12-acceptance
```

The command downloads the version-addressed Logisim-evolution 4.1.0 JAR when
needed, verifies both pinned versions, and loads the maintained project. It
then starts `TinyCPUMain` twice from its electrically asserted initial reset
state and compares the normalized 17-edge AP-5 traces. These independent runs
are the reset/restart and multi-cycle reproducibility check. Finally, the same
invocation runs every AP-11 opcode-family and sticky-error fixture; none of
these simulator checks is optional in CI.

The output directory contains `reset-start.tsv` and `restart.tsv` as untouched
Logisim tables, normalized TSV counterparts, all raw `isa-matrix/*.tsv` tables,
and `acceptance.json`. A passed schema-version-2 report inventories every other
evidence file by relative POSIX path, byte size, and SHA-256 digest. This makes
the uploaded bundle self-checking without including the report in its own
manifest. The JSON report is written as schema version 1 with status `started`
before simulation and replaced by the passed report only after every comparison
succeeds, so an interrupted run cannot be mistaken for accepted hardware. CI
uploads the entire directory even on failure.

A retained or downloaded bundle can be checked independently of Java and
Logisim. The verifier rejects missing, additional, reordered, resized, or
digest-mismatched evidence files. It also rejects symbolic links and other
non-regular inventory entries instead of following them outside the retained
bundle. The report and every inventory entry are schema-checked first, so
malformed paths, byte sizes, and SHA-256 values produce a controlled
verification failure rather than being interpreted as evidence metadata. The
verifier also requires the pinned runtime versions, both linked reset/restart
traces with identical digests and edge counts, and a matrix fixture count that
matches the inventoried tables; an arbitrary inventory alone is not an AP-12
acceptance report:

```bash
PYTHONPATH=src python src/tiny_cpu_logisim.py \
  --verify-acceptance artifacts/tinycpu-ap12-acceptance
```

This directory contains the TinyCPU hardware baseline with a dedicated arithmetic sheet.
Open `TinyCPU.circ` with Logisim-evolution 4.1.x. Das Blatt **`TinyCPUMain` ist
die hierarchische Integrationsseite**. Die fachliche Logik liegt in benannten
FBoxen, die auf andere Schemablätter verweisen, darunter `Operations`,
`EffectiveAddress`, `AddressRangeFBox`, `Datapath`, `AddressPath`, `Memory`,
`FetchDecode` und `ErrorFlags`. Auf `TinyCPUMain` verbleiben nur die externen
Pins, der Splitter des extern sichtbaren Befehlsworts, die FBox-Instanzen und
ihre sichtbaren rechtwinkligen Verbindungen. Insbesondere werden die nach der
manuellen Überarbeitung in `AddressRangeFBox` liegenden Fehlergatter nicht auf
die Integrationsseite zurückverschoben.

Die Hierarchie ist von Hand gepflegt und keine generierte Verdrahtung. Generatoren
in diesem Repository dürfen ausschließlich die eigenständigen Dateien unter
`diagnostics/` aktualisieren; Ausgangspunkt bleibt immer die eingecheckte
`TinyCPU.circ` mit ihrer vorhandenen Seitenstruktur.

Die Quelltunnel für die effektiven Adressen und Adressierungsarten sitzen direkt
auf den östlichen Ausgangspins und zeigen nach Westen. Dadurch wachsen ihre
Beschriftungen in den freien Bereich rechts vom jeweiligen Unterblatt, statt
rückwärts über `AddressPath` oder `FetchDecodeControls`; rein optische lange
Verlängerungsleitungen sind nicht nötig. Die beiden Modus-ODER-Gatter und die
Adressmultiplexer bilden unmittelbar unter den Steuerleitungen einen kompakten
Block. Nur der Empfängertunnel am westlichen `Memory`-Eingang bleibt nach Westen
gerichtet.

Die Eingänge des Unterblatts `EffectiveAddress` tragen auf dem festen Symbol
bewusst kurze Namen, die den angeschlossenen Ausgängen von
`FetchDecodeControls` entsprechen: `ADR_REG` kürzt `ADDRESS_REGISTER` ab und
`REG_OFF` steht für `ADDRESS_REGISTER_PLUS_OFFSET`. So bleiben beispielsweise
`LOAD_ADR_REG`, `ADD_ADR_REG` und `STORE_REG_OFF` vollständig sichtbar. Auch
die vier 16-Bit-Eingänge heißen kompakt `DIRECT_ADDR`, `REG_ADDR`,
`OFFSET_ADDR` und `REG_SELECTED`. Das Präfix `EFFECTIVE_` entfällt an den Eingängen. Die Ausgänge von
`FetchDecodeControls` verwenden dieselben Kürzel (`ADR`, `ADR_REG` und
`REG_OFF`), sodass jede angeschlossene 1:1-Verbindung auf beiden Seiten
denselben Namen trägt; die Pinpositionen ändern sich dadurch nicht.

Die Top-Level-Routen zu `EffectiveAddress` besitzen getrennte Korridore. Die
zuvor kurzgeschlossenen Paare `MUL_ADR_REG`/`MUL_REG_OFF` und
`OR_ADR_REG`/`SUB_ADR_REG` sowie das gemeinsame Netz aus `LOAD_ADR_REG`,
`DIV_ADR_REG` und `STORE_ADR_REG` sind getrennt. Auch `CLEAR_ERROR` und die
sechs `SET_*`-Signale laufen einzeln zu den gleichnamigen `ErrorFlags`-Pins;
keine dieser Leitungen endet mehr auf einer fremden Route.

Nach der manuellen Kompaktierung und der dadurch geänderten Pinreihenfolge von
`FetchDecodeControls` wurden diese Fehlerleitungen an den neuen, benannten
Ausgangspositionen neu angeschlossen. Die kürzeren Korridore sowie die
verschobene `AddressPath`-Box bleiben dabei erhalten. Die beiden vorhandenen
Adressmultiplexer tragen weiterhin stabile Bezeichner; ihre Position und
Verdrahtung wurden durch die erneute Abnahme nicht zurückgesetzt.

Auch die nachträglich gegen den Uhrzeigersinn nach oben zurückgeführten
Eingänge von `ACTIVE_OFFSET_ADDRESS_ERROR` bleiben erhalten. Das Gatter zeigt
nun nach Osten; zwei kurze senkrechte Anschlussstücke führen die vorhandenen
Korridore auf seine tatsächlichen Eingangskoordinaten. Der Strukturtest leitet
die Anschlüsse aus der im XML angegebenen Ausrichtung ab, statt die frühere
westliche Ausrichtung oder die alte Position wiederherzustellen.

Der Hardware-Vertragscheck prüft diese Hierarchie auf direkte und indirekte
rekursive Unterblatt-Aufrufe. Solche Zyklen werden abgewiesen, weil Logisim beim
Laden andernfalls die Symbole unbegrenzt expandieren und dabei den verfügbaren
Speicher aufbrauchen kann.

Zusätzlich enthält die integrierte Datei ausschließlich horizontale oder
vertikale Leitungssegmente. Die früher in `Operations`, `AddSubCircuit` und
`SubSubCircuit` enthaltenen diagonalen XML-Leitungen wurden durch rechtwinklige
Segmente ersetzt. Diagonale `<wire>`-Einträge gehören nicht zum unterstützten
Logisim-Netzformat; beim Öffnen muss Logisim sie andernfalls reparieren oder
fortlaufend neu auswerten. Ein Regressionstest prüft deshalb jetzt unmittelbar
die komplette eingecheckte `TinyCPU.circ` und nicht nur künstliche
Fehlerbeispiele des Inspektors.

Eine ausfüllbare Schritt-für-Schritt-Vorlage für die weitere Integration steht
in [`docs/tiny_cpu_top_level_template.md`](../../docs/tiny_cpu_top_level_template.md).
Sie schreibt insbesondere vor, Leitungen in freien Korridoren **um** Symbole
herumzuführen und jeden neuen Signalverbund einzeln zu prüfen.

## TinyClock: erster Top-Level-Baustein

Die elektrische Integration beginnt bewusst mit dem gemeinsamen Takt. Das
isolierte Blatt `IntegrationClock` in `TinyCPU.circ` beschreibt die spätere
Verteilung eines einzigen `CLK`-Eingangs ohne Gatter auf Fetch/Decode,
Datenpfad, Adresspfad, Speicher und Fehlerflags. Sein Pinvertrag ist Teil von
`tinycpu-16-12.json`, sodass
fehlende, umbenannte oder falsch gerichtete Taktanschlüsse bereits in der
reproduzierbaren Hardwareprüfung auffallen.

Passend zur gewünschten Organisation liegt die eigenständig ladbare Ansicht
unter `diagnostics/TinyCPU-IntegrationClock.circ`. Sie wird wie die anderen
Diagnoseprojekte aus `TinyCPU.circ` erzeugt und bytegenau gegen das eingebettete
Blatt geprüft. Damit gibt es nur eine Schaltungsquelle, aber weiterhin eine
kleine Datei für die Poke-Prüfung in Logisim-evolution. Auf der manuell
wiederhergestellten Übersichtsseite erreicht die Taktleitung jetzt
Fetch/Decode, Datenpfad, Adresspfad, Speicher und Fehlerflags. Der neue Abzweig
verläuft oberhalb der Symbole im freien Korridor und trifft ausschließlich den
`CLK`-Anschluss von `ErrorFlags`.

## TinyReset: definierter Neustart des Befehlszählers

Das isolierte Blatt `IntegrationReset` führt den externen Eingang `RESET`
ohne kombinatorische Logik an den Reset-Anschluss von Fetch/Decode. Damit wird
der Programmzähler reproduzierbar auf den Startzustand gesetzt, ohne den
Inhalt der Daten- und Valid-RAMs oder die getrennte Fehlerlöschung durch
`CLEAR_ERROR` umzudeuten. Das Blatt `IntegrationReset` und das erzeugte
Diagnoseprojekt `diagnostics/TinyCPU-IntegrationReset.circ` frieren diesen
Pinvertrag unabhängig vom breiteren Top-Level ein. Auf der wiederhergestellten
Übersichtsseite erreicht `RESET` ausschließlich Fetch/Decode; Steuernetze,
Daten- und Halt-Netze bleiben davon getrennt.

## Ressourcenverbrauch eingrenzen

### Kleinstmögliche Verdrahtungsproben

Bevor eines der CPU-Blätter geöffnet wird, können die drei Projekte in
`smoke/` geprüft werden:

| Datei | Bauteile | Leitung | Zweck |
|---|---:|---:|---|
| `PinPair-1bit.circ` | 2 Pins | 1 | einfaches Steuersignal |
| `PinPair-12bit.circ` | 2 Pins | 1 | Adressbusbreite der TinyCPU |
| `PinPair-16bit.circ` | 2 Pins | 1 | Datenbusbreite der TinyCPU |

Jede Datei besitzt nur ein Eingangs- und ein Ausgangspin gleicher Breite. Die
beiden Anschlusskoordinaten liegen auf derselben Horizontalen und werden durch
genau ein gerades Leitungssegment verbunden. Es gibt weder Abzweigungen noch
Kreuzungen, Rückkopplungen, Speicher oder Unterblätter. Ein Repository-Test
prüft genau diese Invarianten sowie die XML-Lesbarkeit. Damit trennen die
Proben einen grundsätzlichen Ladefehler der verwendeten Logisim-Version von
Fehlern in der CPU-Verdrahtung.

Die Dateien bitte in der Reihenfolge 1, 12 und 16 Bit einzeln öffnen. Wenn
bereits `PinPair-1bit.circ` nicht ohne stark steigenden Speicherverbrauch lädt,
ist die CPU-Schaltung nicht die Ursache. Wenn alle drei Proben funktionieren,
aber eines der folgenden Diagnoseblätter nicht, ist der Fehler auf dieses
Blatt beziehungsweise dessen Bauteiltypen eingegrenzt.

Die statische Prüfung des Projekts findet 150 XML-Komponenten (davon sechs
reine Textfelder) und 298 rechtwinklige Leitungssegmente. Diagonale Leitungen
werden abgewiesen, weil Logisim sie beim Laden nicht als gültige Drähte
verarbeiten kann. `FetchDecode` ist mit 69 elektrischen
Komponenten der größte Block; `ErrorFlags` folgt mit 34. Die beiden 4096-Zellen-
RAMs liegen ausschließlich in `Memory`. In `ErrorFlags` läuft jede
Rückkopplung über ein getaktetes Register, daher ist dort im Schaltbild keine
rein kombinatorische Rückkopplung erkennbar. Eine Speicherbelegung von mehreren
Gigabyte lässt sich allein durch diese Projektgröße nicht erklären; sie sollte
blockweise in der tatsächlich verwendeten Simulatorversion reproduziert
werden.

Dafür enthält `diagnostics/` fünf eigenständig ladbare Projekte:

| Datei | Elektrische Komponenten | Leitungen | Isoliert insbesondere |
|---|---:|---:|---|
| `TinyCPU-FetchDecode.circ` | 69 | 109 | ROM, Decoder und PC-Steuerung |
| `TinyCPU-Datapath.circ` | 12 | 22 | Akkumulator und Vergleich |
| `TinyCPU-AddressPath.circ` | 12 | 25 | Adressregister und Addierer |
| `TinyCPU-Memory.circ` | 12 | 27 | Daten- und Validitäts-RAM |
| `TinyCPU-ErrorFlags.circ` | 34 | 110 | Sticky-Flag-Rückkopplungen |

Im Blatt `AddressPath` beziehen sich die XML-Koordinaten der Register auf die
linke obere Symbolecke und nicht auf einen Anschluss. D, WE und CLK werden
deshalb gezielt an ihren darunterliegenden Anschlusskoordinaten verdrahtet.
Adressbus und Offset enden getrennt an A und B des Addierers. Die
Offset-Leitung umfährt dabei den ein Bit breiten Reset-Anschluss des
Adressregisters; der Carry-Ausgang beginnt am separaten ein Bit breiten
Addiereranschluss. Die Leitungsführung besteht ausschließlich aus horizontalen und vertikalen
Segmenten, von denen sich keine zwei kollinear überdecken.

Dasselbe Anschlussprinzip gilt im Blatt `Datapath`: `DATA_IN`, `ACC_LOAD` und
`CLK` enden an D, WE und CLK beider Register statt an deren Symbolmitten. Der
16-Bit-Akkumulator und die Nullkonstante belegen außerdem getrennte Eingänge
des Komparators; die ein Bit breiten Statusausgänge bleiben davon isoliert.
`Memory` führt Adresse, Schreibfreigabe und Takt parallel zu beiden RAMs und
legt `VALID_IN` ausschließlich auf den Dateneingang des Validitäts-RAMs. Da
beide RAMs eigene Ausgangsleitungen haben und keinen gemeinsamen Bus treiben,
liegen ihre Output-Enable-Anschlüsse dauerhaft an logisch 1. Output-Enable ist
dabei unabhängig von `WRITE_ENABLE`.
`ErrorFlags` taktet die sechs Sticky-Register über einen segmentierten
gemeinsamen Taktbus; ein High-Pegel an WE sorgt dafür, dass jedes berechnete
Folgebit auf der steigenden Flanke übernommen wird. Die Rückführung von Q zum
jeweiligen `HOLD_*`-Gatter ist jetzt als kurze, U-förmige Leitung vollständig
sichtbar. Sie verläuft im freien Korridor oberhalb der jeweiligen Flag-Zeile
und kreuzt weder Reset-Anschlüsse noch Takt- oder WE-Bus.

## Gestaltungsregel: sichtbare Leitungen vor Tunneln

Die TinyCPU soll eine **graphische und direkt verfolgbare** Schaltung bleiben.
Darum werden zusammengehörige Anschlüsse grundsätzlich mit sichtbaren,
rechtwinkligen Leitungen verbunden. Auf der neu gezeichneten Übersichtsseite
`TinyCPUMain` sind die verbliebenen Tunnel jetzt durch sichtbare Leitungen in
getrennten rechten Routingkorridoren ersetzt; unbeschriftete Logikbausteine
halten dabei den Signalfluss statt interner Netznamen im Vordergrund. Tunnel sind kein Mittel, um eine schwierige
Leitungsführung abzukürzen. Sie sind nur ausnahmsweise zulässig, wenn eine
direkte Route trotz Verschieben der Bauteile und Nutzung freier Korridore die
Lesbarkeit verschlechtern oder fremde Netze elektrisch verbinden würde. Jede
solche Ausnahme muss im Designdokument begründet und bei der nächsten
Überarbeitung erneut auflösbar geprüft werden. Neue oder lokal begrenzte Netze
dürfen nicht als Tunnel angelegt werden. Die sechs bisher getunnelten
Sticky-Flag-Rückkopplungen sind deshalb vollständig durch sichtbare Leitungen
ersetzt.

Die Dateien nacheinander einzeln öffnen und CPU- sowie Speicherverbrauch nach
dem vollständigen Laden notieren. Tritt das Problem schon ohne Takten auf,
grenzt die erste auffällige Datei den verantwortlichen Baustein ein. Tritt es
nur beim Takten auf, zuerst `ErrorFlags`, dann `FetchDecode` prüfen. Bleibt jede
Einzeldatei unauffällig, liegt der Verdacht auf der Integration im Top-Level
oder auf einem Simulatorproblem. Die sechs Diagnoseprojekte enthalten
absichtlich nur je ein Blatt und ersetzen `TinyCPU.circ` nicht als integrierte
Schaltung. Fetch/Decode ist dabei in den Zustands- und ROM-Pfad (`FetchDecode`)
sowie die eigentliche Steuersignaldecodierung (`FetchDecodeControls`)
aufgeteilt.

Das Blatt `Operations` sowie seine Auswahlblöcke `AddSubCircuit` und
`SubSubCircuit` sowie die extrahierte `AndSubCircuit` besitzen getrennte, rechtwinklige Leitungswege für Steuerbits,
16-Bit-Operanden und Gültigkeitssignale. Insbesondere enden die Daten- und
Select-Leitungen an den tatsächlichen Multiplexeranschlüssen; gemeinsame
Operanden werden über eigene Fan-out-Korridore verteilt. Dadurch entstehen an
Kreuzungen weder versehentliche Busverbindungen noch mehrere Treiber auf einem
Netz. Der Strukturtest verlangt für alle drei Blätter einen vollständig
verbundenen Zustand.

Die sichtbaren Aktivierungs- und Gültigkeitsbezeichner folgen auf jedem
Arithmetikblatt der tatsächlichen Operation. Insbesondere heißen sie im
Subtraktionspfad `ACC_SUB_VALID`/`SUB_VALID` und am Multiplikationseingang
`MUL_ACTIVATED`; die zuvor aus den ADD- beziehungsweise SUB-Vorlagen
mitkopierten Namen waren nur falsche Beschriftungen, keine zusätzlichen Netze.
Ein Regressionstest prüft diese Zuordnung nun gemeinsam für ADD, SUB, MUL und
DIV, damit die Verdrahtung beim visuellen Verfolgen nicht mehr irreführend ist.

Für die integrierten Operationszweige bildet `Operations` zusätzlich ein
gemeinsames Aktivitätssignal. Nur wenn dieses aktiv ist und zugleich kein
Zweigergebnis gültig ist, wird `INVALID_OPERAND` gesetzt. Dieser
Ausgang führt im Hauptblatt direkt zu `ErrorFlags.SET_INV`; der gleichnamige
Platzhalterausgang des Decoders ist bewusst nicht mehr angeschlossen. Dadurch
bleibt das Invalid-Flag bei inaktiver Arithmetik gelöscht, obwohl die gegateten
Ergebnis-Gültigkeitssignale dann ebenfalls null sind.

Die zusammengeführte Ergebnisgültigkeit wird dagegen ohne eine weitere
Fehlermaske direkt als `RESULT_IS_VALID` ausgegeben. Jeder Operationszweig
unterdrückt sein `RESULT_VALID` bereits selbst: ADD, SUB und MUL bei Überlauf,
DIV bei Division durch null und alle Zweige bei ungültigen Operanden. Eine
zweite Negation von `INVALID_OPERAND` auf `Operations` wäre daher redundant.

Sie werden reproduzierbar aus dem Hauptprojekt erzeugt. Der Befehl liest
`TinyCPU.circ`, schreibt aber nur Dateien in das angegebene Diagnoseverzeichnis;
er ist ausdrücklich **kein** Weg, das Blatt `TinyCPUMain` wiederherzustellen oder
zu ersetzen:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output hardware/logisim/diagnostics \
  hardware/logisim/TinyCPU.circ
```

## What is implemented

The project fixes the initial hardware profile at 16 data bits and 12 address
bits and splits the design into the same blocks as the hardware contract:

## Korrektur-Arbeitspakete: Datenquellen und indirekte Adressierung

Bei der weiteren Verdrahtung darf der 16-Bit-Operandenanteil des Befehlsworts
nicht pauschal als Datenwert verwendet werden. Er hat je nach Adressierungsart
drei verschiedene Bedeutungen: unmittelbarer Wert (`*_CONST`), direkte
Speicheradresse (`*_ADDRESS`) oder Offset zum Adressregister
(`*_ADDRESS_REGISTER_PLUS_OFFSET`). Bei `*_ADDRESS_REGISTER` besitzt der
Befehl gar keinen Datenoperanden. Der Akkumulator ist davon unabhängig die
linke Seite jeder binären Operation und die Datenquelle für Speicherzugriffe.

Die folgenden Punkte bilden die priorisierte Fehler- und Arbeitsliste. Ein
Punkt wird erst abgehakt, wenn die sichtbare Logisim-Verdrahtung und ein
Struktur- oder Verhaltenstest dieselbe Datenquelle bestätigen:

### Ergebnis der erneuten Verdrahtungsprüfung

Die zentrale Auswahl auf `EffectiveAddress` ist elektrisch getrennt aufgebaut:
Der erste Multiplexer wählt zwischen dem direkten Adressfeld und dem Inhalt
des Adressregisters. Nur wenn eine `*_ADDRESS_REGISTER`-Steuerleitung aktiv
ist, wird der Registereingang ausgewählt. Der zweite Multiplexer wählt danach
für eine aktive `*_ADDRESS_REGISTER_PLUS_OFFSET`-Steuerleitung die bereits in
`AddressPath` berechnete Summe aus Register und Offset; andernfalls reicht er
das Ergebnis des ersten Multiplexers weiter. Damit erreicht immer genau eine
effektive Adresse den gemeinsamen Adresseingang von Daten- und Validitäts-RAM.

Wichtig für den Begriff **indirekt**: Die TinyCPU-ISA implementiert
registerindirekte Adressierung, nicht Memory-indirekte Adressierung. Bei
`LOAD_ADDRESS_REGISTER()` steht die effektive Adresse bereits im
Adressregister; der Daten-RAM wird daher für diese Instruktion nur einmal an
dieser Adresse gelesen. Soll die Adresse ihrerseits aus dem Speicher stammen,
muss sie vorher mit `LOAD_ADDRESS_REGISTER_ADDRESS(address)` in einer eigenen
Instruktion ins Adressregister geladen werden. Erst eine andere, hier nicht
definierte Memory-indirekte Adressierungsart würde innerhalb derselben
Instruktion zwei aufeinanderfolgende Speicherlesevorgänge benötigen.

`AddressPath.OFFSET_CARRY` ist nun über das bezeichnete Gatter
`ACTIVE_OFFSET_ADDRESS_ERROR` mit `ErrorFlags.SET_ADDR` verknüpft. Das Gatter
fordert zusätzlich `EffectiveAddress.EFFECTIVE_OFFSET_MODE`; ein Übertrag des
ständig kombinatorisch berechneten Offsets setzt das Sticky-Flag deshalb nur
für eine tatsächlich aktive Register-plus-Offset-Instruktion. Der bisherige
Decoder-Platzhalter `SET_ADDR` bleibt elektrisch isoliert. Die zentrale
Bereichsprüfung vergleicht die ausgewählte 16-Bit-Adresse mit `0xfff` und wird
nur für eine aktive direkte, Register- oder Register-plus-Offset-Speicherform
ausgewertet. Das benannte Gatter `ACTIVE_ADDRESS_ERROR` vereinigt diesen
Bereichsfehler mit dem aktiven Offset-Übertrag, bevor `ErrorFlags.SET_ADDR`
gesetzt wird. Die beiden Adressmultiplexer tragen wieder stabile
Bezeichner, damit Strukturtests und die Logisim-Ansicht diese Verdrahtung
eindeutig verfolgen können.

Die manuelle Überarbeitung von `Operations` ist dabei ausdrücklich erhalten:
die drei Operationsblöcke und ihre Ergebnis-ODER-Gatter bleiben in den nach
rechts verschobenen, rechtwinklig verdrahteten Routingbahnen. Die Abnahme
bindet diese Anordnung nicht mehr an die Koordinaten der fehlerhaften
Vorgängerversion. Bei der Kontrolle des nächsten Arbeitspakets wurden dagegen
die versehentlich entfernten Bezeichner der beiden Adressmultiplexer wieder
ergänzt. Das ändert weder ihre Position noch ihre Verdrahtung, macht aber die
zentrale Auswahl zwischen direkter Adresse, Registeradresse und Offsetsumme
wieder eindeutig und automatisiert prüfbar.

- [x] Die Python-VM als semantische Referenz absichern: `ADD` und `SUB`
  verwenden in allen vier Adressierungsarten den bisherigen Akkumulator als
  linken Operanden; direkte und beide adressregisterbasierten Varianten lesen
  den rechten Operanden aus dem Speicher. Die gezielten Regressionstests
  unterscheiden bewusst Akkumulator, Konstante, Adresse, Offset und
  Speicherinhalt, sodass ein versehentlich verwendetes Befehlsfeld auffällt.
- [x] `AddSubCircuit` korrigieren: `LEFT` muss von `Datapath.ACC_OUT` kommen.
  `RIGHT` benötigt einen durch die vier `ADD_*`-Signale gesteuerten Pfad, der
  nur für `ADD_CONST` den unmittelbaren Operanden und sonst
  `Memory.MEMORY_DATA` verwendet. Direkte Adresse, Adressregister und
  Adressregister-plus-Offset bestimmen dabei ausschließlich die Speicheradresse.
- [x] `SubSubCircuit` symmetrisch korrigieren. Gerade bei `SUB` darf weder die
  Reihenfolge vertauscht noch für eine indirekte Variante der konstante
  Befehlsoperand subtrahiert werden: Das Ergebnis ist immer
  `ACC_OUT - selected_right_operand`.
- [x] Die Validität der ADD/SUB-Datenquelle parallel zum Datenmultiplexer
  führen: `*_CONST` liefert einen gültigen unmittelbaren Wert; jede
  Speicherform benötigt `Memory.MEMORY_VALID`; beide Fälle benötigen zusätzlich
  `Datapath.ACC_VALID_OUT`. Ein ungültiger Adressregister- oder Speicherwert
  muss `RESULT_VALID` löschen und `SET_INV` auslösen.
- [x] Die effektive Adresse für alle direkten und indirekten Familien zentral
  prüfen: `*_ADDRESS` verwendet das 12-Bit-Adressfeld,
  `*_ADDRESS_REGISTER` den Inhalt des Adressregisters und
  `*_ADDRESS_REGISTER_PLUS_OFFSET` dessen Summe mit dem signierten Offset.
  Übertrag beziehungsweise Bereichsfehler müssen `SET_ADDR` auslösen.
- [x] `MUL` nach demselben Vertrag prüfen und verdrahten: links Akkumulator,
  rechts unmittelbarer Wert oder gelesener Speicherwert. Ergebnis, Validität,
  vorzeichenbehafteter Überlauf und ungültige Operanden werden im
  `Operations`-Blatt zusammengeführt.
- [x] Anschließend `DIV`, `AND` und `OR` nach demselben Vertrag prüfen und
  verdrahten. `DIV` benötigt zusätzlich die Nullprüfung des ausgewählten
  rechten Operanden. `DIV` und `AND` sind abgeschlossen; bei `AND` bleibt der
  inaktive logische Identitätswert `0xffff` erhalten und wird erst an der
  gemeinsamen OR-Ergebnisgrenze auf null normalisiert. `OR` und die danach
  ergänzte `XOR`-Familie sind ebenfalls abgeschlossen.
- [x] Die nicht-binären Datenwege separat auditieren: `STORE_*` schreibt den
  Akkumulator, `NOT` invertiert den Akkumulator, `PRINT` liest den Akkumulator,
  `PRINT_ADDRESS` liest Speicher und `LOAD_*` schreibt den jeweils ausgewählten
  unmittelbaren oder indirekt gelesenen Wert in den Akkumulator. `LOAD_*` und
  `NOT` sind korrekt integriert. Die Prüfung hält ausdrücklich fest, dass die
  Speicher-Schreibeingänge und die beiden Print-Steuerungen noch offen sind;
  ihr Anschluss erfolgt in getrennten Folgepaketen.
- [x] Nach diesen Korrekturen den gemeinsamen Ergebnisbaum und die Fehlerflags
  integrieren. Die neutral gegateten Zweigergebnisse speisen den gemeinsamen
  Daten- und Validitätsbaum; `OVERFLOW`, `DIVIDE_BY_ZERO` und
  `INVALID_OPERAND` erreichen ausschließlich ihre jeweils zuständigen
  Sticky-Fehlerpfade. Die getrennten Strukturtests für Operandenwahl und
  Aggregation bleiben weiterhin beide erforderlich.

Die `AddSubCircuit`-/`SubSubCircuit`-Punkte einschließlich ihrer Validität sind
nun abgeschlossen: Beide Boxen verwenden `ACC_OUT` links und wählen rechts
parallel zwischen unmittelbarem Befehlswert und Speicherwert samt zugehöriger
Gültigkeit. `SET_INV` ist für aktive Operationen mit ungültiger Quelle
integriert. Ebenso sind der Offset-Übertrag und die gemeinsame
12-Bit-Bereichsprüfung nun aktivitätsabhängig an `SET_ADDR` angebunden. Die
`MUL_*`-Familie ist ebenfalls hinter `Operations` integriert. Ihre aktiv
begrenzten Ergebnis-, Validitäts- und Überlaufausgänge erweitern die
vorhandenen Zusammenfassungen; ein aktiver ungültiger MUL-Operand setzt damit
denselben `SET_INV`-Pfad wie ADD und SUB. Als nächster binärer
Operationsschritt folgt die `DIV_*`-Familie.

Die erste DIV-Etappe ist als getrennte `DivSubCircuit`-FBox vorbereitet. Sie
übernimmt denselben linken Akkumulator und dieselbe parallele Auswahl von
unmittelbarem beziehungsweise speicherbasiertem rechten Operanden wie MUL.
Die untergeordnete `DivArithmeticCircuit`-Seite führt zusätzlich eine
explizite Nullprüfung des ausgewählten Divisors heraus und sperrt damit die
Ergebnisgültigkeit. Die Integration in die gemeinsamen Ergebnis- und
Fehlerbäume bleibt das folgende Arbeitspaket. Beim Ausbau werden wachsende
FBoxen nicht dichter zusammengeschoben; sichtbare Routingkorridore bleiben
zwischen ihren Begrenzungen erhalten.

`TinyCPUMain` is the integration sheet. Stateful blocks are encapsulated on
named subpages, and its single `Operations` instance groups the independently
selectable `AddSubCircuit`, `SubSubCircuit`, `MulSubCircuit`, and `NotCircuit`
boxes. Shared
instruction, memory, accumulator, and validity values cross that boundary only
once; result, result-valid, and overflow aggregation remains local to
`Operations`. Every
component and subcircuit instance has a unique label so that signals remain
traceable in Logisim and in the dependency-free inspector.

### Neutrale Operationsausgänge

Die Operationszweige werden schrittweise auf einen neutralen Ausgangsvertrag
umgestellt: Ein nicht ausgewählter Zweig liefert sowohl für `RESULT` als auch
für `RESULT_VALID` null. Dadurch dürfen die Daten aller Zweige mit bitweisen
OR-Gattern zusammengeführt werden. **Auch die Valid-Bits müssen dabei mit OR,
nicht mit AND, vereinigt werden**: Da jeder inaktive Zweig null liefert, würde
eine AND-Verknüpfung den gültigen aktiven Zweig stets wieder auf null ziehen.
Der Decoder muss weiterhin garantieren, dass höchstens eine Operation aktiv
ist; eine Mehrfachaktivierung wäre sonst kein Multiplexing, sondern würde die
Datenwörter bitweise vermischen.

Das neu gezeichnete Integrationsblatt behält die drei getrennten Boxen für
`AddSubCircuit`, `SubSubCircuit` und `NotCircuit` bei. Zwei explizite,
zweistufige ODER-Bäume führen deren neutrale Daten- beziehungsweise
Valid-Ausgänge auf `OPERATION_RESULT` und `OPERATION_VALID` zusammen. Damit
werden weder Ausgangstreiber direkt zusammengeschaltet noch Daten und
Gültigkeit unterschiedlich priorisiert.

`NotCircuit` erfüllt diesen Vertrag bereits direkt: `ACTIVE_NOT_RESULT` sperrt
das invertierte Datenwort mit `NOT_SELECT`, und `ACTIVE_NOT_VALID` sperrt das
zugehörige Valid-Bit. Die ADD- und SUB-Zweige nullen ihre Operanden derzeit über
die vorhandenen Eingangs-Multiplexer. Beim weiteren Umbau sind ihre
Ergebnis-Valid-Bits ebenfalls explizit mit dem jeweiligen Aktivierungssignal zu
sperren, bevor die bisherigen Auswahl-Multiplexer durch OR-Bäume ersetzt
werden. Das ist bewusst eine inkrementelle Fortführung der vorhandenen
Schaltung und kein erneutes Ersetzen des Hauptblatts.

- `TinyCPUMain` connects the functional subcircuits and is the top-level circuit selected when the project is opened;
- `AddSub` bündelt die beiden parallelen 16-Bit-Operanden in einem 32-Bit-Bus und die beiden Gültigkeitsleitungen in einem 2-Bit-Bus. Erst auf dem eigenen Schemablatt teilen Splitter diese Busse für den 16-Bit-Addierer und -Subtrahierer auf; ein gemeinsamer Selektor führt genau ein Ergebnis zurück. Das Blatt kommt vollständig ohne Tunnel aus und bildet damit die neue, kompakte Grenze für den arithmetischen ADD/SUB-Strang;
  its accumulator integration is visually grouped into a decode column and compact,
  labelled ADD/SUB stage columns so related operand, result, and validity logic can
  be read without scrolling to a disconnected lower workspace;
- `Datapath` contains the synchronously loaded 16-bit accumulator and its
  mandatory valid bit; a signed comparator exports `ZERO` and `NEGATIVE`;
- `AddressPath` contains the synchronously loaded 12-bit address register and
  its valid bit, plus the combinational 12-bit offset adder and carry output;
- `Memory` connects a 4096 x 16 data RAM and a 4096 x 1 validity RAM to the
  same address, write-enable, and clock signals; and
- `ErrorFlags` implements the six set-dominant sticky error registers (`OVF`,
  `DIV0`, `ADDR`, `INV`, `ILL`, and `INPUT`) with a shared `CLEAR_ERROR`.
  Each hold path feeds the register output back through an AND gate and therefore
  crosses a clocked register; the feedback is not a combinational loop.
- `FetchDecode` contains the 12-bit `PC`, a 4096-word instruction ROM, the
  sequential/jump PC path, program-limit check, and control decode for the complete symbolic ISA. The expanded decoder
  exposes every addressing, arithmetic, logic, branch, and I/O control plus all six
  error-set paths.
- On the maintained `TinyCPUMain` integration sheet, the 22-bit `FetchDecode.OPCODE` bus is
  the first decode-integration net and drives only the matching input of the
  separately placed `FetchDecodeControls` block. Its left-side route remains
  isolated from the already integrated clock and reset nets.
- The first decoded one-bit control, `CLEAR_ERROR`, leaves
  `FetchDecodeControls` through the free outer-right corridor and reaches only
  the matching `ErrorFlags` input. It remains isolated from clock, reset, and
  the opcode bus.
- The first sticky-error set control, `SET_OVF`, uses a separate outer-right
  lane between `FetchDecodeControls` and `ErrorFlags`. It remains isolated
  from `CLEAR_ERROR` and every earlier top-level net.
- The second sticky-error set control, `SET_DIV0`, runs through its own next
  outer-right lane and reaches only the matching `ErrorFlags` input. It stays
  isolated from `SET_OVF` and all earlier top-level nets.
- The four remaining sticky-error controls (`SET_ADDR`, `SET_INV`, `SET_ILL`,
  and `SET_INPUT`) continue in dedicated outer-right lanes. Each reaches only
  its identically named `ErrorFlags` input, so none of the long routes ends on
  an unconnected grid point or joins another control net.
- The machine word reaches `FetchDecodeControls` through a splitter that
  selects opcode bits 21..16; the split-off 16-bit operand reaches the visible
  `Datapath.DATA_IN` terminal on an isolated net. Splitter, subcircuit, and pin
  `loc` attributes are component anchors, not a reliable substitute for the
  visible terminals of generated symbols; future top-level routes must use
  terminals verified in Logisim rather than coordinates inferred from those
  anchors. All four `LOAD_*`, `ADD_*`, `SUB_*`, `MUL_*`,
  `DIV_*`, `AND_*`, `OR_*`, and `XOR_*` addressing modes are the first eight
  datapath-control families. Separate routes feed the explicitly
  thirty-two-input,
  named `ACC_LOAD_REQUEST` OR gate,
  whose output, the unary `NOT` control, and `INPUT` feed three independent
  inputs of a second, named `ACC_WRITE_REQUEST` OR gate. That final gate alone
  reaches `Datapath.ACC_LOAD`; the decoder outputs are never tied directly
  together. This two-stage arrangement keeps the family aggregator within
  Logisim's 32-input limit while accommodating non-family accumulator writes. The
  structural tests resolve the participating controls and gates by their labels
  and then compare electrical nets. Coordinates remain a drawing detail.
  `INPUT_VALID` independently reports whether `INPUT_VALUE` is usable. The
  first one-bit validity multiplexer chooses the
  immediate-path valid constant or `Memory.MEMORY_VALID` using the same
  `ACC_MEMORY_SELECT` control as the corresponding data selector. The labelled
  `ACC_NOT_VALID_SELECT` stage then selects `Datapath.ACC_VALID_OUT` for `NOT`,
  so an invalid unary operand cannot become valid merely by being inverted.
  The final one-bit multiplexer forwards `INPUT_VALID` to
  `Datapath.VALID_IN` only for `INPUT` and otherwise passes the preceding
  validity result. This validity route remains electrically separate from the
  16-bit accumulator data selectors.
  Endpoint-on-wire junctions are still treated as Logisim connections so an
  accidental wired-OR cannot pass unnoticed. The labelled 16-bit
  `ACC_DATA_SELECT` multiplexer first chooses the instruction operand or memory
  data for all three memory-backed load modes. Its result feeds the default
  input of `ACC_NOT_SELECT`; the other input receives `ACC_OUT` through the
  labelled 16-bit `ACC_NOT_VALUE` inverter, and only the independent `NOT`
  control selects that computed value. The selected 16-bit result follows the
  direct route of the manually corrected drawing to the visible
  `Datapath.DATA_IN` terminal. The same redraw routes `INPUT_VALUE`, the
  `INPUT` selector and `CLEAR_ERROR` directly; the obsolete tunnel endpoints
  are deliberately not reconstructed from inferred subcircuit coordinates.
  Structural tests follow these checked-in routes and keep the one-bit controls
  isolated from the 16-bit accumulator bus. The `ADD_*` validity stage
  independently groups all four addition modes, selects a valid immediate or
  `Memory.MEMORY_VALID`, and ANDs that operand validity with
  `Datapath.ACC_VALID_OUT`. The result is selected between the `NOT` and
  `INPUT` validity stages. The following `SUB_*` data stage selects the
  immediate operand or `Memory.MEMORY_DATA`, subtracts it from `ACC_OUT`, and
  inserts that result before the final `INPUT` data selector. Its parallel
  validity stage requires both `ACC_VALID_OUT` and the matching immediate-or-
  memory operand validity. `INPUT_VALUE` and `INPUT_VALID` therefore retain
  final priority over both binary families.

`AddValidCircuit` and `SubValidCircuit` now have the same six-input/one-output
shape.  Earlier, the drawing referred to as the addition-valid circuit also
contained the surrounding default, memory, `NOT`, and final family selectors.
It was therefore a validity-pipeline wrapper rather than the counterpart of
`SubValidCircuit`; its larger size did not reflect more complex ADD validity
rules.  The extracted ADD circuit now contains only the symmetric rule: group
the three memory-backed modes, combine them with the constant mode, select
constant-valid or `Memory.MEMORY_VALID`, and AND the result with
`Datapath.ACC_VALID_OUT`.

Die eigentlichen 16-Bit-Operationen liegen nicht mehr auf dem gemeinsamen
`AddSub`-Blatt, sondern auf den Unterseiten `AddArithmeticCircuit` und
`SubArithmeticCircuit`. Beide Unterseiten führen neben `RESULT` auch
`OVERFLOW` und `RESULT_VALID` heraus. Damit bleibt die bestehende, nach
Adressierungsart gegliederte Logik in `AddValidCircuit` beziehungsweise
`SubValidCircuit` übersichtlich, während die zugehörige Rechenoperation direkt
darunter gekapselt ist.

## Einheitliche Operationsboxen und Ergebnispriorität

Für die weitere Integration gilt eine Operation als eigene FBox. Neben dem
berechneten Wert liefert sie ihre Gültigkeit und ein Aktivsignal. Fehler sind
ebenfalls Teil der Box; bei `ADD` und `SUB` ist dies `OVERFLOW`. Die neue
`NotCircuit`-Box hat dieselbe äußere Form. Da eine bitweise Invertierung nicht
überlaufen kann, ist ihr `OVERFLOW`-Ausgang fest auf 0 gelegt. `SubCircuit`
übernimmt entsprechend die beiden von der Adressierungslogik vorbereiteten
Operanden, ihre Gültigkeit und das SUB-Aktivsignal und kapselt damit die
vollständige Subtraktion. Die bereits
von Hand angepasste ADD-Box `AddSubCircuit` bleibt erhalten; ihre Ausgänge
`RESULT`, `OVERFLOW`, `ADD_VALID` und `ADD_SELECTED` bilden denselben Vertrag.

Logisim-evolution besitzt keinen einzelnen Multiplexer, der unmittelbar „den
ersten Eingang mit aktiver Enable-Leitung“ auswählt. Ein normaler Multiplexer
erwartet eine binär codierte Auswahl. Dafür kann man entweder einen
Prioritätsencoder vor einen Mehrfachmultiplexer setzen oder – in diesem
Schaltbild besser sichtbar – 2:1-Multiplexer kaskadieren. In der Kaskade wählt
jede Operationsbox mit ihrem `*_SELECTED`-Signal zwischen dem bisherigen Wert
und ihrem Resultat. Die Reihenfolge der Stufen definiert damit ausdrücklich
die Priorität; es entsteht kein Bus mit mehreren gleichzeitig treibenden
Ausgängen. Die Decoderlogik soll zwar weiterhin höchstens eine Operation
aktivieren, die Kaskade bleibt aber auch bei mehreren aktiven Leitungen
elektrisch eindeutig.

Die Bereichsprüfung interpretiert Daten als vorzeichenbehaftete 16-Bit-Werte
im Bereich -32768 bis +32767. Bei der Addition liegt ein Überlauf vor, wenn die
Operanden dasselbe Vorzeichen, das Ergebnis jedoch ein anderes Vorzeichen hat.
Bei der Subtraktion liegt er vor, wenn die Operanden verschiedene Vorzeichen
haben und das Ergebnisvorzeichen vom linken Operanden abweicht. `RESULT_VALID`
ist nur gesetzt, wenn `INPUT_VALID` gesetzt und `OVERFLOW` nicht gesetzt ist;
ein Überlauf in Richtung + oder - unendlich kann deshalb nicht als gültiger
Datenwert in den Akkumulator gelangen.

Der `b in`-Eingang des Logisim-Subtrahierers ist dabei explizit mit der
Konstante 0 verbunden. Ein offener Borrow-Eingang wird von Logisim als
Fehlerwert ausgewertet und würde deshalb auch bei zwei gültigen
16-Bit-Operanden ein rotes `E` an `RESULT` erzeugen.

Dasselbe gilt für den optionalen `c in`-Eingang des Addierers: Er ist auf
`AddArithmeticCircuit` mit `CARRY_IN_ZERO` fest auf 0 gelegt. Damit haben
Addition und Subtraktion vollständig definierte primitive Eingänge. Die
beiden Rechenblätter enthalten außerdem keine Null-Längen-Leitungen mehr;
direkt aneinanderliegende Gate-Anschlüsse werden ohne solche wirkungslosen
XML-Wire-Einträge verbunden.

Auf dem Integrationsblatt besitzt die automatisch erzeugte, breite
`SubArithmeticCircuit`-Darstellung nun einen eigenen sichtbaren Korridor vor
dem Multiplexer `ACC_SUB_SELECT`. Die beiden Ergebnisleitungen wurden bis zu
den verschobenen Multiplexereingängen verlängert; Beschriftungen liegen nicht
mehr auf dem Unterseitensymbol. Ein Strukturtest friert diesen Mindestabstand
ein, damit ein späteres Verschieben die in Logisim sichtbaren Bauteile nicht
erneut übereinanderlegt.

The extracted `SubValidCircuit` is placed below the surrounding validity
selectors so that all six automatically generated input ports remain visible.
The four `SUB_*` decoder controls, `Memory.MEMORY_VALID`, and
`Datapath.ACC_VALID_OUT` are routed individually to those ports; its sole
`SUB_VALID` output then returns to the existing result selector. The
memory-valid branch approaches its port from below, while the `SUB_CONST` branch
ends before that vertical lane and approaches its own port from above. This
avoids both the visually adjacent but electrically open pins that resulted from
merely replacing the original gates with a subcircuit instance and accidental
connections between neighbouring input pins.

Die automatisch gezeichneten Anschlüsse einer Subcircuit-Instanz werden in
der `.circ`-Datei nicht mit ihren Pin-Namen gespeichert. Ihre sichtbaren
Koordinaten hängen von Logisims Symbol-Layout ab und können sich nach einem
manuellen Speichern ändern. Die Tests leiten deshalb für Takt und Reset keine
Top-Level-Anschlusskoordinaten mehr her: Sie prüfen die benannten Pinverträge
der fünf Zustandsblöcke sowie die eigenständigen `IntegrationClock`- und
`IntegrationReset`-Netze. Feste Koordinaten bleiben nur dort Bestandteil eines
Tests, wo die konkrete, eingecheckte Zeichnungsgeometrie selbst der Vertrag ist.

The AP 5 countdown program is loaded into the instruction ROM and its
clock-edge reference trace is checked in as `ap5_countdown_trace.json`. AP 7
replaces the provisional ROM representation with the versioned machine format
described below.

## AP 4 clock sequences

All instructions are fetched combinationally at the current `PC`. On the next
rising edge the selected operation commits and `PC` takes `PC + 1`, except for
a taken `JUMP_NOT_ZERO`, which selects its 12-bit target. The exposed controls
have these sequences:

| Instruction | Decode/execute before edge | Commit at edge |
|---|---|---|
| `LOAD_CONST value` | drive operand to the accumulator and assert load/valid | load `ACC`; increment `PC` |
| `STORE_ADDRESS address` | select memory address, drive `ACC` and validity, assert write | write both RAMs; increment `PC` |
| `ADD_ADDRESS address` | read value/validity and select the adder result | load result/validity into `ACC`; increment `PC` |
| `JUMP_NOT_ZERO target` | combine decode with `!ZERO` and select the target when true | load target or `PC + 1` |
| `PRINT` | present the valid accumulator to the output boundary | emit once; increment `PC` |
| `HALT` | assert the normal halt output | retain halted state and `PC` |

The integration sheet exports the decoded `HALT` and `HALT_ERROR` controls as
the separate `HALT_ENABLE` and `HALT_ERROR_ENABLE` event outputs. Consumers can
therefore retain the stopped state while preserving whether execution ended
normally or explicitly requested an error halt; neither event can masquerade
as the other through a shared net.

The hand-maintained `FetchDecode` drawing now arranges the program-counter
increment before the `PC_RANGE` overflow check. This ordering is intentional:
the range decision belongs to the incremented program-counter path, not to the
former pre-increment layout. Structural regression checks therefore follow the
relative increment/range topology and must not restore the old component
coordinates. An invalid result asserts both `SET_ADDR` and `HALT_ERROR`.

## AP 6 complete symbolic control surface

`FetchDecode` now has a six-bit provisional decoder and exports one named
control for every instruction in `src/tiny_cpu_isa.py`. Its condition boundary
accepts `ZERO`, `NEGATIVE`, and aggregate `ERROR`; its error boundary exports
all six sticky-flag set controls. The hardware profile records the same
instruction, condition, and error sets, and parameterized structural tests
check every member rather than sampling individual controls.

This milestone completes the *symbolic* ISA control surface: constant, direct,
address-register, and address-register-plus-offset modes; arithmetic and logic;
all conditional and unconditional jumps; error clearing; and input/output are
present at the decode boundary. Arithmetic range, invalid operands and
addresses, division by zero, invalid instructions, and invalid input continue
to feed the AP 3 sticky error registers. The AP 5 countdown trace remains the
core behavioral regression.

## AP 7 machine format and encoder

`tinycpu-machine-v1.json` is the stable, machine-readable opcode table. A
machine word contains the six-bit opcode in bits 21..16 and its 16-bit operand
in bits 15..0. Direct addresses and jump targets must fit the unsigned 12-bit
address space; constants and offsets use signed 16-bit two's complement.
Operand-free instructions require zero in their reserved operand field, and
opcode values 46..63 are reserved. Existing assignments are append-only within
format version 1; incompatible changes require a new format version.

`src/tiny_cpu_machine.py` validates those ranges, encodes and decodes individual
instructions, and emits Logisim ROM images plus readable listings. Regenerate
the checked-in countdown artifacts with:

```bash
PYTHONPATH=src python src/tiny_cpu_machine.py \
  hardware/logisim/ap5_countdown.tcpu \
  --rom hardware/logisim/ap5_countdown.rom \
  --listing hardware/logisim/ap5_countdown.lst
```

`TinyCPU.circ` contains exactly this generated 22-bit ROM image. The test suite
roundtrips every symbolic instruction, validates the JSON allocation, and
compares the generated image with both the checked-in `.rom` file and the ROM
embedded in Logisim.

## AP 5 reproducible fixture

`ap5_countdown.tcpu` uses only the six core controls. It stores `-1` at address
101, counts down a value at address 100, prints `3`, `2`, and `1`, and halts
without an error after 17 rising edges. The ROM contents use the version-1 machine words generated by the AP 7 encoder.

The checked-in JSON records the PC, accumulator and validity, status bits,
watched memory cells, cumulative output, error flags, and halt state after every
edge. Regenerate it from the VM or compare an exported Logisim trace with:

```bash
PYTHONPATH=src python src/tiny_cpu_trace.py \
  hardware/logisim/ap5_countdown.tcpu --watch 100 --watch 101
PYTHONPATH=src python src/tiny_cpu_trace.py \
  hardware/logisim/ap5_countdown.tcpu --watch 100 --watch 101 \
  --check hardware/logisim/ap5_countdown_trace.json
```

The comparison is deliberately field-oriented: a failure names the clock edge
and observable field that diverged. This makes the fixture usable both in CI
and while single-stepping the circuit. AP 6 extends decode and execution
without changing this frozen core trace.

The `.rom` file is the supported Logisim interchange representation; the
`.lst` file is diagnostic output and is not consumed by the circuit.

### TinyCPUMain integration boundary trace

`tinycpu_integration_trace.json` freezes three small acceptance scenarios for
the completed top-level output boundary: normal `HALT`, explicit `HALT_ERROR`,
and `PRINT` while the accumulator is invalid. Each edge records the eight
distinct print/halt pins before the rising edge and the sticky errors and halt
state after it. In particular, invalid output asserts `PRINT_ENABLE` while
`PRINT_VALID` remains low; it must not be confused with a successful emission.

The dependency-free verifier regenerates the expected observations with the
Python VM and compares every field with this checked-in interchange fixture.
This is the reference used to review a trace exported from Logisim-evolution;
it is not presented as an electrical simulation when Logisim is unavailable.

The preferred interchange is the table logger's CSV or tab-separated output.
Label the observed signals with the following header names, in any order:

```text
PRINT_ENABLE PRINT_ADDRESS_ENABLE PRINT_VALUE PRINT_VALID
PRINT_ADDRESS_VALUE PRINT_ADDRESS_VALID HALT_ENABLE HALT_ERROR_ENABLE
ERROR_OVF ERROR_DIV0 ERROR_ADDR ERROR_INV ERROR_ILL ERROR_INPUT
HALTED HALTED_WITH_ERROR
```

One data row represents one rising edge. Bits must be `0` or `1`; values may
be decimal or use Python-style `0x`/`0b` prefixes. Save the matching assembly
program separately and compare the electrical table directly with:

```bash
PYTHONPATH=src python src/tiny_cpu_trace.py scenario.tcpu \
  --integration --check-logisim-table logisim_trace.tsv
```

The JSON interchange schema remains supported for hand-authored fixtures:

```bash
PYTHONPATH=src python src/tiny_cpu_trace.py scenario.tcpu \
  --integration --check logisim_trace.json
```

The command selects the integration-boundary sampling contract rather than the
full AP 5 VM-state contract and reports the first differing edge/field. Memory
`--watch` arguments intentionally remain exclusive to the full-state mode.
Undefined electrical cells such as `x` are rejected rather than silently
coerced to a value.

## Automated checks and simulation

### Pinned real-simulator load smoke test

AP 9 pins Logisim-evolution 4.1.0 and Eclipse Temurin Java 21.0.8. CI installs
the exact available Temurin build `21.0.8+9.0.LTS`; the launcher downloads the
version-addressed upstream Logisim JAR into the user cache, prints both
dependency versions, and loads
`TinyCPUMain` through Logisim's non-interactive table interface:

```bash
PYTHONPATH=src python src/tiny_cpu_logisim.py
```

The command returns non-zero if Java has drifted, the simulator cannot start,
the project cannot be parsed, the named top-level circuit is missing, or the
headless load times out. Use `--jar PATH` to test an already downloaded copy;
the copy must still identify itself as version 4.1.0. This gate proves a real
simulator can load the maintained project, but deliberately makes no claim
about VM/CPU trace parity; exporting the AP-5 pins is AP 10.

The launcher intentionally does not pass the former `-circuit` CLI option:
Logisim-evolution 4.1.0 rejects that option. Instead, the project declares
`TinyCPUMain` as its `<main>` circuit, so `-tty table TinyCPU.circ` selects the
maintained integration sheet directly.

With `--trace-output PATH`, the launcher makes a temporary project copy and
replaces only `TinyCPUMain`'s external clock and reset pins with an autonomous
clock and an inactive constant. Driving the maintained circuit directly avoids
depending on Logisim's generated port order for a nested wrapper symbol. The 16
named observation pins expose events, sticky errors, and terminal state to the
table logger. For this normal-
halt AP-5 fixture, `HALTED` is derived directly from the electrically valid
`HALT_ENABLE` event instead of an additional state gate; `HALTED_WITH_ERROR`
likewise mirrors `HALT_ERROR_ENABLE`. The lowercase
`halt` companion pin and the `table,halt` tty mode stop simulation at the
terminal edge; neither the companion pin nor the temporary `TRACE_CLK` pin is
part of the comparator schema. The launcher converts Logisim's grouped,
change-driven display into one stable low-phase sample per rising edge for the
comparison. The unmodified simulator output is written to `PATH`
before comparison, so CI can publish useful electrical evidence on both success
and mismatch. The launcher creates that artifact before dependency checks and
the workflow uploads the complete diagnostics directory, so an unavailable JDK,
download failure, or simulator start failure cannot be hidden by a subsequent
"no files found" artifact error. The checked-in project retains `TinyCPUMain`
as its normal main circuit; the AP-9 load-only invocation therefore remains
independently useful.

### Fresh-checkout acceptance

From the repository root, the supported dependency-free acceptance command is:

```bash
PYTHONPATH=src python src/tiny_cpu_verify.py
```

It checks the versioned hardware contract, reproducible ROM and listing, the
embedded ROM, the 17-edge AP-5 trace, and all three integration-boundary trace
scenarios. Electrical connectivity remains the responsibility of the inspector
and Logisim-evolution. Then run the focused regression tests with:

```bash
PYTHONPATH=src python -m pytest -q tests/detailtests/test_tiny_cpu_logisim.py
```

Neither command modifies the checkout. A stale generated file is reported by
name; regenerate ROM/listing with the AP 7 command above. A trace mismatch is
reported by edge and field; regenerate the trace only after reviewing the VM or
schematic behavior as an intentional compatibility change.

### Architecture and simulation boundary

The clocked state is owned by `FetchDecode` (PC), `Datapath` (accumulator and
validity), `AddressPath` (address register and validity), `Memory` (parallel
value/validity RAM), and `ErrorFlags` (six sticky bits). `FetchDecode` reads the
22-bit instruction word and exposes symbolic controls; the other sheets commit
selected state on the rising edge. `TinyCPUMain` is the integration boundary for
the shared clock, reset, data/control paths, output, and halt state.

The repository includes a dependency-free `.circ` netlist inspector. It parses
the XML, lists circuits and components, and returns a failing exit status when
sheets contain no wires or components have no wire at their anchor. For
`FetchDecode`, the inspector also checks that each exported symbolic control is
wired to its exact six-bit decoder lane; this catches dangling output-pin stubs
or off-by-one-grid wires that would otherwise look connected from the pin alone:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py hardware/logisim/TinyCPU.circ
```

The leaf sheets pass the structural check; the manually maintained top-level
sheet remains pending while its integration wiring is completed. The inspector
is **not** a replacement for Logisim's
component simulator: faithfully emulating the complete Logisim library,
propagation rules, clocks, unknown values, and RAM would amount to maintaining a
second Logisim. Use Logisim-evolution's command-line simulation for electrical
tests once the schematic is wired, and compare clock-by-clock CPU state with
the executable reference model in `src/tiny_cpu_vm.py`.

The completed first work package also freezes the initial structural contract
in `tinycpu-16-12.json`. It can be checked before any wiring is complete:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --profile hardware/logisim/tinycpu-16-12.json --contract-only \
  hardware/logisim/TinyCPU.circ
```

See `docs/tiny_cpu_roadmap.md` for the ordered implementation packages and
their acceptance criteria.

## Electrical construction rule

TinyCPU does **not** use wired-OR nets.  Every net may have at most one active
driver; combine control signals with an explicit OR gate instead of joining
component outputs.  This also applies when a wire endpoint lands in the middle
of another wire: Logisim treats that T contact as a junction even if the longer
segment was not split in the project XML.

Run the structural checker after every schematic edit:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py hardware/logisim/TinyCPU.circ
```

The checker derives output ports for built-in parts and generated subcircuit
symbols and reports a `wired-OR is forbidden` routing conflict when two output
terminals are reachable on one electrical net.

## Division wiring contract

The four `DIV_*` control routes follow the current pin order of the manually
compacted `Operations` symbol. `DivSubCircuit` returns the result, result
validity, and `DIVIDE_BY_ZERO`. It deliberately has no overflow output:
integer division stays in the representable range, while a zero divisor (or an
already invalid operand) makes the result invalid. Result and validity feed
the consolidated OR gates on `Operations`; the superseded chain of
operation-specific OR gates must not be restored.

## Bitwise OR extraction contract

`OrSubCircuit` is the independently inspectable, tunnel-free boundary for the
four `OR_*` addressing modes. It selects the immediate or memory operand and
its validity in parallel, always combines that selected right operand with the
accumulator, and exports `RESULT`, activity-gated `RESULT_VALID`, and
`RESULT_ACTIVE`. `OrArithmeticCircuit` uses a 16-bit bitwise OR primitive and a
zero inactive result, so the unintegrated box cannot drive the shared result
merge. Bitwise OR has no arithmetic-overflow output. Integration into
`Operations` is a separate follow-up package.

## Bitwise XOR extraction contract

`XorSubCircuit` applies the same tunnel-free operand and validity selection as
the OR box to all four `XOR_*` addressing modes. `XorArithmeticCircuit` uses a
16-bit XOR gate, exports a zero result while inactive, and activity-gates
`RESULT_VALID`; bitwise XOR deliberately has no overflow output. The checked-in
leaf diagnostic is generated from the maintained project. `Operations` now
instantiates the box once and extends its maintained seven-way result,
validity, and activity trees through explicit two-input OR stages. Four paired
local tunnel lanes cross the occupied compact merge area; this documented
exception avoids moving the manually maintained boxes. The four XOR controls
append their version-1 opcodes and deliberately add no overflow source.

The manual redraw reviewed with this package is not treated as layout-only:
although reversing the endpoint order of a wire is electrically neutral, its
removed `Operations` routes carried operation controls and the result,
validity, overflow, and invalid-operand aggregations. Removing those routes
would change CPU behaviour. Consequently the maintained routes remain part of
the hardware contract; this package only adds the new OR sheets.


## AP-11-Abdeckungsvertrag

`tinycpu-electrical-matrix-v1.json` ist die maschinenlesbare Soll-Matrix für
die nächste elektrische Abnahmestufe. Sie ordnet jeden Opcode des stabilen
Maschinenformats einer Testfamilie zu und benennt für jedes Sticky-Fehlerbit
eine Fehler-Fixture. Der gepinnte Launcher validiert die Matrix vor Java- und
Logisim-Start gegen `tinycpu-machine-v1.json`; fehlende, doppelte, zusätzliche
oder umnummerierte Opcodes sowie unvollständige Fehlerabdeckung brechen den Lauf
ab. Die Matrix allein ist kein Simulationsnachweis; der Launcher führt deshalb
jede Familie mit ausgetauschtem ROM elektrisch aus und vergleicht ihre
Flankentabelle gegen die VM.

Der CI-Aufruf übergibt zusätzlich
`--matrix-output artifacts/ci/tinycpu-ap11-matrix`. Der Launcher assembliert
damit jede in der Matrix hinterlegte Fixture, ersetzt ausschließlich den ROM-
Inhalt einer temporären Projektkopie und schreibt die unveränderte Logisim-
Tabelle unter der Fixture-ID. Auch die sechs Fehler-Fixtures, einschließlich
des reservierten Roh-Opcodes, werden so gegen den VM-Grenzvertrag geprüft.
