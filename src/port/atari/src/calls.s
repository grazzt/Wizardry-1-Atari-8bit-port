; Jumps, procedure calls and returns, EXIT, and code-segment loading.
;
; Frame layout: mp points at a 12-byte mark-stack word (MSCW), followed by
; local word 1, 2, ... (parameters first, then locals):
;   +0  static link (frame of the lexical parent)
;   +2  dynamic link (caller's frame)
;   +4  return IPC
;   +6  caller's JTAB
;   +8  this procedure's JTAB (gives its lexical level and exit code)
;   +10 caller's segment number    +11 this frame's segment number
; Arguments are popped from the evaluation stack into words 1..n, the last
; one pushed becoming word 1 (a function's two result words are pushed last).

; --- jumps ---------------------------------------------------------------------------
op_ujp: jsr getb
        jmp do_jump

op_fjp: jsr getb
        tax
        pla                     ; condition: low bit set = true
        tay
        pla
        tya
        and #1
        bne @no
        txa
        jmp do_jump
@no:    NEXT

; A = displacement. Non-negative: relative to the next instruction. Negative:
; the jump-table entry at JTAB+A holds a self-relative pointer to the target.
do_jump:
        bmi @table
        clc
        adc ipc
        sta ipc
        bcc @n
        inc ipc+1
@n:     NEXT
@table: clc
        adc jtab
        sta ad
        lda jtab+1
        adc #$FF
        sta ad+1
        jsr self_relative
        lda t0
        sta ipc
        lda t0+1
        sta ipc+1
        NEXT

; t0 := ad - word(ad)
self_relative:
        ldy #0
        sec
        lda ad
        sbc (ad),y
        sta t0
        iny
        lda ad+1
        sbc (ad),y
        sta t0+1
        rts

; XJP: word-aligned low, high, then a UJP to the default case, then the
; self-relative case table.
op_xjp: lda ipc
        and #1
        beq @even
        inc ipc
        bne @even
        inc ipc+1
@even:  ldy #0
        lda (ipc),y
        sta t4
        iny
        lda (ipc),y
        sta t4+1                ; low
        iny
        lda (ipc),y
        sta t5
        iny
        lda (ipc),y
        sta t5+1                ; high
        POPW t3                 ; index
        lda t3                  ; index < low ?
        sta t0
        lda t3+1
        sta t0+1
        lda t4
        sta t1
        lda t4+1
        sta t1+1
        jsr scmp
        bmi @default
        lda t5                  ; high < index ?
        sta t0
        lda t5+1
        sta t0+1
        lda t3
        sta t1
        lda t3+1
        sta t1+1
        jsr scmp
        bmi @default
        sec                     ; entry := ipc + 6 + 2*(index - low)
        lda t3
        sbc t4
        sta t0
        lda t3+1
        sbc t4+1
        sta t0+1
        asl t0
        rol t0+1
        clc
        lda ipc
        adc #6
        sta ad
        lda ipc+1
        adc #0
        sta ad+1
        jsr ad_plus_t0
        jsr self_relative
        lda t0
        sta ipc
        lda t0+1
        sta ipc+1
        NEXT
@default:
        clc                     ; continue at the UJP that follows
        lda ipc
        adc #4
        sta ipc
        bcc @d
        inc ipc+1
@d:     NEXT

; --- calls -----------------------------------------------------------------------------
op_cip: jsr getb                ; CIP, CLP, CGP and CBP: same segment
        sta cproc
        lda curseg
        sta cseg
        jmp docall

op_cxp: jsr getb
        sta cseg
        jsr getb
        sta cproc
        lda cseg
        bne @notos
        jmp os_call             ; segment 0: Pascal OS entry points
@notos: cmp #28
        bne docall
        jmp chainstuff          ; the CHAINSTUFF library unit

docall: ldx calllog_i             ; debugging: log (segment, procedure)
        lda cseg
        sta CALLLOG,x
        lda cproc
        sta CALLLOG+1,x
        inx
        inx
        stx calllog_i
        lda program
        bne @game
        jsr disk_swap           ; the start-up utilities' disk prompts
        jmp @swapped
@game:  jsr music_cue           ; the game: each place's music
@swapped:
        ldx cseg
        jsr load_segment
        ldx cseg
        ; ad := segment end - 2 - 2*proc: the procedure's dictionary entry
        clc
        lda seg_base_lo,x
        adc seg_len_lo,x
        sta t0
        lda seg_base_hi,x
        adc seg_len_hi,x
        sta t0+1
        lda cproc
        asl a
        sta t1
        lda #0
        rol a
        sta t1+1
        clc
        lda t1
        adc #2
        sta t1
        bcc @a
        inc t1+1
@a:     sec
        lda t0
        sbc t1
        sta ad
        lda t0+1
        sbc t1+1
        sta ad+1
        jsr self_relative       ; t0 := JTAB of the callee
        lda t0
        sta t2
        lda t0+1
        sta t2+1
        ldy #0
        lda (t2),y              ; procedure number 0 = native code
        bne @pcode
        lda cseg
        cmp #1
        beq @native
        lda #11
        jmp vmerror
@native:
        jmp native_dispatch

@pcode: ldy #1
        lda (t2),y
        sta lexwant
        sec                     ; ad := JTAB - 8
        lda t2
        sbc #8
        sta ad
        lda t2+1
        sbc #0
        sta ad+1
        ldy #0
        lda (ad),y
        sta t3                  ; local data bytes
        iny
        lda (ad),y
        sta t3+1
        iny
        lda (ad),y
        sta t4                  ; parameter bytes
        iny
        lda (ad),y
        sta t4+1
        clc                     ; ad := JTAB - 2: ENTERIC
        lda ad
        adc #6
        sta ad
        bcc @b
        inc ad+1
@b:     jsr self_relative
        lda t0
        sta t5
        lda t0+1
        sta t5+1

        ; static link: walk out from the caller to lexical level lexwant-1
        jsr fp_mp
@walk:  ldy #8
        lda (fp),y
        sta ad
        iny
        lda (fp),y
        sta ad+1
        ldy #1
        lda (ad),y              ; level of frame fp (signed)
        sec
        sbc lexwant
        bvc @v
        eor #$80
@v:     bmi @found
        ldy #0
        lda (fp),y
        pha
        iny
        lda (fp),y
        sta fp+1
        pla
        sta fp
        jmp @walk

@found: clc                     ; frame size = MSCW + locals + parameters
        lda t3
        adc t4
        sta t7
        lda t3+1
        adc t4+1
        sta t7+1
        clc
        lda t7
        adc #MSCW
        sta t7
        bcc @c
        inc t7+1
@c:     jsr stack_alloc_w
        lda sp
        sta newmp
        sta ad
        lda sp+1
        sta newmp+1
        sta ad+1
        ; arguments into words 1..n
        clc
        lda ad
        adc #MSCW
        sta ad
        bcc @d
        inc ad+1
@d:     lsr t4+1
        ror t4
@args:  lda t4
        ora t4+1
        beq @mscw
        ldy #0
        pla
        sta (ad),y
        iny
        pla
        sta (ad),y
        clc
        lda ad
        adc #2
        sta ad
        bcc @e
        inc ad+1
@e:     lda t4
        bne @f
        dec t4+1
@f:     dec t4
        jmp @args

@mscw:  ldy #0
        lda fp
        sta (newmp),y
        iny
        lda fp+1
        sta (newmp),y
        iny
        lda mp
        sta (newmp),y
        iny
        lda mp+1
        sta (newmp),y
        iny
        lda ipc
        sta (newmp),y
        iny
        lda ipc+1
        sta (newmp),y
        iny
        lda jtab
        sta (newmp),y
        iny
        lda jtab+1
        sta (newmp),y
        iny
        lda t2
        sta (newmp),y
        iny
        lda t2+1
        sta (newmp),y
        iny
        lda curseg
        sta (newmp),y
        iny
        lda cseg
        sta (newmp),y
        ldx cseg
        inc seg_refs,x
        lda newmp
        sta mp
        lda newmp+1
        sta mp+1
        lda t2
        sta jtab
        lda t2+1
        sta jtab+1
        lda cseg
        sta curseg
        lda t5
        sta ipc
        lda t5+1
        sta ipc+1
        lda base+1              ; the first call is the program body
        bne @g
        lda mp
        sta base
        lda mp+1
        sta base+1
@g:     NEXT

; --- returns ---------------------------------------------------------------------------
op_rnp: jsr getb                ; RNP and RBP: return n words
        sta t6
        jsr fp_mp
        ldy #8                  ; ad := own JTAB - 8 (sizes)
        lda (fp),y
        sec
        sbc #8
        sta ad
        iny
        lda (fp),y
        sbc #0
        sta ad+1
        ldy #0
        clc
        lda (ad),y
        ldy #2
        adc (ad),y
        sta t7
        ldy #1
        lda (ad),y
        ldy #3
        adc (ad),y
        sta t7+1
        clc
        lda t7
        adc #MSCW
        sta t7
        bcc @a
        inc t7+1
@a:     ldy #4
        lda (fp),y
        sta ipc
        iny
        lda (fp),y
        sta ipc+1
        iny
        lda (fp),y
        sta jtab
        iny
        lda (fp),y
        sta jtab+1
        ldy #10
        lda (fp),y
        sta curseg
        iny
        lda (fp),y
        sta t6+1                ; segment of the returning frame
        ldy #2
        lda (fp),y
        sta mp
        iny
        lda (fp),y
        sta mp+1
        clc
        lda fp
        adc t7
        sta sp
        lda fp+1
        adc t7+1
        sta sp+1
        ldx t6+1
        dec seg_refs,x
        bne @kept
        clc                     ; last activation: drop the segment
        lda sp
        adc seg_len_lo,x
        sta sp
        lda sp+1
        adc seg_len_hi,x
        sta sp+1
        lda #0
        sta seg_base_lo,x
        sta seg_base_hi,x
@kept:  ; push result words n..1 (word 1 ends on top)
        ldx t6
        beq @done
@res:   txa
        asl a
        adc #MSCW-2+1           ; high byte of word x
        tay
        lda (fp),y
        pha
        dey
        lda (fp),y
        pha
        dex
        bne @res
@done:  lda mp+1                ; returned from the program body?
        cmp osf+1
        bne @n
        lda mp
        cmp osf
        bne @n
        jmp program_end
@n:     NEXT

; --- EXIT(segment, procedure) --------------------------------------------------------------
; Every activation from the current one out to the named procedure runs its
; exit code: the current one now, each caller when its callee returns.
csp_exit:
        POPW t0                 ; procedure
        POPW t1                 ; segment
        jsr fp_mp
@find:  ldy #11
        lda (fp),y
        cmp t1
        bne @next
        ldy #8
        lda (fp),y
        sta ad
        iny
        lda (fp),y
        sta ad+1
        ldy #0
        lda (ad),y
        cmp t0
        beq @found
@next:  lda fp
        cmp osf
        bne @up
        lda fp+1
        cmp osf+1
        bne @up
        lda #3                  ; exit from an uncalled procedure
        jmp vmerror
@up:    ldy #2
        lda (fp),y
        pha
        iny
        lda (fp),y
        sta fp+1
        pla
        sta fp
        jmp @find
@found: lda fp                  ; t3 := target frame
        sta t3
        lda fp+1
        sta t3+1
        lda jtab                ; current procedure continues at its exit code
        sta t2
        lda jtab+1
        sta t2+1
        jsr exit_ic
        lda t0
        sta ipc
        lda t0+1
        sta ipc+1
        jsr fp_mp
@mark:  lda fp
        cmp t3
        bne @set
        lda fp+1
        cmp t3+1
        beq @end
@set:   ldy #2                  ; caller of fp
        lda (fp),y
        sta t4
        iny
        lda (fp),y
        sta t4+1
        ldy #8                  ; caller's JTAB
        lda (t4),y
        sta t2
        iny
        lda (t4),y
        sta t2+1
        jsr exit_ic
        ldy #4                  ; fp returns into the caller's exit code
        lda t0
        sta (fp),y
        iny
        lda t0+1
        sta (fp),y
        lda t4
        sta fp
        lda t4+1
        sta fp+1
        jmp @mark
@end:   NEXT

exit_ic:                        ; t0 := EXITIC of the procedure whose JTAB is t2
        sec
        lda t2
        sbc #4
        sta ad
        lda t2+1
        sbc #0
        sta ad+1
        jmp self_relative

; --- code segments -------------------------------------------------------------------------
; Load segment X onto the memory stack if it is not resident.
load_segment:
        lda seg_base_hi,x
        bne @done
        lda seg_len_lo,x
        ora seg_len_hi,x
        bne @ok
        lda #2                  ; no such segment
        jmp vmerror
@ok:    stx t6
        lda seg_len_lo,x
        sta t7
        lda seg_len_hi,x
        sta t7+1
        jsr stack_alloc_w
        ldx t6
        lda sp
        sta seg_base_lo,x
        sta t2
        lda sp+1
        sta seg_base_hi,x
        sta t2+1
        lda seg_len_lo,x
        sta cnt
        lda seg_len_hi,x
        sta cnt+1
        lda seg_block_lo,x
        sta t4
        lda seg_block_hi,x
        sta t4+1
        jsr disk_read_code
        ldx t6
@done:  rts
