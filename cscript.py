from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from lark import Lark, Token, Tree, UnexpectedInput
from lark.visitors import Interpreter


# ============================================================
# GRAMÁTICA LÉXICA  (solo para la tabla de tokens)
# ============================================================
LEXER_GRAMMAR = r"""
start: token*

token: TYPE | BOOLEAN | REL_OP | LOG_OP
     | IMPRIMIR | LEER | SI | SINO | MIENTRAS | HACER
     | PARA | SEGUN | CASO | DEFECTO | ROMPER | NO
     | EQUAL | PLUS | MINUS | STAR | SLASH | PERCENT
     | LPAR | RPAR | LBRACE | RBRACE | SEMICOLON | COLON
     | DECIMAL | ENTERO | STRING | NAME

TYPE:     "entero" | "decimal" | "texto" | "booleano"
BOOLEAN:  "verdadero" | "falso"
IMPRIMIR: "imprimir"
LEER:     "leer"
SI:       "si"
SINO:     "sino"
MIENTRAS: "mientras"
HACER:    "hacer"
PARA:     "para"
SEGUN:    "segun"
CASO:     "caso"
DEFECTO:  "defecto"
ROMPER:   "romper"
NO:       "no"
LOG_OP:   "y" | "o"

REL_OP:   "==" | "!=" | "<=" | ">=" | "<" | ">"
EQUAL.2:  "="
PLUS.2:   "+"
MINUS.2:  "-"
STAR.2:   "*"
SLASH:    "/"
PERCENT.2:"%"

LPAR:     "("
RPAR:     ")"
LBRACE:   "{"
RBRACE:   "}"
SEMICOLON:";"
COLON:    ":"

DECIMAL.2:/\d+\.\d+/
ENTERO:   /\d+/
NAME:     /[a-zA-Z_][a-zA-Z0-9_]*/

%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/
%ignore /\/\*.*?\*\//s
"""


# ============================================================
# GRAMÁTICA ESTRUCTURAL  (análisis sintáctico)
#
# Expresiones y condiciones unificadas en una jerarquía
# de precedencia:  o  <  y  <  no  <  cmp  <  add  <  mul  <  unary
# Esto evita ambigüedades con "(" en LALR.
# ============================================================
PARSER_GRAMMAR = r"""
start: sentencia*

?sentencia: declaracion ";"
           | asignacion ";"
           | impresion ";"
           | si
           | mientras
           | hacer_mientras ";"
           | para
           | segun

declaracion: TYPE NAME              -> decl
           | TYPE NAME "=" expr     -> decl

asignacion: NAME "=" expr           -> assign

impresion: "imprimir" "(" expr ")"  -> print_stmt

si: "si" "(" expr ")" bloque                 -> if_stmt
  | "si" "(" expr ")" bloque "sino" bloque   -> if_stmt

mientras: "mientras" "(" expr ")" bloque     -> while_stmt

hacer_mientras: "hacer" bloque "mientras" "(" expr ")"  -> do_while_stmt

para: "para" "(" for_init ";" expr ";" for_update ")" bloque -> for_stmt

for_init: declaracion_for  -> for_init
         | asignacion       -> for_init

declaracion_for: TYPE NAME          -> decl_in_for
               | TYPE NAME "=" expr -> decl_in_for

for_update: asignacion -> for_update

segun: "segun" "(" expr ")" "{" caso* defecto? "}"  -> switch_stmt

caso: "caso" literal ":" sentencia* "romper" ";"    -> case_block

defecto: "defecto" ":" sentencia*                   -> default_block

bloque: "{" sentencia* "}"  -> block

// ---- Jerarquía de expresiones/condiciones ----------------
?expr: expr "o" expr_y   -> logic_o
      | expr_y

?expr_y: expr_y "y" expr_no  -> logic_y
        | expr_no

?expr_no: "no" expr_no   -> not_
         | expr_cmp

?expr_cmp: expr_add REL_OP expr_add  -> rel
          | expr_add

?expr_add: expr_add "+" expr_mul  -> add
          | expr_add "-" expr_mul  -> sub
          | expr_mul

?expr_mul: expr_mul "*"  expr_unary  -> mul
          | expr_mul "/"  expr_unary  -> div
          | expr_mul "%"  expr_unary  -> mod
          | expr_unary

?expr_unary: "-" expr_unary  -> neg
            | "leer" "(" ")" -> read
            | atom

?atom: literal
      | NAME  -> var
      | "(" expr ")"

?literal: DECIMAL  -> decimal
         | ENTERO   -> entero
         | STRING   -> string
         | BOOLEAN  -> boolean

// ---- Terminales ------------------------------------------
TYPE.2:    "entero" | "decimal" | "texto" | "booleano"
BOOLEAN.2: "verdadero" | "falso"
REL_OP:    "==" | "!=" | "<=" | ">=" | "<" | ">"
DECIMAL.2: /\d+\.\d+/
ENTERO:    /\d+/
NAME:      /[a-zA-Z_][a-zA-Z0-9_]*/

%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/
%ignore /\/\*.*?\*\//s
"""


