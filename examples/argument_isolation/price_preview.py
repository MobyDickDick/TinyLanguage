"""Working Python baselines for speculative price previews.

The flat prices have immutable leaves: list.copy is sufficient here. Deepcopy
is included for comparison, not as a required or preferred implementation.
"""

from copy import deepcopy


def preview(prices, strategy):
    """Return a preview using the selected explicit isolation boundary."""
    if strategy == "rebuild":
        return [price + 0.5 for price in prices]
    if strategy == "deepcopy":
        prices = deepcopy(prices)
    elif strategy == "shallow":
        prices = prices.copy()
    elif strategy != "shared":
        raise ValueError(f"Unknown strategy: {strategy}")
    for index in range(len(prices)):
        prices[index] += 0.5
    return prices


def run(size, rounds, strategy):
    """Return preview totals, preservation status, and final original total."""
    original = [1000.25 + index for index in range(size)]
    totals = []
    unchanged = True
    for _ in range(rounds):
        trial = preview(original, strategy)
        total = 0
        for index in range(size):
            total += trial[index]
            if original[index] != 1000.25 + index:
                unchanged = False
        totals.append(str(float(total)))
    return "\n".join([*totals, str(unchanged).lower(), str(float(sum(original)))]) + "\n"


def main():
    """Run a standalone baseline with the same defaults as the Tiny example."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--strategy", choices=["deepcopy", "shallow", "rebuild", "shared"],
                        default="deepcopy")
    args = parser.parse_args()
    if min(args.size, args.rounds) < 1:
        parser.error("size and rounds must be positive")
    print(run(args.size, args.rounds, args.strategy), end="")


if __name__ == "__main__":
    main()
