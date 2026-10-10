; Colour for the monster and treasure pictures (the game only), in the game
; overlay at $4000, which start_program loads when WIZARDRY.CODE starts.
;
; Every picture is 50 lines of 10 Apple bytes, drawn by p-code MOVELEFTs at
; hi-res lines 23-72, bytes 1-10 (CINIT.2, REWARDS.2). Text shares those
; scanlines, so the screen stays monochrome mode F and the colour comes from
; players and missiles in front of it: where a player bit is on, a lit pixel
; shows the player's hue at PF1's luminance and an unlit pixel the player's
; colour (measured in Atari800). One player bit covers 2 hi-res pixels: a
; cell. Four players and the four missiles as a fifth player (PF3) cover the
; 40 cells of the picture in five strips of 8 cells.
;
; Apple bytes written there are kept, palette bits included, in a shadow.
; When the last line is written, each cell gets its Apple colour class: black,
; white (a lit dot beside a lit dot) or the hue of a lone dot (column parity
; and palette bit), and an empty cell between two of one hue takes that hue,
; as on the Apple. Coloured cells get a player bit; each strip shows the most
; common hue of every band of 8 lines, set by a display-list interrupt.
; Anything else drawing over the picture turns the colour off (pic_off).
;
; With SPRITES_PRESENT the Apple pictures are not shown at all: build.py has
; put a redrawn picture for every monster, the chest and the gold on the disk
; (pictures.py: its bitmap, player bytes and strip colours). The Apple bytes
; are only summed; when the last line is written the picture is found (the
; monster's number for CINIT, the sum for REWARDS' two) and loaded into the
; box: lines 6-81, bytes 1-11, with a strip colour for every band of 4 lines.

PMBASE_ADDR = $4800             ; missiles at +$300, players at +$400..+$7FF
PICSHADOW   = $5000             ; Apple bytes: columns 1-5, then 6-10, 50 lines each
APPLE_TOP   = 23                ; the Apple picture: lines 23-72, bytes 1-10
.if SPRITES_PRESENT
PIC_TOP     = 6                 ; picture lines 6-81 of the screen
PIC_LINES   = 76
BAND_LINES  = 4
NBANDS      = 19
PIC_HPOS    = 53                ; hi-res x 10-89
PIC_COLS    = 12                ; text columns (bytes) 1-11
PIC_ROW0    = 0                 ; text rows 0-10
PIC_ROW1    = 11
ENEMYINX    = MSCW - 2 + 2 * 19 ; the game's global 19: group 1's monster (CINIT)
REWARDS_SEG = 19
.else
PIC_TOP     = APPLE_TOP
PIC_LINES   = 50
BAND_LINES  = 8
NBANDS      = 7
PIC_HPOS    = 52                ; hi-res x 8-87
PIC_COLS    = 11
PIC_ROW0    = 2
PIC_ROW1    = 10
.endif
PIC_SCAN    = 32 + PIC_TOP      ; scanline of the first (the display starts at 32)
BAND_STEP   = BAND_LINES / 2    ; VCOUNT counts 2 scanlines
STRIP_SIZE  = NBANDS * BAND_STEP
DLI_VCOUNT  = (PIC_SCAN - 1) / 2 ; VCOUNT on the line before the first band
HUE_LUM     = $0A               ; luminance of the unlit pixels of a coloured cell

HPOSP0      = $D000             ; HPOSP0-3, HPOSM0-3
SIZEP0      = $D008             ; SIZEP0-3, SIZEM
GRAFP0      = $D00D             ; GRAFP0-3, GRAFM
COLPM0      = $D012
COLPM1      = $D013
COLPM2      = $D014
COLPM3      = $D015
COLPF3      = $D019
GRACTL      = $D01D
DMACTL      = $D400
PMBASE      = $D407
VCOUNT      = $D40B
GPRIOR      = $026F

pz_ptr      = $E0               ; 2: shadow or player memory
pz_line     = $E2               ; picture line 0-49
pz_b        = $E3               ; byte column 1-10
pz_v        = $E4               ; the byte's dots
pz_lone     = $E5               ; lone dots
pz_white    = $E6               ; dots with a lit neighbour
pz_pal      = $E7               ; palette: 0 or 2
pz_cell     = $E8               ; cell index
pz_c        = $E9
pz_s        = $EA               ; strip
pz_bits     = $EB
pz_t        = $EC

