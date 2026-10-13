; Block I/O on D1: through SIO. After the boot sectors and tables, the disk
; holds two Apple Pascal volumes in block order (boot, then scenario); for
; the volume that is currently drive 1, Pascal block n is 128-byte sectors
; volbase+4n .. volbase+4n+3.
; A partial last sector goes through SECBUF so that bytes beyond the
; transfer are never touched (segments are loaded directly beneath frames).
;
; In: t2 = address, cnt = byte count, t4 = first block. Sets ioresult.
; disk_read_code reads the running program's own volume (codebase), which
; stays put while the utilities swap disks in drive 1.
;
; With SCENCMP the scenario volume is mapped by compressed.s: raw Pascal
; directory/code-header blocks stay in place, writable caches are relocated
; raw blocks, and code/read-only data are independent ZX02 streams. Shared
; decoder code is loaded under the OS ROM at boot, available to utilities
; and the game. SIO always executes with ROM enabled into normal RAM.

disk_read:
        lda #$52
        sta dcmd
        lda #0
        sta dcode
        lda volbase
        ldx volbase+1
        jmp disk_enter
disk_read_code:
        lda #$52
        sta dcmd
        lda #$FF
        sta dcode
        lda codebase
        ldx codebase+1
        jmp disk_enter
disk_write:
        lda #$57
        sta dcmd
        lda #0
        sta dcode
        lda volbase
        ldx volbase+1
disk_enter:
        sta dvol
        stx dvol+1
.ifdef SCENCMP
        cmp #<SCENVOL
        bne disk_base
        cpx #>SCENVOL
        bne disk_base
        lda #0
        jmp comp_call           ; shared decoder in RAM under the OS ROM
.else
        jmp disk_base
.endif

; The raw sector walk: sector := dvol + 4 * t4, then cnt bytes through SIO,
; a partial last sector through SECBUF (read-modify-write when writing).
disk_base:
        lda t4                  ; sector := block*4 + the volume's first sector
        sta sector
        lda t4+1
        sta sector+1
        asl sector
        rol sector+1
        asl sector
        rol sector+1
        clc
        lda sector
        adc dvol
        sta sector
        lda sector+1
        adc dvol+1
        sta sector+1
@loop:  lda cnt
        ora cnt+1
        bne @more
        rts
@more:  lda cnt+1               ; a whole sector left?
        bne @whole
        lda cnt
        cmp #128
        bcs @whole
        ; partial sector through the buffer
        lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda dcmd
        cmp #$57
        bne @pread
        lda #$52                ; read-modify-write
        jsr sio
        ldy #0
@pw:    lda (t2),y
.ifdef SCENCMP
        jsr comp_yield
.endif
        sta SECBUF,y
        iny
        cpy cnt
        bne @pw
        lda #$57
        jsr sio
        jmp @last
@pread: lda #$52
        jsr sio
        ldy #0
@pr:    lda SECBUF,y
.ifdef SCENCMP
        jsr comp_yield
.endif
        sta (t2),y
        iny
        cpy cnt
        bne @pr
@last:  lda #0
        sta cnt
        rts
@whole: lda t2
        sta DBUFLO
        lda t2+1
        sta DBUFHI
        lda dcmd
        jsr sio
        clc
        lda t2
        adc #128
        sta t2
        bcc @a
        inc t2+1
@a:     sec
        lda cnt
        sbc #128
        sta cnt
        bcs @b
        dec cnt+1
@b:     inc sector
.ifdef SCENCMP
        bne @again
.else
        bne @loop
.endif
        inc sector+1
@again:
        jmp @loop

; One SIO sector transfer; command in A, buffer in DBUFLO/HI, sector in
; `sector`. Errors set ioresult (UCSD "bad block" = 16 style, nonzero).
sio:    sta DCOMND
        lda #$31
        sta DDEVIC
        lda #1
        sta DUNIT
        lda DCOMND
        cmp #$57
        beq @w
        lda #$40
        bne @s
@w:     lda #$80
@s:     sta DSTATS
        lda #7
        sta DTIMLO
        lda #128
        sta DBYTLO
        lda #0
        sta DBYTHI
        lda sector
        sta DAUX1
        lda sector+1
        sta DAUX2
        .ifdef SCENCMP
        jsr comp_sio
.else
        jsr SIOV
.endif
        bpl @ok
        lda #16
        sta ioresult
@ok:    rts

dcmd:   .byte 0
dvol:   .word 0
dcode:  .byte 0
