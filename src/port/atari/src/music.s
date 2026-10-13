; NES music on POKEY (see music.py): the title theme while SYSTEM.STARTUP
; runs, and in the game each place's theme, with jingles over them.
;
; The player and the jingles live in the RAM under the OS ROM at $C000, the
; current song (a theme, or the title) at $D800 ("the slot"). The boot routine
; puts the player, jingles and title song there; the game loads each theme
; when its place is entered (musicgame.s). Each vertical blank, the immediate
; VBI hook switches the ROM out, plays one frame and switches it back. This is
; safe because nothing is displayed during vertical blank (ANTIC would read
; the font from RAM), no display-list interrupt can occur then, and IRQs are
; masked meanwhile. While SIO is busy (CRITIC) the music waits: serial
; transfers need their IRQs and use POKEY channels 3 and 4.
; DISK2 omits the title song and relocates jingles to $D800, the player to
; $E600 and the theme slot to $E800. Themes use the shared ZX02 decoder.

PORTB       = $D301
VVBLKI      = $0222
CRITIC      = $42
AUDF1       = $D200
AUDCTL      = $D208
.ifdef DISK2
MUSIC_PLAYER = $E600
MUSIC_SLOT = $E800
mz = $ED                       ; independent of decoder and picture scratch
mt = $EF
.else
MUSIC_PLAYER = $C000            ; player, then the jingles from $C200
MUSIC_SLOT  = $D800             ; the current song
MUSIC_LOAD  = $4000             ; where the boot routine reads them first
mz          = $FA               ; 2: song descriptor (VBI only)
mt          = $FC               ; 2: table (VBI only)
.endif

        .segment "TABLES"

; Shared with the VBI player (normal RAM).
mus_main:   .byte 0             ; 1: the slot's song plays
mus_rew:    .byte 0             ; 1: start the slot's song from the top
mus_jreq:   .byte 0             ; 1: start the jingle at mus_jaddr
mus_jaddr:  .word 0
music_next: .word 0             ; the OS's immediate VBI

.if MUSIC_PRESENT
.ifndef DISK2
; Boot: copy X pages from MUSIC_LOAD to page A, under the ROM.
music_copy:
        sta t1+1
        lda #>MUSIC_LOAD
        sta t0+1
        lda #0
        sta t0
        sta t1
        sei
        sta NMIEN
        lda PORTB
        and #$FE
        sta PORTB
        ldy #0
@copy:  lda (t0),y
        sta (t1),y
        iny
        bne @copy
        inc t0+1
        inc t1+1
        dex
        bne @copy
        lda PORTB
        ora #1
        sta PORTB
        lda #$40
        sta NMIEN
        cli
        rts

; Boot: the player and jingles to $C000, the title song to the slot.
music_boot:
        lda #<MUSA_SECTOR
        ldx #>MUSA_SECTOR
        ldy #MUSA_SECTORS
        jsr music_read
        lda #>MUSIC_PLAYER
        ldx #MUSA_PAGES
        jsr music_copy
        lda #<OPEN_SECTOR
        ldx #>OPEN_SECTOR
        ldy #OPEN_SECTORS
        jsr music_read
        lda #>MUSIC_SLOT
        ldx #OPEN_PAGES
        jsr music_copy
        jmp music_hook

music_read:                     ; Y sectors from sector X:A to MUSIC_LOAD
        sta sector
        stx sector+1
        sty t0
        lda #<MUSIC_LOAD
        sta DBUFLO
        lda #>MUSIC_LOAD
        sta DBUFHI
        jmp load_sectors

.endif
.ifdef DISK2
        .segment "GAMEOVL"
.endif
; Hook the immediate VBI.
music_hook:
        lda VVBLKI
        sta music_next
        lda VVBLKI+1
        sta music_next+1
        sei
        lda #<music_vbi
        sta VVBLKI
        lda #>music_vbi
        sta VVBLKI+1
        cli
        rts

music_vbi:
        lda CRITIC
        bne @out
        php
        sei
        lda PORTB
        and #$FE
        sta PORTB
        jsr music_play
        lda PORTB
        ora #1
        sta PORTB
        plp
@out:   jmp (music_next)
.endif

        .segment "TABLES"
; The title song, from the top (program 0).
music_start:
.ifndef DISK2
        lda #1
        sta mus_rew
        lda #MUSIC_PRESENT
        sta mus_main
.endif
        rts

