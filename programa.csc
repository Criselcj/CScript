imprimir("Ingresa el primer número:");
entero a = leer();

imprimir("Ingresa el segundo número:");
entero b = leer();

entero suma = a + b;

imprimir("Resultado:");
imprimir(suma);

entero i = 1;
suma = 0;

mientras (i <= 10) {
    imprimir(i);
    suma = suma + i;
    i = i + 1;
}

imprimir("Suma del 1 al 10:");
imprimir(suma);