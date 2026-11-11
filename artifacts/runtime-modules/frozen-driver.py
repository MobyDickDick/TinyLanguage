import hashlib, json, os, subprocess
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
root = Path.cwd()
binary = root / 'dist/module-frozen/tiny-language.exe'
work = Path(os.environ['TEMP']) / 'frozen-acceptance'
work.mkdir(parents=True, exist_ok=True)
assert not work.is_relative_to(root)
program = work / 'main.tiny'
program.write_text('import stdlib.math as m; print(m.sqrt(81));', encoding='utf-8')
env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'PYTHONHOME', 'TINYPATH'}}
checks = []
def run(args, expected, extra=None):
    result = subprocess.run([str(binary), *args], cwd=work, env={**env, **(extra or {})}, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == expected, result.stdout
    checks.append({'argv': args, 'environment': extra or {}, 'exit_code': result.returncode, 'stdout': result.stdout})
run(['--version'], 'TinyLanguage 1.0.0')
run([str(program)], '9')
program.write_text('print(6 * 7);', encoding='utf-8')
run(['--native-backend', str(program)], '42')
run(['--backend', 'python', str(program)], '42')
run([str(program)], '42', {'TINYLANG_USE_TINY_PARSER': '1'})
archive = CArchiveReader(binary)
assert not any(name.endswith('.py') for name in archive.toc), list(archive.toc)
report = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'working_directory': str(work), 'outside_checkout': True, 'loose_python_sources': False, 'commands': checks}
(root / 'artifacts/runtime-modules/frozen-acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
