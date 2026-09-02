; =============================================================
; stats_scalar.asm
; Version ESCALAR (referencia) de los kernels de computo.
;
; Convencion de llamada: System V AMD64 ABI
;   enteros/punteros: rdi, rsi, rdx, rcx, r8, r9
;   flotantes:        xmm0, xmm1, xmm2, ...
;   retorno float:    xmm0
;   callee-saved:     rbx, rbp, r12-r15 (si los usa, debe preservarlos)
; =============================================================

    global sum_array
    global compute_stats
    global normalize_array

    section .text

; ---------------------------------------------------------------
; float sum_array(const float *arr, int n)
;   rdi = arr, esi = n 
;   retorna la suma en xmm0
;
; IMPLEMENTADA COMO EJEMPLO: estudien este patron (recorrido,
; acumulador, condicion de salida) antes de escribir compute_stats
; y normalize_array.
; ---------------------------------------------------------------
sum_array: 
    xor     eax, eax           ; eax = i = 0 Hacer el xor consigo mismo es una forma rapida de poner un registro a cero
    xorps   xmm0, xmm0         ; xmm0 = acumulador = 0.0

.sum_loop:
    cmp     eax, esi ; comparo i con n , n es el tamaño del arreglo
    jge     .sum_done ; Aquí termino si i >= n
    movss   xmm1, [rdi + rax*4] ; eb xmm1 guardo arr[i] (cada float ocupa 4 bytes, por eso multiplico i por 4)
    addss   xmm0, xmm1 ; Voy sumando arr[i] al acumulador xmm0 = xmm0 + arr[i]
    inc     eax
    jmp     .sum_loop 

.sum_done:
    ret

; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
;
;   var = varianza POBLACIONAL = sum((x - mean)^2) / n
;   Caso borde: si n == 0, escriba 0.0 en mean/var/min/max.
;
; TODO (estudiante):
;   1) Calcular mean = suma(arr) / n. Puede reutilizar sum_array con
;      'call sum_array', pero recuerde que eso destruye los
;      registros caller-saved (rax, rcx, rdx, rsi, rdi, r8-r11):
;      guarde arr/n/mean*/var*/min*/max* en registros callee-saved
;      (rbx, r12-r15) ANTES de llamar.
;   2) Recorrer el arreglo una segunda vez para acumular
;      sum((x - mean)^2) y obtener var = esa suma / n.
;   3) Recorrer el arreglo (puede combinarlo con el paso 1) llevando
;      min y max con comiss + saltos condicionales (ja/jb, etc.)
;      o con las instrucciones minss/maxss.
;   4) Guardar los resultados en las direcciones recibidas por
;      puntero: [rdx]=mean, [rcx]=var, [r8]=min, [r9]=max.
;   5) No olvide restaurar los registros callee-saved en el epilogo.
; ---------------------------------------------------------------
compute_stats:
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    ; TODO: implementar el algoritmo descrito arriba.


    ; Caso borde: si n == 0, escriba 0.0 en mean/var/min/max.
    cmp     esi, 0 ; comparo n con 0
    je      .zero_case ; si n == 0



    ; Mean:
    ; Primero vamos a guardar los punteros y el tamaño del arreglo en registros callee-saved
    ; Solo hace falta guardar mean, var, min y max, arr y n. Este ultimo hay que guardarlo en la pila porque no hay mas registros callee-saved disponibles
    mov    rbx, rdx ; mean
    mov    r12, rcx ; var
    mov    r13, r8 ; min
    mov    r14, r9 ; max
    mov    r15, rdi ; arr

    push   rsi ; Guardo n en la pila porque no hay mas registros callee-saved disponibles
    push   rsi; para cumplir la convención de alineación de memoria de la pila, que requiere que el stack esté alineado a 16 bytes antes de llamar a una función. 

    call    sum_array ; xmm0 = suma(arr)
    pop    rsi ; Recuperamos n de la pila
    pop    rsi ; Recuperamos n de la pila

    ;en xmm0 tengo la suma, ahora calculo mean = suma(arr) / n
    cvtsi2ss xmm1, esi ; Convertir n a float y lo guardo en xmm1. Uso solo la parte baja de rsi (esi) porque es un entero de 32 bits, en los otros 32 bits superiores de rsi hay basura.
    divss   xmm0, xmm1 ; mean = suma(arr) / n Listo
    movss   [rbx], xmm0 ; Guardo mean en la dirección apuntada por mean*

    ; cvtsi2ss: Convert Scalar Integer to Scalar Single-Precision Floating-Point Value

    ;Ahora recupero lo que habia guardado en los registros callee-saved, ya no se va a usar ninguna otra call
    mov     rdx, rbx ; mean*
    mov     rcx, r12 ; var*
    mov     r8, r13 ; min*
    mov     r9, r14 ; max*
    mov     rdi, r15 ; arr


    ; Varianza: Aquí sí hay que hacer el bucle a mano. sum((x - mean)^2) y obtener var = esa suma / n.

    .var_array:
        xor     eax, eax  ; i =0
        xorps   xmm0, xmm0 ; acumulador = 0.0

    .var_loop:
        cmp     eax, esi ; comparo i con n
        jge     .var_done ; terminA si i >= n
        movss   xmm1, [rdi + rax*4] ; arr[i]
        subss   xmm1, [rbx] ; arr[i] - mean
        mulss   xmm1, xmm1 ; (arr[i] - mean)^2
        addss   xmm0, xmm1 ; acumulador += (arr[i] - mean)^2
        inc     eax
        jmp     .var_loop

    .var_done:
    ; Ahora calculo var = acumulador / n
    cvtsi2ss xmm1, esi ; Convertir n a float y lo guardo en xmm1
    divss   xmm0, xmm1 ; var = acumulador / n
    movss   [rcx], xmm0 ; Guardo var en la dirección apuntada por var*


    ; min y max
    ; Primero inicializo min y max con el primer elemento del arreglo
    ; Se hace otro loop que recorre el arreglo y va comparando cada elemento con min y max, actualizando según corresponda
    movss   xmm0, [rdi] ; min = arr[0] rdi es la dirección base, sin offset
    movss   xmm1, [rdi] ; max = arr[0]

    .min_max:
        mov     eax, 1  ; i = 1 Para empezar desde el segundo elemento del arreglo
    .min_max_loop:
        cmp     eax, esi ; comparo i con n
        jge     .min_max_done ; termina si i >= n
        movss   xmm2, [rdi + rax*4] ; arr[i]
        comiss  xmm2, xmm0 ; comparo arr[i] con min
        ; Comiss: Compare Scalar Ordered Single-Precision Floating-Point Values
        jb      .update_min ; si arr[i] < min, actualizo min
        comiss  xmm2, xmm1 ; comparo arr[i] con max
        ja      .update_max ; si arr[i] > max, actualizo max
        inc     eax 
        jmp     .min_max_loop

    .update_min:
        movss   xmm0, xmm2 ; min = arr[i]
        inc     eax
        jmp     .min_max_loop  

    .update_max:
        movss   xmm1, xmm2 ; max = arr[i]
        inc     eax
        jmp     .min_max_loop

    .min_max_done:
    movss   [r8], xmm0 ; Guardo min en la dirección apuntada por min*
    movss   [r9], xmm1 ; Guardo max en la dirección apuntada por max*

    ;NOTA: Este bucle de min y max podría haberse hecho junto con el de var, pero por orden y claridad lo hice aparte.

    jmp    .done


    .zero_case:
    ; Caso borde: si n == 0, escriba 0.0 en mean/var/min/max.
    xorps xmm0, xmm0    ; xmm0 = 0.0
    movss   [rdx], xmm0 ; mean = 0.0
    movss   [rcx], xmm0 ; var = 0.0
    movss   [r8], xmm0 ; min = 0.0
    movss   [r9], xmm0 ; max = 0.0  


    .done:
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    ret

; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                       float mean, float stddev)
;   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev
;
;   out[i] = (in[i] - mean) / stddev
;   Caso borde: si stddev == 0.0, copie in[i] en out[i] tal cual
;   (evite division por cero).
;
; TODO (estudiante): implementar el bucle escalar.
; Sugerencia: guarde mean (xmm0) y stddev (xmm1) en registros que no
; se sobrescriban dentro del bucle (por ejemplo xmm8/xmm9, que en
; System V no se usan para pasar argumentos), o vuelva a cargarlos
; en cada iteracion desde una copia guardada en la pila.
; ---------------------------------------------------------------
normalize_array:
    ; TODO: implementar el bucle escalar.

    ; Aceptando la sugerencia, guardo mean y stddev en xmm8 y xmm9 respectivamente
    movaps  xmm8, xmm0 ; Guardar mean en xmm8
    movaps  xmm9, xmm1 ; Guardar stddev en xmm9

    xor     eax, eax ; i = 0

    xorps   xmm2, xmm2 ; xmm2 = 0.0, lo uso para comparar con stddev
    comiss  xmm9, xmm2 ; comparo stddev con 0.0
    je      .copy_in ; si stddev == 0.0, copiar in[i] en out[i]

.normalize_loop:
    cmp     eax, edx ; comparo i con n Lo bueno es que si n == 0, el bucle no se ejecuta y termina inmediatamente
    jge     .normalize_done ; termina si i >= n
    movss   xmm2, [rdi + rax*4] ; in[i]
    subss   xmm2, xmm8 ; in[i] - mean
    
    divss   xmm2, xmm9 ; (in[i] - mean) / stddev
    movss   [rsi + rax*4], xmm2 ; out[i] = (in[i] - mean) / stddev
    inc     eax
    jmp     .normalize_loop

.copy_in:
    cmp     eax, edx ; comparo i con n
    jge     .normalize_done ; termina si i >= n
    movss   xmm2, [rdi + rax*4] ; in[i]
    movss   [rsi + rax*4], xmm2 ; out[i] = in[i] (simplemente copia)
    inc     eax
    jmp     .copy_in

.normalize_done:
    ret
