global sum_array
    global compute_stats
    global normalize_array

    section .text

sum_array:
    xor     eax, eax           ; eax = i = 0
    xorpd   xmm0, xmm0         ; xmm0 = acumulador EN DOUBLE = 0.0
    ; Antes se acumulaba en xmm0 como float (addss), pero eso pierde
    ; precision en sumas largas (igual que le paso al vectorial).
    ; Se corrige igual que en el vectorial: cada elemento se convierte
    ; a double antes de sumarlo, y el acumulador se mantiene en double
    ; durante todo el recorrido. Se usan
    ; mas bits de precision intermedia; la logica del bucle no cambia.

.sum_loop:
    cmp     eax, esi
    jge     .sum_done
    cvtss2sd xmm1, [rdi + rax*4]   ; arr[i]: float -> double
    addsd   xmm0, xmm1              ; acumulador += arr[i], en double
    inc     eax
    jmp     .sum_loop

.sum_done:
    cvtsd2ss xmm0, xmm0            ; convierto el resultado final a float
    ret                             ; (la firma de la funcion sigue siendo float)

compute_stats:
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    cmp     esi, 0
    je      .zero_case

    mov    rbx, rdx
    mov    r12, rcx
    mov    r13, r8
    mov    r14, r9
    mov    r15, rdi

    push   rsi
    push   rsi

    call    sum_array
    pop    rsi
    pop    rsi

    cvtsi2ss xmm1, esi
    divss   xmm0, xmm1
    movss   [rbx], xmm0

    mov     rdx, rbx
    mov     rcx, r12
    mov     r8, r13
    mov     r9, r14
    mov     rdi, r15

    xor     eax, eax
    xorpd   xmm0, xmm0          ; acumulador EN DOUBLE = 0.0
    cvtss2sd xmm2, [rbx]        ; mean (float) -> double, se lee UNA vez
                                 ; y se reutiliza en cada vuelta del bucle

    .var_loop:
        cmp     eax, esi
        jge     .var_done
        cvtss2sd xmm1, [rdi + rax*4]   ; arr[i]: float -> double
        subsd   xmm1, xmm2               ; (arr[i] - mean), en double
        mulsd   xmm1, xmm1               ; (arr[i] - mean)^2, en double
        addsd   xmm0, xmm1               ; acumulador += eso, en double
        inc     eax
        jmp     .var_loop

    .var_done:
    cvtsi2sd xmm1, esi
    divsd   xmm0, xmm1          ; var = acumulador / n, en double
    cvtsd2ss xmm0, xmm0         ; convierto el resultado final a float
    movss   [rcx], xmm0

    movss   xmm0, [rdi]
    movss   xmm1, [rdi]

    mov     eax, 1
    .min_max_loop:
        cmp     eax, esi
        jge     .min_max_done
        movss   xmm2, [rdi + rax*4]
        comiss  xmm2, xmm0
        jb      .update_min
        comiss  xmm2, xmm1
        ja      .update_max
        inc     eax
        jmp     .min_max_loop

    .update_min:
        movss   xmm0, xmm2
        inc     eax
        jmp     .min_max_loop

    .update_max:
        movss   xmm1, xmm2
        inc     eax
        jmp     .min_max_loop

    .min_max_done:
    movss   [r8], xmm0
    movss   [r9], xmm1

    jmp    .done

    .zero_case:
    xorps xmm0, xmm0
    movss   [rdx], xmm0
    movss   [rcx], xmm0
    movss   [r8], xmm0
    movss   [r9], xmm0

    .done:
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    ret

normalize_array:
    movaps  xmm8, xmm0
    movaps  xmm9, xmm1

    xor     eax, eax

    xorps   xmm2, xmm2
    comiss  xmm9, xmm2
    je      .copy_in

.normalize_loop:
    cmp     eax, edx
    jge     .normalize_done
    movss   xmm2, [rdi + rax*4]
    subss   xmm2, xmm8
    divss   xmm2, xmm9
    movss   [rsi + rax*4], xmm2
    inc     eax
    jmp     .normalize_loop

.copy_in:
    cmp     eax, edx
    jge     .normalize_done
    movss   xmm2, [rdi + rax*4]
    movss   [rsi + rax*4], xmm2
    inc     eax
    jmp     .copy_in

.normalize_done:
    ret

section .note.GNU-stack noalloc noexec nowrite progbits