# ============================================================
# TABLA DE NOMBRES DE TOKENS  (análisis léxico)
# ============================================================
TOKEN_NAMES: dict[str, str] = {
    "TYPE":      "TIPO_DATO",
    "NAME":      "IDENTIFICADOR",
    "ENTERO":    "ENTERO",
    "DECIMAL":   "DECIMAL",
    "STRING":    "TEXTO",
    "BOOLEAN":   "BOOLEANO",
    "REL_OP":    "OP_RELACIONAL",
    "LOG_OP":    "OP_LOGICO",
    "EQUAL":     "ASIGNACION",
    "PLUS":      "OP_ARITMETICO",
    "MINUS":     "OP_ARITMETICO",
    "STAR":      "OP_ARITMETICO",
    "SLASH":     "OP_ARITMETICO",
    "PERCENT":   "OP_ARITMETICO",
    "LPAR":      "PAR_ABRE",
    "RPAR":      "PAR_CIERRA",
    "LBRACE":    "LLAVE_ABRE",
    "RBRACE":    "LLAVE_CIERRA",
    "SEMICOLON": "PUNTO_COMA",
    "COLON":     "DOS_PUNTOS",
    "IMPRIMIR":  "IMPRIMIR",
    "LEER":      "LEER",
    "SI":        "SI",
    "SINO":      "SINO",
    "MIENTRAS":  "MIENTRAS",
    "HACER":     "HACER",
    "PARA":      "PARA",
    "SEGUN":     "SEGUN",
    "CASO":      "CASO",
    "DEFECTO":   "DEFECTO",
    "ROMPER":    "ROMPER",
    "NO":        "NO",
}

_RESERVADAS: dict[str, str] = {
    "si": "SI", "sino": "SINO", "mientras": "MIENTRAS", "hacer": "HACER",
    "para": "PARA", "segun": "SEGUN", "caso": "CASO", "defecto": "DEFECTO",
    "romper": "ROMPER", "imprimir": "IMPRIMIR", "leer": "LEER",
    "no": "NO", "y": "OP_LOGICO", "o": "OP_LOGICO",
    "entero": "TIPO_DATO", "decimal": "TIPO_DATO",
    "texto": "TIPO_DATO", "booleano": "TIPO_DATO",
    "verdadero": "BOOLEANO", "falso": "BOOLEANO",
}

_SIMBOLOS: dict[str, str] = {
    "=": "ASIGNACION", "+": "OP_ARITMETICO", "-": "OP_ARITMETICO",
    "*": "OP_ARITMETICO", "/": "OP_ARITMETICO", "%": "OP_ARITMETICO",
    "(": "PAR_ABRE", ")": "PAR_CIERRA", "{": "LLAVE_ABRE", "}": "LLAVE_CIERRA",
    ";": "PUNTO_COMA", ":": "DOS_PUNTOS",
    "==": "OP_RELACIONAL", "!=": "OP_RELACIONAL",
    "<=": "OP_RELACIONAL", ">=": "OP_RELACIONAL",
    "<":  "OP_RELACIONAL", ">":  "OP_RELACIONAL",
}


