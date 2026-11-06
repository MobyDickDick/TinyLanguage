"""Contract-derived examples for the independent correctness audit.

Expected values never come from a Tiny backend. Arithmetic uses Fraction;
the remaining examples state a small semantic derivation in ``basis``.
"""

from dataclasses import dataclass
from fractions import Fraction
import random


BACKENDS = ("interpreter", "native", "llvm", "c")
RICH = BACKENDS[:-1]


@dataclass(frozen=True)
class Case:
    name: str
    features: tuple[str, ...]
    source: str
    expected: str
    basis: str
    backends: tuple[str, ...] = BACKENDS
    error: str = ""
    error_stage: str = "execute"
    copy_on_call: bool = False
    file_context: bool = False


def arithmetic_case() -> Case:
    """Generate 160 exact results, all small and exactly binary-representable."""
    rng = random.Random(90210)
    source, expected = [], []
    for _ in range(40):
        a, b = rng.randint(-100, 100), 2 ** rng.randrange(0, 5)
        for op, value in (("+", Fraction(a) + b), ("-", Fraction(a) - b),
                          ("*", Fraction(a) * b), ("/", Fraction(a, b))):
            source.append(f"print({a} {op} {b});")
            expected.append(str(float(value)) if value.denominator != 1 else str(value.numerator))
    return Case("exact-arithmetic", ("arithmetic",), "\n".join(source),
                "\n".join(expected) + "\n",
                "Fraction(a,b), seed 90210: 40 integer pairs, + - * /; divisors are powers of two. "
                "Compare exact rational values of decimal output, without rounding tolerances.")


def comparison_case() -> Case:
    """Enumerate all six comparison relations, including equality and negative values."""
    relations = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b,
                 "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
                 ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
    source, expected = [], []
    for a in (-2, 0, 3):
        for b in (-2, 0, 3):
            for op, relation in relations.items():
                source.append(f"if ({a} {op} {b}) {{ print(1); }} else {{ print(0); }}")
                expected.append(str(int(relation(Fraction(a), Fraction(b)))))
    return Case("comparison-relations", ("comparisons",), "\n".join(source),
                "\n".join(expected) + "\n", "54 exact order/equality relations over {-2,0,3}, "
                "derived independently with Fraction; branch output avoids backend boolean rendering differences.")


