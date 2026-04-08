from __future__ import annotations

import re
import threading
import tkinter as tk
import ctypes
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from lark import Lark, UnexpectedInput

from cscript import (
    GRAMMAR,
    CScriptInterpreter,
    LexicalErrorInfo,
    analizar_lexico,
)


# ---------------------------------------------------------------------------
# Interpreter con I/O redirigida a la GUI
# ---------------------------------------------------------------------------

class GUICScriptInterpreter(CScriptInterpreter):
    def __init__(self, output_fn, input_fn):
        super().__init__()
        self._output = output_fn
        self._input = input_fn

    def print_stmt(self, tree):
        value = self._eval(tree.children[0])
        self._output(str(value) + "\n")

    def read(self, tree):
        return self._input()


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

KEYWORDS = [
    "si", "sino", "mientras", "hacer", "para", "segun", "caso",
    "defecto", "romper", "imprimir", "leer", "no", "y", "o",
    "entero", "decimal", "texto", "booleano", "verdadero", "falso",
]

BG        = "#1e1e1e"
BG2       = "#252526"
BG3       = "#2d2d30"
FG        = "#d4d4d4"
ACCENT    = "#007acc"
GREEN     = "#4ec9b0"
ORANGE    = "#ce9178"
BLUE      = "#569cd6"
COMMENT   = "#6a9955"
NUMBER    = "#b5cea8"
RED       = "#f44747"
YELLOW    = "#dcdcaa"


class CScriptIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CScript IDE")
        self.iconbitmap("cscript.ico") 
        self.geometry("1200x720")
        self.minsize(900, 550)
        self.configure(bg=BG)

        self._current_file: Optional[str] = None
        self._running = False

        self._build_ui()
        self._apply_theme()
        self._setup_bindings()
        self._update_line_numbers()

    # -----------------------------------------------------------------------
    # Construcción de la interfaz
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self._build_toolbar()
        self._build_main_area()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG3, pady=4)
        bar.pack(side=tk.TOP, fill=tk.X)

        def tbtn(parent, text, cmd, **kw):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=BG3, fg=FG, relief=tk.FLAT,
                          activebackground="#3e3e42", activeforeground=FG,
                          padx=10, pady=3, font=("Segoe UI", 9), **kw)
            b.pack(side=tk.LEFT, padx=2)
            return b

        def sep():
            tk.Frame(bar, bg="#555", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        tbtn(bar, "Nuevo",      self._new_file)
        tbtn(bar, "Abrir",      self._open_file)
        tbtn(bar, "Guardar",    self._save_file)
        tbtn(bar, "Guardar como", self._save_as_file)
        sep()
        self.btn_run = tk.Button(
            bar, text="▶ Analizar", command=self._analyze_only,
            bg="#0e7a0d", fg="white", relief=tk.FLAT,
            activebackground="#1a9918", activeforeground="white",
            padx=12, pady=3, font=("Segoe UI", 9, "bold"),
        )
        self.btn_run.pack(side=tk.LEFT, padx=2)
        # tbtn(bar, "Solo analizar", self._analyze_only)
        sep()
        tbtn(bar, "Limpiar salida", self._clear_output)

    def _build_main_area(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               sashwidth=5, sashrelief=tk.FLAT,
                               bg=BG3)
        paned.pack(fill=tk.BOTH, expand=True)

        # ---- Panel izquierdo: editor ----
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

        self.line_nums = tk.Text(inner, width=4, padx=6,
                                  state=tk.DISABLED, takefocus=0,
                                  wrap=tk.NONE, cursor="arrow")
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

        # ---- Panel derecho: notebook de resultados ----
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=350)
        paned.paneconfig(left, width=580)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_tokens_tab()
        self._build_errors_tab()
        self._build_console_tab()

    def _build_tokens_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Tokens  ")

        cols = ("no", "linea", "col", "token", "lexema")
        self.token_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                        selectmode="browse")
        for col, hdr, w, anchor in [
            ("no",     "#",        45,  tk.CENTER),
            ("linea",  "Línea",    65,  tk.CENTER),
            ("col",    "Col",      55,  tk.CENTER),
            ("token",  "Token",   170,  tk.W),
            ("lexema", "Lexema",  200,  tk.W),
        ]:
            self.token_tree.heading(col, text=hdr)
            self.token_tree.column(col, width=w, anchor=anchor, stretch=col == "lexema")

        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL,   command=self.token_tree.yview)
        hsb = tk.Scrollbar(tab, orient=tk.HORIZONTAL, command=self.token_tree.xview)
        self.token_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.token_tree.pack(fill=tk.BOTH, expand=True)

        # summary label
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
            ("tipo",       "Tipo",        80),
            ("linea",      "Línea",       60),
            ("col",        "Col",         50),
            ("lexema",     "Lexema",      90),
            ("descripcion","Descripción", 260),
            ("sugerencia", "Sugerencia",  260),
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

    def _build_console_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Consola  ")

        self.console = tk.Text(
            tab, state=tk.DISABLED, wrap=tk.WORD,
            font=("Consolas", 11), cursor="arrow",
        )
        vsb = tk.Scrollbar(tab, orient=tk.VERTICAL, command=self.console.yview)
        self.console.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.pack(fill=tk.BOTH, expand=True)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=ACCENT, height=22)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Listo")
        tk.Label(bar, textvariable=self.status_var,
                 bg=ACCENT, fg="white", font=("Segoe UI", 9),
                 padx=8).pack(side=tk.LEFT, anchor=tk.CENTER)
        self.lbl_cursor = tk.Label(bar, text="Ln 1, Col 1",
                                    bg=ACCENT, fg="white",
                                    font=("Segoe UI", 9), padx=8)
        self.lbl_cursor.pack(side=tk.RIGHT, anchor=tk.CENTER)

    # -----------------------------------------------------------------------
    # Tema / colores
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
        self.console.configure(
            bg="#0c0c0c", fg=FG, relief=tk.FLAT,
        )

        # editor syntax tags
        self.editor.tag_configure("keyword", foreground=BLUE)
        self.editor.tag_configure("string",  foreground=ORANGE)
        self.editor.tag_configure("comment", foreground=COMMENT)
        self.editor.tag_configure("number",  foreground=NUMBER)

        # console tags
        self.console.tag_configure("output",       foreground=FG)
        self.console.tag_configure("error",        foreground=RED)
        self.console.tag_configure("info",         foreground=GREEN)
        self.console.tag_configure("input_prompt", foreground=YELLOW)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=22,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background=BG3, foreground=FG,
                        relief=tk.FLAT)
        style.map("Treeview",
                  background=[("selected", "#094771")],
                  foreground=[("selected", "white")])
        style.configure("TNotebook",        background=BG3, borderwidth=0)
        style.configure("TNotebook.Tab",    background=BG3, foreground="#888",
                        padding=[12, 5], borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", FG)])

        # alternate row colors in treeviews
        self.token_tree.tag_configure("odd",  background=BG)
        self.token_tree.tag_configure("even", background=BG2)
        self.error_tree.tag_configure("odd",  background=BG)
        self.error_tree.tag_configure("even", background=BG2)

    # -----------------------------------------------------------------------
    # Eventos / bindings
    # -----------------------------------------------------------------------

    def _setup_bindings(self):
        self.editor.bind("<KeyRelease>",   self._on_edit)
        self.editor.bind("<ButtonRelease>", self._on_edit)
        self.editor.bind("<MouseWheel>",   self._on_mouse_wheel)
        self.bind("<F5>",         lambda e: self._run_code())
        self.bind("<Control-s>",  lambda e: self._save_file())
        self.bind("<Control-o>",  lambda e: self._open_file())
        self.bind("<Control-n>",  lambda e: self._new_file())

    def _on_yscroll(self, *args):
        self.editor.yview(*args)
        self._sync_line_nums()

    def _on_mouse_wheel(self, event=None):
        self.after_idle(self._sync_line_nums)

    def _on_edit(self, event=None):
        self._update_line_numbers()
        self._highlight_syntax()
        self._update_cursor_pos()

    def _update_cursor_pos(self):
        pos = self.editor.index(tk.INSERT)
        ln, col = pos.split(".")
        self.lbl_cursor.config(text=f"Ln {ln}, Col {int(col)+1}")

    # -----------------------------------------------------------------------
    # Numeración de líneas
    # -----------------------------------------------------------------------

    def _update_line_numbers(self):
        self.line_nums.config(state=tk.NORMAL)
        self.line_nums.delete("1.0", tk.END)
        total = int(self.editor.index(tk.END).split(".")[0]) - 1
        self.line_nums.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
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
            s = f"1.0+{match.start()}c"
            e = f"1.0+{match.end()}c"
            self.editor.tag_add(name, s, e)

        # comments (block first, then line)
        for m in re.finditer(r"/\*.*?\*/", content, re.DOTALL):
            tag(m, "comment")
        for m in re.finditer(r"//[^\n]*", content):
            tag(m, "comment")

        # strings
        for m in re.finditer(r'"(?:[^"\\]|\\.)*"', content):
            tag(m, "string")

        # numbers
        for m in re.finditer(r'\b\d+\.?\d*\b', content):
            tag(m, "number")

        # keywords (last so they override numbers in edge cases)
        pat = r'\b(' + '|'.join(KEYWORDS) + r')\b'
        for m in re.finditer(pat, content):
            tag(m, "keyword")

    # -----------------------------------------------------------------------
    # Operaciones de archivo
    # -----------------------------------------------------------------------

    def _new_file(self):
        if messagebox.askyesno("Nuevo archivo",
                               "¿Descartar el contenido actual y crear un archivo nuevo?",
                               parent=self):
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
            content = self.editor.get("1.0", tk.END)
            with open(self._current_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_var.set(f"Guardado: {self._current_file}")
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
        for row in self.token_tree.get_children():
            self.token_tree.delete(row)
        for row in self.error_tree.get_children():
            self.error_tree.delete(row)
        self.lbl_token_count.config(text="")
        self.lbl_error_count.config(text="")

    # -----------------------------------------------------------------------
    # Análisis léxico / ejecución
    # -----------------------------------------------------------------------

    def _analyze_only(self):
        self._clear_output()
        code = self.editor.get("1.0", tk.END)
        tokens, errores = analizar_lexico(code)
        self._populate_tokens(tokens)
        self._populate_errors(errores)
        count_msg = f"  {len(tokens)} tokens encontrados"
        self.lbl_token_count.config(text=count_msg)
        err_msg = f"  {len(errores)} error(es)" if errores else "  Sin errores"
        self.lbl_error_count.config(text=err_msg)
        self.notebook.select(0)
        self._console_write(
            f"Análisis léxico completado — {len(tokens)} tokens, {len(errores)} error(es).\n",
            "info",
        )
        self.status_var.set(f"Análisis léxico — {len(tokens)} tokens")

    def _populate_tokens(self, tokens):
        for row in self.token_tree.get_children():
            self.token_tree.delete(row)
        for i, t in enumerate(tokens):
            tag = "even" if i % 2 == 0 else "odd"
            self.token_tree.insert("", tk.END, tags=(tag,), values=(
                t["no"], t["linea"], t["columna"], t["token"], t["lexema"],
            ))

    def _populate_errors(self, errores, tipo="Léxico"):
        for row in self.error_tree.get_children():
            self.error_tree.delete(row)
        for i, e in enumerate(errores):
            tag = "even" if i % 2 == 0 else "odd"
            self.error_tree.insert("", tk.END, tags=(tag,), values=(
                tipo, e.linea, e.columna, repr(e.lexema),
                e.descripcion, e.sugerencia,
            ))

    def _run_code(self):
        if self._running:
            return
        self._clear_output()
        self.notebook.select(2)  # consola
        code = self.editor.get("1.0", tk.END)

        # 1. Análisis léxico
        tokens, lex_errors = analizar_lexico(code)
        self._populate_tokens(tokens)
        self.lbl_token_count.config(text=f"  {len(tokens)} tokens encontrados")

        if lex_errors:
            self._populate_errors(lex_errors)
            self.lbl_error_count.config(text=f"  {len(lex_errors)} error(es)")
            self._console_write("=== ERRORES LÉXICOS ===\n", "error")
            for e in lex_errors:
                self._console_write(
                    f"  Línea {e.linea}, Col {e.columna} — lexema {repr(e.lexema)}\n"
                    f"  {e.descripcion}\n"
                    f"  Sugerencia: {e.sugerencia}\n\n",
                    "error",
                )
            self.notebook.select(1)
            self.status_var.set("Detenido — errores léxicos")
            return

        self.lbl_error_count.config(text="  Sin errores léxicos")
        self._console_write(
            f"=== ANÁLISIS LÉXICO OK — {len(tokens)} tokens ===\n\n", "info"
        )

        # 2. Parseo + ejecución en hilo separado
        self._running = True
        self.btn_run.config(state=tk.DISABLED, text="⏳  Ejecutando…")
        self.status_var.set("Ejecutando…")
        threading.Thread(target=self._execute, args=(code,), daemon=True).start()

    def _execute(self, code: str):
        parser = Lark(GRAMMAR, parser="lalr", lexer="contextual",
                      propagate_positions=True)
        try:
            tree = parser.parse(code)
        except UnexpectedInput as e:
            msg = (
                f"[ERROR DE SINTAXIS]\n"
                f"  Línea {e.line}, Columna {e.column}\n"
                f"{e.get_context(code)}\n"
            )
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
        self.btn_run.config(state=tk.NORMAL, text="▶  Ejecutar (F5)")
        if success:
            self._console_write("\n=== EJECUCIÓN COMPLETADA ===\n", "info")
            self.status_var.set("Ejecución completada")
        else:
            self.status_var.set("Ejecución con errores")

    def _gui_input(self) -> str:
        """Solicita entrada al usuario desde el hilo de ejecución."""
        result: list[str] = []
        done = threading.Event()

        def ask():
            val = simpledialog.askstring(
                "Entrada requerida",
                "Ingresa un valor:",
                parent=self,
            )
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
    myappid = 'umg.huehuetenango.cscript.ide.1.0' # Una cadena única
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = CScriptIDE()
    app.mainloop()


if __name__ == "__main__":
    main()