; --- set-up -----------------------------------------------------------------------

pic_init:
        lda #>PMBASE_ADDR
        sta PMBASE
        ldx #7
@h:     lda hpos_tab,x
        sta HPOSP0,x
        dex
        bpl @h
        ldx #4
        lda #0
@s:     sta SIZEP0,x
        dex
        bpl @s
        sta pic_on
        lda #$11                ; players in front; missiles as a fifth player
        sta GPRIOR
        ldx #PIC_TOP - 2 + 5    ; interrupts two display lines before each band
@d:     lda DL_GFX,x
        ora #$80
        sta DL_GFX,x
        txa
        clc
        adc #BAND_LINES
        tax
        cpx #PIC_TOP - 2 + 5 + NBANDS * BAND_LINES
        bne @d
        lda #<pm_dli
        sta VDSLST
        lda #>pm_dli
        sta VDSLST+1
        lda #<(PMBASE_ADDR + $300)  ; clear missiles, players and the shadow
        sta pz_ptr
        lda #>(PMBASE_ADDR + $300)
        sta pz_ptr+1
        ldx #7
        lda #0
        tay
@c:     sta (pz_ptr),y
        iny
        bne @c
        inc pz_ptr+1
        dex
        bne @c
        jmp pm_vis

; --- the redrawn pictures ----------------------------------------------------------

.if SPRITES_PRESENT
; write_apple (game): Apple byte nat0+2 at row Y, column nat0+6. Carry set if
; the byte is part of a picture, which is not drawn. Keeps nat0..2.
pic_write:
        cpy #APPLE_TOP
        bcc @show
        cpy #APPLE_TOP + 50
        bcs @show
        ldx nat0+6
        beq @show
        cpx #11
        bcs @show
        cpy #APPLE_TOP          ; the first byte starts the sum
        bne @add
        cpx #1
        bne @add
        lda #0
        sta pic_sum
        sta pic_sum+1
@add:   lda nat0+2
        clc
        adc pic_sum
        sta pic_sum
        bcc @last
        inc pic_sum+1
@last:  cpy #APPLE_TOP + 49
        bne @hide
        cpx #10
        bne @hide
        stx pic_full            ; the last byte: show ours when the move ends
@hide:  sec
        rts
@show:  clc
        rts

; hires_done (game): after a transfer
pic_done:
        lda pic_full
        beq @r
        lda #0
        sta pic_full
        lda curseg
        cmp #REWARDS_SEG
        bne @monster
        ldx #PIC_CHEST          ; REWARDS: the chest or the gold, by the bytes' sum
        lda pic_sum
        cmp #<CHEST_SUM
        bne @gold
        lda pic_sum+1
        cmp #>CHEST_SUM
        beq pic_load
@gold:  ldx #PIC_GOLD
        lda pic_sum
        cmp #<GOLD_SUM
        bne @r
        lda pic_sum+1
        cmp #>GOLD_SUM
        beq pic_load
@r:     rts
@monster:
        ldy #ENEMYINX + 1
        lda (base),y
        bne @r
        dey
        lda (base),y
        cmp #MONSTERS
        bcs @r
        tax
        lda pic_of_monster,x
        tax
        ; (falls through)

; Picture X from the disk into the box: a sector with the first line, the line
; count, the strip colours and each band's interrupt flag ($80: it changes a
; colour), then sectors of 8 lines (11 bitmap bytes and the 5 strips' player
; bytes each).
pic_load:
        lda pic_sec_lo,x
        sta sector
        lda pic_sec_hi,x
        sta sector+1
        lda ioresult            ; the game's IORESULT must not see these reads
        pha
        ldx #PIC_SCAN
        lda #0
@clr:   sta PMBASE_ADDR+$300,x
        sta PMBASE_ADDR+$400,x
        sta PMBASE_ADDR+$500,x
        sta PMBASE_ADDR+$600,x
        sta PMBASE_ADDR+$700,x
        inx
        cpx #PIC_SCAN + PIC_LINES
        bne @clr
        jsr @read
        lda SECBUF
        sta pz_line
        lda SECBUF+1
        sta pz_c                ; lines to go
        ldx #5 * NBANDS - 1
        ldy #2 * 5 * NBANDS - 2 ; (BAND_STEP is 2)
