; p-code instruction handlers (opcodes 128-255) and arithmetic helpers.
; Only the instructions WIZARDRY.CODE uses are implemented; the rest raise
; execution error 11, as RTSTRP.APPLE does for the opcodes it strips.

optab:
        .word op_abi, op_bad, op_adi, op_bad, op_land, op_bad, op_dvi, op_bad    ; 128
        .word op_bad, op_bad, op_bad, op_bad, op_bad, op_lor, op_modi, op_mpi    ; 136
        .word op_bad, op_ngi, op_bad, op_lnot, op_bad, op_sbi, op_bad, op_bad    ; 144
        .word op_bad, op_bad, op_sto, op_bad, op_bad, op_bad, op_csp, op_ldcn    ; 152
        .word op_bad, op_fjp, op_inc, op_ind, op_ixa, op_lao, op_lsa, op_bad     ; 160
        .word op_mov, op_ldo, op_sas, op_sro, op_xjp, op_rnp, op_cip, op_equ     ; 168
        .word op_bad, op_bad, op_lda, op_bad, op_bad, op_bad, op_lod, op_neq     ; 176
        .word op_str, op_ujp, op_ldp, op_stp, op_bad, op_bad, op_ldb, op_stb     ; 184
        .word op_ixp, op_rnp, op_cip, op_equi, op_geqi, op_grti, op_lla, op_ldci ; 192
        .word op_leqi, op_lesi, op_ldl, op_neqi, op_stl, op_cxp, op_cip, op_cip  ; 200
        .word op_bad, op_bad, op_bad, op_bad, op_bad, op_bad, op_bad, op_nop     ; 208
        .word op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl ; 216
        .word op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl, op_sldl ; 224
        .word op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo ; 232
        .word op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo, op_sldo ; 240
        .word op_sind, op_sind, op_sind, op_sind, op_sind, op_sind, op_sind, op_sind ; 248

op_bad: lda #11
        jmp vmerror

op_nop: NEXT

; --- constants and short loads ------------------------------------------------
op_ldci:
        jsr getw
        PUSHW t0
        NEXT

op_ldcn:
        lda #0
        pha
        pha
        NEXT

op_sldl:                        ; SLDL1..16: local word opcode-215
        lda opcode
        sec
        sbc #215
        asl a
        adc #MSCW-2             ; carry is clear after ASL of a small value
        tay
        lda (mp),y
        tax
        iny
        lda (mp),y
        pha
        txa
        pha
        NEXT

op_sldo:                        ; SLDO1..16: global word opcode-231
        lda opcode
        sec
        sbc #231
        asl a
        adc #MSCW-2
        tay
        lda (base),y
        tax
        iny
        lda (base),y
        pha
        txa
        pha
        NEXT

op_sind:                        ; SIND0..7: load word at TOS + 2*n
        POPW ad
        lda opcode
        sec
        sbc #248
        asl a
        tay
push_ad_y:
        lda (ad),y
        tax
        iny
        lda (ad),y
        pha
        txa
        pha
        NEXT

; --- locals, globals, intermediates ---------------------------------------------
op_ldl: jsr getbig
        jsr fp_mp
        jmp push_local
op_ldo: jsr getbig
        jsr fp_base
        jmp push_local
op_lod: jsr getb
        jsr walk
        jsr getbig
push_local:
        jsr frame_addr
push_ad:
        ldy #0
        jmp push_ad_y

op_lla: jsr getbig
        jsr fp_mp
        jmp push_laddr
op_lao: jsr getbig
        jsr fp_base
        jmp push_laddr
op_lda: jsr getb
        jsr walk
        jsr getbig
push_laddr:
        jsr frame_addr
        PUSHW ad
        NEXT

op_stl: jsr getbig
        jsr fp_mp
        jmp store_local
op_sro: jsr getbig
        jsr fp_base
        jmp store_local
op_str: jsr getb
        jsr walk
        jsr getbig
store_local:
        jsr frame_addr
store_ad:
        ldy #0
        pla
        sta (ad),y
        pla
        iny
        sta (ad),y
        NEXT

