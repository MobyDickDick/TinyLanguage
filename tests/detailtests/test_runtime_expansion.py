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


def test_repeated_new_delete_pairs(run_tiny_source):
    out = run_tiny_source(
        """
def total = 0;
def i = 0;
while (i < 5) {
    def ptr = new(1);
    heap_set(ptr, 0, i);
    total = total + heap_get(ptr, 0);
    delete(ptr);
    i = i + 1;
}
print(total);
""".strip()
    )

    assert out.strip() == "10"


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