@col:   lda SECBUF+2,x
        sta bandcol,y
        dey
        dey
        dex
        bpl @col
        ldx #NBANDS - 1         ; interrupts only for the bands that change a colour
        ldy #PIC_TOP - 2 + 5 + (NBANDS - 1) * BAND_LINES
@dl:    lda DL_GFX,y
        and #$7F
        ora SECBUF+2+5*NBANDS,x
        sta DL_GFX,y
        dey
        dey
        dey
        dey
        dex
        bpl @dl
@sec:   lda pz_c
        beq @done
        jsr @read
        ldx #0
@line:  stx pz_s
        txa
        clc
        adc #<(SECBUF - 1)
        sta pz_ptr
        lda #>(SECBUF - 1)
        adc #0
        sta pz_ptr+1
        ldx pz_line
        lda bm_row_lo,x
        sta nat0
        lda bm_row_hi,x
        sta nat0+1
        ldy #11
@bm:    lda (pz_ptr),y
        sta (nat0),y
        dey
        bne @bm
        txa
        clc
        adc #32
        tax                     ; the line's scanline
        ldy #12
        lda (pz_ptr),y
        sta PMBASE_ADDR+$400,x
        iny
        lda (pz_ptr),y
        sta PMBASE_ADDR+$500,x
        iny
        lda (pz_ptr),y
        sta PMBASE_ADDR+$600,x
        iny
        lda (pz_ptr),y
        sta PMBASE_ADDR+$700,x
        iny
        lda (pz_ptr),y
        sta PMBASE_ADDR+$300,x
        inc pz_line
        dec pz_c
        beq @done
        lda pz_s
        clc
        adc #16
        tax
        bpl @line               ; 8 lines a sector
        bmi @sec
@done:  pla
        sta ioresult
        lda #1
        sta pic_on
        jmp pm_vis
@read:  lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda #$52
        jsr sio
        inc sector
        bne @rr
        inc sector+1
@rr:    rts

.else
; --- recording the Apple picture ----------------------------------------------------

; write_apple (game): Apple byte nat0+2 at row Y, column nat0+6. Keeps nat0..2.
pic_write:
        cpy #PIC_TOP
        bcc @r
        cpy #PIC_TOP + 50
        bcs @r
        ldx nat0+6
        beq @r
        cpx #11
        bcs @r
        tya
        sbc #PIC_TOP - 1        ; (carry clear) line 0-49
        sta pz_line
        lda pic_on
        beq @w
        jsr pic_off             ; the picture is changing
@w:
        jsr shadow_ptr
        lda nat0+2
        ldy #0
        sta (pz_ptr),y
        lda pz_line
        cmp #49
        bne @r
        sta pic_full            ; the last line: colour it when the move ends
@r:     clc                     ; draw the byte
        rts

; pz_ptr := shadow address of line pz_line, column X (1-10)
shadow_ptr:
        lda col_off-1,x
        clc
        adc pz_line
        sta pz_ptr
        lda col_page-1,x
        sta pz_ptr+1
        rts

; hires_done (game): after a transfer
pic_done:
        lda pic_full
        beq @r
        lda #0
        sta pic_full
        jmp pic_render
@r:     rts

; --- colouring --------------------------------------------------------------------

pic_render:
        lda #0
        sta pz_line
@band:  ldx #19
        lda #0
@z:     sta votes,x
        dex
        bpl @z
@line:  jsr class_line
        jsr gap_fill
        jsr pm_line
        inc pz_line
        lda pz_line
        cmp #50
        beq @last
        and #7
        bne @line
        jsr band_colours
        jmp @band
@last:  jsr band_colours
        lda #1
        sta pic_on
        jmp pm_vis

; cells[0..39] := colour classes of line pz_line: 0 black, 1 white, 2-5 hue
class_line:
        lda #0
        sta pz_cell
        lda #1
        sta pz_b
@byte:  ldx pz_b
        jsr shadow_ptr
        ldy #0
        lda (pz_ptr),y
        tay
        and #$80
        asl a
        rol a
        asl a                   ; palette bit -> 0 or 2
        sta pz_pal
        tya
        and #$7F
        sta pz_v
        ; left neighbours: dot j-1 (dot 6 of the byte before for j = 0)
        asl a
        sta pz_lone
        ldx pz_b
        dex
        beq @nl
        jsr shadow_ptr
        ldy #0
        lda (pz_ptr),y
        and #$40
        beq @nl
        inc pz_lone
