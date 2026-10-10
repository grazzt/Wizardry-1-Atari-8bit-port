; Console: 40x24 text screen with Apple Pascal control codes, the graphics
; display list, and the keyboard.

con_init:
        lda #1
        sta CRSINH
        lda #$00                ; black background, white characters/pixels
        sta COLOR2
        sta COLOR4
        lda #$0E
        sta COLOR1
        ldx #0                  ; text display list
        ldy #0
@tdl:   lda text_dl,y
        sta DL_TEXT,y
        iny
        cpy #text_dl_end-text_dl
        bne @tdl
        jsr build_gfx_dl
        jsr con_clear
        jmp con_textmode

; Graphics display list: 3 blank, LMS line 0, 101 lines, LMS line 102,
; 89 lines, jump back. (Monochrome mode F; colour_dl_on converts it.)
build_gfx_dl:
        ldx #0
        lda #$70
        sta DL_GFX,x
        inx
        sta DL_GFX,x
        inx
        sta DL_GFX,x
        inx
        lda #$4F
        sta DL_GFX,x
        inx
        lda #<BITMAP
        sta DL_GFX,x
        inx
        lda #>BITMAP
        sta DL_GFX,x
        inx
        ldy #101
        lda #$0F
@g1:    sta DL_GFX,x
        inx
        dey
        bne @g1
        lda #$4F
        sta DL_GFX,x
        inx
        lda #<BITMAP2
        sta DL_GFX,x
        inx
        lda #>BITMAP2
        sta DL_GFX,x
        inx
        ldy #89
        lda #$0F
@g2:    sta DL_GFX,x
        inx
        dey
        bne @g2
        lda #$41
        sta DL_GFX,x
        inx
        lda #<DL_GFX
        sta DL_GFX,x
        inx
        lda #>DL_GFX
        sta DL_GFX,x
        rts

con_textmode:
        lda #0
        sta gfx_mode
        lda #<DL_TEXT
        sta SDLSTL
        lda #>DL_TEXT
        sta SDLSTL+1
        jmp pic_hook_vis

con_gfxmode:
        lda program             ; the title is shown in colour
        bne @mono
        jsr color_dl_on
@mono:  lda #1
        sta gfx_mode
        lda #<DL_GFX
        sta SDLSTL
        lda #>DL_GFX
        sta SDLSTL+1
        jmp pic_hook_vis

text_dl:
        .byte $70, $70, $70, $42, <TEXTSCR, >TEXTSCR
        .res 23, $02
        .byte $41, <DL_TEXT, >DL_TEXT
text_dl_end:

; Clear the whole text screen and home the cursor.
con_clear:
        lda #0
        sta con_x
        sta con_y
        ldx #0
@l:     sta TEXTSCR,x
        sta TEXTSCR+$100,x
        sta TEXTSCR+$200,x
        sta TEXTSCR+$2C0,x      ; overlaps; covers up to $3BF
        inx
        bne @l
        rts

; con_ptr := start of row con_y
con_row:
        ldx con_y
        lda rowtab_lo,x
        sta con_ptr
        lda rowtab_hi,x
        sta con_ptr+1
        rts

; Output one character (ASCII in A). Preserves nothing.
con_put:
        cmp #32
        bcc @ctrl
        ldx con_x
        cpx #40
        bcs @adv                ; past the right edge: dropped
        pha
        jsr con_row
        pla
        and #$7F                ; ASCII -> ANTIC internal code
        cmp #$60
        bcs @store
        sec
        sbc #$20
@store: ldy con_x
        sta (con_ptr),y
@adv:   inc con_x
        bne @r
        dec con_x               ; saturate at 255
@r:     rts

@ctrl:  cmp #13
        beq @cr
        cmp #10
        beq @down
        cmp #12
        beq con_clear
        cmp #11
        beq @eos
        cmp #29
        beq @eol
        cmp #25
        beq @home
        cmp #8
        beq @left
        cmp #28
        beq @right
        cmp #31
        beq @up
        rts                     ; 7 (bell) and others: ignored for now
@cr:    lda #0
        sta con_x
@down:  lda con_y
        cmp #23
        bcs @scroll
        inc con_y
        rts
@scroll:
        jmp con_scroll
@home:  lda #0
        sta con_x
        sta con_y
        rts
@left:  lda con_x
        beq @r
        dec con_x
        rts
@right: inc con_x
        rts
@up:    lda con_y
        beq @r
        dec con_y
        rts
@eol:   jsr con_row
        ldy con_x
        lda #0
@e1:    cpy #40
        bcs @r
        sta (con_ptr),y
        iny
        bne @e1
@eos:   jsr @eol
        ldx con_y
@e2:    inx
        cpx #24
        bcs @r
        lda rowtab_lo,x
        sta con_ptr
        lda rowtab_hi,x
        sta con_ptr+1
        ldy #39
        lda #0
@e3:    sta (con_ptr),y
        dey
        bpl @e3
        bmi @e2

con_scroll:                     ; move rows 1-23 up one row, clear row 23
        lda #<(TEXTSCR+40)
        sta nat0
        lda #>(TEXTSCR+40)
        sta nat0+1
        lda #<TEXTSCR
        sta con_ptr
        lda #>TEXTSCR
        sta con_ptr+1
        ldx #3                  ; 3 full pages, then 920-768 = 152 bytes
        ldy #0
@page:  lda (nat0),y
        sta (con_ptr),y
        iny
        bne @page
        inc nat0+1
        inc con_ptr+1
        dex
        bne @page
@rest:  lda (nat0),y
        sta (con_ptr),y
        iny
        cpy #152
        bne @rest
        lda #0
        ldx #39
@c:     sta TEXTSCR+920,x
        dex
        bpl @c
        rts

con_hex:
        pha
        lsr a
        lsr a
        lsr a
        lsr a
        jsr @digit
        pla
        and #$0F
@digit: cmp #10
        bcc @n
        adc #6
@n:     adc #'0'
        jmp con_put

rowtab_lo:
        .repeat 24, I
        .byte <(TEXTSCR + 40*I)
        .endrepeat
rowtab_hi:
        .repeat 24, I
        .byte >(TEXTSCR + 40*I)
        .endrepeat

; --- keyboard --------------------------------------------------------------------
kbd_init:                       ; open IOCB 1 on K:
        ldx #$10
        lda #3
        sta ICCOM,x
        lda #<kname
        sta ICBAL,x
        lda #>kname
        sta ICBAH,x
        lda #4
        sta ICAX1,x
        lda #0
        sta ICAX2,x
        jmp CIOV
kname:  .byte "K:", $9B

; Wait for a key; return ASCII in A (RETURN = 13, BACK S = 8, upper case).
get_key:
        lda #1
        sta WAITING
        ldx #$10
        lda #7
        sta ICCOM,x
        lda #0
        sta ICBLL,x
        sta ICBLH,x
        jsr CIOV
        ldx #0
        stx WAITING
        cmp #$9B
        bne @a
        lda #13
        rts
@a:     cmp #$7E
        bne @b
        lda #8
        rts
@b:     cmp #'a'
        bcc @c
        cmp #'z'+1
        bcs @c
        and #$DF
@c:     rts

; A <> 0 if a key is waiting.
key_waiting:
        lda CH
        eor #$FF
        rts
