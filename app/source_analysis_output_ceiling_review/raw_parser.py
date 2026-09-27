"""
Parseur JSON préfixe — forensics uniquement.

Aucune réparation. Aucune publication. Un préfixe invalide reste invalide.
Les objets incomplets ne sont pas complétés.
"""

from __future__ import annotations

from typing import Any


def skip_ws(text: str, index: int) -> int:
    length = len(text)
    while index < length and text[index] in " \t\r\n":
        index += 1
    return index


def parse_string(text: str, index: int) -> tuple[str, int] | None:
    if index >= len(text) or text[index] != '"':
        return None
    index += 1
    chars: list[str] = []
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            return "".join(chars), index + 1
        if char == "\\":
            if index + 1 >= length:
                return None
            escape = text[index + 1]
            mapping = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            if escape in mapping:
                chars.append(mapping[escape])
                index += 2
                continue
            if escape == "u":
                hex_digits = text[index + 2 : index + 6]
                if len(hex_digits) < 4:
                    return None
                try:
                    chars.append(chr(int(hex_digits, 16)))
                except ValueError:
                    return None
                index += 6
                continue
            return None
        chars.append(char)
        index += 1
    return None


def parse_number(text: str, index: int) -> tuple[int | float, int] | None:
    length = len(text)
    start = index
    if index < length and text[index] == "-":
        index += 1
    digits = 0
    while index < length and text[index].isdigit():
        index += 1
        digits += 1
    if digits == 0:
        return None
    if index < length and text[index] == ".":
        index += 1
        frac = 0
        while index < length and text[index].isdigit():
            index += 1
            frac += 1
        if frac == 0:
            return None
    if index < length and text[index] in "eE":
        index += 1
        if index < length and text[index] in "+-":
            index += 1
        exp = 0
        while index < length and text[index].isdigit():
            index += 1
            exp += 1
        if exp == 0:
            return None
    raw = text[start:index]
    if any(token in raw for token in (".", "e", "E")):
        return float(raw), index
    return int(raw), index


def parse_literal(text: str, index: int) -> tuple[Any, int] | None:
    for token, value in (("true", True), ("false", False), ("null", None)):
        if text.startswith(token, index):
            return value, index + len(token)
    return None


def parse_value(text: str, index: int) -> tuple[Any, int] | None:
    index = skip_ws(text, index)
    if index >= len(text):
        return None
    char = text[index]
    if char == '"':
        return parse_string(text, index)
    if char == "{":
        return parse_object(text, index)
    if char == "[":
        return parse_array(text, index)
    if char == "-" or char.isdigit():
        return parse_number(text, index)
    return parse_literal(text, index)


def parse_object(text: str, index: int) -> tuple[dict[str, Any], int] | None:
    if index >= len(text) or text[index] != "{":
        return None
    index = skip_ws(text, index + 1)
    result: dict[str, Any] = {}
    if index < len(text) and text[index] == "}":
        return result, index + 1
    while index < len(text):
        key_parsed = parse_string(text, skip_ws(text, index))
        if key_parsed is None:
            return None
        key, index = key_parsed
        index = skip_ws(text, index)
        if index >= len(text) or text[index] != ":":
            return None
        value_parsed = parse_value(text, index + 1)
        if value_parsed is None:
            return None
        value, index = value_parsed
        result[key] = value
        index = skip_ws(text, index)
        if index >= len(text):
            return None
        if text[index] == "}":
            return result, index + 1
        if text[index] != ",":
            return None
        index += 1
    return None


def parse_array(text: str, index: int) -> tuple[list[Any], int] | None:
    if index >= len(text) or text[index] != "[":
        return None
    index = skip_ws(text, index + 1)
    result: list[Any] = []
    if index < len(text) and text[index] == "]":
        return result, index + 1
    while index < len(text):
        value_parsed = parse_value(text, index)
        if value_parsed is None:
            return None
        value, index = value_parsed
        result.append(value)
        index = skip_ws(text, index)
        if index >= len(text):
            return None
        if text[index] == "]":
            return result, index + 1
        if text[index] != ",":
            return None
        index += 1
    return None


def extract_complete_array_items(text: str, index: int) -> tuple[list[Any], int, bool]:
    """
    Lit les éléments complets d'un array à partir de '['.

    Retourne (items_complets, index_après_dernier_item_complet, array_fermé).
    N'invente pas l'élément tronqué.
    """
    index = skip_ws(text, index)
    if index >= len(text) or text[index] != "[":
        return [], index, False
    index = skip_ws(text, index + 1)
    items: list[Any] = []
    if index < len(text) and text[index] == "]":
        return items, index + 1, True
    while index < len(text):
        value_parsed = parse_value(text, index)
        if value_parsed is None:
            return items, index, False
        value, index = value_parsed
        items.append(value)
        index = skip_ws(text, index)
        if index >= len(text):
            return items, index, False
        if text[index] == "]":
            return items, index + 1, True
        if text[index] != ",":
            return items, index, False
        index += 1
    return items, index, False


def extract_root_prefix(text: str) -> dict[str, Any]:
    """
    Extrait les paires racine dont la valeur est complète.

    `records` n'est jamais réparé : seuls les objets records complets
    sont listés. Le JSON reste invalide.
    """
    index = skip_ws(text, 0)
    if index >= len(text) or text[index] != "{":
        return {
            "starts_with_object": False,
            "root_keys_complete": [],
            "records_array_reached": False,
            "records_array_closed": False,
            "complete_records": [],
            "incomplete_record_present": False,
            "scan_stopped_at": index,
        }
    index = skip_ws(text, index + 1)
    keys: list[str] = []
    values: dict[str, Any] = {}
    records: list[Any] = []
    records_reached = False
    records_closed = False
    incomplete_record = False
    stopped = index
    while index < len(text):
        key_parsed = parse_string(text, skip_ws(text, index))
        if key_parsed is None:
            stopped = skip_ws(text, index)
            break
        key, index = key_parsed
        index = skip_ws(text, index)
        if index >= len(text) or text[index] != ":":
            stopped = index
            break
        index += 1
        if key == "records":
            records_reached = True
            records, next_index, records_closed = extract_complete_array_items(
                text, skip_ws(text, index)
            )
            incomplete_record = not records_closed
            keys.append(key)
            stopped = next_index
            index = next_index
            if records_closed:
                index = skip_ws(text, index)
                if index < len(text) and text[index] == ",":
                    index += 1
                    continue
            break
        value_parsed = parse_value(text, index)
        if value_parsed is None:
            stopped = skip_ws(text, index)
            break
        value, index = value_parsed
        keys.append(key)
        values[key] = value
        index = skip_ws(text, index)
        stopped = index
        if index >= len(text):
            break
        if text[index] == "}":
            stopped = index + 1
            break
        if text[index] != ",":
            break
        index += 1
    return {
        "starts_with_object": True,
        "root_keys_complete": keys,
        "root_scalar_values": values,
        "records_array_reached": records_reached,
        "records_array_closed": records_closed,
        "complete_records": records,
        "incomplete_record_present": incomplete_record and records_reached,
        "scan_stopped_at": stopped,
    }


__all__ = [
    "extract_complete_array_items",
    "extract_root_prefix",
    "parse_array",
    "parse_object",
    "parse_string",
    "parse_value",
    "skip_ws",
]
