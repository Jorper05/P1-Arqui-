; =============================================================
; stats_vector.asm
; Version VECTORIZADA (AVX2, 8 floats por iteracion) de los
; kernels de computo. Misma ABI que la version escalar.
;
; Antes de compilar/ejecutar en su maquina, confirme soporte AVX2:
;   lscpu | grep avx2
;   cat /proc/cpuinfo | grep avx2
; =============================================================

    global sum_array
    global compute_stats
    global normalize_array





    section .rodata ;Necesario para inicializar min y max con +infinito y -infinito respectivamente, para que cualquier valor del arreglo sea mayor que max y menor que min.
    align 4
    pos_inf: dd __Infinity__
    neg_inf: dd -__Infinity__

    section .text

; ---------------------------------------------------------------
; float sum_array(const float *arr, int n)
;   rdi = arr, esi = n -> retorna la suma en xmm0
;
; IMPLEMENTADA COMO EJEMPLO. Fijense especialmente en:
;   (1) como se calcula cuantos elementos entran en bucles de 8
;       ("and ecx, ~7" redondea n hacia abajo al multiplo de 8),
;   (2) la REDUCCION HORIZONTAL para pasar de 8 sumas parciales
;       (un YMM) a un unico escalar,
;   (3) el BUCLE ESCALAR DE CIERRE para el remanente (n % 8 != 0).
; Reutilicen este mismo patron en compute_stats y normalize_array.
; ---------------------------------------------------------------


sum_array:
    xor     eax, eax               ; eax = i = 0
    vxorps  ymm0, ymm0, ymm0       ; ymm0 = acumulador vectorial (8 carriles) = 0
                                   ; estas instrucciones tienen 3 operandos, el primero es el destino, el segundo y tercero son fuentes

    mov     ecx, esi               ; ecx = n
    and     ecx, ~7                ; ecx = n redondeado hacia abajo, multiplo de 8 Ejemplo si n = 20, ecx = 16. Si n = 7, ecx = 0. Si n = 8, ecx = 8.
    test    ecx, ecx               ; Si ecx <= 8, salta a .sum_reduce. Si ecx > 8, entra al bucle vectorial.
                                   ; En resumen en esi guardo el tamaño original del arreglo, en ecx guardo el tamaño redondeado hacia abajo al multiplo de 8 y en eax voy a ir iterando de 0 a n-1.
    jle     .sum_reduce            ;verifica si el n es menor a 8 

.sum_vec_loop:
    cmp     eax, ecx               ; ecx es el total de grupos de 8, eax es mi índice.
    jge     .sum_reduce            ; cuando ya terminé con los grupos de 8
    vmovups ymm1, [rdi + rax*4]    ; carga 8 floats (unaligned: siempre valido)
    vaddps  ymm0, ymm0, ymm1       ; acumula por carril
    add     eax, 8                 ;Agrego 8 al indice por los 8 que ya procesé
    jmp     .sum_vec_loop

.sum_reduce: ; Sumo todas las sumas parciales de los 8 carriles de ymm0 en xmm0[0]
    ; --- reduccion horizontal: 8 carriles de ymm0 -> un escalar ---
    
    vextractf128 xmm2, ymm0, 1     ; xmm2 = mitad alta (carriles 4-7)
    vaddps  xmm0, xmm0, xmm2       ; xmm0 = 4 sumas parciales (carriles 0-3 + 4-7) Ya de por sí xmm0 tenía 4 sumas parciales (carriles 0-3) y ahora le sumo los carriles 4-7 que están en xmm2
    vhaddps xmm0, xmm0, xmm0       ; suma horizontal dentro de 128 bits  *Reduzco de 4 sumas parciales a 2 sumas parciales*
    vhaddps xmm0, xmm0, xmm0       ; xmm0[0] = suma total de los 8 carriles originales *Sumo las ultimas 2 sumas parciales*

.sum_scalar_tail:
    ; --- elementos sobrantes (n % 8), uno a la vez ---
    cmp     eax, esi           ; eax = i, esi = n aquí eax empieza en el primer elemento sobrante, ya que los primeros n/8*8 elementos ya fueron procesados
    jge     .sum_done
    vmovss  xmm1, [rdi + rax*4]
    vaddss  xmm0, xmm0, xmm1
    inc     eax
    jmp     .sum_scalar_tail

.sum_done:
    vzeroupper                     ; evita penalizacion de transicion AVX/SSE
                                   ;Limpia la miemoria de los registros YMM, para que no haya penalización al usar instrucciones SSE después de usar AVX.
    ret

; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
;
; TODO (estudiante):
;   1) mean = suma(arr) / n (puede llamar a sum_array; recuerde
;      guardar arr/n/mean*/var*/min*/max* en registros callee-saved
;      antes, porque la llamada destruye registros caller-saved).
;   2) Segunda pasada VECTORIZADA para acumular sum((x-mean)^2):
;        - "broadcast" de mean a los 8 carriles con vbroadcastss.
;        - vsubps + vmulps (o vfmadd231ps si quieren ir mas alla)
;          para acumular los cuadrados de las diferencias,
;        - misma reduccion horizontal que en sum_array,
;        - bucle escalar para el remanente (subss/mulss/addss).
;   3) Min/max VECTORIZADOS con vminps/vmaxps a lo largo del bucle
;      principal, reduccion final con vextractf128 + vminps/vmaxps
;      (y shuffles si quieren reducir los 4 restantes a 1), mas
;      bucle escalar de cierre con minss/maxss o comiss.
;   4) Guarde los resultados en [rdx]=mean, [rcx]=var, [r8]=min,
;      [r9]=max. Si n == 0, escriba 0.0 en los cuatro.
;   5) 'vzeroupper' antes de cualquier 'ret' en una funcion que usa
;      registros YMM.
; ---------------------------------------------------------------
compute_stats:
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15


    ;zero_check:
    ; Caso borde: si n == 0, escribir 0.0 en todo
    vxorps  xmm0, xmm0, xmm0
    vmovss  [rdx], xmm0
    vmovss  [rcx], xmm0
    vmovss  [r8], xmm0
    vmovss  [r9], xmm0
    cmp     esi, 0
    jz      .compute_done



    ;mean:
    ; Aquí parecido al caso escalar, se guardan las variables en registros callee-saved para poder llamar a sum_array y no perder su valor.
    mov    rbx, rdx ; Guardar mean* en rbx
    mov    r12, rcx ; Guardar var* en r12
    mov    r13, r8  ; Guardar min* en r13
    mov    r14, r9  ; Guardar max* en r14
    mov   r15, rdi ; Guardar arr en r15

    ; para n usamos la pila
    push   rsi ; Guardar n en la pila
    push   rsi ; se guarda 2 veces para mantener el alineamiento de la pila (16 bytes) y poder usar instrucciones AVX2

    ;Ahora sí puedo llamar a sum_array para calcular la media
    call   sum_array ; xmm0 = suma(arr)
    pop    rsi ; Recuperar n de la pila
    pop    rsi ; Recuperar n de la pila

    ; recupero lo que habia guardado en los registros callee-saved
    mov    rdx, rbx ; Recuperar mean* en rdx
    mov    rcx, r12 ; Recuperar var* en rcx
    mov    r8,  r13 ; Recuperar min* en r8
    mov    r9,  r14 ; Recuperar max* en r9
    mov    rdi, r15 ; Recuperar arr en rdi

    ; Calcular mean = suma(arr) / n Esto se trabaja igual porque la suma y n son escalares
    vcvtsi2ss xmm1, xmm1, esi ; Convertir n a float en xmm1            
    vdivss   xmm0, xmm0, xmm1 ; Dividir suma(arr) entre n *Equivalente a divss xmm0, xmm1 pero de forma vectorial, decidí usar esta nomenclatura para que quede explicito en el codigo vectorial.
    vmovss   [rdx], xmm0 ; Guardar mean en [mean*] Usar esta instrucción tiene el mismo efecto que movss ya que esto es un valor escalar
    ; OJO: el vmovss no funciona con 3 operandos sino con 2 aunque sea vectorial.
    

    ; Varianza: sum((x-mean)^2)/n

    ; La varianza se calcula muy parecido al caso escalar, haciendo el caso vectorial como el sum

    ;var_array:
    xor     eax, eax    ; i = 0
    vxorps  ymm0, ymm0, ymm0 ; Acumulador vectorial
    vbroadcastss ymm1, [rdx] ; Guarda mean a los 8 carriles de ymm1
                           
    mov     r10d, esi          ; guardar n en r10d (Parte baja de r10 que es de 64 bits), aquí se usa otro registro para no ocupar el registro ecx donde irá la varianza
    and     r10d, ~7           ; r10d = n redondeado hacia abajo            
    test    r10d, r10d          
                           
    jle     .var_scalar_tail       ;Si tengo menos de 8 elementos, salta a trabajar el remanente escalar 

    .var_loop:
        cmp     eax, r10d
        jge     .var_reduce
        vmovups ymm2, [rdi + rax*4] ; Cargar 8 floats de arr
        vsubps  ymm2, ymm2, ymm1    ; (x - mean) 
        vmulps  ymm2, ymm2, ymm2    ; (x - mean)^2
        vaddps  ymm0, ymm0, ymm2       ; acumular la suma de los cuadrados
        add     eax, 8              ; Incrementar el índice en 8
        jmp     .var_loop        

    .var_reduce:
        ; --- reduccion horizontal: 8 carriles de ymm0 -> un escalar ---
        vextractf128 xmm2, ymm0, 1     ; xmm2 = mitad alta (carriles 4-7)
        vaddps  xmm0, xmm0, xmm2       ; xmm0 = 4 sumas parciales (carriles 0-3 + 4-7) Ya de por sí xmm0 tenía 4 sumas parciales (carriles 0-3) y ahora le sumo los carriles 4-7 que están en xmm2
        vhaddps xmm0, xmm0, xmm0       ; suma horizontal dentro de 128 bits  *Reduzco de 4 sumas parciales a 2 sumas parciales*
        vhaddps xmm0, xmm0, xmm0       ; xmm0[0] = suma total de los 8 carriles originales *Sumo las ultimas 2 sumas parciales*

    .var_scalar_tail: ;Mismo algoritmo que en la parte escalar
        cmp     eax, esi           ; eax = i, esi = n 
        jge     .var_done
        vmovss  xmm2, [rdi + rax*4] ; Cargar el elemento sobrante
        vsubss  xmm2, xmm2, [rdx] ; (x - mean) 
        vmulss  xmm2, xmm2, xmm2 ; (x - mean)^2
        vaddss  xmm0, xmm0, xmm2 ; acumular la suma de los cuadrados
        inc     eax
        jmp     .var_scalar_tail

    .var_done:
        vcvtsi2ss xmm1, xmm1, esi ; Convertir n a float en xmm1            
        vdivss   xmm0, xmm0, xmm1 ; Dividir suma(arr) entre n *Equivalente a divss xmm0, xmm1 pero de forma vectorial, decidí usar esta nomenclatura para que quede explicito en el codigo vectorial.
        vmovss   [rcx], xmm0 ; Guardar var en [var*] Usar esta instrucción tiene el mismo efecto que movss ya que esto es un valor escalar
        



    ;min_max:
    ; Funciones vminps y vmaxps para calcular min y max de 8 elementos a la vez, luego se hace una reduccion horizontal para obtener el min y max final, y finalmente se hace un bucle escalar para los elementos sobrantes.
    xor eax, eax ; i = 0

    ;Hay que inicializar min y max con +infinito y -infinito respectivamente, para que cualquier valor del arreglo sea mayor que max y menor que min. Evito segmentation fault si el arreglo tiene menos de 8 elementos. 

    ; Se cargan +inf y -inf con instrucciones de comparación:
    vbroadcastss  ymm0, [rel pos_inf] ; min = +infinito
    vbroadcastss  ymm1, [rel neg_inf] ; max = -infinito

    mov     r10d, esi          ; guardar n en r10d (Parte baja de r10 que es de 64 bits)
    and     r10d, ~7           ; r10d = n redondeado hacia abajo            
    test    r10d, r10d

    jle     .min_max_scalar_tail       ;Si tengo menos de 8 elementos, salta a trabajar el remanente escalar

    

    .min_max_loop:
        cmp     eax, r10d
        jge     .min_max_reduce
        vmovups ymm2, [rdi + rax*4] ; Cargar 8 floats de arr
        vminps  ymm0, ymm0, ymm2    ; min = min(min, arr[i])
        vmaxps  ymm1, ymm1, ymm2    ; max = max(max, arr[i])
        add     eax, 8              ; Incrementar el índice en 8
        jmp     .min_max_loop


    .min_max_reduce:
        ; --- reduccion horizontal: 8 carriles de ymm0/ymm1 -> un escalar ---
        vextractf128 xmm2, ymm0, 1     ; xmm2 = mitad alta (carriles 4-7)
        vminps  xmm0, xmm0, xmm2       ; xmm0 = min(min[0-3], min[4-7]) 
        vextractf128 xmm3, ymm1, 1     ; xmm3 = mitad alta (carriles 4-7)
        vmaxps  xmm1, xmm1, xmm3       ; xmm1 = max(max[0-3], max[4-7])

        vshufps xmm2, xmm0, xmm0, 0xB1 ; Máscara que intercambia los carriles 0 y 1, y los carriles 2 y 3.
        ;Intercambiando los carriles se puede comparar min[0] con min[1] y min[2] con min[3] 
        vminps  xmm0, xmm0, xmm2       ; min = min(min[0], min[1]), min(min[2], min[3])
        vshufps xmm2, xmm0, xmm0, 0x4E ; Máscara que intercambia los carriles 0 y 2, y los carriles 1 y 3.
        vminps  xmm0, xmm0, xmm2       ; min = min(min[0], min[1], min[2], min[3])

        vshufps xmm3, xmm1, xmm1, 0xB1 
        vmaxps  xmm1, xmm1, xmm3        ; max = max(max[0], max[1]), max(max[2], max[3])
        vshufps xmm3, xmm1, xmm1, 0x4E
        vmaxps  xmm1, xmm1, xmm3        ; max = max(max[0], max[1], max[2], max[3])

        ; Aquí se hice algo similar a las fuciones de reducción horizontal
        ; pero hay que hacer manualmente la inversión para comparar carriles vecinos.


    .min_max_scalar_tail: ;Mismo algoritmo que en la parte escalar
        cmp     eax, esi           ; eax = i, esi = n 
        jge     .min_max_done
        vmovss  xmm2, [rdi + rax*4] ; Cargar el elemento sobrante
        vminss  xmm0, xmm0, xmm2 ; min = min(min, arr[i])
        vmaxss  xmm1, xmm1, xmm2 ; max = max(max, arr[i])
        inc     eax
        jmp     .min_max_scalar_tail


    .min_max_done:
        vmovss   [r8], xmm0 ; Guardar min en [min*]
        vmovss   [r9], xmm1 ; Guardar max en [max*]

    .compute_done:
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    vzeroupper
    ret

; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                       float mean, float stddev)
;   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev
;
;   out[i] = (in[i] - mean) / stddev
;   Caso borde: si stddev == 0.0, copie in[i] en out[i] tal cual.
;
; TODO (estudiante):
;   - "Broadcast" mean y stddev a registros YMM con vbroadcastss
;     (guarde antes xmm0/xmm1 en otros registros o en la pila, ya
;     que planea usar xmm0/xmm1 tambien como temporales del bucle).
;   - Bucle vectorial de 8 en 8: vmovups/vmovaps carga, vsubps,
;     vdivps (o vmulps por el reciproco de stddev si quieren
;     optimizar), vmovups/vmovaps guarda.
;   - Bucle escalar de cierre para el remanente (n % 8), igual que
;     en sum_array.
;   - 'vzeroupper' antes del 'ret'.
; ---------------------------------------------------------------
normalize_array:
    ; TODO: implementar

    movaps  xmm8, xmm0 ; Guardar mean en xmm8
    movaps  xmm9, xmm1 ; Guardar stddev en xmm9

    vbroadcastss ymm0, xmm0 ; mean
    vbroadcastss ymm1, xmm1 ; stddev

    xor     eax, eax ; i = 0
    vxorps  xmm2, xmm2, xmm2
    vcomiss xmm9, xmm2
    je      .stddev_zero_case

    mov     r10d, edx          ; guardar n en r10d (Parte baja de r10 que es de 64 bits)
    and     r10d, ~7           ; r10d = n redondeado hacia abajo            
    test    r10d, r10d

    jle     .normalize_scalar_tail


    
    .normalize_loop:
        cmp     eax, r10d
        jge     .normalize_done
        vmovups ymm2, [rdi+rax*4] ; Cargar 8 floats de in
        vsubps  ymm2, ymm2, ymm0 ; (in[i] - mean)
        vdivps  ymm2, ymm2, ymm1 ; (in[i] - mean) / stddev
        vmovups [rsi+rax*4], ymm2 ; Guardar en out
        add     eax, 8
        jmp     .normalize_loop

    .normalize_scalar_tail:
        cmp    eax, edx           ; eax = i, edx = n
        jge    .normalize_done
        vmovss  xmm3, [rdi + rax*4] ; Cargar el elemento sobrante
        vsubss  xmm2, xmm3, xmm8 ; (in[i] - mean)
        vdivss  xmm2, xmm2, xmm9 ; (in[i] - mean) / stddev
        vmovss  [rsi + rax*4], xmm2 ; Guardar en out
        inc     eax
        jmp     .normalize_scalar_tail

        
    .stddev_zero_case:
    cmp     eax, edx ; comparo i con n
    jge     .normalize_done ; termina si i >= n
    vmovss  xmm2, [rdi + rax*4] ; in[i]
    vmovss  [rsi + rax*4], xmm2 ; out[i] = in[i]
    inc     eax
    jmp     .stddev_zero_case

    .normalize_done:
    vzeroupper
    ret

