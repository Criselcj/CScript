from __future__ import annotations

import re
import threading
import tkinter as tk
import ctypes
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from lark import Token, Tree

from cscript import (
    CScriptInterpreter,
    LexicalErrorInfo,
    SyntacticErrorInfo,
    SemanticErrorInfo,
    SymbolInfo,
    analizar_lexico,
    analizar_sintactico,
    SemanticAnalyzer,
    SymbolTableBuilder,
    format_tree,
)


# ---------------------------------------------------------------------------
# Constantes de color
# ---------------------------------------------------------------------------
KEYWORDS = [
    "si", "sino", "mientras", "hacer", "para", "segun", "caso",
    "defecto", "romper", "imprimir", "leer", "no", "y", "o",
    "entero", "decimal", "texto", "booleano", "verdadero", "falso",
]

BG      = "#1e1e1e"
BG2     = "#252526"
BG3     = "#2d2d30"
FG      = "#d4d4d4"
ACCENT  = "#007acc"
GREEN   = "#4ec9b0"
ORANGE  = "#ce9178"
BLUE    = "#569cd6"
COMMENT = "#6a9955"
NUMBER  = "#b5cea8"
RED     = "#f44747"
YELLOW  = "#dcdcaa"


# ---------------------------------------------------------------------------
# Árbol gráfico estilo libro de texto
# Nodos: etiquetas <regla> y valores de token sin cajas
# Aristas: líneas amarillas rectas (como el ejemplo del slide)
# ---------------------------------------------------------------------------

# Mapeo nombre interno → etiqueta con corchetes angulares (BNF)
_RULE_LABEL: dict[str, str] = {
    "start":         "<programa>",
    "decl":          "<declaracion>",
    "assign":        "<asignacion>",
    "print_stmt":    "<impresion>",
    "if_stmt":       "<si>",
    "while_stmt":    "<mientras>",
    "do_while_stmt": "<hacer_mientras>",
    "for_stmt":      "<para>",
    "for_init":      "<inicio_for>",
    "for_update":    "<actualizacion_for>",
    "decl_in_for":   "<decl_for>",
    "switch_stmt":   "<segun>",
    "case_block":    "<caso>",
    "default_block": "<defecto>",
    "block":         "<bloque>",
    "rel":           "<condicion>",
    "logic_o":       "<condicion>",
    "logic_y":       "<condicion>",
    "not_":          "<condicion>",
    "add":           "<expresion>",
    "sub":           "<expresion>",
    "mul":           "<termino>",
    "div":           "<termino>",
    "mod":           "<termino>",
    "neg":           "<factor>",
    "var":           "<identificador>",
    "entero":        "<entero>",
    "decimal":       "<decimal>",
    "string":        "<texto>",
    "boolean":       "<booleano>",
    "read":          "<leer>",
}


