; The game's music (game overlay): each place's theme starts when the game
; calls the procedure for that place, by the cue table music.py generates
; from the Ewers listing (music_cues.inc). Themes are loaded from disk into
; the slot under the OS ROM when needed; jingles are always there and play
; over the theme, which then starts again.

.if MUSIC_PRESENT
cur_song:   .byte 1             ; the slot holds the title song after start-up
ml_count:   .byte 0

; docall in the game: the callee is cseg/cproc, the caller curseg/(jtab).
music_cue:
        ldx cseg
        cpx #32
        bcs @r
        lda cue_first,x
        cmp #$FF
        beq @r
        tax
@l:     lda cue_seg,x
        cmp cseg
        bne @r                  ; past this segment's cues
        lda cue_proc,x
        cmp cproc
        bne @n
        lda cue_fseg,x
        beq @hit                ; from anywhere
        cmp curseg
        bne @n
        ldy #0
        lda (jtab),y            ; the calling procedure's number
        cmp cue_fproc,x
        bne @n
@hit:   lda cue_song,x
        jmp music_song
@n:     inx
        bne @l
@r:     rts

; Play song A (NSF numbering): a jingle at once, or the theme, loaded first.
music_song:
        cmp #15                 ; ENCOUNTER and after: jingles
        bcc @theme
        tax
        lda song_jlo-1,x
        sta mus_jaddr
        lda song_jhi-1,x
        sta mus_jaddr+1
        lda #1
        sta mus_jreq
        rts
@theme: cmp cur_song
        beq @r
        sta cur_song
        tax
        lda #0
        sta mus_main            ; the VBI stops the slot's song
        lda song_secs-1,x
        beq @r
        sta ml_count
        lda song_sec_lo-1,x
        sta sector
        lda song_sec_hi-1,x
        sta sector+1
        lda #<MUSIC_SLOT
        sta pz_ptr
        lda #>MUSIC_SLOT
        sta pz_ptr+1
        lda ioresult            ; the game's IORESULT must not see these reads
        pha
@sec:   lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda #$52
        jsr sio
        sei                     ; copy under the ROM: no interrupts meanwhile
        lda #0
        sta NMIEN
        lda PORTB
        and #$FE
        sta PORTB
        ldy #127
@c:     lda SECBUF,y
        sta (pz_ptr),y
        dey
        bpl @c
        lda PORTB
        ora #1
        sta PORTB
        jsr pm_vis              ; the interrupts (and players) as they were
        cli
        clc
        lda pz_ptr
        adc #128
        sta pz_ptr
        bcc @a
        inc pz_ptr+1
@a:     inc sector
        bne @b
        inc sector+1
@b:     dec ml_count
        bne @sec
        pla
        sta ioresult
        lda #1
        sta mus_rew
        sta mus_main
@r:     rts

        .include "music_cues.inc"
.else
music_cue:
        rts
.endif
