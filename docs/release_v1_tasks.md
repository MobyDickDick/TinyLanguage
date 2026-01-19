# TinyLanguage v1.0 Aufgabenliste (Issue-Backlog)

Diese Datei dokumentiert die priorisierte Aufgabenliste für einen v1.0-Release.
Sie basiert auf den Roadmap-Bereichen (Frontend/Language, Typdisziplin, Runtime,
Tooling, Native Backends) sowie den Validierungszielen aus dem
Self-Hosting-Port-Plan.

## A. Release-Grundlagen (Scope & DoD)

1. **v1.0-DoD dokumentieren (Release-Kriterien)**
   - **Beschreibung:** Definiere klar, wann TinyLanguage als „v1.0-vollständig“ gilt.
   - **DoD:** Dokument enthält klare Kriterien zu Diagnostics, Typdisziplin,
     Runtime-Sicherheit, Tooling, Backend-Scope.

2. **Spec Freeze-Scope festlegen**
   - **Beschreibung:** Festlegen, welche Syntax/Features im v1.0-Release stabil bleiben.
   - **DoD:** Abschnitt im Release-Dokument, der Syntaxänderungen für v1.0 ausschließt.

## B. Diagnostics & Language Core

3. **Source-Span/Position-Konsistenz prüfen**
   - **Beschreibung:** Fehlerdiagnosen über Parser/Linter/Runtime konsistent machen.
   - **DoD:** Tests decken line/column-Genauigkeit in allen Fehlerpfaden ab.

4. **Einheitliches Fehlerformat definieren**
   - **Beschreibung:** Einheitliche Fehlerklassen/Format (Parser, Linter, Runtime).
   - **DoD:** Dokumentiertes Fehlerformat + Regression-Tests.

## C. Typdisziplin v1

5. **Regeln für Typwechsel finalisieren**
   - **Beschreibung:** Explizite Regeln für Typänderungen festlegen.
   - **DoD:** Dokumentation + Tests für erlaubte/unerlaubte Typwechsel.

6. **Optionale Typinferenz definieren (Scope)**
   - **Beschreibung:** Festlegen, ob „simple type inference“ Teil v1.0 ist.
   - **DoD:** Klarer Scope („in v1.0“ oder „post-v1.0“) dokumentiert.

## D. Runtime-Sicherheit (Heap/API)

7. **Heap-Diagnostik vollständige Abdeckung**
   - **Beschreibung:** invalid pointer, out-of-bounds, double delete, leak tracking.
   - **DoD:** Tests für alle Fehlerfälle; Diagnosen konsistent.

8. **Heap-Regression-Tests erweitern**
   - **Beschreibung:** Testfälle für nested arrays, deep recursion, OOB.
   - **DoD:** Erweiterte Regression-Suite mit stabiler Fehlermeldung.

## E. Tooling & Developer Experience

9. **CLI-Workflows stabilisieren**
   - **Beschreibung:** Interpreter/Native-CLI konsistent dokumentiert.
   - **DoD:** CLI-Guide aktualisiert + Smoke-Tests für Standard-Flows.

10. **Formatter/Lint-Workflows definieren**
    - **Beschreibung:** Standard-Lintprofile, Formatter-Workflow, CI-Checks.
    - **DoD:** Dokumentation + CI-Checks definiert.

11. **LSP-Workflows als CI-Gate**
    - **Beschreibung:** LSP-Tests (hover/completion/diagnostics) fixieren.
    - **DoD:** Tests laufen zuverlässig in CI.

## F. Backend-Parity & Release Candidate

12. **Interpreter als „golden path“**
    - **Beschreibung:** Interpreter-Parität als harte Voraussetzung für v1.0.
    - **DoD:** Parity-Tests in CI verpflichtend.

13. **C-Backend stabilisieren (Feature-Subset)**
    - **Beschreibung:** Dokumentiere unterstützten Feature-Subset.
    - **DoD:** Dokumentation + Feature-Matrix aktualisiert.

14. **LLVM-Backend klar als experimentell markieren**
    - **Beschreibung:** Eindeutige Dokumentation + Known Limitations.
    - **DoD:** LLVM-Scope explizit „non-blocking“ für v1.0.

## G. Release & Stabilisierung

15. **Release-Notes + Breaking-Changes**
    - **Beschreibung:** Zusammenfassung finaler API-/Syntax-Änderungen.
    - **DoD:** Release-Notes enthalten Breaking Changes + Known Limitations.

16. **Finaler Regression-Run (RC)**
    - **Beschreibung:** Voller Test-Run (Interpreter + Native + LSP).
    - **DoD:** Alle Gates grün, v1.0-Release freigegeben.
