"""Traffic share helpers. Keitaro expects integer shares; active offers of a stream must total 100%."""


def equal_split(count: int, total: int = 100) -> list[int]:
    if count <= 0:
        return []
    base, remainder = divmod(total, count)
    return [base + (1 if i < remainder else 0) for i in range(count)]


def scale_to_total(values: list[int], total: int = 100) -> list[int]:
    """Proportionally rescale integer values so that they sum to ``total`` (largest remainder method)."""
    if not values:
        return []
    current = sum(values)
    if current <= 0:
        return equal_split(len(values), total)
    raw = [v * total / current for v in values]
    result = [int(r) for r in raw]
    missing = total - sum(result)
    order = sorted(range(len(values)), key=lambda i: raw[i] - result[i], reverse=True)
    for i in order[:missing]:
        result[i] += 1
    return result