fp_mp:  lda mp
        sta fp
        lda mp+1
        sta fp+1
        rts
fp_base:
        lda base
        sta fp
        lda base+1
        sta fp+1
        rts

; --- indirection and addressing -------------------------------------------------
op_sto: POPW t0                 ; value
        POPW ad
        ldy #0
        lda t0
        sta (ad),y
        iny
        lda t0+1
        sta (ad),y
        NEXT

op_ind: jsr getbig
        POPW ad
        jsr ad_plus_2t0
        jmp push_ad

op_inc: jsr getbig
        POPW ad
        jsr ad_plus_2t0
        PUSHW ad
        NEXT

ad_plus_2t0:
        asl t0
        rol t0+1
ad_plus_t0:
        clc
        lda ad
        adc t0
        sta ad
        lda ad+1
        adc t0+1
        sta ad+1
        rts

op_ixa: jsr getbig              ; element size in words
        POPW t1                 ; index
        POPW ad                 ; array base
        jsr mul16               ; t0 * t1 -> mulx
        lda mulx
        sta t0
        lda mulx+1
        sta t0+1
        jsr ad_plus_2t0
        PUSHW ad
        NEXT

op_ixp: jsr getb                ; elements per word
        sta t1
        jsr getb                ; field width
        sta t3
        POPW t0                 ; index
        POPW ad
        lda #0
        sta t1+1
        jsr divu16              ; t0 := index / per-word, mulx := remainder
        jsr ad_plus_2t0
        PUSHW ad
        lda #0
        pha
        lda t3
        pha
        ldx mulx                ; right bit = remainder * width
        lda #0
@mul:   cpx #0
        beq @done
        clc
        adc t3
        dex
        bne @mul
@done:  tax
        lda #0
        pha
        txa
        pha
        NEXT

field_mask:                     ; t2 := (1 << t1) - 1 for width t1 (1..16)
        lda #0
        sta t2
        sta t2+1
        ldx t1
@m:     sec
        rol t2
        rol t2+1
        dex
        bne @m
        rts

op_ldp: POPW t0                 ; right bit
        POPW t1                 ; width
        POPW ad
        ldy #0
        lda (ad),y
        sta t3
        iny
        lda (ad),y
        sta t3+1
        ldx t0
        beq @mask
@shift: lsr t3+1
        ror t3
        dex
        bne @shift
@mask:  jsr field_mask
        lda t3+1
        and t2+1
        pha
        lda t3
        and t2
        pha
        NEXT

op_stp: POPW t4                 ; value
        POPW t0                 ; right bit
        POPW t1                 ; width
        POPW ad
        jsr field_mask
        ldx t0
        beq @placed
@shift: asl t2
        rol t2+1
        asl t4
        rol t4+1
        dex
        bne @shift
@placed:
        ldy #0
        lda t2
        eor #$FF
        and (ad),y
        sta t5
        lda t4
        and t2
        ora t5
        sta (ad),y
        iny
        lda t2+1
        eor #$FF
        and (ad),y
        sta t5
        lda t4+1
        and t2+1
        ora t5
        sta (ad),y
        NEXT

op_ldb: POPW t0                 ; index
        POPW ad
        jsr ad_plus_t0
        lda ad+1
        cmp #$BF
        bcc @mem
        jmp ldb_io              ; Apple keyboard / BIOS locations
@mem:   lda #0
        pha
        tay
        lda (ad),y
        pha
        NEXT

op_stb: POPW t1                 ; value
        POPW t0                 ; index
        POPW ad
        jsr ad_plus_t0
        lda ad+1
        cmp #$C0
        bne @mem
        jmp stb_io              ; Apple soft switch
@mem:   ldy #0
        lda t1
        sta (ad),y
        NEXT

op_mov: jsr getbig              ; words
        asl t0
        rol t0+1
        lda t0
        sta cnt
        lda t0+1
        sta cnt+1
        POPW t1                 ; source
        POPW t2                 ; destination
        jsr memcpy
        NEXT

op_lsa: PUSHW ipc               ; address of the length byte
        jsr getb
        clc
        adc ipc
        sta ipc
        bcc @n
        inc ipc+1
