# Standard library examples

Each section below contains a TinyLanguage example for a stdlib module plus the
exact output it produces. The tests in `tests/detailtests/test_stdlib_doc_examples.py`
execute every `tiny` snippet and compare stdout with the matching `text` block.

## stdlib.argparse

```tiny
import stdlib.argparse;

def args = new["--count", "2", "input.txt"];
def flags = new[
  { name: "count", long: "count", takes_value: true, default_value: "1" }
];
def positionals = new[
  { name: "input", required: true }
];
def spec = { flags: flags, positionals: positionals };

def parsed = argparse.parse(args, spec);
print(Map.get(parsed, "count"));
print(Map.get(parsed, "input"));
def _cleanup_parsed = delete(parsed);
def _cleanup_args = delete(args);
def _cleanup_flags = delete(flags);
def _cleanup_positionals = delete(positionals);
```

```text
2
input.txt
```

## stdlib.collections

```tiny
import stdlib.collections;

def _unused = collections;
def nums = new[1, 2, 3];
print(Collections.len(nums));
print(Collections.contains(nums, 2));
def _cleanup_nums = delete(nums);
```

```text
3
true
```

## stdlib.csv

```tiny
import stdlib.csv;

def rows = csv.parse_with_header("name,score\nAda,10");
def first = heap_get(rows, 0);
print(Map.get(first, "name", ""));
print(Map.get(first, "score", ""));
def _cleanup_first = delete(first);
def _cleanup_rows = delete(rows);
```

```text
Ada
10
```

## stdlib.datetime

```tiny
import stdlib.datetime;

print(datetime.date_isoformat(2025, 1, 2));
```

```text
2025-01-02
```

## stdlib.fswatch

```tiny
import stdlib.fswatch;

def res = fswatch.watch("mock://events", Null);

def rendered = match(res) {
  case Ok { value: watch } => Collections.len(watch.events);
  case Err { code: code, message: message } => code;
};

print(rendered);
def _cleanup = match(res) {
  case Ok { value: watch } => delete(watch.events);
  case Err { code: code, message: message } => Null;
};
```

```text
2
```

## stdlib.http

```tiny
import stdlib.http;

def res = http.get("mock://ok", Null);

def rendered = match(res) {
  case Ok { value: response } => response.status;
  case Err { code: code, message: message } => code;
};

print(rendered);
```

```text
200
```

## stdlib.io

```tiny
import stdlib.io;

def _unused = io;
print(File.exists("README.md"));
```

```text
true
```

## stdlib.json

```tiny
import stdlib.json;

def value = json.parse("{\"ok\":true}");
print(Map.get(value, "ok", false));
print(json.stringify(value));
```

```text
true
{"ok":true}
```

## stdlib.logging

```tiny
import stdlib.logging;

print(logging.format("info", "hello", Null, "2025-01-01T00:00:00Z"));
```

```text
{"level":"info","message":"hello","timestamp":"2025-01-01T00:00:00Z"}
```

## stdlib.math

```tiny
import stdlib.math;

print(math.max(3, 5));
```

```text
5
```

## stdlib.os

```tiny
import stdlib.os;

print(os.path.join("docs", "stdlib_examples.md"));
```

```text
docs/stdlib_examples.md
```

## stdlib.path

```tiny
import stdlib.path;

print(path.normalize("/tmp//demo/../file.txt"));
```

```text
/tmp/file.txt
```

## stdlib.pathlib

```tiny
import stdlib.os;
import stdlib.pathlib;

def _unused = os;
def path = pathlib.Path("docs/stdlib_examples.md");
print(path.name());
```

```text
stdlib_examples.md
```

## stdlib.process

```tiny
import stdlib.process;

def args = new[];
def res = process.run("mock://exit/0", args, Null);

def rendered = match(res) {
  case Ok { value: result } => result.exit_code;
  case Err { code: code, message: message } => code;
};

print(rendered);
def _cleanup_args = delete(args);
```

```text
0
```

## stdlib.random

```tiny
import stdlib.random;

def choices = new["only"];
def choice = random.choice(choices);
print(choice);
def _cleanup_choices = delete(choices);
```

```text
only
```

## stdlib.regex

```tiny
import stdlib.regex;

print(regex.replace("a+", "caaat", "a"));
```

```text
cat
```

## stdlib.statistics

```tiny
import stdlib.statistics;

def values = new[2, 4, 6];
print(statistics.mean(values));
def _cleanup_values = delete(values);
```

```text
4.0
```

## stdlib.string

```tiny
import stdlib.string;

print(string.upper("tiny"));
print(string.replace("a-b", "-", "_"));
```

```text
TINY
a_b
```

## stdlib.time

```tiny
import stdlib.time;

print(time.sleep_ms(0) >= 0);
```

```text
true
```

## stdlib.yaml

```tiny
import stdlib.yaml;

def _unused = yaml;
try {
  def _value = yaml.parse("key: value");
} catch (err) {
  def _ignored = err;
  print("not implemented");
}
```

```text
not implemented
```
