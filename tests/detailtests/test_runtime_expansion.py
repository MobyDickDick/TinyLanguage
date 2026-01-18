import re


def test_nested_arrays_roundtrip(run_tiny_source):
    out = run_tiny_source(
        """
def nested = new[new[1, 2], new[3, 4], new[5, 6]];
print(heap_get(heap_get(nested, 0), 1));
print(heap_get(heap_get(nested, 1), 0));
print(heap_get(heap_get(nested, 2), 1));
""".strip()
    )

    assert out.strip().splitlines() == ["2", "3", "6"]


def test_nested_arrays_three_levels(run_tiny_source):
    out = run_tiny_source(
        """
def nested = new[
    new[1, new[2, 3]],
    new[new[4], 5],
    new[new[6, 7], new[8, 9]]
];
print(heap_get(heap_get(heap_get(nested, 0), 1), 0));
print(heap_get(heap_get(heap_get(nested, 1), 0), 0));
print(heap_get(heap_get(heap_get(nested, 2), 1), 1));
""".strip()
    )

    assert out.strip().splitlines() == ["2", "4", "9"]


def test_repeated_new_delete_pairs(run_tiny_source):
    out = run_tiny_source(
        """
def total = 0;
def i = 0;
while (i < 5) {
    def ptr = new(1);
    def ignored1 = heap_set(ptr, 0, i);
    total = total + heap_get(ptr, 0);
    def _unused8 = delete(ptr);
    i = i + 1;
}
print(total);
""".strip()
    )

    assert out.strip() == "10"


def test_many_new_delete_pairs(run_tiny_source):
    out = run_tiny_source(
        """
def total = 0;
def i = 0;
while (i < 20) {
    def ptr = new(1);
    def ignored1 = heap_set(ptr, 0, i);
    total = total + heap_get(ptr, 0);
    def _unused11 = delete(ptr);
    i = i + 1;
}
print(total);
""".strip()
    )

    assert out.strip() == "190"


def test_deep_recursion_sum(run_tiny_source):
    out = run_tiny_source(
        """
fn sum(n) {
    if (n == 0) {
        return 0;
    }
    return n + sum(n - 1);
}

print(sum(25));
""".strip()
    )

    assert out.strip() == "325"


def test_deeper_recursion_sum(run_tiny_source):
    out = run_tiny_source(
        """
fn sum(n) {
    if (n == 0) {
        return 0;
    }
    return n + sum(n - 1);
}

print(sum(50));
""".strip()
    )

    assert out.strip() == "1275"


def test_heap_api_error_scenarios(run_tiny_source, monkeypatch):
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny_source(
        """
def ptr = new(2);
def ignored1 = heap_set(ptr, 0, 10);
def ignored2 = heap_set(ptr, 5, 99);
print(errorMessage);
def _unused1 = delete(ptr);
def _unused2 = delete(ptr);
print(errorMessage);
def ignored3 = heap_get(42, 0);
print(errorMessage);
""".strip()
    )

    assert re.search(r"heap access error: index 5 out of range for pointer 1", out)
    assert re.search(r"heap delete error: pointer 1 was already freed", out)
    assert re.search(r"heap access error: unknown pointer 42", out)
