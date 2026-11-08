import json, os, sys
from pathlib import Path
root = Path.cwd()
work = Path(r'C:\Users\marku\.codex\visualizations\2026\11\08\01a1ba44-4dd4-7393-b12f-df861396a142\runtime-validation\frozen-acceptance')
os.chdir(work)
sys.path.insert(0, str(root))
import tiny_language as facade
import tiny_language_api as api
import tiny_language_ast as nodes
import tiny_language_runtime as runtime
assert Path(facade.__file__) == root / 'tiny_language.py'
assert facade.compile_and_run is api.compile_and_run
assert facade.Runtime is runtime.Runtime
assert facade.Fn is nodes.Fn
assert facade.__all__ == api.__all__
assert facade.compile_and_run('print(6 * 7);', stream_output=False).strip() == '42'
report = {'wrapper': str(Path(facade.__file__)), 'outside_working_directory': str(work), 'canonical_identity': True, 'public_exports': facade.__all__, 'output': '42'}
(root / 'artifacts/runtime-modules/root-wrapper.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