@n:     NEXT

op_sas: jsr getb                ; declared maximum length
        sta t3
        POPW t1                 ; source: string address, or a character
        POPW t2                 ; destination
        lda t1+1
        bne @string
        ldy #0
        lda #1
        sta (t2),y
        iny
        lda t1
        sta (t2),y
        NEXT
@string:
        ldy #0
        lda (t1),y
        cmp t3
        beq @fits
        bcc @fits
        lda #13                 ; string overflow
        jmp vmerror
@fits:  clc
        adc #1
        sta cnt
        lda #0
        adc #0
        sta cnt+1
        jsr memcpy
        NEXT

; memcpy: cnt bytes from (t1) to (t2), ascending. Clobbers t1, t2, cnt.
memcpy: ldy #0
@loop:  lda cnt
        ora cnt+1
        beq @done
        lda (t1),y
        sta (t2),y
        inc t1
        bne @s
        inc t1+1
@s:     inc t2
        bne @d
        inc t2+1
@d:     lda cnt
        bne @c
        dec cnt+1
@c:     dec cnt
        jmp @loop
@done:  rts

; --- arithmetic -------------------------------------------------------------------
op_adi: POPW t1
        POPW t0
        clc
        lda t0
        adc t1
        tax
        lda t0+1
        adc t1+1
        pha
        txa
        pha
        NEXT

op_sbi: POPW t1
        POPW t0
        sec
        lda t0
        sbc t1
        tax
        lda t0+1
        sbc t1+1
        pha
        txa
        pha
        NEXT

op_land:
        POPW t1
        pla
        and t1
        tax
        pla
        and t1+1
        pha
        txa
        pha
        NEXT

op_lor: POPW t1
        pla
        ora t1
        tax
        pla
        ora t1+1
        pha
        txa
        pha
        NEXT

op_lnot:
        pla
        eor #$FF
        tax
        pla
        eor #$FF
        pha
        txa
        pha
        NEXT

op_ngi: POPW t0
        jsr neg_t0
        PUSHW t0
        NEXT

op_abi: POPW t0
        lda t0+1
        bpl @pos
        jsr neg_t0
@pos:   PUSHW t0
        NEXT

neg_t0: sec
        lda #0
        sbc t0
        sta t0
        lda #0
        sbc t0+1
        sta t0+1
        rts

neg_t1: sec
        lda #0
        sbc t1
        sta t1
        lda #0
        sbc t1+1
        sta t1+1
        rts

op_mpi: POPW t1
        POPW t0
        jsr mul16
        PUSHW mulx
        NEXT

; mulx := t0 * t1 (low 16 bits). Clobbers t0, t1.
mul16:  lda #0
        sta mulx
        sta mulx+1
        ldx #16
@loop:  lsr t1+1
        ror t1
        bcc @skip
        clc
        lda mulx
        adc t0
        sta mulx
        lda mulx+1
        adc t0+1
        sta mulx+1
@skip:  asl t0
        rol t0+1
        dex
        bne @loop
        rts

; t0 := t0 / t1, mulx := t0 mod t1 (unsigned).
divu16: lda #0
        sta mulx
        sta mulx+1
        ldx #16
@loop:  asl t0
        rol t0+1
        rol mulx
        rol mulx+1
        sec
        lda mulx
        sbc t1
        tay
        lda mulx+1
        sbc t1+1
        bcc @skip
        sta mulx+1
        sty mulx
        inc t0
@skip:  dex
        bne @loop
        rts

; Signed divide: quotient truncates toward zero; the remainder takes the
; dividend's sign.
divs16: lda t1
        ora t1+1
        bne @ok
        lda #6                  ; divide by zero
        jmp vmerror
@ok:    lda t0+1
        sta sign                ; dividend sign (bit 7)
        eor t1+1
        sta sign+1              ; quotient sign
        lda t0+1
        bpl @a
        jsr neg_t0
@a:     lda t1+1
        bpl @b
        jsr neg_t1
@b:     jsr divu16
        lda sign+1
        bpl @q
        jsr neg_t0
