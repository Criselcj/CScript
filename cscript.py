from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from lark import Lark, Token, Tree
from lark.visitors import Interpreter


GRAMMAR = r"""
?start: stmt*

?stmt: decl ";"
     | assign ";"
     | print_stmt ";"
     | if_stmt
     | while_stmt
     | do_while_stmt ";"
     | for_stmt
     | switch_stmt

decl: TYPE NAME ("=" expr)?
assign: NAME "=" expr
print_stmt: "imprimir" "(" expr ")"

if_stmt: "si" "(" cond ")" block ("sino" block)?
while_stmt: "mientras" "(" cond ")" block
do_while_stmt: "hacer" block "mientras" "(" cond ")"

for_stmt: "para" "(" for_init? ";" cond? ";" for_update? ")" block
for_init: decl_in_for | assign
decl_in_for: TYPE NAME ("=" expr)?
for_update: assign

switch_stmt: "segun" "(" expr ")" "{" case_block* default_block? "}"
case_block: "caso" literal ":" stmt* "romper" ";"
default_block: "defecto" ":" stmt*

block: "{" stmt* "}"

?literal: NUMBER   -> number
        | STRING   -> string
        | BOOLEAN  -> boolean

?cond: expr REL_OP expr      -> rel
     | "no" cond             -> not_
     | cond LOG_OP cond      -> logic
     | "(" cond ")"

?expr: term
     | expr "+" term         -> add
     | expr "-" term         -> sub

?term: factor
     | term "*" factor       -> mul
     | term "/" factor       -> div
     | term "%" factor       -> mod

?factor: "-" factor          -> neg
       | "leer" "(" ")"      -> read
       | literal
       | NAME                -> var
       | "(" expr ")"

TYPE: "entero" | "decimal" | "texto" | "booleano"
BOOLEAN: "verdadero" | "falso"
REL_OP: "==" | "!=" | "<=" | ">=" | "<" | ">"
LOG_OP: "y" | "o"

NAME: /(?!entero|decimal|texto|booleano|verdadero|falso|si|sino|mientras|para|hacer|segun|caso|defecto|romper|imprimir|leer)\b[a-zA-Z_][a-zA-Z0-9_]*/

%import common.SIGNED_NUMBER -> NUMBER
%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS

%ignore /\/\/[^\n]*/
%ignore /\/\*.*?\*\//s
"""


class BreakSwitch(Exception):
    pass


@dataclass
class Env:
    values: Dict[str, Any]
    types: Dict[str, str]


class CScriptInterpreter(Interpreter):
    def __init__(self) -> None:
        super().__init__()
        self.env = Env(values={}, types={})

    # -------------------------
    # Helpers
    # -------------------------

    def _coerce(self, declared_type: Optional[str], value: Any) -> Any:
        if declared_type is None:
            return value

        if declared_type == "entero":
            return int(value)

        if declared_type == "decimal":
            return float(value)

        if declared_type == "texto":
            return str(value)

        if declared_type == "booleano":
            if isinstance(value, str):
                if value.lower() == "verdadero":
                    return True
                if value.lower() == "falso":
                    return False
                raise RuntimeError("Valor inválido para booleano.")
            return bool(value)

        return value

    def _eval(self, node: Any) -> Any:
        if isinstance(node, Tree):
            method = getattr(self, node.data)
            return method(node)

        if isinstance(node, Token):
            if node.type == "NUMBER":
                s = str(node)
                return float(s) if "." in s else int(s)
            if node.type == "STRING":
                return str(node)[1:-1]
            if node.type == "BOOLEAN":
                return True if str(node) == "verdadero" else False
            if node.type == "NAME":
                name = str(node)
                if name not in self.env.values:
                    raise RuntimeError(f"Variable no definida: {name}")
                return self.env.values[name]

        return node

    # -------------------------
    # Literales / Variables
    # -------------------------

    def number(self, tree: Tree):
        s = str(tree.children[0])
        return float(s) if "." in s else int(s)

    def string(self, tree: Tree):
        return str(tree.children[0])[1:-1]

    def boolean(self, tree: Tree):
        return True if str(tree.children[0]) == "verdadero" else False

    def var(self, tree: Tree):
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no definida: {name}")
        return self.env.values[name]

    def read(self, tree: Tree):
        return input("> ")

    # -------------------------
    # Expresiones
    # -------------------------

    def add(self, tree: Tree):
        return self._eval(tree.children[0]) + self._eval(tree.children[1])

    def sub(self, tree: Tree):
        return self._eval(tree.children[0]) - self._eval(tree.children[1])

    def mul(self, tree: Tree):
        return self._eval(tree.children[0]) * self._eval(tree.children[1])

    def div(self, tree: Tree):
        return self._eval(tree.children[0]) / self._eval(tree.children[1])

    def mod(self, tree: Tree):
        return self._eval(tree.children[0]) % self._eval(tree.children[1])

    def neg(self, tree: Tree):
        return -self._eval(tree.children[0])

    # -------------------------
    # Sentencias
    # -------------------------

    def decl(self, tree: Tree):
        t = str(tree.children[0])
        name = str(tree.children[1])

        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")

        self.env.types[name] = t

        if len(tree.children) == 2:
            defaults = {
                "entero": 0,
                "decimal": 0.0,
                "texto": "",
                "booleano": False
            }
            self.env.values[name] = defaults.get(t)
        else:
            value = self._eval(tree.children[2])
            self.env.values[name] = self._coerce(t, value)

    def assign(self, tree: Tree):
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no declarada: {name}")
        value = self._eval(tree.children[1])
        self.env.values[name] = self._coerce(self.env.types[name], value)

    def print_stmt(self, tree: Tree):
        print(self._eval(tree.children[0]))

    def block(self, tree: Tree):
        for stmt in tree.children:
            self.visit(stmt)


def run(program_text: str):
    parser = Lark(GRAMMAR, parser="lalr")
    tree = parser.parse(program_text)
    interp = CScriptInterpreter()
    interp.visit(tree)


if __name__ == "__main__":
    with open("programa.cs", "r", encoding="utf-8") as f:
        code = f.read()
    run(code)