def normalizar_token(tok: Token) -> str:
    texto = str(tok)
    if texto in _RESERVADAS:
        return _RESERVADAS[texto]
    if texto in _SIMBOLOS:
        return _SIMBOLOS[texto]
    return TOKEN_NAMES.get(tok.type, tok.type)


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class LexicalErrorInfo:
    numero: int
    linea: int
    columna: int
    lexema: str
    descripcion: str
    sugerencia: str


@dataclass
class SyntacticErrorInfo:
    numero: int
    linea: int
    columna: int
    descripcion: str
    sugerencia: str
    contexto: str


@dataclass
class SemanticErrorInfo:
    numero: int
    linea: int
    columna: int
    variable: str
    descripcion: str
    sugerencia: str


@dataclass
class SymbolInfo:
    numero: int
    nombre: str
    tipo_estructura: str
    tipo_dato: str
    linea: int
    valor_inicial: Optional[str]


# ============================================================
# ANÁLISIS LÉXICO
# ============================================================

def analizar_lexico(program_text: str) -> tuple[list[dict], list[LexicalErrorInfo]]:
    parser = Lark(LEXER_GRAMMAR, parser=None, lexer="contextual",
                  propagate_positions=True)
    tokens: list[dict] = []
    errores: list[LexicalErrorInfo] = []

    try:
        for i, tok in enumerate(parser.lex(program_text), start=1):
            tokens.append({
                "no":       i,
                "linea":    tok.line,
                "columna":  tok.column,
                "token":    normalizar_token(tok),
                "lexema":   tok.value,
                "tipo_lark": tok.type,
            })
    except UnexpectedInput as e:
        linea   = getattr(e, "line", 0)
        columna = getattr(e, "column", 0)
        lexema  = "desconocido"
        lineas  = program_text.splitlines()
        if linea > 0 and linea <= len(lineas):
            fila = lineas[linea - 1]
            if 1 <= columna <= len(fila):
                lexema = fila[columna - 1]

        errores.append(LexicalErrorInfo(
            numero=1, linea=linea, columna=columna, lexema=lexema,
            descripcion="Símbolo o secuencia no reconocida por el lenguaje.",
            sugerencia="Verifica caracteres especiales, cadenas sin cerrar o identificadores mal escritos.",
        ))

    return tokens, errores


# ============================================================
# ANÁLISIS SINTÁCTICO
# ============================================================

_PARSER_CACHE: Optional[Lark] = None


def _get_parser() -> Lark:
    global _PARSER_CACHE
    if _PARSER_CACHE is None:
        _PARSER_CACHE = Lark(
            PARSER_GRAMMAR, parser="lalr", lexer="contextual",
            propagate_positions=True,
        )
    return _PARSER_CACHE


def analizar_sintactico(code: str) -> tuple[Optional[Tree], list[SyntacticErrorInfo]]:
    errores: list[SyntacticErrorInfo] = []
    try:
        tree = _get_parser().parse(code)
        return tree, errores
    except UnexpectedInput as e:
        linea   = getattr(e, "line", 0)
        columna = getattr(e, "column", 0)
        contexto = ""
        try:
            contexto = e.get_context(code)
        except Exception:
            pass
        errores.append(SyntacticErrorInfo(
            numero=1, linea=linea, columna=columna,
            descripcion="Error de sintaxis: construcción no válida.",
            sugerencia=_sugerencia_sintactica(e),
            contexto=contexto,
        ))
        return None, errores
    except Exception as e:
        errores.append(SyntacticErrorInfo(
            numero=1, linea=0, columna=0,
            descripcion=f"Error inesperado: {e}",
            sugerencia="Revisa la estructura general del programa.",
            contexto="",
        ))
        return None, errores


