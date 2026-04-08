from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from lark import Lark, Token, Tree, UnexpectedInput
from lark.visitors import Interpreter

from dataclasses import dataclass

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

decl: TYPE NAME ("=" value)?
assign: NAME "=" value
print_stmt: "imprimir" "(" value ")"

?value: cond
      | expr

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

?literal: DECIMAL  -> decimal
        | ENTERO   -> entero
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

ENTERO: /\d+/
DECIMAL: /\d+\.\d+/

NAME: /(?!entero|decimal|texto|booleano|verdadero|falso|si|sino|mientras|para|hacer|segun|caso|defecto|romper|imprimir|leer|no|y|o)\b[a-zA-Z_][a-zA-Z0-9_]*/

%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS

%ignore /\/\/[^\n]*/
%ignore /\/\*.*?\*\//s
"""


TOKEN_NAMES = {
    "TYPE": "TIPO_DATO",
    "NAME": "IDENTIFICADOR",
    "ENTERO": "ENTERO",
    "DECIMAL": "DECIMAL",
    "STRING": "TEXTO",
    "BOOLEAN": "BOOLEANO",
    "REL_OP": "OP_RELACIONAL",
    "LOG_OP": "OP_LOGICO",

    "EQUAL": "ASIGNACION",
    "PLUS": "OP_ARITMETICO",
    "MINUS": "OP_ARITMETICO",
    "STAR": "OP_ARITMETICO",
    "SLASH": "OP_ARITMETICO",
    "PERCENT": "OP_ARITMETICO",

    "LPAR": "PAR_ABRE",
    "RPAR": "PAR_CIERRA",
    "LBRACE": "LLAVE_ABRE",
    "RBRACE": "LLAVE_CIERRA",
    "SEMICOLON": "PUNTO_COMA",
    "COLON": "DOS_PUNTOS",
}


def normalizar_token(tok: Token) -> str:
    texto = str(tok)

    reservadas = {
        "si": "SI",
        "sino": "SINO",
        "mientras": "MIENTRAS",
        "hacer": "HACER",
        "para": "PARA",
        "segun": "SEGUN",
        "caso": "CASO",
        "defecto": "DEFECTO",
        "romper": "ROMPER",
        "imprimir": "IMPRIMIR",
        "leer": "LEER",
        "no": "NO",
        "y": "Y",
        "o": "O",
        "entero": "TIPO_DATO",
        "decimal": "TIPO_DATO",
        "texto": "TIPO_DATO",
        "booleano": "TIPO_DATO",
        "verdadero": "BOOLEANO",
        "falso": "BOOLEANO",
    }

    simbolos = {
        "=": "ASIGNACION",
        "+": "OP_ARITMETICO",
        "-": "OP_ARITMETICO",
        "*": "OP_ARITMETICO",
        "/": "OP_ARITMETICO",
        "%": "OP_ARITMETICO",
        "(": "PAR_ABRE",
        ")": "PAR_CIERRA",
        "{": "LLAVE_ABRE",
        "}": "LLAVE_CIERRA",
        ";": "PUNTO_COMA",
        ":": "DOS_PUNTOS",
        "==": "OP_RELACIONAL",
        "!=": "OP_RELACIONAL",
        "<=": "OP_RELACIONAL",
        ">=": "OP_RELACIONAL",
        "<": "OP_RELACIONAL",
        ">": "OP_RELACIONAL",
    }

    if texto in reservadas:
        return reservadas[texto]

    if texto in simbolos:
        return simbolos[texto]

    return TOKEN_NAMES.get(tok.type, tok.type)


def analizar_lexico(program_text: str) -> tuple[list[dict], list[LexicalErrorInfo]]:
    parser = Lark(GRAMMAR, parser="lalr", lexer="contextual", propagate_positions=True)#lexer="contextual" activa el componente que separa el texto en tokens
    tokens = []
    errores = []

    try:
        for i, tok in enumerate(parser.lex(program_text), start=1):
            tokens.append({
                "no": i,
                "linea": tok.line,
                "columna": tok.column,
                "token": normalizar_token(tok),
                "lexema": tok.value,
                "tipo_lark": tok.type,
            })
    #obtención del error
    except UnexpectedInput as e:
        linea = getattr(e, "line", 0)
        columna = getattr(e, "column", 0)

        lexema = "desconocido"
        if linea > 0 and 1 <= linea <= len(program_text.splitlines()):
            linea_texto = program_text.splitlines()[linea - 1]
            if 1 <= columna <= len(linea_texto):
                lexema = linea_texto[columna - 1]

        errores.append(
            LexicalErrorInfo(
                numero=1,
                linea=linea,
                columna=columna,
                lexema=lexema,
                descripcion="Se encontró un símbolo o secuencia no reconocida por el lenguaje.",
                sugerencia="Verifica caracteres especiales, cadenas sin cerrar o identificadores mal escritos."
            )
        )

    return tokens, errores


def mostrar_logs_lexicos(program_text: str) -> bool:
    tokens, errores = analizar_lexico(program_text)

    print("\n" + "=" * 84)
    print("TERMINAL LEXICA - TOKENS Y LEXEMAS")
    print("=" * 84)

    if tokens:
        print(f"{'No.':<5} {'Linea':<7} {'Col':<6} {'Token':<20} {'Lexema'}")
        print("-" * 84)

        for t in tokens:
            print(f"{t['no']:<5} {t['linea']:<7} {t['columna']:<6} {t['token']:<20} {repr(t['lexema'])}")

        print("-" * 84)
        print(f"Total de tokens: {len(tokens)}")

    if errores:
        print("\n" + "=" * 84)
        print("ERRORES LEXICOS")
        print("=" * 84)

        for err in errores:
            print(f"[Error {err.numero}]")
            print(f"Línea      : {err.linea}")
            print(f"Columna    : {err.columna}")
            print(f"Lexema     : {repr(err.lexema)}")
            print(f"Descripción: {err.descripcion}")
            print(f"Sugerencia : {err.sugerencia}")
            print("-" * 84)

        return False

    print("=" * 84 + "\n")
    return True


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
        if isinstance(value, list) and len(value) == 1:
            value = value[0]

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
        if isinstance(node, list):
            if len(node) == 1:
                return self._eval(node[0])
            return [self._eval(x) for x in node]

        if isinstance(node, Tree):
            if node.data in ("expr", "term", "factor", "cond"):
                if len(node.children) == 1:
                    return self._eval(node.children[0])

            method = getattr(self, node.data, None)
            if method is None:
                raise RuntimeError(f"No hay handler para: {node.data}")

            result = method(node)

            if isinstance(result, list) and len(result) == 1:
                return self._eval(result[0])

            return result

        if isinstance(node, Token):
            if node.type == "ENTERO":
                return int(str(node))

            if node.type == "DECIMAL":
                return float(str(node))

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
    def entero(self, tree: Tree) -> int:
        return int(str(tree.children[0]))

    def decimal(self, tree: Tree) -> float:
        return float(str(tree.children[0]))

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
            defaults = {
                "entero": 0,
                "decimal": 0.0,
                "texto": "",
                "booleano": False
            }
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
    # Control de flujo
    # -------------------------------------------------------------------------
    def if_stmt(self, tree: Tree) -> None:
        cond_tree = tree.children[0]
        then_block = tree.children[1]
        else_block = tree.children[2] if len(tree.children) > 2 else None

        if bool(self._eval(cond_tree)):
            self.visit(then_block)
        elif else_block is not None:
            self.visit(else_block)

    def while_stmt(self, tree: Tree) -> None:
        cond_tree = tree.children[0]
        block_tree = tree.children[1]

        while bool(self._eval(cond_tree)):
            self.visit(block_tree)

    def do_while_stmt(self, tree: Tree) -> None:
        block_tree = tree.children[0]
        cond_tree = tree.children[1]

        while True:
            self.visit(block_tree)
            if not bool(self._eval(cond_tree)):
                break

    # -------------------------------------------------------------------------
    # For
    # -------------------------------------------------------------------------
    def decl_in_for(self, tree: Tree) -> None:
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
            self.env.values[name] = defaults.get(t, None)
            return

        value = self._eval(tree.children[2])
        self.env.values[name] = self._coerce(t, value)

    def for_init(self, tree: Tree) -> None:
        self.visit(tree.children[0])

    def for_update(self, tree: Tree) -> None:
        self.visit(tree.children[0])

    def for_stmt(self, tree: Tree) -> None:
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

    # -------------------------------------------------------------------------
    # Switch
    # -------------------------------------------------------------------------
    def switch_stmt(self, tree: Tree) -> None:
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

            case_value = self._eval(b.children[0])
            if target == case_value:
                for stmt in b.children[1:]:
                    self.visit(stmt)
                return

        if default_block is not None:
            for stmt in default_block.children:
                self.visit(stmt)

    def case_block(self, tree: Tree) -> Tree:
        return tree

    def default_block(self, tree: Tree) -> Tree:
        return tree


@dataclass
class LexicalErrorInfo:
    numero: int
    linea: int
    columna: int
    lexema: str
    descripcion: str
    sugerencia: str


# def run(program_text: str, mostrar_lexico: bool = True) -> None:
#     parser = Lark(GRAMMAR, parser="lalr", lexer="contextual", propagate_positions=True)

#     try:
#         if mostrar_lexico:
#             ok = mostrar_logs_lexicos(program_text)
#             if not ok:
#                 print("[EJECUCION DETENIDA] Hay errores léxicos en el código.")
#                 return

#         tree = parser.parse(program_text)
#         interp = CScriptInterpreter()
#         interp.visit(tree)

#     except UnexpectedInput as e:
#         print("\n[ERROR DE ANALISIS]")
#         print(f"Línea: {e.line}")
#         print(f"Columna: {e.column}")
#         print("Se encontró un lexema no reconocido o una estructura inválida.")
#         print(e.get_context(program_text))

#     except Exception as e:
#         print(f"\n[ERROR DE EJECUCION] {e}")

def run(program_text: str, mostrar_lexico: bool = True) -> None:
    if mostrar_lexico:
        ok = mostrar_logs_lexicos(program_text)
        if not ok:
            print("[EJECUCION DETENIDA] Hay errores léxicos en el código.")
            return

    print("[MODO LEXICO] Análisis léxico finalizado.")

if __name__ == "__main__":
    with open("programa.csc", "r", encoding="utf-8") as f:
        code = f.read()

    run(code, mostrar_lexico=True)