"""
Mini-parser YAML restringido para los archivos de configuración del
DefenseMesh. Soporta únicamente el subset que el proyecto usa:

  * mapas anidados (clave: valor)
  * listas con "- item"
  * strings (con o sin comillas dobles)
  * ints, floats, bool (true/false), null (~)
  * comentarios con ``#`` (no dentro de strings)

NO soporta: anclas, merge keys, multi-documento, flow style, tags, comillas
escapadas, ni comillas simples. Suficiente para config + playbooks.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}
_NULL = {"null", "none", "~", ""}


def _coerce(token: str) -> Any:
    s = token.strip()
    low = s.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    if low in _NULL:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except ValueError:
            return s
    if re.fullmatch(r"-?\d+\.\d+", s):
        try:
            return float(s)
        except ValueError:
            return s
    return s


def _strip_comment(line: str) -> str:
    in_dq = False
    in_sq = False
    for i, ch in enumerate(line):
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == "#" and not in_dq and not in_sq:
            return line[:i]
    return line


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


class _Parser:
    def __init__(self, lines: List[str]):
        self.lines = lines
        self.n = len(lines)

    def _next(self, idx: int) -> Tuple[str, int, int]:
        """Encuentra la siguiente línea no vacía/no comentario desde ``idx``.
        Devuelve (línea_limpia, indent, índice_de_la_línea). Si no hay
        más, devuelve ('', -1, n)."""
        while idx < self.n:
            raw = self.lines[idx]
            stripped = _strip_comment(raw).rstrip()
            if not stripped.strip():
                idx += 1
                continue
            return stripped, _indent_of(stripped), idx
        return "", -1, idx

    def parse(self) -> Any:
        line, ind, idx = self._next(0)
        if ind != 0:
            raise ValueError(f"Top-level must have indent 0, got {ind}")
        if ":" in line:
            return self._parse_map(idx, 0)[0]
        if line.lstrip().startswith("- "):
            return self._parse_list(idx, 0)[0]
        return _coerce(line.lstrip()), idx

    def _parse_map(self, start: int, base_indent: int) -> Tuple[Dict[str, Any], int]:
        result: Dict[str, Any] = {}
        idx = start
        while idx < self.n:
            line, ind, found_idx = self._next(idx)
            if ind < base_indent or line == "":
                return result, idx
            if ind > base_indent:
                # Indent mayor: ya no es parte de este mapa.
                return result, idx
            content = line[base_indent:]
            if content.startswith("- "):
                # Inicio de lista, no parte de este mapa.
                return result, idx
            if ":" not in content:
                # Línea sin ':' — la saltamos para no colgar.
                idx = found_idx + 1
                continue
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                # Sub-bloque
                child_indent = base_indent + 2
                peek_line, peek_ind, peek_idx = self._next(found_idx + 1)
                if peek_ind == child_indent or peek_ind > child_indent:
                    child, idx = self._parse_value(found_idx + 1, child_indent)
                    result[key] = child
                else:
                    result[key] = None
                    idx = found_idx + 1
            else:
                result[key] = _coerce(value)
                idx = found_idx + 1
        return result, idx

    def _parse_value(self, start: int, base_indent: int) -> Tuple[Any, int]:
        """Parsea un valor que puede ser mapa, lista o escalar."""
        line, ind, found_idx = self._next(start)
        if line == "" or ind < base_indent:
            return None, start
        content = line[base_indent:]
        if content.startswith("- "):
            return self._parse_list(start, base_indent)
        if ":" in content:
            return self._parse_map(start, base_indent)
        return _coerce(content), found_idx + 1

    def _parse_list(self, start: int, base_indent: int) -> Tuple[List[Any], int]:
        result: List[Any] = []
        idx = start
        while idx < self.n:
            line, ind, found_idx = self._next(idx)
            if line == "" or ind < base_indent:
                return result, idx
            if ind > base_indent:
                return result, idx
            content = line[base_indent:]
            if not content.startswith("- "):
                return result, idx
            item_text = content[2:].strip()
            if item_text == "":
                # Sub-bloque en las siguientes líneas
                child_indent = base_indent + 2
                peek_line, peek_ind, peek_idx = self._next(found_idx + 1)
                if peek_ind == child_indent or peek_ind > child_indent:
                    child, idx = self._parse_value(found_idx + 1, child_indent)
                    result.append(child)
                else:
                    idx = found_idx + 1
            elif ":" in item_text and not (item_text.startswith('"') or item_text.startswith("'")):
                # Inline map "- key: value" o "- key:" con sub-bloque
                k, _, v = item_text.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "":
                    child_indent = base_indent + 2
                    peek_line, peek_ind, peek_idx = self._next(found_idx + 1)
                    if peek_ind == child_indent or peek_ind > child_indent:
                        child, idx = self._parse_value(found_idx + 1, child_indent)
                        if isinstance(child, dict):
                            # Prepend la clave inline
                            child = {k: None, **child} if k not in child else {k: child[k], **child}
                            result.append(child)
                        else:
                            result.append({k: child})
                    else:
                        result.append({k: None})
                        idx = found_idx + 1
                else:
                    sub_map = {k: _coerce(v)}
                    idx = found_idx + 1
                    child_indent = base_indent + 2
                    while idx < self.n:
                        peek_line, peek_ind, peek_idx = self._next(idx)
                        if peek_ind != child_indent:
                            break
                        peek_content = peek_line[child_indent:]
                        if peek_content.startswith("- "):
                            break
                        if ":" in peek_content:
                            kk, _, vv = peek_content.partition(":")
                            kk = kk.strip()
                            vv = vv.strip()
                            if vv == "":
                                grandchild_indent = child_indent + 2
                                peek2_line, peek2_ind, _ = self._next(idx + 1)
                                if peek2_ind == grandchild_indent or peek2_ind > grandchild_indent:
                                    child_val, idx = self._parse_value(idx + 1, grandchild_indent)
                                    sub_map[kk] = child_val
                                else:
                                    sub_map[kk] = None
                                    idx = peek_idx + 1
                            else:
                                sub_map[kk] = _coerce(vv)
                                idx = peek_idx + 1
                        else:
                            idx = peek_idx + 1
                    result.append(sub_map)
            else:
                result.append(_coerce(item_text))
                idx = found_idx + 1
        return result, idx


def load(stream) -> Dict[str, Any]:
    if hasattr(stream, "read"):
        text = stream.read()
    else:
        text = stream
    lines = text.splitlines()
    filtered = [l for i, l in enumerate(lines) if not (i == 0 and l.strip() == "---")]
    parser = _Parser(filtered)
    result = parser.parse()
    if not isinstance(result, dict):
        raise ValueError("Top-level YAML must be a mapping")
    return result


def dumps(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        out = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                out.append(f"{pad}{k}:\n{dumps(v, indent + 1)}")
            else:
                out.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(out)
    if isinstance(obj, list):
        if not obj:
            return "[]"
        out = []
        for v in obj:
            if isinstance(v, (dict, list)):
                out.append(f"{pad}-\n{dumps(v, indent + 1)}")
            else:
                out.append(f"{pad}- {_scalar(v)}")
        return "\n".join(out)
    return f"{pad}{_scalar(obj)}"


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in [":", "#"]) or s.strip() != s:
        return f'"{s}"'
    return s