def _sugerencia_sintactica(e: UnexpectedInput) -> str:
    exp = str(getattr(e, "expected", ""))
    if "SEMICOLON" in exp:
        return "Falta un punto y coma ';' al final de la sentencia."
    if "RBRACE" in exp:
        return "Falta una llave de cierre '}'."
    if "RPAR" in exp:
        return "Falta un paréntesis de cierre ')'."
    if "LBRACE" in exp:
        return "Se esperaba '{' para iniciar un bloque."
    if "LPAR" in exp:
        return "Se esperaba '(' después de la palabra clave."
    if "REL_OP" in exp:
        return "Se esperaba un operador relacional (==, !=, <, >, <=, >=)."
    if "NAME" in exp:
        return "Se esperaba un identificador (nombre de variable)."
    if "TYPE" in exp:
        return "Se esperaba un tipo de dato: entero, decimal, texto o booleano."
    if "$END" in exp:
        return "El programa tiene tokens inesperados al final."
    return "Verifica la estructura de la sentencia en esta línea."


# ============================================================
# TABLA DE SÍMBOLOS
# ============================================================

class SymbolTableBuilder:
    def __init__(self) -> None:
        self._symbols: list[SymbolInfo] = []
        self._counter = 0

    def build(self, tree: Tree) -> list[SymbolInfo]:
        self._symbols = []
        self._counter = 0
        self._walk(tree)
        return self._symbols

    def _walk(self, node: Any) -> None:
        if not isinstance(node, Tree):
            return
        if node.data == "decl":
            self._add(node, "Variable")
        elif node.data == "decl_in_for":
            self._add(node, "Variable (para)")
        for child in node.children:
            self._walk(child)

    def _add(self, node: Tree, estructura: str) -> None:
        self._counter += 1
        tipo_tok   = node.children[0]
        nombre_tok = node.children[1]
        linea      = getattr(nombre_tok, "line", 0)
        valor      = "<expresión>" if len(node.children) > 2 else None
        self._symbols.append(SymbolInfo(
            numero=self._counter,
            nombre=str(nombre_tok),
            tipo_estructura=estructura,
            tipo_dato=str(tipo_tok),
            linea=linea,
            valor_inicial=valor,
        ))


# ============================================================
# ANÁLISIS SEMÁNTICO  (4 reglas)
# ============================================================

