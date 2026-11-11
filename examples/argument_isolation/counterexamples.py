"""Executable boundaries of the copy-on-call ergonomics hypothesis."""

from copy import deepcopy

BOX = """
class Box {
    price: number;
    fn bump(self) { self.price = self.price + 0.5; return self; }
}
def original = new Box { price: 1000.25; };
"""

GLOBAL_ALIAS = BOX + """
fn preview(box) {
    original.price = original.price + 0.5;
    return box;
}
def result = preview(original);
print(result.price);
"""

METHOD_RECEIVER = BOX + """
def result = original.bump();
print(original.price);
print(result.price);
"""

NESTED_CALL = BOX + """
fn inner(box) { box.price = box.price + 0.5; return box; }
fn outer(box) { def ignored = inner(box); return box; }
def result = outer(original);
print(original.price);
print(result.price);
"""

DISCARDED_HEAP = """
fn inspect(prices) { return len(prices); }
def original = new[1000.25];
print(inspect(original));
def ignored = delete(original);
"""


def python_global_alias():
    """An explicit copy does not prevent mutation through another alias."""
    original = {"price": 1000.25}

    def preview(box):
        """Mutate a captured original even though the parameter is copied."""
        box = deepcopy(box)
        original["price"] += 0.5
        return box

    result = preview(original)
    return [original["price"], result["price"]]


def python_nested(copy_inner):
    """One explicit outer copy differs from a copy at every call boundary."""
    original = {"price": 1000.25}

    def inner(box):
        """Optionally copy to reproduce the nested Tiny boundary."""
        if copy_inner:
            box = deepcopy(box)
        box["price"] += 0.5
        return box

    def outer(box):
        """Discard the helper's return, exposing the boundary difference."""
        box = deepcopy(box)
        inner(box)
        return box

    result = outer(original)
    return [original["price"], result["price"]]


def python_nested_rows(deep):
    """Shallow copying ceases to isolate when price rows become mutable."""
    original = [[1000.25]]
    result = deepcopy(original) if deep else original.copy()
    result[0][0] += 0.5
    return [original[0][0], result[0][0]]
