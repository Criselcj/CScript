// ================================================
// PRUEBA COMPLETA - CScript
// Cubre todas las estructuras del lenguaje
// ================================================

// ---------- Declaraciones y tipos ---------------
entero    contador = 0;
entero    suma     = 0;
decimal   promedio = 0.0;
texto     mensaje  = "Iniciando CScript...";
booleano  activo   = verdadero;

imprimir(mensaje);

// ---------- Asignacion --------------------------
contador = 10;
suma     = contador * 2 + 5;
imprimir(suma);

// ---------- si / sino ---------------------------
si (suma > 20) {
    imprimir("La suma es mayor que 20");
} sino {
    imprimir("La suma es 20 o menor");
}

// ---------- si anidado --------------------------
entero nivel = 75;

si (nivel >= 90) {
    imprimir("Nivel: Excelente");
} sino {
    si (nivel >= 70) {
        imprimir("Nivel: Bueno");
    } sino {
        imprimir("Nivel: Regular");
    }
}

// ---------- mientras ----------------------------
imprimir("Contando con mientras:");
entero i = 1;

mientras (i <= 5) {
    imprimir(i);
    i = i + 1;
}

// ---------- hacer_mientras ----------------------
imprimir("Potencias de 2:");
entero potencia = 1;

hacer {
    imprimir(potencia);
    potencia = potencia * 2;
} mientras (potencia <= 16);

// ---------- para --------------------------------
imprimir("Tabla del 3:");

para (entero k = 1; k <= 10; k = k + 1) {
    imprimir(3 * k);
}

// ---------- acumulador con para -----------------
entero total = 0;

para (entero n = 1; n <= 100; n = n + 1) {
    total = total + n;
}

imprimir("Suma del 1 al 100:");
imprimir(total);

promedio = total / 100;
imprimir("Promedio:");
imprimir(promedio);

// ---------- condiciones compuestas --------------
entero x = 8;
entero y = 15;

si (x > 5 y y < 20) {
    imprimir("x>5 y y<20: verdadero");
}

si (x > 100 o y > 10) {
    imprimir("x>100 o y>10: verdadero");
}

si (no activo o x < 10) {
    imprimir("condicion con 'no': verdadera");
}

// ---------- segun / caso / defecto --------------
entero dia = 3;
imprimir("Dia de la semana:");

segun (dia) {
    caso 1: imprimir("Lunes");    romper;
    caso 2: imprimir("Martes");   romper;
    caso 3: imprimir("Miercoles");romper;
    caso 4: imprimir("Jueves");   romper;
    caso 5: imprimir("Viernes");  romper;
    defecto: imprimir("Fin de semana");
}

// ---------- expresiones aritmeticas -------------
entero a = 10;
entero b = 3;

imprimir("Division entera:");
imprimir(a / b);

imprimir("Modulo:");
imprimir(a % b);

imprimir("Negativo:");
imprimir(-a + 100);

// ---------- booleanos ---------------------------
booleano esPar  = verdadero;
booleano esMayor = x > 5;

si (esPar y esMayor) {
    imprimir("Par y mayor que 5");
}

imprimir("Programa finalizado.");