class ParseTreeCanvas:
    """
    Arbol de parseo estilo libro de texto:
      * Nodos internos  ->  <nombre_regla>  en cian
      * Nodos hoja      ->  valor del token  en blanco
      * Aristas         ->  lineas amarillas rectas
      * Sin cajas: solo texto y lineas
    """

    FONT_INT = ("Consolas", 10, "bold")   # nodos de regla
    FONT_TOK = ("Consolas", 10)           # tokens hoja

    CLR_LINE = "#505050"   # gris oscuro  (aristas)
    CLR_INT  = "#4a9ede"   # azul         (nodos de regla)
    CLR_TOK  = "#ce9178"   # naranja      (tokens hoja)
    CLR_ROOT = "#4ec9b0"   # verde teal   (raiz <programa>)
    CLR_BG   = "#1e1e1e"   # fondo oscuro

    H_MARGIN = 20    # espacio horizontal a cada lado del texto
    V_GAP    = 90    # distancia vertical entre niveles
    TXT_H    = 8     # offset desde centro del texto hasta extremo de la linea
    CHAR_PX  = 7     # pixeles por caracter (Consolas 10)

    def __init__(self, parent: tk.Widget) -> None:
        self._vbar = tk.Scrollbar(parent, orient=tk.VERTICAL)
        self._hbar = tk.Scrollbar(parent, orient=tk.HORIZONTAL)
        self._cv   = tk.Canvas(parent, bg=self.CLR_BG, highlightthickness=0,
                               yscrollcommand=self._vbar.set,
                               xscrollcommand=self._hbar.set)
        self._vbar.config(command=self._cv.yview)
        self._hbar.config(command=self._cv.xview)
        self._vbar.pack(side=tk.RIGHT,  fill=tk.Y)
        self._hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self._cv.pack(fill=tk.BOTH, expand=True)

        self._cv.bind("<MouseWheel>",
                      lambda e: self._cv.yview_scroll(int(-e.delta / 120), "units"))
        self._cv.bind("<Shift-MouseWheel>",
                      lambda e: self._cv.xview_scroll(int(-e.delta / 120), "units"))

    # ── API publica ───────────────────────────────────────────────────────

    def clear(self) -> None:
        self._cv.delete("all")
        self._cv.config(scrollregion=(0, 0, 100, 100))

    def draw(self, tree) -> None:
        self._cv.delete("all")
        if tree is None:
            return

        widths: dict = {}
        self._calc_widths(tree, widths)

        pos: dict = {}
        self._layout(tree, 24, 30, widths, pos)

        # aristas primero (quedan detras del texto)
        self._draw_edges(tree, pos)
        self._draw_nodes(tree, pos)

        self._cv.update_idletasks()
        bb = self._cv.bbox("all")
        if bb:
            x1, y1, x2, y2 = bb
            self._cv.config(scrollregion=(x1 - 20, y1 - 20, x2 + 20, y2 + 20))

    # ── etiqueta de cada nodo ─────────────────────────────────────────────

    def _label(self, node) -> tuple[str, bool]:
        """(texto_visible, es_token)"""
        if isinstance(node, Token):
            return str(node), True
        lbl = _RULE_LABEL.get(node.data, f"<{node.data}>")
        return lbl, False

    def _text_w(self, text: str) -> int:
        return len(text) * self.CHAR_PX + self.H_MARGIN * 2

    # ── calcular ancho de cada subarbol ───────────────────────────────────

    def _calc_widths(self, node, out: dict) -> int:
        text, _ = self._label(node)
        own = self._text_w(text)

        if isinstance(node, Token) or not node.children:
            out[id(node)] = own
            return own

        kids_total = sum(self._calc_widths(c, out) for c in node.children)
        total = max(own, kids_total)
        out[id(node)] = total
        return total

    # ── asignar posiciones (x, y) a cada nodo ────────────────────────────

    def _layout(self, node, lx: int, y: int,
                widths: dict, pos: dict) -> None:
        cx = lx + widths[id(node)] // 2
        pos[id(node)] = (cx, y)

        if isinstance(node, Token) or not node.children:
            return

        child_x = lx
        next_y  = y + self.V_GAP
        for child in node.children:
            self._layout(child, child_x, next_y, widths, pos)
            child_x += widths[id(child)]

    # ── dibujar aristas amarillas ─────────────────────────────────────────

    def _draw_edges(self, node, pos: dict) -> None:
        if isinstance(node, Token) or not node.children:
            return
        px, py = pos[id(node)]
        for child in node.children:
            cx, cy = pos[id(child)]
            self._cv.create_line(
                px, py + self.TXT_H,
                cx, cy - self.TXT_H,
                fill=self.CLR_LINE, width=1.8,
            )
            self._draw_edges(child, pos)

    # ── dibujar nodos (solo texto) ────────────────────────────────────────

    def _draw_nodes(self, node, pos: dict) -> None:
        text, is_tok = self._label(node)
        cx, cy = pos[id(node)]

        if is_tok:
            color = self.CLR_TOK
            font  = self.FONT_TOK
        elif node.data == "start":
            color = self.CLR_ROOT
            font  = self.FONT_INT
        else:
            color = self.CLR_INT
            font  = self.FONT_INT

        self._cv.create_text(cx, cy, text=text, fill=color,
                              font=font, anchor=tk.CENTER)

        if not isinstance(node, Token):
            for child in node.children:
                self._draw_nodes(child, pos)


# ---------------------------------------------------------------------------
# Intérprete con I/O redirigida a la GUI
# ---------------------------------------------------------------------------

class GUICScriptInterpreter(CScriptInterpreter):
    def __init__(self, output_fn, input_fn):
        super().__init__()
        self._output = output_fn
        self._input  = input_fn

    def print_stmt(self, tree):
        self._output(str(self._eval(tree.children[0])) + "\n")

    def read(self, tree):
        return self._input()


# ---------------------------------------------------------------------------
# IDE principal
# ---------------------------------------------------------------------------

class CScriptIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CScript IDE")
        self.iconbitmap("cscript.ico")
        self.geometry("1300x760")
        self.minsize(960, 580)
        self.configure(bg=BG)

        self._current_file: Optional[str] = None
        self._running       = False
        self._debounce_id   = None   # id del after() pendiente para live-analysis
        self._last_tree     = None   # último árbol parseado con éxito

        self._build_ui()
        self._apply_theme()
        self._setup_bindings()
        self._update_line_numbers()

    # -----------------------------------------------------------------------
    # Construcción de UI
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self._build_toolbar()
        self._build_main_area()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG3, pady=4)
        bar.pack(side=tk.TOP, fill=tk.X)

        def tbtn(text, cmd):
            b = tk.Button(bar, text=text, command=cmd,
                          bg=BG3, fg=FG, relief=tk.FLAT,
                          activebackground="#3e3e42", activeforeground=FG,
                          padx=10, pady=3, font=("Segoe UI", 9))
            b.pack(side=tk.LEFT, padx=2)
            return b

        def sep():
            tk.Frame(bar, bg="#555", width=1).pack(
                side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        tbtn("Nuevo",        self._new_file)
        tbtn("Abrir",        self._open_file)
        tbtn("Guardar",      self._save_file)
        tbtn("Guardar como", self._save_as_file)
        sep()
        self.btn_analyze = tk.Button(
            bar, text="▶ Analizar", command=self._analyze_full,
            bg="#0e7a0d", fg="white", relief=tk.FLAT,
            activebackground="#1a9918", activeforeground="white",
            padx=12, pady=3, font=("Segoe UI", 9, "bold"),
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=2)
        sep()
        tbtn("Limpiar salida", self._clear_output)

    def _build_main_area(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               sashwidth=5, sashrelief=tk.FLAT, bg=BG3)
        paned.pack(fill=tk.BOTH, expand=True)

        # ── editor ──────────────────────────────────────────────────────────
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=350)

        hdr = tk.Frame(left, bg=BG2, pady=3)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  Editor", bg=BG2, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_filename = tk.Label(hdr, text="sin título", bg=BG2,
                                     fg="#858585", font=("Segoe UI", 9))
        self.lbl_filename.pack(side=tk.LEFT, padx=8)

        inner = tk.Frame(left, bg=BG)
        inner.pack(fill=tk.BOTH, expand=True)

        self.line_nums = tk.Text(inner, width=4, padx=6, state=tk.DISABLED,
                                  takefocus=0, wrap=tk.NONE, cursor="arrow")
        self.line_nums.pack(side=tk.LEFT, fill=tk.Y)

        yscroll = tk.Scrollbar(inner, orient=tk.VERTICAL)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll = tk.Scrollbar(left, orient=tk.HORIZONTAL)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.editor = tk.Text(
            inner, wrap=tk.NONE, undo=True,
            font=("Consolas", 12),
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        yscroll.config(command=self._on_yscroll)
        xscroll.config(command=self.editor.xview)

        # ── panel derecho: notebook ─────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=400)
        paned.paneconfig(left, width=580)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_tokens_tab()    # 0
        self._build_errors_tab()    # 1
        self._build_symbols_tab()   # 2
        self._build_tree_tab()      # 3 – canvas gráfico
        self._build_console_tab()   # 4

    # ---- tabs ---------------------------------------------------------------

    def _build_tokens_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Tokens  ")

        cols = ("no", "linea", "col", "token", "lexema")
        self.token_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                        selectmode="browse")
        for col, hdr, w, anch in [
            ("no",     "#",        45,  tk.CENTER),
            ("linea",  "Línea",    65,  tk.CENTER),
            ("col",    "Col",      55,  tk.CENTER),
            ("token",  "Token",   175,  tk.W),
            ("lexema", "Lexema",  200,  tk.W),
        ]:
            self.token_tree.heading(col, text=hdr)
            self.token_tree.column(col, width=w, anchor=anch,
                                   stretch=(col == "lexema"))

        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL,   command=self.token_tree.yview)
        hsb = tk.Scrollbar(tab, orient=tk.HORIZONTAL, command=self.token_tree.xview)
        self.token_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.token_tree.pack(fill=tk.BOTH, expand=True)

        self.lbl_token_count = tk.Label(tab, text="", bg=BG2, fg="#858585",
                                         font=("Segoe UI", 9), pady=3)
        self.lbl_token_count.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_errors_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Errores  ")

        cols = ("tipo", "linea", "col", "lexema", "descripcion", "sugerencia")
        self.error_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                        selectmode="browse")
        for col, hdr, w in [
            ("tipo",        "Tipo",       88),
            ("linea",       "Línea",      60),
            ("col",         "Col",        50),
            ("lexema",      "Lexema",     90),
            ("descripcion", "Descripción",280),
            ("sugerencia",  "Sugerencia", 280),
        ]:
            self.error_tree.heading(col, text=hdr)
            self.error_tree.column(col, width=w, anchor=tk.W)

        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL, command=self.error_tree.yview)
        self.error_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.error_tree.pack(fill=tk.BOTH, expand=True)

        self.lbl_error_count = tk.Label(tab, text="", bg=BG2, fg="#858585",
                                         font=("Segoe UI", 9), pady=3)
        self.lbl_error_count.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_symbols_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Tabla de Símbolos  ")

        cols = ("no", "nombre", "estructura", "tipo", "linea", "valor")
        self.sym_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for col, hdr, w, anch in [
            ("no",         "#",               45,  tk.CENTER),
            ("nombre",     "Nombre",          130, tk.W),
            ("estructura", "Tipo Estructura", 145, tk.W),
            ("tipo",       "Tipo Dato",       110, tk.W),
            ("linea",      "Línea",            60, tk.CENTER),
            ("valor",      "Valor inicial",   130, tk.W),
        ]:
            self.sym_tree.heading(col, text=hdr)
            self.sym_tree.column(col, width=w, anchor=anch)

        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL, command=self.sym_tree.yview)
        self.sym_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sym_tree.pack(fill=tk.BOTH, expand=True)

        self.lbl_sym_count = tk.Label(tab, text="", bg=BG2, fg="#858585",
                                       font=("Segoe UI", 9), pady=3)
        self.lbl_sym_count.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_tree_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Árbol Sintáctico  ")
        self._tree_canvas = ParseTreeCanvas(tab)

    def _build_console_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Consola  ")

        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL)
        self.console = tk.Text(
            tab, state=tk.DISABLED, wrap=tk.WORD,
            font=("Consolas", 11), cursor="arrow",
            yscrollcommand=vsb.set,
        )
        vsb.config(command=self.console.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.pack(fill=tk.BOTH, expand=True)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=ACCENT, height=22)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Listo")
        self._status_lbl = tk.Label(bar, textvariable=self.status_var,
                                     bg=ACCENT, fg="white",
                                     font=("Segoe UI", 9), padx=8)
        self._status_lbl.pack(side=tk.LEFT, anchor=tk.CENTER)
        self.lbl_cursor = tk.Label(bar, text="Ln 1, Col 1",
                                    bg=ACCENT, fg="white",
                                    font=("Segoe UI", 9), padx=8)
        self.lbl_cursor.pack(side=tk.RIGHT, anchor=tk.CENTER)

    # -----------------------------------------------------------------------
    # Tema
    # -----------------------------------------------------------------------

    def _apply_theme(self):
        self.editor.configure(
            bg=BG, fg=FG, insertbackground="white",
            selectbackground="#264f78", selectforeground=FG,
            relief=tk.FLAT, borderwidth=0,
        )
        self.line_nums.configure(
            bg=BG2, fg="#555", relief=tk.FLAT, borderwidth=0,
            font=("Consolas", 12),
        )
        self.console.configure(bg="#0c0c0c", fg=FG, relief=tk.FLAT)

        # tags de sintaxis
        self.editor.tag_configure("keyword", foreground=BLUE)
        self.editor.tag_configure("string",  foreground=ORANGE)
        self.editor.tag_configure("comment", foreground=COMMENT)
        self.editor.tag_configure("number",  foreground=NUMBER)

        # tags de error en tiempo real
        self.editor.tag_configure(
            "error_char",
            background="#7a0000", foreground="white",
        )
        self.editor.tag_configure(
            "error_line",
            underline=True, foreground=RED,
        )
        # tag para error léxico (subrayado rojo más intenso)
        self.editor.tag_configure(
            "lex_err",
            background="#5c0000", underline=True,
        )

        # tags consola
        self.console.tag_configure("output",       foreground=FG)
        self.console.tag_configure("error",        foreground=RED)
        self.console.tag_configure("info",         foreground=GREEN)
        self.console.tag_configure("input_prompt", foreground=YELLOW)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=22, borderwidth=0)
        style.configure("Treeview.Heading",
                        background=BG3, foreground=FG, relief=tk.FLAT)
        style.map("Treeview",
                  background=[("selected", "#094771")],
                  foreground=[("selected", "white")])
        style.configure("TNotebook",     background=BG3, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground="#888",
                        padding=[12, 5], borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", FG)])

        for tv in (self.token_tree, self.error_tree, self.sym_tree):
            tv.tag_configure("odd",      background=BG)
            tv.tag_configure("even",     background=BG2)
            tv.tag_configure("sem_warn", background="#2a2000")

    # -----------------------------------------------------------------------
    # Bindings
    # -----------------------------------------------------------------------

    def _setup_bindings(self):
        self.editor.bind("<KeyRelease>",    self._on_edit)
        self.editor.bind("<ButtonRelease>", self._on_edit)
        self.editor.bind("<MouseWheel>",    self._on_mouse_wheel)
        self.bind("<F5>",        lambda e: self._run_code())
        self.bind("<Control-s>", lambda e: self._save_file())
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-n>", lambda e: self._new_file())

    def _on_yscroll(self, *args):
        self.editor.yview(*args)
        self._sync_line_nums()

    def _on_mouse_wheel(self, event=None):
        self.after_idle(self._sync_line_nums)

    def _on_edit(self, event=None):
        self._update_line_numbers()
        self._highlight_syntax()
        self._update_cursor_pos()
        self._schedule_live_analysis()

    def _update_cursor_pos(self):
        pos = self.editor.index(tk.INSERT)
        ln, col = pos.split(".")
        self.lbl_cursor.config(text=f"Ln {ln}, Col {int(col)+1}")

    # -----------------------------------------------------------------------
    # Análisis en tiempo real  (debounced 450 ms)
    # -----------------------------------------------------------------------

    def _schedule_live_analysis(self):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(450, self._live_analyze)

    def _live_analyze(self):
        """Análisis rápido mientras el usuario escribe. Solo actualiza el editor."""
        self._debounce_id = None
        code = self.editor.get("1.0", tk.END)

        # Limpiar marcas anteriores
        for tag in ("error_char", "error_line", "lex_err"):
            self.editor.tag_remove(tag, "1.0", tk.END)

        # ── 1. Léxico ────────────────────────────────────────────────────────
        _, lex_errors = analizar_lexico(code)
        if lex_errors:
            e = lex_errors[0]
            if e.linea > 0:
                col0 = max(0, e.columna - 1)
                col1 = col0 + max(1, len(e.lexema))
                self.editor.tag_add("lex_err",
                                    f"{e.linea}.{col0}",
                                    f"{e.linea}.{col1}")
            self._set_status(f"⚠ Error léxico — Línea {e.linea}: {e.sugerencia}",
                             "error")
            return

        # ── 2. Sintáctico ────────────────────────────────────────────────────
        tree, syn_errors = analizar_sintactico(code)
        if syn_errors:
            e = syn_errors[0]
            if e.linea > 0:
                col0 = max(0, e.columna - 1)
                # subrayar desde el punto de error hasta fin de línea
                self.editor.tag_add("error_line",
                                    f"{e.linea}.{col0}",
                                    f"{e.linea}.end")
            self._set_status(
                f"⚠ Error sintáctico — Línea {e.linea}: {e.sugerencia}", "error")
            return

        # ── 3. Semántico (ligero) ────────────────────────────────────────────
        sem_errors = SemanticAnalyzer().analyze(tree)
        if sem_errors:
            e = sem_errors[0]
            if e.linea > 0:
                self.editor.tag_add("error_line",
                                    f"{e.linea}.0", f"{e.linea}.end")
            self._set_status(
                f"⚠ Advertencia semántica — Línea {e.linea}: {e.descripcion}",
                "warning")
        else:
            self._set_status("✔ Sin errores", "ok")

    # -----------------------------------------------------------------------
    # Barra de estado
    # -----------------------------------------------------------------------

    def _set_status(self, msg: str, kind: str = "ok") -> None:
        colors = {
            "ok":      ("white",  ACCENT),
            "error":   ("white",  "#7a1500"),
            "warning": ("white",  "#6a5500"),
        }
        fg, bg = colors.get(kind, ("white", ACCENT))
        self.status_var.set(msg)
        self._status_lbl.config(fg=fg, bg=bg)
        self._status_lbl.master.config(bg=bg)

    # -----------------------------------------------------------------------
    # Numeración de líneas
    # -----------------------------------------------------------------------

    def _update_line_numbers(self):
        self.line_nums.config(state=tk.NORMAL)
        self.line_nums.delete("1.0", tk.END)
        total = int(self.editor.index(tk.END).split(".")[0]) - 1
        self.line_nums.insert("1.0",
                              "\n".join(str(i) for i in range(1, total + 1)))
        self.line_nums.config(state=tk.DISABLED)
        self._sync_line_nums()

    def _sync_line_nums(self):
        self.line_nums.yview_moveto(self.editor.yview()[0])

    # -----------------------------------------------------------------------
    # Resaltado de sintaxis
    # -----------------------------------------------------------------------

    def _highlight_syntax(self):
        content = self.editor.get("1.0", tk.END)
        for tag in ("keyword", "string", "comment", "number"):
            self.editor.tag_remove(tag, "1.0", tk.END)

        def tag(match, name):
            self.editor.tag_add(name,
                                f"1.0+{match.start()}c",
                                f"1.0+{match.end()}c")

        for m in re.finditer(r"/\*.*?\*/", content, re.DOTALL): tag(m, "comment")
        for m in re.finditer(r"//[^\n]*",  content):            tag(m, "comment")
        for m in re.finditer(r'"(?:[^"\\]|\\.)*"', content):    tag(m, "string")
        for m in re.finditer(r'\b\d+\.?\d*\b', content):        tag(m, "number")
        kw_pat = r'\b(' + '|'.join(KEYWORDS) + r')\b'
        for m in re.finditer(kw_pat, content):                   tag(m, "keyword")

    # -----------------------------------------------------------------------
    # Operaciones de archivo
    # -----------------------------------------------------------------------

    def _new_file(self):
        if messagebox.askyesno("Nuevo archivo",
                               "¿Descartar el contenido actual?", parent=self):
            self.editor.delete("1.0", tk.END)
            self._current_file = None
            self.lbl_filename.config(text="sin título")
            self.title("CScript IDE")
            self._on_edit()

    def _open_file(self):
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("CScript", "*.csc"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", content)
        self._current_file = path
        name = path.replace("\\", "/").split("/")[-1]
        self.lbl_filename.config(text=name)
        self.title(f"CScript IDE — {name}")
        self._on_edit()

    def _save_file(self):
        if self._current_file:
            with open(self._current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", tk.END))
            self._set_status(f"Guardado: {self._current_file}")
        else:
            self._save_as_file()

    def _save_as_file(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csc",
            filetypes=[("CScript", "*.csc"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        self._current_file = path
        name = path.replace("\\", "/").split("/")[-1]
        self.lbl_filename.config(text=name)
        self.title(f"CScript IDE — {name}")
        self._save_file()

    # -----------------------------------------------------------------------
    # Consola helpers
    # -----------------------------------------------------------------------

    def _console_write(self, text: str, tag: str = "output"):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, text, tag)
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)
        self.update_idletasks()

    def _clear_output(self):
        self.console.config(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.config(state=tk.DISABLED)

        self._tree_canvas.clear()

        for tv in (self.token_tree, self.error_tree, self.sym_tree):
            for row in tv.get_children():
                tv.delete(row)

        self.lbl_token_count.config(text="")
        self.lbl_error_count.config(text="")
        self.lbl_sym_count.config(text="")

        for tag in ("error_char", "error_line", "lex_err"):
            self.editor.tag_remove(tag, "1.0", tk.END)

    # -----------------------------------------------------------------------
    # Población de tablas
    # -----------------------------------------------------------------------

    def _populate_tokens(self, tokens):
        for row in self.token_tree.get_children():
            self.token_tree.delete(row)
        for i, t in enumerate(tokens):
            tg = "even" if i % 2 == 0 else "odd"
            self.token_tree.insert("", tk.END, tags=(tg,), values=(
                t["no"], t["linea"], t["columna"], t["token"], t["lexema"],
            ))

    def _populate_errors(self, errores: list, tipo: str):
        for row in self.error_tree.get_children():
            self.error_tree.delete(row)
        self._append_errors(errores, tipo)

    def _append_errors(self, errores: list, tipo: str):
        start = len(self.error_tree.get_children())
        for i, e in enumerate(errores):
            idx = start + i
            tg  = "even" if idx % 2 == 0 else "odd"
            extra = ("sem_warn",) if isinstance(e, SemanticErrorInfo) else ()
            if isinstance(e, LexicalErrorInfo):
                vals = (tipo, e.linea, e.columna, repr(e.lexema),
                        e.descripcion, e.sugerencia)
            elif isinstance(e, SyntacticErrorInfo):
                vals = (tipo, e.linea, e.columna, "",
                        e.descripcion, e.sugerencia)
            elif isinstance(e, SemanticErrorInfo):
                vals = (tipo, e.linea, e.columna, e.variable,
                        e.descripcion, e.sugerencia)
            else:
                continue
            self.error_tree.insert("", tk.END, tags=(tg, *extra), values=vals)

    def _populate_symbols(self, symbols: list[SymbolInfo]):
        for row in self.sym_tree.get_children():
            self.sym_tree.delete(row)
        for i, s in enumerate(symbols):
            tg = "even" if i % 2 == 0 else "odd"
            self.sym_tree.insert("", tk.END, tags=(tg,), values=(
                s.numero, s.nombre, s.tipo_estructura,
                s.tipo_dato, s.linea,
                s.valor_inicial if s.valor_inicial else "—",
            ))

    # -----------------------------------------------------------------------
    # Pipeline completo de análisis  ("▶ Analizar")
    # -----------------------------------------------------------------------

    def _analyze_full(self):
        self._clear_output()
        code = self.editor.get("1.0", tk.END)

        # ── Léxico ───────────────────────────────────────────────────────────
        tokens, lex_errors = analizar_lexico(code)
        self._populate_tokens(tokens)
        self.lbl_token_count.config(text=f"  {len(tokens)} tokens encontrados")

        if lex_errors:
            self._populate_errors(lex_errors, "Léxico")
            self.lbl_error_count.config(
                text=f"  {len(lex_errors)} error(es) léxico(s)")
            e = lex_errors[0]
            if e.linea > 0:
                col0 = max(0, e.columna - 1)
                self.editor.tag_add("lex_err",
                                    f"{e.linea}.{col0}",
                                    f"{e.linea}.{col0 + 1}")
            self._console_write("=== ERRORES LÉXICOS ===\n", "error")
            for err in lex_errors:
                self._console_write(
                    f"  Línea {err.linea}, Col {err.columna} — '{err.lexema}'\n"
                    f"  {err.descripcion}\n"
                    f"  Sugerencia: {err.sugerencia}\n\n", "error")
            self.notebook.select(1)
            self._set_status(f"Detenido — {len(lex_errors)} error(es) léxico(s)",
                             "error")
            return

        # ── Sintáctico ───────────────────────────────────────────────────────
        tree, syn_errors = analizar_sintactico(code)

        if syn_errors:
            self._populate_errors(syn_errors, "Sintáctico")
            self.lbl_error_count.config(
                text=f"  {len(syn_errors)} error(es) sintáctico(s)")
            e = syn_errors[0]
            if e.linea > 0:
                col0 = max(0, e.columna - 1)
                self.editor.tag_add("error_line",
                                    f"{e.linea}.{col0}", f"{e.linea}.end")
            self._console_write("=== ERRORES SINTÁCTICOS ===\n", "error")
            for err in syn_errors:
                self._console_write(
                    f"  Línea {err.linea}, Col {err.columna}\n"
                    f"  {err.descripcion}\n"
                    f"  Sugerencia: {err.sugerencia}\n", "error")
                if err.contexto:
                    self._console_write(f"\n{err.contexto}\n", "error")
            self.notebook.select(1)
            self._set_status(
                f"Detenido — {len(syn_errors)} error(es) sintáctico(s)", "error")
            return

        # ── Tabla de símbolos ────────────────────────────────────────────────
        symbols = SymbolTableBuilder().build(tree)
        self._populate_symbols(symbols)
        self.lbl_sym_count.config(
            text=f"  {len(symbols)} símbolo(s) encontrado(s)")

        # ── Árbol gráfico ────────────────────────────────────────────────────
        self._tree_canvas.draw(tree)

        # ── Semántico ────────────────────────────────────────────────────────
        sem_errors = SemanticAnalyzer().analyze(tree)

        if sem_errors:
            self._populate_errors([], "")
            self._append_errors(sem_errors, "Semántico")
            self.lbl_error_count.config(
                text=f"  {len(sem_errors)} advertencia(s) semántica(s)")
            e = sem_errors[0]
            if e.linea > 0:
                self.editor.tag_add("error_line",
                                    f"{e.linea}.0", f"{e.linea}.end")
            self._console_write("=== ADVERTENCIAS SEMÁNTICAS ===\n", "error")
            for err in sem_errors:
                self._console_write(
                    f"  Línea {err.linea} — [{err.variable}]\n"
                    f"  {err.descripcion}\n"
                    f"  Sugerencia: {err.sugerencia}\n\n", "error")
            self.notebook.select(1)
            self._set_status(
                f"Análisis OK con {len(sem_errors)} advertencia(s) semántica(s)",
                "warning")
        else:
            self.lbl_error_count.config(text="  Sin errores")
            self._console_write(
                f"=== ANÁLISIS COMPLETO OK ===\n"
                f"  Tokens:   {len(tokens)}\n"
                f"  Símbolos: {len(symbols)}\n"
                f"  Errores:  0\n\n", "info")
            self.notebook.select(3)   # mostrar árbol
            self._set_status(
                f"✔ Análisis OK — {len(tokens)} tokens, {len(symbols)} símbolos",
                "ok")

    # -----------------------------------------------------------------------
    # Ejecución  (F5)
    # -----------------------------------------------------------------------

    def _run_code(self):
        if self._running:
            return
        self._clear_output()
        self.notebook.select(4)
        code = self.editor.get("1.0", tk.END)

        tokens, lex_errors = analizar_lexico(code)
        self._populate_tokens(tokens)
        self.lbl_token_count.config(text=f"  {len(tokens)} tokens encontrados")

        if lex_errors:
            self._populate_errors(lex_errors, "Léxico")
            self.lbl_error_count.config(text=f"  {len(lex_errors)} error(es)")
            self._console_write("=== ERRORES LÉXICOS ===\n", "error")
            for e in lex_errors:
                self._console_write(
                    f"  Línea {e.linea}, Col {e.columna} — '{e.lexema}'\n"
                    f"  {e.descripcion}\n  Sugerencia: {e.sugerencia}\n\n", "error")
            self.notebook.select(1)
            self._set_status("Detenido — errores léxicos", "error")
            return

        self._console_write(f"=== LÉXICO OK — {len(tokens)} tokens ===\n\n", "info")

        self._running = True
        self.btn_analyze.config(state=tk.DISABLED, text="⏳ Ejecutando…")
        self._set_status("Ejecutando…")
        threading.Thread(target=self._execute, args=(code,), daemon=True).start()

    def _execute(self, code: str):
        tree, syn_errors = analizar_sintactico(code)
        if syn_errors:
            e = syn_errors[0]
            msg = (f"[ERROR SINTÁCTICO]\n"
                   f"  Línea {e.linea}, Col {e.columna}\n"
                   f"  {e.descripcion}\n  {e.sugerencia}\n")
            if e.contexto:
                msg += f"\n{e.contexto}\n"
            self.after(0, self._console_write, msg, "error")
            self.after(0, self._finish_run, False)
            return

        interp = GUICScriptInterpreter(
            output_fn=lambda s: self.after(0, self._console_write, s, "output"),
            input_fn=self._gui_input,
        )
        try:
            interp.visit(tree)
        except Exception as exc:
            self.after(0, self._console_write,
                       f"\n[ERROR DE EJECUCIÓN] {exc}\n", "error")
            self.after(0, self._finish_run, False)
            return

        self.after(0, self._finish_run, True)

    def _finish_run(self, success: bool):
        self._running = False
        self.btn_analyze.config(state=tk.NORMAL, text="▶ Analizar")
        if success:
            self._console_write("\n=== EJECUCIÓN COMPLETADA ===\n", "info")
            self._set_status("✔ Ejecución completada", "ok")
        else:
            self._set_status("Ejecución con errores", "error")

    def _gui_input(self) -> str:
        result: list[str] = []
        done = threading.Event()

        def ask():
            val = simpledialog.askstring(
                "Entrada requerida", "Ingresa un valor:", parent=self)
            result.append(val if val is not None else "")
            done.set()

        self.after(0, ask)
        done.wait()
        entered = result[0]
        self.after(0, self._console_write, f"> {entered}\n", "input_prompt")
        return entered


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    myappid = "umg.huehuetenango.cscript.ide.2.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Pre-calentar el parser LALR en background para que la primera análisis
    # en tiempo real sea instantánea
    threading.Thread(
        target=lambda: analizar_sintactico("entero x = 0;"),
        daemon=True,
    ).start()

    app = CScriptIDE()
    app.mainloop()


if __name__ == "__main__":
    main()