@q:     lda sign
        bpl @r
        sec
        lda #0
        sbc mulx
        sta mulx
        lda #0
        sbc mulx+1
        sta mulx+1
@r:     rts

op_dvi: POPW t1
        POPW t0
        jsr divs16
        PUSHW t0
        NEXT

op_modi:
        POPW t1
        POPW t0
        jsr divs16
        PUSHW mulx
        NEXT

; --- comparisons ------------------------------------------------------------------
push_true:
        lda #0
        pha
        lda #1
        pha
        NEXT
push_false:
        lda #0
        pha
        pha
        NEXT

op_equi:
        POPW t1
        POPW t0
        jsr ucmp_eq
        bne @f
        jmp push_true
@f:     jmp push_false

op_neqi:
        POPW t1
        POPW t0
        jsr ucmp_eq
        beq @f
        jmp push_true
@f:     jmp push_false

ucmp_eq:                        ; Z=1 if t0 == t1
        lda t0
        cmp t1
        bne @r
        lda t0+1
        cmp t1+1
@r:     rts

scmp:                           ; N=1 if t0 < t1 (signed)
        lda t0
        cmp t1
        lda t0+1
        sbc t1+1
        bvc @v
        eor #$80
@v:     rts

op_lesi:                        ; a < b
        POPW t1
        POPW t0
        jsr scmp
        bpl @f
        jmp push_true
@f:     jmp push_false

op_geqi:                        ; a >= b
        POPW t1
        POPW t0
        jsr scmp
        bmi @f
        jmp push_true
@f:     jmp push_false

op_grti:                        ; a > b  ==  b < a
        POPW t0
        POPW t1
        jsr scmp
        bpl @f
        jmp push_true
@f:     jmp push_false

op_leqi:                        ; a <= b  ==  not (b < a)
        POPW t0
        POPW t1
        jsr scmp
        bmi @f
        jmp push_true
@f:     jmp push_false

; EQU/NEQ on strings (type 4) and multi-word blocks (type 12): the only
; non-integer comparisons Wizardry uses. Operands are addresses.
op_equ: jsr cmp_operands
        POPW t1
        POPW t2
        jsr cmp_blocks
        bne @f
        jmp push_true
@f:     jmp push_false

op_neq: jsr cmp_operands
        POPW t1
        POPW t2
        jsr cmp_blocks
        beq @f
        jmp push_true
@f:     jmp push_false

cmp_operands:                   ; t3 := type; cnt := bytes for type 12
        jsr getb
        sta t3
        cmp #4
        beq @r
        cmp #12
        beq @words
        lda #11
        jmp vmerror
@words: jsr getbig
        asl t0
        rol t0+1
        lda t0
        sta cnt
        lda t0+1
        sta cnt+1
@r:     rts

cmp_blocks:                     ; Z=1 if equal
        ldy #0
        lda t3
        cmp #4
        beq @str
@wl:    lda cnt
        ora cnt+1
        beq @eq
        lda (t1),y
        cmp (t2),y
        bne @ne
        inc t1
        bne @w1
        inc t1+1
@w1:    inc t2
        bne @w2
        inc t2+1
@w2:    lda cnt
        bne @w3
        dec cnt+1
@w3:    dec cnt
        jmp @wl
@str:   lda t1+1                ; a character operand is a 1-character string
        bne @s1
        jsr @charstr1
@s1:    lda t2+1
        bne @s2
        jsr @charstr2
@s2:    lda (t1),y
        cmp (t2),y
        bne @ne
        tax
        beq @eq
@sl:    iny
        lda (t1),y
        cmp (t2),y
        bne @ne
        dex
        bne @sl
@eq:    lda #0
        rts
@ne:    lda #1
        rts
@charstr1:
        lda t1
        sta charbuf1+1
        lda #<charbuf1
        sta t1
        lda #>charbuf1
        sta t1+1
        rts
@charstr2:
        lda t2
        sta charbuf2+1
        lda #<charbuf2
        sta t2
        lda #>charbuf2
        sta t2+1
        rts

charbuf1:   .byte 1, 0
charbuf2:   .byte 1, 0
