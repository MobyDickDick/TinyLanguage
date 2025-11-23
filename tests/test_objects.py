import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def test_class_operator_overloads_with_numbers():
    src = """
    class Counter {
        total: number;
        tag: string;
    }

    fn Counter(value, name) {
        return new Counter { total: value; tag: name; };
    }

    operator + (a: Counter, b: number) -> Counter { return Counter(a.total + b, a.tag + "+n"); }
    operator + (a: number, b: Counter) -> Counter { return Counter(a + b.total, "n+" + b.tag); }
    operator - (a: Counter, b: number) -> Counter { return Counter(a.total - b, a.tag + "-n"); }
    operator - (a: number, b: Counter) -> Counter { return Counter(a - b.total, "n-" + b.tag); }
    operator == (a: Counter, b: Counter) -> bool { return a.total == b.total and a.tag == b.tag; }

    tag(5, "number");
    tag(20, "number");
    tag(3, "number");

    define base = Counter(10, "base");

    define added_right = base + 5;
    define added_left = 5 + base;

    define sub_right = base - 3;
    define sub_left = 20 - base;

    print(added_right.total);
    print(added_right.tag);
    print(added_left.total);
    print(added_left.tag);
    print(sub_right.total);
    print(sub_right.tag);
    print(sub_left.total);
    print(sub_left.tag);

    define same_value_and_tag = Counter(15, "base+n");
    define same_value_diff_tag = Counter(15, "other");
    define diff_value = Counter(14, "base+n");

    print(added_right == same_value_and_tag);
    print(added_right == same_value_diff_tag);
    print(added_right == diff_value);
    """

    out = run_tiny(src)

    assert out == "15\nbase+n\n15\nn+base\n7\nbase-n\n10\nn-base\ntrue\nfalse\nfalse\n"
