; Atari versions of WIZARDRY.CODE's seven native routines (segment 1,
; procedures 26-32). They take their arguments from the evaluation stack
; like the Apple originals, last argument on top.
;
; Graphics: each Apple hi-res byte (7 pixels, bit 0 leftmost) becomes one
; Atari mode F byte in the same column (8 pixels, bit 7 leftmost, the 7th
; pixel doubled). 40 columns x 8 = 320 pixels: the Apple layout fills the
; Atari screen exactly, slightly stretched.

native_dispatch:
        lda program
        bne @game
        lda cproc               ; SYSTEM.STARTUP: LZDECOMP only (CHKSYNCH is
        cmp #2                  ; patched out with the copy protection)
        bne @bad
        jmp nat_lzdecomp
@game:  lda cproc
        sec
        sbc #26
        cmp #7
        bcc @ok
@bad:   lda #11
        jmp vmerror
@ok:    asl a
        tax
        lda native_tab,x
        sta vec
        lda native_tab+1,x
        sta vec+1
        jmp (vec)

native_tab:
        .word nat_clrpict, nat_drawline, nat_random, nat_keyavail
        .word nat_clrrect, nat_mvcursor, nat_prgrchr

; CLRPICT(x1, y1, x2, y2): with y2 = 100, clear the 82x79 picture area
; (hi-res lines 5-83), keeping the frame pixels at both edges. Otherwise set
; the clipping box for DRAWLINE.
nat_clrpict:
        pla
        sta nat0                ; y2
        pla
        lda nat0
        cmp #100
        beq @clear
        sta clip_yhi
        pla
        sta clip_xhi
        pla
        pla
        sta clip_ylo
        pla
        pla
        sta clip_xlo
        pla
        NEXT
@clear: pla                     ; discard x1, y1, x2
        pla
        pla
        pla
        pla
        pla
        jsr pic_hook_off
        ldx #5
@line:  lda bm_row_lo,x
        sta nat0
        lda bm_row_hi,x
        sta nat0+1
        ldy #0
        lda (nat0),y
        and #$F0                ; Apple AND #$0F: keep the 4 frame pixels
        sta (nat0),y
        lda #0
@zero:  iny
        sta (nat0),y
        cpy #11
        bne @zero
        iny
        lda (nat0),y
        and #$3F                ; Apple AND #$FC
        sta (nat0),y
        inx
        cpx #84
        bne @line
        NEXT

; DRAWLINE(x, y, dh, dv, length): plot length pixels (0 = 256) from (x, y)
; in picture coordinates, stepping by (dh, dv), skipping points outside the
; clipping box. The comparisons copy the Apple code's CMP/BMI tests exactly.
nat_drawline:
        jsr pic_hook_off        ; the maze replaces any picture
        pla
        sta nat0+4              ; length
        pla
        pla
        sta nat0+3              ; dv
        pla
        pla
        sta nat0+2              ; dh
        pla
        pla
        sta nat0+5              ; y
        pla
        pla
        sta nat0+6              ; x
        pla
@pixel: lda nat0+6
        cmp clip_xlo
        bmi @step
        cmp clip_xhi
        beq @xok
        bpl @step
@xok:   tax
        lda nat0+5
        cmp clip_ylo
        bmi @step
        cmp clip_yhi
        beq @yok
        bpl @step
@yok:   clc
        adc #5                  ; picture row 0 is hi-res line 5
        tay
        lda bm_row_lo,y
        sta nat0
        lda bm_row_hi,y
        sta nat0+1
        ldy draw_col,x
        lda draw_mask,x
        ora (nat0),y
        sta (nat0),y
@step:  clc
        lda nat0+6
        adc nat0+2
        sta nat0+6
        clc
        lda nat0+5
        adc nat0+3
        sta nat0+5
        dec nat0+4
        bne @pixel
        NEXT

; RANDOM: 0..32767, the Apple algorithm on the same four state bytes.
nat_random:
        pla                     ; the caller's two result words
        pla
        pla
        pla
        ldy #7
@shift: asl rng                 ; $47A
        php
        rol rng+1               ; $4FA
        rol rng+2               ; $57A
        rol rng+3               ; $5FB
        bmi @neg
        plp
        bpl @next
        bmi @inc
@neg:   plp
        bmi @next
@inc:   inc rng
@next:  dey
        bne @shift
        lda rng
        lsr a
        pha                     ; high byte
        lda rng+2
        pha                     ; low byte
        NEXT

; KEYAVAIL: TRUE if a key is waiting.
nat_keyavail:
        pla
        pla
        pla
        pla
        lda #0
        pha
        jsr key_waiting
        beq @no
        lda #1
@no:    pha
        NEXT

; MVCURSOR(x, y): special x values select modes; otherwise set the
; character cursor used by PRGRCHR.
nat_mvcursor:
        pla
        sta nat0+1              ; y
        pla
        pla
        sta nat0                ; x
        pla
        lda nat0
        cmp #40
        bne @m50
        jsr con_gfxmode
        NEXT
@m50:   cmp #50
        bne @m60
        jsr con_textmode
        NEXT
@m60:   cmp #60                 ; jump to the copy-protection code: never
        bne @m70                ; reached, COPYPROT is patched at build time
        NEXT
@m70:   cmp #70                 ; copy protection "crash and burn"
        bne @m80
        lda #$70
        jmp vmerror
@m80:   cmp #80
        bne @set
        jsr wait_key_stir
        NEXT
@set:   sta cur_col
        lda nat0+1
        sta cur_row
        NEXT

; Stir the RNG until a key is waiting: the counter at $47A..$47D on the
; Apple, of which only $47A is part of RANDOM's state.
wait_key_stir:
        lda TESTMODE
        beq @real
        lda #1
        sta WAITING
@wait:  jsr key_waiting         ; test mode: wait, then stir a fixed amount
        beq @wait
        lda #0
        sta WAITING
        lda TESTPOLLS
        sta nat0
        lda TESTPOLLS+1
        sta nat0+1
@fixed: jsr stir_once
        lda nat0
        ora nat0+1
        beq @done
        lda nat0
        bne @f1
        dec nat0+1
@f1:    dec nat0
        jmp @fixed
@real:  jsr key_waiting
        bne @done
        lda #1
        sta WAITING
@loop:  jsr stir_once
@chk:   jsr key_waiting
        beq @loop
        lda #0
        sta WAITING
@done:  rts

stir_once:
        inc rng
        bne @r
        inc rngpad
        bne @r
        inc rngpad+1
        bne @r
        inc rngpad+2
@r:     rts

; PRGRCHR(var image): draw an 8-row character image at the cursor, advance.
nat_prgrchr:
        jsr pic_hook_char
        POPW nat0+2             ; image address
        lda cur_row
        cmp #24
        bcs @off
        asl a
        asl a
        asl a                   ; pixel row = character row * 8
        sta nat0+4
        ldx #0
@row:   ldy nat0+4
        lda bm_row_lo,y
        sta nat0
        lda bm_row_hi,y
        sta nat0+1
        txa
        tay
        lda (nat0+2),y
        tay
        lda expand7,y
        ldy cur_col
        cpy #40
        bcs @skip
        sta (nat0),y
@skip:  inc nat0+4
        inx
        cpx #8
        bne @row
@off:   inc cur_col
        NEXT

; CLRRECT(x, y, width, height): clear width columns x height character rows.
nat_clrrect:
        pla
        sta nat0+4              ; height (rows)
        pla
        pla
        sta nat0+5              ; width (columns)
        pla
        pla
        asl a
        asl a
        asl a
        sta nat0+6              ; first pixel row
        pla
        pla
        sta nat0+7              ; first column
        pla
        jsr pic_hook_rect
        lda nat0+4
        asl a
        asl a
        asl a
        sta nat0+4              ; pixel rows
        beq @done
@row:   ldy nat0+6
        cpy #192
        bcs @done
        lda bm_row_lo,y
        sta nat0
        lda bm_row_hi,y
        sta nat0+1
        ldy nat0+7
        ldx nat0+5
        beq @next
        lda #0
@col:   cpy #40
        bcs @next
        sta (nat0),y
        iny
        dex
        bne @col
@next:  inc nat0+6
        dec nat0+4
        bne @row
@done:  NEXT

        .segment "TABLES"

; Bitmap row addresses: lines 0-101 at $2000, 102-191 at $3000 (ANTIC
; cannot cross a 4K boundary within a line).
bm_row_lo:
        .repeat 192, I
        .byte <(BITMAP + 40*I + (I >= 102) * 16)
        .endrepeat
bm_row_hi:
        .repeat 192, I
        .byte >(BITMAP + 40*I + (I >= 102) * 16)
        .endrepeat

; DRAWLINE: picture x -> byte column and Atari bit mask. Picture x 0 is
; hi-res pixel 4 (the first 4 columns belong to the frame).
draw_col:
        .repeat 89, I
        .byte (I + 4) / 7
        .endrepeat
draw_mask:
        .repeat 89, I
        .byte ((((I + 4) .mod 7) = 0) << 7) | ((((I + 4) .mod 7) = 1) << 6) | ((((I + 4) .mod 7) = 2) << 5) | ((((I + 4) .mod 7) = 3) << 4) | ((((I + 4) .mod 7) = 4) << 3) | ((((I + 4) .mod 7) = 5) << 2) | ((((I + 4) .mod 7) = 6) * 3)
        .endrepeat

; Apple hi-res byte -> Atari byte (bit order reversed, 7th pixel doubled).
expand7:
        .repeat 256, I
        .byte ((I & 1) << 7) | ((I & 2) << 5) | ((I & 4) << 3) | ((I & 8) << 1) | ((I & 16) >> 1) | ((I & 32) >> 3) | ((I & 64) >> 5) | ((I & 64) >> 6)
        .endrepeat

        .segment "CODE"
