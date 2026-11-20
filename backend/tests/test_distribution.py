from app.services.distribution import equal_split, scale_to_total


def test_equal_split_sums_to_100():
    assert equal_split(3) == [34, 33, 33]
    assert sum(equal_split(7)) == 100


def test_scale_to_total():
    assert scale_to_total([50, 25]) == [67, 33]
    assert scale_to_total([0, 0]) == [50, 50]
    assert sum(scale_to_total([13, 29, 41])) == 100
