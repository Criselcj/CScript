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
    """Usado internamente para salir de un 'caso' en 'segun'."""
    pass


@dataclass
class Env:
    values: Dict[str, Any]
    types: Dict[str, str]


class CScriptInterpreter(Interpreter):
    def __init__(self) -> None:
        super().__init__()
        self.env = Env(values={}, types={})

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _coerce(self, declared_type: Optional[str], value: Any) -> Any:
        """Convierte value al tipo declarado (sirve especialmente para leer())."""
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
                v = value.strip().lower()
                if v == "verdadero":
                    return True
                if v == "falso":
                    return False
                raise RuntimeError("Valor inválido para booleano (usa verdadero/falso).")
            return bool(value)

        return value

    def _eval(self, node: Any) -> Any:
        """Evalúa expresiones y condiciones (Tree/Token)."""
        if isinstance(node, Tree):
            method = getattr(self, node.data, None)
            if method is None:
                raise RuntimeError(f"No hay handler para: {node.data}")
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
            return str(node)

        return node

    # -------------------------------------------------------------------------
    # Literales / variables / leer()
    # -------------------------------------------------------------------------
    def number(self, tree: Tree) -> Any:
        s = str(tree.children[0])
        return float(s) if "." in s else int(s)

    def string(self, tree: Tree) -> str:
        return str(tree.children[0])[1:-1]

    def boolean(self, tree: Tree) -> bool:
        return True if str(tree.children[0]) == "verdadero" else False

    def var(self, tree: Tree) -> Any:
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no definida: {name}")
        return self.env.values[name]

    def read(self, tree: Tree) -> str:
        """leer() -> string crudo; luego decl/assign lo convierten con _coerce."""
        return input("> ")

    # -------------------------------------------------------------------------
    # Expresiones
    # -------------------------------------------------------------------------
    def add(self, tree: Tree) -> Any:
        return self._eval(tree.children[0]) + self._eval(tree.children[1])

    def sub(self, tree: Tree) -> Any:
        return self._eval(tree.children[0]) - self._eval(tree.children[1])

    def mul(self, tree: Tree) -> Any:
        return self._eval(tree.children[0]) * self._eval(tree.children[1])

    def div(self, tree: Tree) -> Any:
        return self._eval(tree.children[0]) / self._eval(tree.children[1])

    def mod(self, tree: Tree) -> Any:
        return self._eval(tree.children[0]) % self._eval(tree.children[1])

    def neg(self, tree: Tree) -> Any:
        return -self._eval(tree.children[0])

    # -------------------------------------------------------------------------
    # Condiciones
    # -------------------------------------------------------------------------
    def rel(self, tree: Tree) -> bool:
        left = self._eval(tree.children[0])
        op = str(tree.children[1])
        right = self._eval(tree.children[2])

        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        raise RuntimeError(f"Operador relacional inválido: {op}")

    def not_(self, tree: Tree) -> bool:
        return not bool(self._eval(tree.children[0]))

    def logic(self, tree: Tree) -> bool:
        a = bool(self._eval(tree.children[0]))
        op = str(tree.children[1])
        b = bool(self._eval(tree.children[2]))

        if op == "y":
            return a and b
        if op == "o":
            return a or b
        raise RuntimeError(f"Operador lógico inválido: {op}")

    # -------------------------------------------------------------------------
    # Sentencias básicas
    # -------------------------------------------------------------------------
    def decl(self, tree: Tree) -> None:
        t = str(tree.children[0])
        name = str(tree.children[1])

        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")

        self.env.types[name] = t

        if len(tree.children) == 2:
            defaults = {"entero": 0, "decimal": 0.0, "texto": "", "booleano": False}
            self.env.values[name] = defaults.get(t, None)
            return

        value = self._eval(tree.children[2])
        self.env.values[name] = self._coerce(t, value)

    def assign(self, tree: Tree) -> None:
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no declarada: {name}")

        value = self._eval(tree.children[1])
        declared_type = self.env.types.get(name)
        self.env.values[name] = self._coerce(declared_type, value)

    def print_stmt(self, tree: Tree) -> None:
        print(self._eval(tree.children[0]))

    def block(self, tree: Tree) -> None:
        for stmt in tree.children:
            self.visit(stmt)

    # -------------------------------------------------------------------------
    # Control de flujo (ARREGLADO)
    # -------------------------------------------------------------------------
    def if_stmt(self, tree: Tree) -> None:
        # if_stmt: "si" "(" cond ")" block ("sino" block)?
        cond_tree = tree.children[0]
        then_block = tree.children[1]
        else_block = tree.children[2] if len(tree.children) > 2 else None

        if bool(self._eval(cond_tree)):
            self.visit(then_block)
        elif else_block is not None:
            self.visit(else_block)

    def while_stmt(self, tree: Tree) -> None:
        # while_stmt: "mientras" "(" cond ")" block
        cond_tree = tree.children[0]
        block_tree = tree.children[1]

        while bool(self._eval(cond_tree)):
            self.visit(block_tree)

    def do_while_stmt(self, tree: Tree) -> None:
        # do_while_stmt: "hacer" block "mientras" "(" cond ")"
        block_tree = tree.children[0]
        cond_tree = tree.children[1]

        while True:
            self.visit(block_tree)
            if not bool(self._eval(cond_tree)):
                break

    # ---- for ----
    def decl_in_for(self, tree: Tree) -> None:
        # decl_in_for: TYPE NAME ("=" expr)?
        # Igual que decl, pero sin ';'
        t = str(tree.children[0])
        name = str(tree.children[1])

        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")

        self.env.types[name] = t

        if len(tree.children) == 2:
            defaults = {"entero": 0, "decimal": 0.0, "texto": "", "booleano": False}
            self.env.values[name] = defaults.get(t, None)
            return

        value = self._eval(tree.children[2])
        self.env.values[name] = self._coerce(t, value)

    def for_init(self, tree: Tree) -> None:
        # wrapper: decl_in_for | assign
        self.visit(tree.children[0])

    def for_update(self, tree: Tree) -> None:
        # wrapper: assign
        self.visit(tree.children[0])

    def for_stmt(self, tree: Tree) -> None:
        # for_stmt: "para" "(" for_init? ";" cond? ";" for_update? ")" block
        # children: (0..3 header) + block
        parts = list(tree.children)
        block_tree = parts[-1]
        header = parts[:-1]

        init = None
        cond = None
        update = None

        def is_init_node(n: Tree) -> bool:
            return isinstance(n, Tree) and n.data in ("for_init", "decl_in_for", "decl", "assign")

        def is_update_node(n: Tree) -> bool:
            return isinstance(n, Tree) and n.data in ("for_update", "assign")

        if len(header) == 1:
            if is_init_node(header[0]):
                init = header[0]
            else:
                cond = header[0]
        elif len(header) == 2:
            if is_init_node(header[0]):
                init = header[0]
                if is_update_node(header[1]):
                    update = header[1]
                else:
                    cond = header[1]
            else:
                cond, update = header[0], header[1]
        elif len(header) == 3:
            init, cond, update = header

        if init is not None:
            self.visit(init)

        while True:
            if cond is not None and not bool(self._eval(cond)):
                break

            self.visit(block_tree)

            if update is not None:
                self.visit(update)

    # ---- switch ----
    def switch_stmt(self, tree: Tree) -> None:
        # switch_stmt: "segun" "(" expr ")" "{" case_block* default_block? "}"
        target = self._eval(tree.children[0])
        blocks = tree.children[1:]

        default_block = None
        for b in blocks:
            if isinstance(b, Tree) and b.data == "default_block":
                default_block = b

        for b in blocks:
            if not isinstance(b, Tree):
                continue
            if b.data != "case_block":
                continue

            case_value = self._eval(b.children[0])  # literal
            if target == case_value:
                # ejecutar stmt* (los hijos después del literal)
                for stmt in b.children[1:]:
                    self.visit(stmt)
                return

        if default_block is not None:
            for stmt in default_block.children:
                self.visit(stmt)

    def case_block(self, tree: Tree) -> Tree:
        # No se ejecuta aquí; se ejecuta desde switch_stmt
        return tree

    def default_block(self, tree: Tree) -> Tree:
        return tree


def run(program_text: str) -> None:
    parser = Lark(GRAMMAR, parser="lalr")
    tree = parser.parse(program_text)
    interp = CScriptInterpreter()
    interp.visit(tree)


if __name__ == "__main__":
    with open("programa.csc", "r", encoding="utf-8") as f:
        code = f.read()
    run(code)