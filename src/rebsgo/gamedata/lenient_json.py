# github.com/Shran21
from __future__ import annotations

import json

_NON_EXECUTE_PREFIX = ")]}'"
_WS = " \t\n\r\f"
_UNQUOTED_TERMINATORS = set("{}[]:,;=/\\# \t\n\r\f")
_ESCAPES = {'"': '"', "'": "'", "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n",
            "r": "\r", "t": "\t"}


class _LenientDecodeError(ValueError):
    pass


class _LenientParser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def _skip_ws(self) -> None:
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in _WS:
                self.i += 1
                continue
            if c == "/" and self.i + 1 < n and s[self.i + 1] == "/":
                self.i += 2
                while self.i < n and s[self.i] not in "\n\r":
                    self.i += 1
                continue
            if c == "/" and self.i + 1 < n and s[self.i + 1] == "*":
                self.i += 2
                while self.i + 1 < n and not (s[self.i] == "*" and s[self.i + 1] == "/"):
                    self.i += 1
                self.i += 2
                continue
            if c == "#":
                self.i += 1
                while self.i < n and s[self.i] not in "\n\r":
                    self.i += 1
                continue
            break

    def parse_document(self):
        if self.s[self.i:self.i + len(_NON_EXECUTE_PREFIX)] == _NON_EXECUTE_PREFIX:
            self.i += len(_NON_EXECUTE_PREFIX)
        self._skip_ws()
        ertek = self._parse_value()
        self._skip_ws()
        return ertek

    def _parse_value(self):
        self._skip_ws()
        if self.i >= self.n:
            raise _LenientDecodeError("unexpected end of input")
        c = self.s[self.i]
        if c == "{":
            return self._parse_object()
        if c == "[":
            return self._parse_array()
        if c == '"' or c == "'":
            return self._parse_quoted(c)
        return self._parse_unquoted()

    def _parse_object(self) -> dict:
        self.i += 1
        obj: dict = {}
        self._skip_ws()
        if self.i < self.n and self.s[self.i] == "}":
            self.i += 1
            return obj
        while True:
            self._skip_ws()
            c = self.s[self.i] if self.i < self.n else ""
            if c == '"' or c == "'":
                nev = self._parse_quoted(c)
            else:
                nev = self._parse_unquoted_name
            self._skip_ws()
            if self.i >= self.n:
                raise _LenientDecodeError("expected name/value separator")
            sep = self.s[self.i]
            if sep == ":":
                self.i += 1
            elif sep == "=":
                self.i += 1
                if self.i < self.n and self.s[self.i] == ">":
                    self.i += 1
            else:
                raise _LenientDecodeError("expected ':' but found %r" % sep)
            ertek = self._parse_value()
            obj[nev] = ertek
            self._skip_ws()
            if self.i >= self.n:
                raise _LenientDecodeError("unterminated object")
            c = self.s[self.i]
            if c == "," or c == ";":
                self.i += 1
                self._skip_ws()
                if self.i < self.n and self.s[self.i] == "}":
                    self.i += 1
                    return obj
                continue
            if c == "}":
                self.i += 1
                return obj
            raise _LenientDecodeError("expected ',' or '}' but found %r" % c)

    def _parse_array(self) -> list:
        self.i += 1
        tomb: list = []
        self._skip_ws()
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return tomb
        while True:
            ertek = self._parse_value()
            tomb.append(ertek)
            self._skip_ws()
            if self.i >= self.n:
                raise _LenientDecodeError("unterminated array")
            c = self.s[self.i]
            if c == "," or c == ";":
                self.i += 1
                self._skip_ws()
                if self.i < self.n and self.s[self.i] == "]":
                    self.i += 1
                    return tomb
                continue
            if c == "]":
                self.i += 1
                return tomb
            raise _LenientDecodeError("expected ',' or ']' but found %r" % c)

    def _parse_quoted(self, quote: str) -> str:
        self.i += 1
        s, n = self.s, self.n
        out: list[str] = []
        while self.i < n:
            c = s[self.i]
            if c == "\\":
                self.i += 1
                if self.i >= n:
                    break
                e = s[self.i]
                if e == "u":
                    hexd = s[self.i + 1:self.i + 5]
                    out.append(chr(int(hexd, 16)))
                    self.i += 5
                    continue
                out.append(_ESCAPES.get(e, e))
                self.i += 1
                continue
            if c == quote:
                self.i += 1
                return "".join(out)
            out.append(c)
            self.i += 1
        raise _LenientDecodeError("unterminated string")

    def _read_unquoted_token(self) -> str:
        s, n = self.s, self.n
        kezdet = self.i
        while self.i < n and s[self.i] not in _UNQUOTED_TERMINATORS:
            self.i += 1
        if self.i == kezdet:
            raise _LenientDecodeError("expected a value at index %d" % kezdet)
        return s[kezdet:self.i]

    @property
    def _parse_unquoted_name(self) -> str:
        return self._read_unquoted_token()

    _SZAVAK = {"true": True, "false": False, "null": None}

    def _parse_unquoted(self):
        token = self._read_unquoted_token()
        if token in _LenientParser._SZAVAK:
            return _LenientParser._SZAVAK[token]
        szam = _try_number(token)
        return token if szam is None else szam


def _try_number(token: str):
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return None


def loads(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _LenientParser(text).parse_document()
