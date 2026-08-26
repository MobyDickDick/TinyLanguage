# TinyCPU-Operationsarchitektur

Dieses Dokument war ursprünglich eine ALU-Skizze für einen Zwischenstand.
Die darin vorgeschlagene Umstellung auf ein 24-Bit-Instruktionswort und einen
8-Bit-Opcode wurde **nicht** Teil der TinyCPU. Maßgeblich sind heute das
versionierte Maschinenformat und die gewartete Logisim-Schaltung.

## Verbindliche Breiten

- Daten und Rechenwerte: 16 Bit im Zweierkomplement.
- Speicher: 4096 Zellen mit 12 wirksamen Adressbits.
- Maschinenwort: 22 Bit, aufgeteilt in `OPCODE[21:16]` und
  `OPERAND[15:0]`.
- Opcode: 6 Bit. Die konkrete Zuordnung steht ausschließlich in
  `hardware/logisim/tinycpu-machine-v1.json`.

Eine Verbreiterung ist kein ausstehendes Arbeitspaket. Sie würde eine neue
Version des Maschinenformats, Encoder- und Decoderänderungen sowie neue
elektrische Abnahmen erfordern.

## Umgesetzte Rechengrenze

Statt eines einzelnen, noch anzulegenden `ALU`-Blatts kapselt das gewartete
Blatt `Operations` die binären Befehlsfamilien. Je ein Unterblatt für `ADD`,
`SUB`, `MUL`, `DIV`, `AND`, `OR` und `XOR` wählt seine vier Adressierungsarten
aus. `NOT` besitzt einen eigenen unären Pfad. Die Zweige liefern neutrale
Ausgänge, solange sie inaktiv sind; `Operations` führt Ergebnis, Validität,
Overflow, Division-durch-null und ungültige Operanden zusammen.

```text
ACC, OPERAND, MEMORY, VALIDITY, DECODE CONTROLS
                         |
       +-----------------+-----------------+
       | ADD/SUB/MUL/DIV | AND/OR/XOR      | NOT
       +-----------------+-----------------+
                         |
          RESULT / RESULT_VALID / ERRORS
                         |
                    Datapath.ACC
```

`ZERO` und `NEGATIVE` werden am Akkumulator im Blatt `Datapath` abgeleitet.
Sticky-Fehlerzustände speichert `ErrorFlags`; sie gehören daher nicht als
Register in eine separate ALU. Diese Aufteilung entspricht der Schaltung, dem
Hardwareprofil und den AP-11/AP-12-Traces.

## Status und Änderungsregel

Die Rechenpfade und das 22-Bit-Maschinenformat sind integriert und elektrisch
abgenommen. Es gibt aus dieser historischen Skizze **kein offenes
Folgepaket**. Neue TinyCPU-Arbeit muss zuerst mit eigenem Umfang und
Abnahmekriterien in `docs/open_tasks.md` festgelegt werden; sie darf nicht aus
dem früheren ALU-Vorschlag abgeleitet werden.
