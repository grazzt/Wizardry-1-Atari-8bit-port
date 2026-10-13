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
.ifdef DISK2
        pha
        lda ml_player_ready
        bne @ready
        pla
        rts
@ready: pla
.endif
        cmp #15                 ; ENCOUNTER and after: jingles
        bcc @theme
        tax
.ifdef DISK2
        lda jingle_bits-15,x
        and ml_jingles
        beq @r
.endif
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
.ifdef DISK2
        jsr music_load_cmp
        bcs @loaded
        lda #0
        sta cur_song           ; permit the next cue to retry after an SIO failure
        rts
@loaded:
        lda #1
        sta mus_rew
        sta mus_main
.else
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
.endif
@r:     rts

.ifdef DISK2
; Copy the linked player from the program disk into its relocated ROM-RAM.
; The common copy helper runs in normal RAM and uses real OS SIO.
music_prepare:
        lda ioresult
        pha
        lda #0
        sta ioresult
        lda #<MUSA_SECTOR
        sta sector
        lda #>MUSA_SECTOR
        sta sector+1
        lda #<MUSIC_PLAYER
        sta t1
        lda #>MUSIC_PLAYER
        sta t1+1
        lda #MUSA_SECTORS
        sta t0
        jsr comp_copy
        lda ioresult
        bne @bad
        lda #1
        sta ml_player_ready
@bad:   pla
        sta ioresult
        rts

music_init_game:
        lda ml_player_ready
        beq @done
        lda #0
        sta ml_jingles
        lda #15
        sta ml_init_song
@load:  ldx ml_init_song
        jsr music_load_cmp
        bcc @next
        ldx ml_init_song
        lda jingle_bits-15,x
        ora ml_jingles
        sta ml_jingles
@next:  inc ml_init_song
        lda ml_init_song
        cmp #19
        bne @load
        jmp music_hook
@done:  rts
ml_player_ready: .byte 0
ml_jingles:     .byte 0
jingle_bits:    .byte 1, 2, 4, 8
ml_init_song: .byte 0
ml_failed:    .byte 0

; X = song. Decode from disk 2 straight into the theme slot or jingle area.
; Preserve the game's IORESULT; carry set on a successful music load.
music_load_cmp:
        lda ioresult
        pha
        lda #0
        sta ioresult
        lda song_sec_lo-1,x
        sta sector
        lda song_sec_hi-1,x
        sta sector+1
        lda song_cmp_ctl-1,x
        sta lz_token+1
        lda song_len_lo-1,x
        sta lz_left
        lda song_len_hi-1,x
        sta lz_left+1
        cpx #15
        bcs @jingle
        lda #<MUSIC_SLOT
        sta lz_dst
        lda #>MUSIC_SLOT
        sta lz_dst+1
        jmp @decode
@jingle:
        lda song_jlo-1,x
        sta lz_dst
        lda song_jhi-1,x
        sta lz_dst+1
@decode:
        lda #4
        jsr comp_call
        lda ioresult
        sta ml_failed
        pla
        sta ioresult
        lda ml_failed
        bne @bad
        sec
        rts
@bad:   clc
        rts
.endif

        .include "music_cues.inc"
.else
music_cue:
        rts
.endif
