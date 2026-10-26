import pytest

from etl.address import a2_key


@pytest.mark.parametrize("args, key", [
    (("1", "Example Street", "11201"), "1 EXAMPLE ST 11201"),
    (("1", "EXAMPLE ST.", "11201-1234"), "1 EXAMPLE ST 11201"),
    (("224", "54  Street", "11220"), "224 54 ST 11220"),
    (("5413", "7 Avenue", "11220"), "5413 7 AVE 11220"),
])
def test_a2_key(args, key):
    assert a2_key(*args) == key
