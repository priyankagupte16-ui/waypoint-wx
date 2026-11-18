def to_out(c, unit: str):
    if c is None:
        return None
    if unit == "fahrenheit":
        return round(c * 9 / 5 + 32, 1)
    return round(float(c), 1)


def mm_out(mm, unit: str):
    if mm is None:
        return None
    if unit == "fahrenheit":
        return round(mm / 25.4, 2)
    return round(float(mm), 2)


def unit_labels(unit: str):
    if unit == "fahrenheit":
        return {"temp": "F", "precip": "in"}
    return {"temp": "C", "precip": "mm"}
