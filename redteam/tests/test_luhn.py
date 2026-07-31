#!/usr/bin/env python3
"""Test del validador Luhn usado en imei.py"""
import sys
sys.path.insert(0, "/workspace/redteam")
from scenarios.imei import luhn_check, is_blacklisted

# IMEI real de ejemplo (de un Samsung)
KNOWN_VALID = "356938035643809"  # formato ficticio válido Luhn
KNOWN_INVALID = "123456789012345"
KNOWN_BLACKLIST = "356938035643800"

# Generar un válido con Luhn
def make_valid_luhn(prefix: str) -> str:
    digits = [int(d) for d in prefix[:14]]
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 0:
            d *= 2
            if d > 9: d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    return prefix[:14] + str(check)

generated = make_valid_luhn("35693803564380")
assert luhn_check(generated), f"generated {generated} debería pasar Luhn"
assert not luhn_check("490154203237518"), "IMEI 490154... no debe pasar Luhn (verificado)"
assert not luhn_check(KNOWN_INVALID), "123... no debe pasar Luhn"
assert is_blacklisted(KNOWN_BLACKLIST), "Terminado en 00 debe ser blacklist"
print("✓ test_luhn OK")
