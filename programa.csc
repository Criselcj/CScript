imprimir("Ingresa el primer número:");
entero a = leer();

imprimir("Ingresa el segundo número:");
entero b = leer();

entero suma = a + b;
decimal promedio = (a + b) / 2;
texto mensaje = "Resultado calculado";
booleano mayor = suma > 10;

imprimir(mensaje);
imprimir("Suma:");
imprimir(suma);

imprimir("Promedio:");
imprimir(promedio);

imprimir("Mayor que 10:");
imprimir(mayor);

si (suma > 10) {
    imprimir("La suma es mayor que 10");
} sino {
    imprimir("La suma no es mayor que 10");
}

//texto mensaje = "Hola Mundo;
//imprimir(mensaje)