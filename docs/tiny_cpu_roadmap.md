# Arbeitsplan: TinyCPU-Hardware

Dieser Plan führt die vorhandene symbolische ISA schrittweise zu einer in
Logisim-evolution ausführbaren TinyCPU. Die Python-VM bleibt während des
gesamten Aufbaus das Referenzmodell. Jeder Schritt muss einzeln prüfbar sein;
ein Maschinenformat wird erst festgelegt, wenn Datenpfad und Steuerwerk stabil
sind.

## Ziel und Definition of Done

Das erste Zielsystem verwendet 16 Datenbits, 12 Adressbits und 4096
Speicherzellen. Fertig ist die TinyCPU, wenn ein Logisim-Testlauf das
Kernprogramm aus Arbeitspaket 5 taktweise mit der VM vergleichen kann und
Ausgabe, Haltzustand, Register, Speicher-Validität und Fehlerflags
übereinstimmen.

## Arbeitspakete

| AP | Inhalt | Ergebnis und Abnahme |
|---|---|---|
| **1. Hardwarevertrag einfrieren** | Zielprofil, benötigte Subcircuits, Register, RAM-Breiten und Fehlerbits maschinenlesbar festlegen. | Versioniertes Profil; der Inspector bestätigt, dass `TinyCPU.circ` den Vertrag erfüllt. |
| **2. Daten- und Adresspfad** | Akkumulator und Adressregister samt Valid-Bits verdrahten; Zero und Negative ableiten; Offset-Addition ergänzen. | Register lassen sich taktsynchron laden; Statusausgänge entsprechen der VM für Grenzwerte. |
| **3. Speicher und Fehlerregister** | Daten- und Valid-RAM an gemeinsame Adresse und Write-Enable legen; sechs set-dominante Sticky-Flags und `CLEAR_ERROR` bauen. | Lesen, Schreiben, Invaliditätsfortpflanzung und Set-vor-Clear-Priorität sind getestet. |
| **4. Fetch und Decode** | PC, Instruktions-ROM und Steuerwerk für `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT` und `HALT` aufbauen. | Jede Kerninstruktion besitzt einen dokumentierten Taktablauf; ungültiger PC setzt `ADDR` und hält fehlerhaft. |
| **5. Kernprogramm integrieren** | Zählschleife als reproduzierbare Fixture ausführen und Zustände nach jedem Takt gegen die VM vergleichen. | Identische Trace, Ausgabe und Haltstatus in VM und Logisim. |
| **6. ISA vervollständigen** | Weitere Adressierungsarten, Arithmetik, Logik, Sprünge und I/O ergänzen. | Parametrisierte Positiv- und Fehlertests decken jede Instruktion ab. |
| **7. Maschinenformat und Tooling** | Versionierte Opcode-Tabelle und Wortlayout definieren; Encoder, ROM-Image und Listing erzeugen. | Roundtrip-Tests und ein durch den Encoder geladenes Logisim-Programm bestehen. |
| **8. Abschluss und Dokumentation** | Bedienung, Schaltplanarchitektur und automatisierte Regressionstests vervollständigen. | Ein frischer Checkout kann die dokumentierten Prüfungen reproduzieren. |

## Abhängigkeiten und Reihenfolge

AP 1 ist die gemeinsame Schnittstelle aller folgenden Pakete. AP 2 und AP 3
können danach getrennt entwickelt werden; AP 4 benötigt beide. AP 5 friert den
Kern als Integrationsbasis ein, bevor AP 6 den Befehlssatz verbreitert. Das
binäre Format in AP 7 kommt bewusst spät, damit frühe Schaltungsänderungen
keine dauerhaft inkompatiblen Opcodes erzeugen.

## Stand

- [x] **AP 1:** `hardware/logisim/tinycpu-16-12.json` beschreibt den Vertrag;
  `tiny_cpu_circuit.py --profile … --contract-only` prüft ihn unabhängig von
  der noch fehlenden Verdrahtung.
- [x] **AP 2:** Daten- und Adresspfad; `Datapath` lädt Akkumulator und
  Valid-Bit an derselben Taktflanke und leitet `ZERO`/`NEGATIVE` über einen
  vorzeichenbehafteten Vergleicher ab. `AddressPath` lädt Adressregister und
  Valid-Bit synchron und stellt die 12-Bit-Offset-Summe samt Carry bereit. Das
  Hardwareprofil und die Netlist-Tests frieren diese Schnittstellen ein.
- [x] **AP 3:** Speicher und Fehlerregister; Daten- und Valid-RAM teilen sich
  Adresse, Write-Enable und Takt. Sechs set-dominante Sticky-Flags implementieren
  `SET OR (Q AND NOT CLEAR_ERROR)` und exportieren ihren Zustand.
- [x] **AP 4:** Fetch und Decode; ein 12-Bit-PC adressiert das interne ROM,
  `CORE_DECODER` erzeugt die Steuersignale des Kernbefehlssatzes und
  `PC_RANGE` setzt bei einem PC außerhalb `PROGRAM_LIMIT` gleichzeitig `ADDR`
  und `HALT_ERROR`. Die Taktabläufe und das vorläufige interne ROM-Wort sind
  in `hardware/logisim/README.md` dokumentiert und im Hardwareprofil fixiert.
- [ ] **AP 5:** Kernprogramm integrieren
- [ ] **AP 6:** ISA vervollständigen
- [ ] **AP 7:** Maschinenformat und Tooling
- [ ] **AP 8:** Abschluss und Dokumentation
