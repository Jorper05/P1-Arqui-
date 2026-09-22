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
    xor     eax, eax
    vxorps  ymm0, ymm0, ymm0

    mov     ecx, esi
    and     ecx, -8                  ; cantidad procesable en bloques de 8

.sum_vec_loop:
    cmp     eax, ecx
    jge     .sum_reduce

    vmovaps ymm1, [rdi + rax*4]      ; 8 floats, base alineada a 32 B
    vaddps  ymm0, ymm0, ymm1

    add     eax, 8
    jmp     .sum_vec_loop


.sum_reduce:
    ; --- reduccion horizontal: 8 carriles de ymm0 -> un escalar ---
    vextractf128 xmm2, ymm0, 1     ; xmm2 = mitad alta (carriles 4-7)
    vaddps  xmm0, xmm0, xmm2       ; xmm0 = 4 sumas parciales (carriles 0-3 + 4-7)
    vhaddps xmm0, xmm0, xmm0       ; suma horizontal dentro de 128 bits
    vhaddps xmm0, xmm0, xmm0       ; xmm0[0] = suma total de los 8 carriles originales

.sum_tail:
    cmp     eax, esi
    jge     .sum_done

    vmovss  xmm1, [rdi + rax*4]
    vaddss  xmm0, xmm0, xmm1

    inc     eax
    jmp     .sum_tail

.sum_done:
    vzeroupper                     ; evita penalizacion de transicion AVX/SSE
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
    test    esi, esi
    jg      .stats_nonzero

    ; Caso n == 0: escribir 0.0 en todos los resultados.
    vxorps  xmm0, xmm0, xmm0
    vmovss  [rdx], xmm0
    vmovss  [rcx], xmm0
    vmovss  [r8],  xmm0
    vmovss  [r9],  xmm0
    vzeroupper
    ret

.stats_nonzero:
    ; -----------------------------------------------------------
    ; Primera pasada: SUM, MIN y MAX.
    ; -----------------------------------------------------------
    xor     eax, eax
    mov     r10d, esi
    and     r10d, -8                 ; limite vectorial

    vxorps  ymm0, ymm0, ymm0         ; acumulador de suma

    ; Inicializar min/max con arr[0].
    vbroadcastss ymm3, [rdi]
    vmovaps ymm4, ymm3

.stats_first_vec:
    cmp     eax, r10d
    jge     .stats_first_reduce

    vmovaps ymm1, [rdi + rax*4]
    vaddps  ymm0, ymm0, ymm1
    vminps  ymm3, ymm3, ymm1
    vmaxps  ymm4, ymm4, ymm1

    add     eax, 8
    jmp     .stats_first_vec

.stats_first_reduce:
    ; SUM: ymm0 -> xmm10[0]
    vextractf128 xmm2, ymm0, 1
    vaddps  xmm0, xmm0, xmm2
    vhaddps xmm0, xmm0, xmm0
    vhaddps xmm0, xmm0, xmm0
    vmovss  xmm10, xmm0              ; xmm10 = suma escalar

    ; MIN: ymm3 -> xmm11[0]
    vextractf128 xmm5, ymm3, 1
    vminps  xmm3, xmm3, xmm5
    vshufps xmm5, xmm3, xmm3, 0x4E
    vminps  xmm3, xmm3, xmm5
    vshufps xmm5, xmm3, xmm3, 0xB1
    vminps  xmm3, xmm3, xmm5
    vmovss  xmm11, xmm3

    ; MAX: ymm4 -> xmm12[0]
    vextractf128 xmm5, ymm4, 1
    vmaxps  xmm4, xmm4, xmm5
    vshufps xmm5, xmm4, xmm4, 0x4E
    vmaxps  xmm4, xmm4, xmm5
    vshufps xmm5, xmm4, xmm4, 0xB1
    vmaxps  xmm4, xmm4, xmm5
    vmovss  xmm12, xmm4

.stats_first_tail:
    ; Completar suma/min/max para n % 8 elementos.
    cmp     eax, esi
    jge     .stats_mean

    vmovss  xmm1, [rdi + rax*4]
    vaddss  xmm10, xmm10, xmm1
    vminss  xmm11, xmm11, xmm1
    vmaxss  xmm12, xmm12, xmm1

    inc     eax
    jmp     .stats_first_tail