@nl:    ; right neighbours: dot j+1 (dot 0 of the byte after for j = 6)
        lda pz_v
        lsr a
        sta pz_white
        ldx pz_b
        cpx #10
        beq @nr
        inx
        jsr shadow_ptr
        ldy #0
        lda (pz_ptr),y
        lsr a
        bcc @nr
        lda pz_white
        ora #$40
        sta pz_white
@nr:    lda pz_lone             ; lone = v & ~(left | right); white = v & ~lone
        ora pz_white
        eor #$FF
        and pz_v
        sta pz_lone
        eor pz_v
        sta pz_white
        ldx #0
@cell:  stx pz_c
        lda pz_white
        and cell_mask,x
        beq @nw
        lda #1
        bne @st
@nw:    lda pz_lone
        and cell_mask,x
        beq @st                 ; black
        and first_dot,x         ; which dot: column parity = byte + dot
        beq @second
        lda #0
        beq @par
@second:
        lda #1
@par:   eor pz_b
        and #1
        ora pz_pal
        clc
        adc #2
@st:    ldy pz_cell
        sta cells,y
        inc pz_cell
        ldx pz_c
        inx
        cpx #4
        bne @cell
        inc pz_b
        lda pz_b
        cmp #11
        beq @done
        jmp @byte
@done:  rts

gap_fill:                       ; an empty cell between two of one hue takes it
        ldx #1
@g:     lda cells,x
        bne @n
        lda cells-1,x
        cmp #2
        bcc @n
        cmp cells+1,x
        bne @n
        sta cells,x
@n:     inx
        cpx #39
        bne @g
        rts

; Player and missile bytes of line pz_line, and the band's hue votes.
pm_line:
        lda #0
        sta pz_s
        tax                     ; cell
@strip: lda #0
        sta pz_bits
        ldy #0
@k:     lda cells,x
        cmp #2
        bcc @nc
        sty pz_t
        sbc #2                  ; (carry set)
        sta pz_c
        lda pz_s
        asl a
        asl a
        ora pz_c
        tay
        lda votes,y
        clc
        adc #1
        bcs @full
        sta votes,y
@full:  ldy pz_t
        lda pz_s
        cmp #4
        lda pz_bits
        bcs @mis
        ora player_bit,y
        bne @set
@mis:   ora missile_bit,y
@set:   sta pz_bits
@nc:    inx
        iny
        cpy #8
        bne @k
        ldy pz_s
        lda strip_page,y
        sta pz_ptr+1
        lda #PIC_SCAN
        clc
        adc pz_line
        sta pz_ptr
        ldy #0
        lda pz_bits
        sta (pz_ptr),y
        inc pz_s
        lda pz_s
        cmp #5
        bne @strip
        rts

; Each strip's most common hue in the band just finished (line pz_line-1).
band_colours:
        ldx pz_line
        dex
        txa
        lsr a
        lsr a
        lsr a
        sta pz_t                ; band
        lda #0
        sta pz_s
@strip: lda pz_s
        asl a
        asl a
        tax
        lda #0
        sta pz_bits             ; best count
        sta pz_c                ; best hue
        ldy #0
@h:     lda votes,x
        cmp pz_bits
        bcc @n
        beq @n
        sta pz_bits
        sty pz_c
@n:     inx
        iny
        cpy #4
        bne @h
        ldy pz_c
        lda pz_s                ; bandcol[(strip * 7 + band) * BAND_STEP]
        asl a
        asl a
        asl a
        sec
        sbc pz_s
        clc
        adc pz_t
        asl a
        asl a
        tax
        lda hue_value,y
        sta bandcol,x
        inc pz_s
        lda pz_s
        cmp #5
        bne @strip
        rts

.endif

; --- showing it -------------------------------------------------------------------

; Players on while a picture is coloured and graphics are shown.
pm_vis: lda pic_on
        beq @off
        lda gfx_mode
        beq @off
        lda #$3E                ; players and missiles, one line resolution
        sta SDMCTL
        sta DMACTL
        lda #3
        sta GRACTL
        lda #$C0
        sta NMIEN
        rts
@off:   lda #$22
        sta SDMCTL
        sta DMACTL
        lda #0
        sta GRACTL
        ldx #4
@g:     sta GRAFP0,x            ; the graphics latches keep their last values
        dex
        bpl @g
        lda #$40
        sta NMIEN
        rts

