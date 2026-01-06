"""Inheritance walkthrough distilled from `all_features.tiny`'s counter classes.

This covers method overriding, base-field assignments and method calls on derived
instances to ensure the runtime respects the class hierarchy.
"""

from tests.utils import run_tiny


def test_counter_and_fancy_counter_hierarchy():
    out = run_tiny(
        """
        class Counter {
          value: number;
          label: string;

          fn init(self, start, label) {
            self.value = start;
            self.label = label;
            return self;
          }

          fn bump(self, delta) {
            self.value = self.value + delta;
            return self;
          }

          fn read(self) { return self.value; }
        }

        class FancyCounter: Counter {
          bonus: number;

          fn init(self, start, label, bonus) {
            Counter.value = start;
            self.label = label;
            self.bonus = bonus;
            return self;
          }

          fn bump(self, delta) {
            self.value = self.value + delta;
            return self;
          }

          fn total(self) { return Counter.value + self.bonus; }
        }

        def fc = new FancyCounter { bonus: 0; label: "temp"; value: 0; };
        fc = fc.init(3, "fancy", 7);
        fc = fc.bump(2);
        print(fc.total());
        print(fc.read());
        """
    )

    assert out == "12\n5\n"