.stats_mean:
    ; mean = sum / n
    vxorps      xmm6, xmm6, xmm6
    vcvtsi2ss   xmm6, xmm6, esi
    vdivss      xmm13, xmm10, xmm6   ; xmm13 = mean

    vmovss  [rdx], xmm13
    vmovss  [r8],  xmm11
    vmovss  [r9],  xmm12

    ; -----------------------------------------------------------
    ; Segunda pasada: sum((x - mean)^2)
    ; -----------------------------------------------------------
    xor     eax, eax
    vxorps  ymm2, ymm2, ymm2         ; acumulador de cuadrados
    vbroadcastss ymm6, xmm13          ; mean en los 8 carriles

.stats_var_vec:
    cmp     eax, r10d
    jge     .stats_var_reduce

    vmovaps ymm1, [rdi + rax*4]
    vsubps  ymm1, ymm1, ymm6
    vmulps  ymm1, ymm1, ymm1
    vaddps  ymm2, ymm2, ymm1

    add     eax, 8
    jmp     .stats_var_vec

.stats_var_reduce:
    ; Reducir el acumulador vectorial de varianza.
    vextractf128 xmm5, ymm2, 1
    vaddps  xmm2, xmm2, xmm5
    vhaddps xmm2, xmm2, xmm2
    vhaddps xmm2, xmm2, xmm2
    vmovss  xmm14, xmm2              ; suma de cuadrados escalar

.stats_var_tail:
    cmp     eax, esi
    jge     .stats_var_finish

    vmovss  xmm1, [rdi + rax*4]
    vsubss  xmm1, xmm1, xmm13
    vmulss  xmm1, xmm1, xmm1
    vaddss  xmm14, xmm14, xmm1

    inc     eax
    jmp     .stats_var_tail

.stats_var_finish:
    ; var = suma_cuadrados / n
    vxorps      xmm6, xmm6, xmm6
    vcvtsi2ss   xmm6, xmm6, esi
    vdivss      xmm14, xmm14, xmm6
    vmovss      [rcx], xmm14

    vzeroupper
    ret


; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                      float mean, float stddev)
;
;   rdi = in
;   rsi = out
;   edx = n
;   xmm0 = mean
;   xmm1 = stddev
;
; out[i] = (in[i] - mean) / stddev
;
; Si stddev == 0.0, se copia in[] a out[] para evitar division
; entre cero, tal como especifica include/stats.h.
; ---------------------------------------------------------------
normalize_array:
    test    edx, edx
    jle     .norm_done

    ; Comprobar stddev == 0.0 (tambien considera -0.0 como cero).
    vxorps  xmm2, xmm2, xmm2
    vucomiss xmm1, xmm2
    je      .norm_copy

    ; Guardar/broadcast de argumentos escalares antes del bucle.
    vmovss      xmm8, xmm0
    vmovss      xmm9, xmm1
    vbroadcastss ymm6, xmm8          ; mean
    vbroadcastss ymm7, xmm9          ; stddev

    xor     eax, eax
    mov     ecx, edx
    and     ecx, -8

.norm_vec_loop:
    cmp     eax, ecx
    jge     .norm_tail

    vmovaps ymm0, [rdi + rax*4]
    vsubps  ymm0, ymm0, ymm6
    vdivps  ymm0, ymm0, ymm7
    vmovaps [rsi + rax*4], ymm0

    add     eax, 8
    jmp     .norm_vec_loop

.norm_tail:
    cmp     eax, edx
    jge     .norm_done

    vmovss  xmm0, [rdi + rax*4]
    vsubss  xmm0, xmm0, xmm8
    vdivss  xmm0, xmm0, xmm9
    vmovss  [rsi + rax*4], xmm0

    inc     eax
    jmp     .norm_tail

.norm_copy:
    ; stddev == 0: copiar el arreglo sin modificarlo.
    xor     eax, eax
    mov     ecx, edx
    and     ecx, -8

.norm_copy_vec:
    cmp     eax, ecx
    jge     .norm_copy_tail

    vmovaps ymm0, [rdi + rax*4]
    vmovaps [rsi + rax*4], ymm0

    add     eax, 8
    jmp     .norm_copy_vec

.norm_copy_tail:
    cmp     eax, edx
    jge     .norm_done

    vmovss  xmm0, [rdi + rax*4]
    vmovss  [rsi + rax*4], xmm0

    inc     eax
    jmp     .norm_copy_tail

.norm_done:
    vzeroupper
    ret

; Evita el warning del linker por stack ejecutable.
section .note.GNU-stack noalloc noexec nowrite progbits