class SemanticAnalyzer:
    """
    Regla 1 – Variable usada sin declarar.
    Regla 2 – Variable redeclarada en el mismo ámbito.
    Regla 3 – Tipo incompatible en declaración/asignación.
    Regla 4 – División por literal cero.
    """

    def __init__(self) -> None:
        self._errores: list[SemanticErrorInfo] = []
        self._tabla:   dict[str, str]          = {}
        self._counter  = 0

    def analyze(self, tree: Tree) -> list[SemanticErrorInfo]:
        self._errores = []
        self._tabla   = {}
        self._counter = 0
        self._walk(tree)
        return self._errores

    # ---- recorrido del árbol ----

    def _walk(self, node: Any) -> None:
        if not isinstance(node, Tree):
            return

        if node.data in ("decl", "decl_in_for"):
            self._check_decl(node)
            if len(node.children) > 2:
                self._walk(node.children[2])
            return

        if node.data == "assign":
            self._check_assign(node)
        elif node.data == "var":
            self._check_var(node)
        elif node.data == "div":
            self._check_div(node)

        for child in node.children:
            self._walk(child)

    # ---- regla 1 + 2 (decl) ----

    def _check_decl(self, node: Tree) -> None:
        tipo       = str(node.children[0])
        nombre_tok = node.children[1]
        nombre     = str(nombre_tok)
        linea      = getattr(nombre_tok, "line", 0)

        if nombre in self._tabla:
            self._add(linea, nombre,
                f"Regla 2 – Variable '{nombre}' ya fue declarada anteriormente.",
                f"Usa un nombre diferente o elimina la declaración duplicada de '{nombre}'.")
        else:
            self._tabla[nombre] = tipo

        if len(node.children) > 2:
            expr_tipo = self._infer(node.children[2])
            if expr_tipo and not self._compatibles(tipo, expr_tipo):
                self._add(linea, nombre,
                    f"Regla 3 – Tipo incompatible: '{nombre}' es '{tipo}' pero la expresión es '{expr_tipo}'.",
                    f"Asigna un valor de tipo '{tipo}' a la variable '{nombre}'.")

    # ---- regla 3 (assign) ----

    def _check_assign(self, node: Tree) -> None:
        nombre_tok = node.children[0]
        nombre     = str(nombre_tok)
        linea      = getattr(nombre_tok, "line", 0)
        if nombre not in self._tabla:
            return
        expr_tipo = self._infer(node.children[1])
        tipo_dec  = self._tabla[nombre]
        if expr_tipo and not self._compatibles(tipo_dec, expr_tipo):
            self._add(linea, nombre,
                f"Regla 3 – Tipo incompatible: '{nombre}' es '{tipo_dec}' pero la expresión es '{expr_tipo}'.",
                f"Verifica el tipo de la expresión asignada a '{nombre}'.")

    # ---- regla 1 (var) ----

    def _check_var(self, node: Tree) -> None:
        nombre_tok = node.children[0]
        nombre     = str(nombre_tok)
        linea      = getattr(nombre_tok, "line", 0)
        if nombre not in self._tabla:
            self._add(linea, nombre,
                f"Regla 1 – Variable '{nombre}' usada sin declarar.",
                f"Declara '{nombre}' antes de usarla, p. ej.: 'entero {nombre} = 0;'")

    # ---- regla 4 (div) ----

    def _check_div(self, node: Tree) -> None:
        right = node.children[1]
        if not isinstance(right, Tree):
            return
        zero = False
        tok  = None
        if right.data == "entero":
            tok  = right.children[0]
            zero = str(tok) == "0"
        elif right.data == "decimal":
            tok = right.children[0]
            try:
                zero = float(str(tok)) == 0.0
            except ValueError:
                pass
        if zero and tok is not None:
            linea = getattr(tok, "line", 0)
            self._add(linea, str(tok),
                "Regla 4 – División por literal cero detectada.",
                "El divisor no puede ser cero. Usa una variable o verifica el valor.")

    # ---- inferencia de tipo ----

    def _infer(self, node: Any) -> Optional[str]:
        if not isinstance(node, Tree):
            return None
        if node.data == "entero":
            return "entero"
        if node.data == "decimal":
            return "decimal"
        if node.data == "string":
            return "texto"
        if node.data == "boolean":
            return "booleano"
        if node.data == "var":
            return self._tabla.get(str(node.children[0]))
        if node.data in ("add", "sub"):
            t1 = self._infer(node.children[0])
            t2 = self._infer(node.children[1])
            if "texto"   in (t1, t2): return "texto"
            if "decimal" in (t1, t2): return "decimal"
            return "entero"
        if node.data in ("mul", "div", "mod"):
            t1 = self._infer(node.children[0])
            t2 = self._infer(node.children[1])
            if "decimal" in (t1, t2): return "decimal"
            return "entero"
        if node.data == "neg":
            return self._infer(node.children[0])
        if node.data in ("rel", "logic_o", "logic_y", "not_"):
            return "booleano"
        return None

    @staticmethod
    def _compatibles(esperado: str, actual: str) -> bool:
        if esperado == actual:
            return True
        if esperado == "decimal" and actual == "entero":
            return True
        if esperado == "texto":
            return True
        return False

    def _add(self, linea: int, variable: str, descripcion: str, sugerencia: str) -> None:
        self._counter += 1
        self._errores.append(SemanticErrorInfo(
            numero=self._counter, linea=linea, columna=0,
            variable=variable, descripcion=descripcion, sugerencia=sugerencia,
        ))


# ============================================================
# FORMATO DEL ÁRBOL SINTÁCTICO
# ============================================================

