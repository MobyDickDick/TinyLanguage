"""Tests for objects."""

def test_class_operator_overloads_with_numbers(run_tiny_source):
    """Test that class operator overloads with numbers."""
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

    def _unused1 = tag(5, "number");
    def _unused2 = tag(20, "number");
    def _unused3 = tag(3, "number");

    def base = Counter(10, "base");

    def added_right = base + 5;
    def added_left = 5 + base;

    def sub_right = base - 3;
    def sub_left = 20 - base;

    print(added_right.total);
    print(added_right.tag);
    print(added_left.total);
    print(added_left.tag);
    print(sub_right.total);
    print(sub_right.tag);
    print(sub_left.total);
    print(sub_left.tag);

    def same_value_and_tag = Counter(15, "base+n");
    def same_value_diff_tag = Counter(15, "other");
    def diff_value = Counter(14, "base+n");

    print(added_right == same_value_and_tag);
    print(added_right == same_value_diff_tag);
    print(added_right == diff_value);
    """

    out = run_tiny_source(src)

    assert out == "15\nbase+n\n15\nn+base\n7\nbase-n\n10\nn-base\ntrue\nfalse\nfalse\n"
