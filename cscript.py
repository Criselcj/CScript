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
       | literal
       | NAME                -> var
       | "(" expr ")"

TYPE: "entero" | "decimal" | "texto" | "booleano"
BOOLEAN: "verdadero" | "falso"
REL_OP: "==" | "!=" | "<=" | ">=" | "<" | ">"
LOG_OP: "y" | "o"

NAME: /(?!entero|decimal|texto|booleano|verdadero|falso|si|sino|mientras|para|hacer|segun|caso|defecto|romper|imprimir)\b[a-zA-Z_][a-zA-Z0-9_]*/

%import common.SIGNED_NUMBER -> NUMBER
%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS

// Comentarios
%ignore /\/\/[^\n]*/
%ignore /\/\*.*?\*\//s
"""


class BreakSwitch(Exception):
    """Se usa internamente para salir de un caso en 'segun'."""
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
    def _tok(self, x: Any) -> str:
        return str(x)

    def _coerce(self, declared_type: Optional[str], value: Any) -> Any:
        """Convierte 'value' al tipo declarado si corresponde."""
        if declared_type is None:
            return value

        t = declared_type
        if t == "entero":
            if isinstance(value, bool):
                raise RuntimeError("No puedes asignar booleano a entero.")
            return int(value)
        if t == "decimal":
            if isinstance(value, bool):
                raise RuntimeError("No puedes asignar booleano a decimal.")
            return float(value)
        if t == "texto":
            return str(value)
        if t == "booleano":
            if isinstance(value, str):
                raise RuntimeError("No puedes asignar texto a booleano directamente.")
            return bool(value)

        return value

    def _eval(self, node: Any) -> Any:
        """Evalúa una expresión o condición (Tree/Token)."""
        if isinstance(node, Tree):
            method = getattr(self, node.data, None)
            if method is None:
                raise RuntimeError(f"No hay handler para: {node.data}")
            return method(node)
        if isinstance(node, Token):
            # Normalmente aquí no deberían llegar literales “crudos” por la gramática,
            # pero lo dejamos por seguridad.
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

    def _exec_block(self, block_tree: Tree) -> None:
        # block: "{" stmt* "}"
        for child in block_tree.children:
            self._exec_stmt(child)

    def _exec_stmt(self, stmt_tree: Tree) -> None:
        # stmt es un Tree con data = una regla (decl, assign, if_stmt, etc.)
        if not isinstance(stmt_tree, Tree):
            return
        handler = getattr(self, stmt_tree.data, None)
        if handler is None:
            raise RuntimeError(f"No hay handler para sentencia: {stmt_tree.data}")
        handler(stmt_tree)

    # -------------------------
    # Literales / variables
    # -------------------------
    def number(self, tree: Tree) -> Any:
        tok = tree.children[0]
        s = str(tok)
        return float(s) if "." in s else int(s)

    def string(self, tree: Tree) -> str:
        tok = tree.children[0]
        return str(tok)[1:-1]

    def boolean(self, tree: Tree) -> bool:
        tok = tree.children[0]
        return True if str(tok) == "verdadero" else False

    def var(self, tree: Tree) -> Any:
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no definida: {name}")
        return self.env.values[name]

    # -------------------------
    # Expresiones
    # -------------------------
    def add(self, tree: Tree) -> Any:
        a = self._eval(tree.children[0])
        b = self._eval(tree.children[1])
        return a + b

    def sub(self, tree: Tree) -> Any:
        a = self._eval(tree.children[0])
        b = self._eval(tree.children[1])
        return a - b

    def mul(self, tree: Tree) -> Any:
        a = self._eval(tree.children[0])
        b = self._eval(tree.children[1])
        return a * b

    def div(self, tree: Tree) -> Any:
        a = self._eval(tree.children[0])
        b = self._eval(tree.children[1])
        return a / b

    def mod(self, tree: Tree) -> Any:
        a = self._eval(tree.children[0])
        b = self._eval(tree.children[1])
        return a % b

    def neg(self, tree: Tree) -> Any:
        v = self._eval(tree.children[0])
        return -v

    # -------------------------
    # Condiciones
    # -------------------------
    def rel(self, tree: Tree) -> bool:
        left = self._eval(tree.children[0])
        op = str(tree.children[1])
        right = self._eval(tree.children[2])

        if op == "==": return left == right
        if op == "!=": return left != right
        if op == "<":  return left < right
        if op == ">":  return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        raise RuntimeError(f"Operador relacional inválido: {op}")

    def not_(self, tree: Tree) -> bool:
        c = self._eval(tree.children[0])
        return not c

    def logic(self, tree: Tree) -> bool:
        a = self._eval(tree.children[0])
        op = str(tree.children[1])
        b = self._eval(tree.children[2])

        if op == "y": return bool(a) and bool(b)
        if op == "o": return bool(a) or bool(b)
        raise RuntimeError(f"Operador lógico inválido: {op}")

    # -------------------------
    # Sentencias
    # -------------------------
    def decl(self, tree: Tree) -> None:
        # decl: TYPE NAME ("=" expr)?
        t = str(tree.children[0])
        name = str(tree.children[1])

        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")

        self.env.types[name] = t

        if len(tree.children) == 2:
            # default por tipo
            if t == "entero": self.env.values[name] = 0
            elif t == "decimal": self.env.values[name] = 0.0
            elif t == "texto": self.env.values[name] = ""
            elif t == "booleano": self.env.values[name] = False
            else: self.env.values[name] = None
        else:
            value = self._eval(tree.children[2])
            self.env.values[name] = self._coerce(t, value)

    def assign(self, tree: Tree) -> None:
        # assign: NAME "=" expr
        name = str(tree.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"No puedes asignar: variable no declarada: {name}")
        value = self._eval(tree.children[1])
        declared_type = self.env.types.get(name)
        self.env.values[name] = self._coerce(declared_type, value)

    def print_stmt(self, tree: Tree) -> None:
        value = self._eval(tree.children[0])
        print(value)

    def block(self, tree: Tree) -> None:
        self._exec_block(tree)

    def if_stmt(self, tree: Tree) -> None:
        # if_stmt: "si" "(" cond ")" block ("sino" block)?
        condition = self._eval(tree.children[0])
        then_block = tree.children[1]
        else_block = tree.children[2] if len(tree.children) > 2 else None

        if condition:
            self._exec_block(then_block)
        elif else_block is not None:
            self._exec_block(else_block)

    def while_stmt(self, tree: Tree) -> None:
        # while_stmt: "mientras" "(" cond ")" block
        cond_tree = tree.children[0]
        block_tree = tree.children[1]

        while self._eval(cond_tree):
            self._exec_block(block_tree)

    def do_while_stmt(self, tree: Tree) -> None:
        # do_while_stmt: "hacer" block "mientras" "(" cond ")"
        block_tree = tree.children[0]
        cond_tree = tree.children[1]

        while True:
            self._exec_block(block_tree)
            if not self._eval(cond_tree):
                break

    def for_stmt(self, tree: Tree) -> None:
        # for_stmt: "para" "(" for_init? ";" cond? ";" for_update? ")" block
        # children: [for_init? , cond? , for_update? , block] pero los opcionales pueden faltar
        # Mejor: detectar por tipo.
        parts = list(tree.children)
        block_tree = parts[-1]
        header = parts[:-1]

        init = None
        cond = None
        update = None

        # header puede tener 0..3 nodos, en orden: init, cond, update
        if len(header) == 1:
            # puede ser cond o init o update; pero por la gramática normalmente será cond
            cond = header[0]
        elif len(header) == 2:
            init, cond = header
        elif len(header) == 3:
            init, cond, update = header

        if init is not None:
            self._exec_stmt(init if isinstance(init, Tree) else init)

        while True:
            if cond is not None and not self._eval(cond):
                break

            self._exec_block(block_tree)

            if update is not None:
                self._exec_stmt(update)

    def decl_in_for(self, tree: Tree) -> None:
        # reutiliza decl sin ';'
        # decl_in_for: TYPE NAME ("=" expr)?
        # misma lógica que decl
        t = str(tree.children[0])
        name = str(tree.children[1])

        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")

        self.env.types[name] = t

        if len(tree.children) == 2:
            if t == "entero": self.env.values[name] = 0
            elif t == "decimal": self.env.values[name] = 0.0
            elif t == "texto": self.env.values[name] = ""
            elif t == "booleano": self.env.values[name] = False
            else: self.env.values[name] = None
        else:
            value = self._eval(tree.children[2])
            self.env.values[name] = self._coerce(t, value)

    def for_init(self, tree: Tree) -> None:
        # un wrapper: decl_in_for | assign
        self._exec_stmt(tree.children[0])

    def for_update(self, tree: Tree) -> None:
        self._exec_stmt(tree.children[0])

    def switch_stmt(self, tree: Tree) -> None:
        # switch_stmt: "segun" "(" expr ")" "{" case_block* default_block? "}"
        target = self._eval(tree.children[0])

        # el resto son case_block / default_block
        blocks = tree.children[1:]

        matched = False
        for b in blocks:
            if not isinstance(b, Tree):
                continue

            if b.data == "case_block":
                case_lit = self._eval(b.children[0])  # literal
                if (not matched) and (target == case_lit):
                    matched = True
                    try:
                        # ejecutar sentencias del caso (después del literal)
                        for stmt in b.children[1:]:
                            self._exec_stmt(stmt)
                    except BreakSwitch:
                        return
            elif b.data == "default_block":
                if not matched:
                    for stmt in b.children:
                        self._exec_stmt(stmt)

    def case_block(self, tree: Tree) -> Tree:
        # case_block: "caso" literal ":" stmt* "romper" ";"
        # No se ejecuta aquí; se ejecuta en switch_stmt
        # Pero sí necesitamos "interceptar" el romper; lo hacemos convirtiéndolo en una sentencia break_switch.
        new_children = []
        # children: [literal, stmt*, ...] pero 'romper' no llega como stmt; está en la regla.
        # Lark nos deja: literal + stmt* (sin el "romper" ";")? depende del parser.
        # Para asegurar el break, inyectamos un nodo al final:
        for c in tree.children:
            new_children.append(c)
        new_children.append(Tree("break_switch", []))
        return Tree("case_block", new_children)

    def default_block(self, tree: Tree) -> Tree:
        return tree

    def break_switch(self, tree: Tree) -> None:
        raise BreakSwitch()


def run(program_text: str) -> None:
    parser = Lark(GRAMMAR, parser="lalr")
    tree = parser.parse(program_text)
    interp = CScriptInterpreter()
    interp.visit(tree)


if __name__ == "__main__":
    with open("programa.csc", "r", encoding="utf-8") as f:
        code = f.read()
    run(code)