CASES = (
    arithmetic_case(),
    comparison_case(),
    Case("integer-boundary", ("integer-boundary",),
         "print(9007199254740993); print(2147483647+1);",
         "9007199254740993\n2147483648\n", "Exact integer literals and addition: 2^53+1, 2^31. "
         "Neither the binary64 mantissa boundary nor a host C long may silently alter values."),
    Case("literals", ("literals", "print"), 'print(42); print("Tiny"); print(true); print(false); print(Null);',
         "42\nTiny\ntrue\nfalse\nNull\n", "Literal spelling and print contract: language_spec.md, Literals."),
    Case("control-flow", ("variables", "comparisons", "if", "while"),
         "def n = 0; def total = 0; while (n < 5) { if (n == 3) { total = total + 10; } "
         "else { total = total + n; } n = n + 1; } print(total);",
         "17\n", "0+1+2+10+4 = 17; assignments persist across loop iterations."),
    Case("recursion", ("functions", "recursion"),
         "fn fact(n) { if (n < 2) { return 1; } return n * fact(n - 1); } print(fact(6));",
         "720\n", "Induction: fact(1)=1; fact(n)=n*fact(n-1); 6!=720."),
    Case("evaluation-order", ("evaluation-order",),
         'fn mark(n) { print(n); return n; } fn add(a,b) { return a+b; } '
         'print(add(mark(1),mark(2))); print(mark(3)+mark(4)*mark(5));',
         "1\n2\n3\n3\n4\n5\n23\n", "Left-to-right calls and operands; 1+2=3, 3+4*5=23. language_spec.md, Evaluation order."),
    Case("short-circuit", ("short-circuit",),
         'fn effect() { print("unexpected"); return true; } '
         'def a = false && effect(); def b = true || effect(); if (a) { print(99); } if (b) { print(7); }',
         "7\n", "false && rhs and true || rhs never evaluate rhs; only b's branch runs."),
    Case("heap", ("heap", "arrays", "ownership"),
         "def p = new[11,22]; def ignored = heap_set(p,1,33); print(heap_get(p,0)); "
         "print(heap_get(p,1)); def ignored_delete = delete(p);",
         "11\n33\n", "Two owned slots; write changes only slot 1; owner deletes allocation.", RICH),
    Case("heap-length", ("heap-length",),
         "def p = new[11,22]; print(len(p)); def ignored_delete = delete(p);",
         "2\n", "A two-slot allocation has length 2. language_spec.md, Arrays and heap.", RICH),
    Case("borrow-mutation", ("aliasing",),
         "fn write(p) { def ignored = heap_set(p,0,19); return heap_get(p,0); } "
         "def p = new[7]; print(write(p)); print(heap_get(p,0)); def ignored_delete = delete(p);",
         "19\n19\n", "Default calls borrow identity: write through the parameter changes caller slot. copy_on_call_contract.md.", RICH),
    Case("copy-isolation", ("copy-on-call",),
         "fn write(p) { def ignored = heap_set(p,0,19); return len(p); } "
         "def p = new[7]; print(write(p)); print(heap_get(p,0)); def ignored_delete = delete(p);",
         "1\n7\n", "Opt-in isolation: scalar return cannot grant mutation of caller storage. copy_on_call_contract.md.",
         ("interpreter",), copy_on_call=True),
    Case("class-method", ("classes",),
         "class Box { value: number; fn add(self,n) { self.value = self.value+n; return self.value; } } "
         "def box = new Box { value: 8 }; print(box.add(3)); print(box.value);",
         "11\n11\n", "Method receiver retains identity; adding 3 to field 8 updates field to 11.", RICH),
    Case("operator", ("operators",),
         "class Box { value: number; } operator + (a: Box,b: Box) -> number { return a.value+b.value; } "
         "def a = new Box { value: 2 }; def b = new Box { value: 5 }; print(a+b);",
         "7\n", "The declared overload adds fields 2+5=7.", RICH),
    Case("match", ("adt",),
         "type Choice { One { value: number }; Two { value: number }; } "
         "fn value(x) { return match x { case One { value: n }: n; case Two { value: n }: n*2; }; } "
         "print(value(One { value: 3 })); print(value(Two { value: 4 }));",
         "3\n8\n", "Tag selects arm; One returns 3; Two doubles 4.", RICH),
    Case("collections", ("collections",),
         "def m = Map.new(); def ignored_map = Map.set(m,1,2); print(Map.get(m,1,0)); "
         "def s = Set.new(); def ignored_set = Set.add(s,5); if (Set.has(s,5)) { print(5); } "
         "def q = Deque.new(); def ignored_push = Deque.push_right(q,9); print(Deque.pop_left(q));",
         "2\n5\n9\n", "Map lookup of assigned key; set membership after add; FIFO singleton deque.", RICH),
    Case("spawn-join", ("concurrency",),
         "fn add(a,b) { return a+b; } def task = spawn add(2,3); print(join(task));",
         "5\n", "Joining a worker observes its completed sum 2+3; does not establish parallel scheduling.", RICH),
    Case("tokens", ("tokens",),
         'def token = Async.token(); def ignored_cancel = Async.cancel(token,"stop"); '
         'if (Async.is_cancelled(token)) { print(7); } print(Async.reason(token));',
         "7\nstop\n", "Cancel sets token state and preserves the supplied reason; no scheduling claim.", RICH),
    Case("imports", ("imports",),
         'import audit_helper; print(audit_helper.twice(6));',
         "12\n", "Separate module defines twice(n)=n*2; 6*2=12.", RICH, file_context=True),
    Case("file-builtins", ("file-builtins",),
         "def p = new[7]; def ignored = heap_set(p,0,9); print(heap_get(p,0)); def ignored_delete = delete(p);",
         "9\n", "File/module context cannot change builtin heap_set/get/delete resolution.",
         RICH, file_context=True),
    Case("python-interop", ("interop",),
         'def ignored_module = Python.import_module("math",new["sqrt"]); '
         'print(Python.call("math","sqrt",new[9]));',
         "3\n", "Positive square root of exact integer 9 is exactly 3.", RICH),
    Case("division-error", ("runtime-errors",), 'print(1 / 0); print("unreachable");',
         "", "Division by zero must fail before the following observable print.",
         error="division by zero"),
    Case("arity-error", ("frontend-errors",),
         'fn add(a,b) { return a+b; } print(add(1)); print("unreachable");',
         "", "E009: two parameters require two arguments; rejection occurs before execution.",
         error="E009", error_stage="frontend"),
    Case("heap-error-status", ("ownership-errors",),
         "fn release(p) { return delete(p); } fn store(p) { return heap_set(p,0,42); } "
         "def p = new(1); def first = release(p); print(first.e.code); "
         "def second = release(p); print(second.e.code); def write = store(p); print(write.e.code);",
         "0\n1\n1\n", "Heap result contract: initial delete succeeds (0); double delete and writing "
         "freed storage return error records (1). These operations record errors instead of throwing. "
         "heap_usage_guidelines.md, Runtime heap failure results.", RICH),
)
