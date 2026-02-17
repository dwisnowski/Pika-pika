; Runtime variable-cycle delay for PRU
; First argument (number of 2-cycle iterations) in r14 (PRU C ABI).
; Total delay = 2 * iterations cycles (SUB + QBNE per iteration).
; Call from C as: delay_cycles_runtime(sample_period_cycles >> 1);

    .sect ".text"
    .global delay_cycles_runtime
    .asmfunc
delay_cycles_runtime:
    QBEQ done, r14, 0    ; if iterations == 0, return
delay_loop:
    SUB r14, r14, 1
    QBNE delay_loop, r14, 0
done:
    JMP r3.w2            ; return (r3.w2 = return address)
    .endasmfunc