pic_off:
        lda #0
        sta pic_on
        jmp pm_vis

; PRGRCHR at the cursor: text over the picture?
pic_char:
        lda cur_row
.if PIC_ROW0 > 0
        cmp #PIC_ROW0
        bcc @r
.endif
        cmp #PIC_ROW1
        bcs @r
        lda cur_col
        beq @r
        cmp #PIC_COLS
        bcs @r
        jmp pic_off
@r:     rts

; CLRRECT: first pixel row nat0+6, rows nat0+4, first column nat0+7, width nat0+5
pic_rect:
        lda nat0+6
        cmp #PIC_TOP + PIC_LINES
        bcs @r
        lda nat0+4
        asl a
        asl a
        asl a
        bcs @rows
        adc nat0+6
        bcs @rows
        cmp #PIC_TOP + 1
        bcc @r
@rows:  lda nat0+7
        cmp #PIC_COLS
        bcs @r
        clc
        adc nat0+5
        cmp #2
        bcc @r
        jmp pic_off
@r:     rts

; Display-list interrupt two lines before each band: its strip colours. Each
; must change after its strip on the line before the band and before its
; strip on the band's first line. An interrupt starts up to 6 cycles late, so
; it first waits for the end of its line; from there the timing is exact:
; the first colour is written just after the beam has passed the first strip
; (hence DLI_DELAY; the others follow about 20 colour clocks apart, each
; behind its own strip), all long before the next line's picture. Measured
; in Atari800, which is cycle-exact here: pictures match the converter's
; prediction pixel for pixel with 9 to 20 NOPs, and not with 8 or 26. The
; colours are indexed by VCOUNT itself to save the arithmetic.
DLI_DELAY = 14                  ; in NOPs
pm_dli: pha
        sta WSYNC
        txa
        pha
        .repeat DLI_DELAY
        nop
        .endrepeat
        ldx VCOUNT
        lda bandcol - DLI_VCOUNT,x
        sta COLPM0
        lda bandcol - DLI_VCOUNT + STRIP_SIZE,x
        sta COLPM1
        lda bandcol - DLI_VCOUNT + 2 * STRIP_SIZE,x
        sta COLPM2
        lda bandcol - DLI_VCOUNT + 3 * STRIP_SIZE,x
        sta COLPM3
        lda bandcol - DLI_VCOUNT + 4 * STRIP_SIZE,x
        sta COLPF3
        pla
        tax
        pla
        rti

; --- tables -----------------------------------------------------------------------

hpos_tab:   .byte PIC_HPOS, PIC_HPOS + 8, PIC_HPOS + 16, PIC_HPOS + 24     ; P0-P3, then M0-M3
            .byte PIC_HPOS + 32, PIC_HPOS + 34, PIC_HPOS + 36, PIC_HPOS + 38
col_off:    .byte 0, 50, 100, 150, 200, 0, 50, 100, 150, 200
col_page:   .byte >PICSHADOW, >PICSHADOW, >PICSHADOW, >PICSHADOW, >PICSHADOW
            .byte >PICSHADOW+1, >PICSHADOW+1, >PICSHADOW+1, >PICSHADOW+1, >PICSHADOW+1
cell_mask:  .byte $03, $0C, $30, $40                ; Apple dots of the 4 cells of a byte
first_dot:  .byte $01, $04, $10, $40                ; (the 4th is dot 6, doubled)
player_bit: .byte $80, $40, $20, $10, $08, $04, $02, $01
missile_bit: .byte $02, $01, $08, $04, $20, $10, $80, $40
strip_page: .byte >PMBASE_ADDR+4, >PMBASE_ADDR+5, >PMBASE_ADDR+6, >PMBASE_ADDR+7, >PMBASE_ADDR+3
hue_value:  .byte $60 | HUE_LUM, $C0 | HUE_LUM, $A0 | HUE_LUM, $30 | HUE_LUM  ; purple green blue orange
pic_full:   .byte 0
bandcol:    .res 5 * STRIP_SIZE ; strip * STRIP_SIZE + band * BAND_STEP
.if SPRITES_PRESENT
pic_sum:    .word 0             ; sum of the Apple picture's bytes
        .include "picture_tables.inc"
.else
votes:      .res 20             ; strip * 4 + hue
cells:      .res 40
.endif