; Silence (program 1 starts; its places load their themes).
music_stop:
        lda #0
        sta mus_main
        sta mus_jreq
        sta mus_jing
        ldx #7
@s:     sta AUDF1,x
        dex
        bpl @s
        sta AUDCTL
        rts

mus_jing:   .byte 0             ; 1: a jingle plays (the slot's song waits)

        .segment "MUSIC"

.if MUSIC_PRESENT
; One frame (VBI, ROM out). Plays a requested or running jingle, else the
; slot's song; at a jingle's end the slot's song starts again from the top.
music_play:
        lda mus_jreq
        beq @nj
        lda #0
        sta mus_jreq
        lda mus_jaddr
        sta mus_base
        lda mus_jaddr+1
        sta mus_base+1
        lda #1
        sta mus_jing
        jsr mus_top
@nj:    lda mus_jing
        bne @play
        lda mus_main
        beq mus_quiet
        lda mus_rew
        beq @play
        lda #0
        sta mus_rew
        lda #<MUSIC_SLOT
        sta mus_base
        lda #>MUSIC_SLOT
        sta mus_base+1
        jsr mus_top
@play:  jsr mus_frame
        ldx #7
@w:     lda mus_regs,x
        sta AUDF1,x
        dex
        bpl @w
        lda #$50                ; channel 1 at 1.79 MHz, channels 1+2 joined
        sta AUDCTL
        lda mus_j2              ; next frame, block, pattern
        clc
        adc #2
        cmp #6 * 2
        bcc @j
        lda mus_k2
        adc #1                  ; (carry set) + 2
        cmp #8 * 2
        bcc @k
        inc mus_p
        ldy #0
        lda mus_p
        cmp (mz),y              ; patterns
        bcc @p
        iny
        lda (mz),y              ; loop pattern
        cmp #$FF
        beq @end
        sta mus_p
@p:     lda #0
@k:     sta mus_k2
        lda #0
@j:     sta mus_j2
        rts
@end:   lda mus_jing            ; a jingle ends: the slot's song again
        beq @stop
        lda #0
        sta mus_jing
        lda #1
        sta mus_rew
        rts
@stop:  lda #0
        sta mus_main
        rts                     ; keep the final frame; silence starts next VBI
mus_quiet:
        lda #0
        ldx #7
@q:     sta AUDF1,x
        dex
        bpl @q
        rts

mus_top:
        lda #0
        sta mus_j2
        sta mus_k2
        sta mus_p
        rts

; mus_regs := this frame's values: for each stream, its pattern, block and
; then each register's value. Leaves mz at the song header.
mus_frame:
        clc
        lda mus_base
        adc #2
        sta mz
        lda mus_base+1
        adc #0
        sta mz+1
        lda #6
        sta mus_n
@s:     ldy #1                  ; order list
        lda (mz),y
        sta mt
        iny
        lda (mz),y
        sta mt+1
        ldy mus_p
        lda (mt),y
        sta mus_pat
        lda mus_k2              ; pattern column k
        clc
        adc #3
        tay
        lda (mz),y
        sta mt
        iny
        lda (mz),y
        sta mt+1
        ldy mus_pat
        lda (mt),y
        sta mus_blk
        ldy #0
        lda (mz),y
        sta mus_r               ; registers
        lda #19
        sta mus_ro
@r:     ldy mus_ro
        lda (mz),y
        tax                     ; POKEY register
        tya
        sec
        adc mus_j2              ; block column j
        tay
        lda (mz),y
        sta mt
        iny
        lda (mz),y
        sta mt+1
        ldy mus_blk
        lda (mt),y
        sta mus_regs,x
        lda mus_ro
        clc
        adc #13
        sta mus_ro
        dec mus_r
        bne @r
        clc
        lda mz
        adc #45
        sta mz
        bcc @n
        inc mz+1
@n:     dec mus_n
        bne @s
        lda mus_base            ; back to the header
        sta mz
        lda mus_base+1
        sta mz+1
        rts

mus_base:   .word 0
mus_j2:     .byte 0             ; frame in block * 2
mus_k2:     .byte 0             ; block in pattern * 2
mus_p:      .byte 0             ; order-list position
mus_n:      .byte 0
mus_pat:    .byte 0
mus_blk:    .byte 0
mus_r:      .byte 0
mus_ro:     .byte 0
mus_regs:   .res 8              ; AUDF1, AUDC1, ... AUDC4
.endif