def format_tree(node: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if isinstance(node, Token):
        return f"{prefix}[{node.type}] {repr(str(node))}\n"
    if isinstance(node, Tree):
        result = f"{prefix}({node.data})\n"
        for child in node.children:
            result += format_tree(child, indent + 1)
        return result
    return f"{prefix}{repr(node)}\n"


# ============================================================
# INTÉRPRETE
# ============================================================

@dataclass
class Env:
    values: Dict[str, Any]
    types:  Dict[str, str]


class CScriptInterpreter(Interpreter):
    def __init__(self) -> None:
        super().__init__()
        self.env = Env(values={}, types={})

    # ---- helpers ----

    def _coerce(self, declared_type: Optional[str], value: Any) -> Any:
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if declared_type is None:
            return value
        if declared_type == "entero":
            return int(float(value))
        if declared_type == "decimal":
            return float(value)
        if declared_type == "texto":
            return str(value)
        if declared_type == "booleano":
            if isinstance(value, str):
                v = value.strip().lower()
                if v == "verdadero": return True
                if v == "falso":     return False
                raise RuntimeError("Valor inválido para booleano (usa verdadero/falso).")
            return bool(value)
        return value

    def _eval(self, node: Any) -> Any:
        if isinstance(node, list):
            return self._eval(node[0]) if len(node) == 1 else [self._eval(x) for x in node]
        if isinstance(node, Tree):
            method = getattr(self, node.data, None)
            if method is None:
                raise RuntimeError(f"Sin handler para nodo: {node.data}")
            return method(node)
        if isinstance(node, Token):
            if node.type == "ENTERO":   return int(str(node))
            if node.type == "DECIMAL":  return float(str(node))
            if node.type == "STRING":   return str(node)[1:-1]
            if node.type == "BOOLEAN":  return str(node) == "verdadero"
            if node.type == "NAME":
                name = str(node)
                if name not in self.env.values:
                    raise RuntimeError(f"Variable no definida: {name}")
                return self.env.values[name]
            return str(node)
        return node

    # ---- literales ----

    def entero(self, t: Tree) -> int:   return int(str(t.children[0]))
    def decimal(self, t: Tree) -> float: return float(str(t.children[0]))
    def string(self,  t: Tree) -> str:  return str(t.children[0])[1:-1]
    def boolean(self, t: Tree) -> bool: return str(t.children[0]) == "verdadero"

    def var(self, t: Tree) -> Any:
        name = str(t.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no definida: {name}")
        return self.env.values[name]

    def read(self, t: Tree) -> str:
        return input("> ")

    # ---- aritmética ----

    def add(self, t: Tree) -> Any: return self._eval(t.children[0]) + self._eval(t.children[1])
    def sub(self, t: Tree) -> Any: return self._eval(t.children[0]) - self._eval(t.children[1])
    def mul(self, t: Tree) -> Any: return self._eval(t.children[0]) * self._eval(t.children[1])
    def div(self, t: Tree) -> Any: return self._eval(t.children[0]) / self._eval(t.children[1])
    def mod(self, t: Tree) -> Any: return self._eval(t.children[0]) % self._eval(t.children[1])
    def neg(self, t: Tree) -> Any: return -self._eval(t.children[0])

    # ---- condiciones ----

    def rel(self, t: Tree) -> bool:
        l, op, r = self._eval(t.children[0]), str(t.children[1]), self._eval(t.children[2])
        return {
            "==": l == r, "!=": l != r, "<": l < r,
            ">":  l > r,  "<=": l <= r, ">=": l >= r,
        }.get(op, False)

    def not_(self,    t: Tree) -> bool: return not bool(self._eval(t.children[0]))
    def logic_o(self, t: Tree) -> bool: return bool(self._eval(t.children[0])) or  bool(self._eval(t.children[1]))
    def logic_y(self, t: Tree) -> bool: return bool(self._eval(t.children[0])) and bool(self._eval(t.children[1]))

    # ---- sentencias básicas ----

    def decl(self, t: Tree) -> None:
        tipo   = str(t.children[0])
        name   = str(t.children[1])
        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")
        self.env.types[name] = tipo
        if len(t.children) == 2:
            self.env.values[name] = {"entero": 0, "decimal": 0.0, "texto": "", "booleano": False}.get(tipo)
        else:
            self.env.values[name] = self._coerce(tipo, self._eval(t.children[2]))

    def assign(self, t: Tree) -> None:
        name = str(t.children[0])
        if name not in self.env.values:
            raise RuntimeError(f"Variable no declarada: {name}")
        self.env.values[name] = self._coerce(self.env.types.get(name), self._eval(t.children[1]))

    def print_stmt(self, t: Tree) -> None:
        print(self._eval(t.children[0]))

    def block(self, t: Tree) -> None:
        for stmt in t.children:
            self.visit(stmt)

    # ---- control de flujo ----

    def if_stmt(self, t: Tree) -> None:
        ok = bool(self._eval(t.children[0]))
        if ok:
            self.visit(t.children[1])
        elif len(t.children) > 2:
            self.visit(t.children[2])

    def while_stmt(self, t: Tree) -> None:
        while bool(self._eval(t.children[0])):
            self.visit(t.children[1])

    def do_while_stmt(self, t: Tree) -> None:
        while True:
            self.visit(t.children[0])
            if not bool(self._eval(t.children[1])):
                break

    # ---- para ----

    def decl_in_for(self, t: Tree) -> None:
        tipo = str(t.children[0])
        name = str(t.children[1])
        if name in self.env.values:
            raise RuntimeError(f"Variable ya declarada: {name}")
        self.env.types[name] = tipo
        if len(t.children) == 2:
            self.env.values[name] = {"entero": 0, "decimal": 0.0, "texto": "", "booleano": False}.get(tipo)
        else:
            self.env.values[name] = self._coerce(tipo, self._eval(t.children[2]))

    def for_init(self, t: Tree) -> None:
        self.visit(t.children[0])

    def for_update(self, t: Tree) -> None:
        self.visit(t.children[0])

    def for_stmt(self, t: Tree) -> None:
        parts      = list(t.children)
        block_tree = parts[-1]
        header     = parts[:-1]

        def is_init(n):
            return isinstance(n, Tree) and n.data in ("for_init", "decl_in_for", "decl", "assign")
        def is_update(n):
            return isinstance(n, Tree) and n.data in ("for_update", "assign")

        init = cond = update = None
        if len(header) == 1:
            init = header[0] if is_init(header[0]) else None
            if init is None: cond = header[0]
        elif len(header) == 2:
            if is_init(header[0]):
                init = header[0]
                update = header[1] if is_update(header[1]) else None
                if update is None: cond = header[1]
            else:
                cond, update = header[0], header[1]
        elif len(header) == 3:
            init, cond, update = header

        if init   is not None: self.visit(init)
        while True:
            if cond is not None and not bool(self._eval(cond)): break
            self.visit(block_tree)
            if update is not None: self.visit(update)

    # ---- segun ----

    def switch_stmt(self, t: Tree) -> None:
        target = self._eval(t.children[0])
        blocks = t.children[1:]
        default_b = next((b for b in blocks if isinstance(b, Tree) and b.data == "default_block"), None)
        for b in blocks:
            if not isinstance(b, Tree) or b.data != "case_block": continue
            if target == self._eval(b.children[0]):
                for s in b.children[1:]: self.visit(s)
                return
        if default_b is not None:
            for s in default_b.children: self.visit(s)

    def case_block(self,    t: Tree) -> Tree: return t
    def default_block(self, t: Tree) -> Tree: return t


# ============================================================
# PUNTO DE ENTRADA  (terminal)
# ============================================================

def run(program_text: str) -> None:
    _, lex_err = analizar_lexico(program_text)
    if lex_err:
        for e in lex_err:
            print(f"[ERROR LÉXICO] Línea {e.linea}: {e.descripcion}")
        return

    tree, syn_err = analizar_sintactico(program_text)
    if syn_err:
        for e in syn_err:
            print(f"[ERROR SINTÁCTICO] Línea {e.linea}: {e.descripcion}")
        return

    sem_err = SemanticAnalyzer().analyze(tree)
    if sem_err:
        for e in sem_err:
            print(f"[ERROR SEMÁNTICO] Línea {e.linea}: {e.descripcion}")

    CScriptInterpreter().visit(tree)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "programa.csc"
    with open(path, encoding="utf-8") as f:
        run(f.read())
