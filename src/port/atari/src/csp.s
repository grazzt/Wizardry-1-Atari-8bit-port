; Standard procedures (CSP n) and the Pascal OS entry points (CXP 0,n) that
; Wizardry uses. Arguments are on the evaluation stack, last argument on top.

op_csp: jsr getb
        CASE 2, csp_moveleft
        CASE 3, csp_moveright
        CASE 4, csp_exit
        CASE 5, csp_unitread
        CASE 6, csp_unitwrite
        CASE 10, csp_fillchar
        CASE 34, csp_ioresult
        CASE 33, csp_release
        CASE 32, csp_mark
        CASE 1, csp_new
        CASE 38, csp_unitclear
        CASE 39, csp_halt
        CASE 40, csp_memavail
        CASE 0, csp_iocheck
        CASE 21, csp_segctl
        CASE 22, csp_segctl
        lda #11
        jmp vmerror

csp_ioresult:
        lda #0
        pha
        lda ioresult
        pha
        NEXT

csp_iocheck:
        lda ioresult
        bne @err
        NEXT
@err:   lda #10
        jmp vmerror

csp_unitclear:
        pla                     ; unit
        tax
        pla
        lda #0
        sta ioresult
        cpx #1                  ; the console: drop any waiting key
        bne @n
        lda #$FF
        sta CH
@n:     NEXT

csp_segctl:                     ; GETSEG / RELSEG: segments load on call anyway
        pla
        pla
        NEXT

csp_halt:
        lda #14
        jmp vmerror

csp_memavail:                   ; (sp - heap) / 2 words
        sec
        lda sp
        sbc heap
        tax
        lda sp+1
        sbc heap+1
        lsr a
        pha
        txa
        ror a
        pha
        NEXT

csp_release:
        POPW ad
        ldy #0
        lda (ad),y
        sta heap
        iny
        lda (ad),y
        sta heap+1
        NEXT

csp_mark:
        POPW ad
        ldy #0
        lda heap
        sta (ad),y
        iny
        lda heap+1
        sta (ad),y
        NEXT

csp_new:                        ; NEW(var p, words)
        POPW t0
        POPW ad
        ldy #0
        lda heap
        sta (ad),y
        iny
        lda heap+1
        sta (ad),y
        asl t0
        rol t0+1
        clc
        lda heap
        adc t0
        sta heap
        lda heap+1
        adc t0+1
        sta heap+1
        NEXT

; MOVELEFT(src, srcoff, dst, dstoff, count)
csp_moveleft:
        jsr pop_move_args
        bcs @n
        jsr hires_involved
        bcs @h
        jsr memcpy
@n:     NEXT
@h:     jsr hires_move
        NEXT

csp_moveright:
        jsr pop_move_args
        bcs @n
        jsr hires_involved
        bcs @h
        jsr memcpy_down
@n:     NEXT
@h:     jsr hires_move
        NEXT

; The move arguments sit beneath this subroutine's return address, so read
; them through the stack pointer and then drop them. Sets carry if count <= 0.
pop_move_args:
        tsx
        lda $0103,x
        sta cnt
        lda $0104,x
        sta cnt+1
        clc
        lda $0107,x             ; dst
        adc $0105,x             ; + dstoff
        sta t2
        lda $0108,x
        adc $0106,x
        sta t2+1
        clc
        lda $010B,x             ; src
        adc $0109,x             ; + srcoff
        sta t1
        lda $010C,x
        adc $010A,x
        sta t1+1
        lda $0101,x             ; move the return address up over the 10 bytes
        sta $010B,x
        lda $0102,x
        sta $010C,x
        txa
        clc
        adc #10
        tax
        txs
        lda cnt+1
        bmi @none
        ora cnt
        beq @none
        clc
        rts
@none:  sec
        rts

memcpy_down:                    ; copy cnt bytes, highest first
        clc
        lda t1
        adc cnt
        sta t1
        lda t1+1
        adc cnt+1
        sta t1+1
        clc
        lda t2
        adc cnt
        sta t2
        lda t2+1
        adc cnt+1
        sta t2+1
@loop:  lda cnt
        ora cnt+1
        beq @done
        lda t1
        bne @a
        dec t1+1
@a:     dec t1
        lda t2
        bne @b
        dec t2+1
@b:     dec t2
        ldy #0
        lda (t1),y
        sta (t2),y
        lda cnt
        bne @c
        dec cnt+1
@c:     dec cnt
        jmp @loop
@done:  rts

; FILLCHAR(addr, offset, count, ch)
csp_fillchar:
        pla
        sta t0                  ; character
        pla
        POPW cnt
        POPW t3
        POPW t2
        jsr t2_plus_t3
        lda cnt+1
        bmi @done
        lda t2+1                ; Apple hi-res destination?
        cmp #$20
        bcc @plain
        cmp #$40
        bcs @plain
@hl:    lda cnt
        ora cnt+1
        beq @hdone
        lda t0
        jsr write_apple
        inc t2
        bne @h1
        inc t2+1
@h1:    lda cnt
        bne @h2
        dec cnt+1
@h2:    dec cnt
        jmp @hl
@plain: ldy #0
        beq @loop
@hdone: jsr hires_done
        NEXT
@loop:  lda cnt
        ora cnt+1
        beq @done
        lda t0
        sta (t2),y
        inc t2
        bne @a
        inc t2+1
@a:     lda cnt
        bne @b
        dec cnt+1
@b:     dec cnt
        jmp @loop
@done:  NEXT

t2_plus_t3:
        clc
        lda t2
        adc t3
        sta t2
        lda t2+1
        adc t3+1
        sta t2+1
        rts

; UNITREAD/UNITWRITE(unit, addr, offset, count, block, mode)
csp_unitread:
        lda #0
        beq unit_io
csp_unitwrite:
        lda #1
unit_io:
        sta t6+1                ; 0 = read, 1 = write
        pla                     ; mode (ignored)
        pla
        POPW t4                 ; block
        POPW cnt                ; byte count
        POPW t3                 ; offset
        POPW t2                 ; address
        jsr t2_plus_t3
        POPW t5                 ; unit
        lda #0
        sta ioresult
        lda t5
        cmp #4
        bne @console
        lda t6+1
        beq @rd
        lda vol_ro              ; the boot disk is write-protected
        beq @w
        lda #16
        sta ioresult
        NEXT
@rd:    lda t6+1
        bne @w
        jsr disk_read
        NEXT
@w:     jsr disk_write
        NEXT
@console:
        cmp #1
        beq @con
        cmp #2
        beq @con
        lda #9                  ; no such volume
        sta ioresult
        NEXT
@con:   lda t6+1
        bne @conw
@cr:    lda cnt
        ora cnt+1
        beq @done
        jsr get_key
        ldy #0
        sta (t2),y
        ldx t5
        cpx #1
        bne @noecho
        jsr con_put
@noecho:
        inc t2
        bne @r1
        inc t2+1
@r1:    lda cnt
        bne @r2
        dec cnt+1
@r2:    dec cnt
        jmp @cr
@conw:  lda cnt
        ora cnt+1
        beq @done
        ldy #0
        lda (t2),y
        jsr con_put
        inc t2
        bne @w1
        inc t2+1
@w1:    lda cnt
        bne @w2
        dec cnt+1
@w2:    dec cnt
        jmp @conw
@done:  NEXT

; --- Pascal OS entry points -------------------------------------------------------------
os_call:
        lda cproc
        CASE 19, os_writestr
        CASE 17, os_writechar
        CASE 29, os_gotoxy
        CASE 22, os_writeln
        CASE 13, os_writeint
        CASE 16, os_readchar
        CASE 21, os_readln
        CASE 11, os_eoln
        CASE 23, os_concat
        CASE 25, os_copy
        CASE 3, os_finit
        CASE 5, os_fopen
        CASE 6, os_fclose
        CASE 28, os_fblockio
        lda #11
        jmp vmerror

os_writeln:                     ; WRITELN(f)
        pla
        pla
        lda #13
        jsr con_put
        NEXT

os_gotoxy:                      ; GOTOXY(x, y)
        POPW t1
        POPW t0
        lda t1+1
        bmi @y0
        bne @y23
        lda t1
        cmp #24
        bcc @y
@y23:   lda #23
        bne @y
@y0:    lda #0
@y:     sta con_y
        lda t0+1
        bmi @x0
        bne @x255
        lda t0
        jmp @x
@x255:  lda #255
        bne @x
@x0:    lda #0
@x:     sta con_x
        NEXT

os_writechar:                   ; WRITE(f, ch:width)
        POPW t1                 ; width
        POPW t0
        pla
        pla
        lda #1
        jsr pad_width
        lda t0
        jsr con_put
        NEXT

os_writestr:                    ; WRITE(f, s:width)
        POPW t1
        POPW t2
        pla
        pla
        ldy #0
        lda (t2),y
        sta t3
        jsr pad_width
        ldy #0
@loop:  cpy t3
        beq @done
        iny
        lda (t2),y
        sty t3+1
        jsr con_put
        ldy t3+1
        jmp @loop
@done:  NEXT

; Print (width - A) spaces if positive; width in t1.
pad_width:
        sta t7
        lda t1+1
        bne @r                  ; negative or huge: no padding
        sec
        lda t1
        sbc t7
        bcc @r
        beq @r
        sta oscnt
@sp:    lda #' '
        jsr con_put
        dec oscnt
        bne @sp
@r:     rts

os_writeint:                    ; WRITE(f, i:width)
        POPW t1                 ; width
        POPW t0                 ; value
        pla
        pla
        ldx #0                  ; build digits backwards in numbuf
        lda t0+1
        sta sign
        bpl @pos
        jsr neg_t0
@pos:   lda t1
        pha
        lda t1+1
        pha
        lda #10
        sta t1
        lda #0
        sta t1+1
@digit: stx t6
        jsr divu16
        ldx t6
        lda mulx
        ora #'0'
        sta numbuf,x
        inx
        lda t0
        ora t0+1
        bne @digit
        lda sign
        bpl @nosign
        lda #'-'
        sta numbuf,x
        inx
@nosign:
        pla
        sta t1+1
        pla
        sta t1
        stx t6
        txa
        jsr pad_width
        ldx t6
@out:   dex
        lda numbuf,x
        stx t6
        jsr con_put
        ldx t6
        cpx #0
        bne @out
        NEXT

numbuf: .res 8

os_readchar:                    ; READ(f, var ch)
        POPW ad
        pla
        pla
        jsr get_key
        cmp #13
        bne @plain
        lda #1
        sta eoln
        lda #' '
        bne @store
@plain: ldx #0
        stx eoln
        cmp #' '
        bcc @store
        pha
        jsr con_put             ; INPUT echoes
        pla
@store: ldy #0
        sta (ad),y
        iny
        lda #0
        sta (ad),y
        NEXT

os_readln:                      ; READLN(f)
        pla
        pla
        lda eoln
        beq @skip
        lda #0
        sta eoln
        NEXT
@skip:  jsr get_key
        cmp #13
        bne @skip
        NEXT

os_eoln:                        ; EOLN(f): two result words, then the file
        pla
        pla
        pla
        pla
        pla
        pla
        lda #0
        pha
        lda eoln
        pha
        NEXT

os_concat:                      ; dest := dest + src
        pla
        pla
        POPW t1                 ; src
        POPW t2                 ; dest
        ldy #0
        lda (t1),y
        sta t3                  ; source length
        lda (t2),y
        sta t3+1                ; dest length
        ldx #0
@loop:  cpx t3
        beq @done
        lda t3+1
        cmp #255
        beq @done
        inx
        txa
        tay
        lda (t1),y
        inc t3+1
        ldy t3+1
        sta (t2),y
        jmp @loop
@done:  ldy #0
        lda t3+1
        sta (t2),y
        NEXT

os_copy:                        ; COPY(src, dest, index, count)
        POPW cnt                ; count
        POPW t0                 ; index (1-based)
        POPW t2                 ; dest
        POPW t1                 ; src
        ldy #0
        lda (t1),y
        sta t3                  ; source length
        lda t0+1
        bne @empty
        lda t0
        beq @empty
        cmp t3
        beq @ok
        bcs @empty
@ok:    lda cnt+1
        bmi @empty
        ; available = len - index + 1
        sec
        lda t3
        sbc t0
        clc
        adc #1
        sta t3+1
        lda cnt+1
        bne @clip
        lda cnt
        cmp t3+1
        bcc @take
@clip:  lda t3+1
@take:  sta t3+1                ; characters to copy
        lda #1
        sta t4                  ; next destination index
@loop:  lda t3+1
        beq @len
        ldy t0
        lda (t1),y
        ldy t4
        sta (t2),y
        inc t0
        inc t4
        dec t3+1
        jmp @loop
@len:   ldx t4
        dex
        txa
        ldy #0
        sta (t2),y
        NEXT
@empty: ldy #0
        tya
        sta (t2),y
        NEXT

        .segment "TABLES"       ; (high area: the main code area is full)

; --- Apple hi-res addresses in p-code ------------------------------------------------
; The game computes Apple hi-res addresses itself in three places (monster
; and treasure pictures, and scrolling the monster-group list) and moves bytes
; there with MOVELEFT/FILLCHAR. Any such transfer touching $2000-$3FFF is done
; byte by byte in Apple terms: hi-res bytes are read back to Apple form and
; written through the 7-to-8 pixel expansion at the Atari position of the
; same row and column. (Nothing else of the p-machine lives in $2000-$3FFF.)

hires_involved:                 ; carry set if src (t1) or dst (t2) is hi-res
        lda t1+1
        jsr @in
        bcs @r
        lda t2+1
@in:    cmp #$20
        bcc @no
        cmp #$40
        bcs @no
        sec
        rts
@no:    clc
@r:     rts

hires_move:                     ; cnt bytes from (t1) to (t2), Apple terms
@loop:  lda cnt
        ora cnt+1
        beq hires_done
        jsr read_apple
        jsr write_apple
        inc t1
        bne @a
        inc t1+1
@a:     inc t2
        bne @b
        inc t2+1
@b:     lda cnt
        bne @c
        dec cnt+1
@c:     dec cnt
        jmp @loop

hires_done:                     ; after a transfer: redraw the title's changed lines,
        lda program             ; or colour a finished picture in the game
        bne @game
        jmp render_dirty
@game:  jmp pic_done

; A := Apple byte at address t1
read_apple:
        lda t1+1
        cmp #$20
        bcc @plain
        cmp #$40
        bcs @plain
        lda t1
        ldx t1+1
        jsr apple_to_atari
        bcs @hole
        lda program             ; the title: exact Apple bytes from the shadow
        bne @mono
        jmp color_read
@mono:  ldy #0
        lda (nat0),y
        lsr a                   ; drop the doubled 7th pixel, then reverse 7 bits
        sta nat0+2
        lda #0
        ldx #7
@rev:   lsr nat0+2
        rol a
        dex
        bne @rev
        rts
@hole:  lda #0
        rts
@plain: ldy #0
        lda (t1),y
        rts

; Apple byte A to address t2
write_apple:
        tay
        lda t2+1
        cmp #$20
        bcc @plain
        cmp #$40
        bcs @plain
        sty nat0+2
        lda t2
        ldx t2+1
        jsr apple_to_atari
        bcs @r                  ; a screen hole: not displayed
        lda program
        bne @mono
        jmp color_write         ; the title: shadow + redraw later (row in Y)
@mono:  jsr pic_write             ; the game: picture colour (row in Y)
        bcs @r                  ; a picture byte that ours replaces
        ldx nat0+2
        lda expand7,x
        ldy #0
        sta (nat0),y
@r:     rts
@plain: tya
        ldy #0
        sta (t2),y
        rts

; Apple hi-res address (A = low, X = high) -> Atari bitmap address in nat0.
; Carry set if the address is one of the undisplayed "screen hole" bytes.
apple_to_atari:
        sta nat0+3              ; low byte
        txa
        sec
        sbc #$20
        sta nat0+4              ; offset high byte (0..$1F)
        lsr a
        lsr a
        sta nat0+5              ; line within a character row (y & 7)
        lda nat0+4
        and #3
        asl a
        sta nat0+6
        lda nat0+3
        asl a                   ; bit 7 of the low byte -> carry
        lda nat0+6
        adc #0
        asl a
        asl a
        asl a                   ; block * 8
        ora nat0+5
        sta nat0+5              ; row within the third: block*8 + line
        lda nat0+3
        and #$7F                ; position within the 128-byte group
        cmp #120
        bcs @hole
        ldx #0
@third: cmp #40
        bcc @col
        sbc #40
        inx
        bne @third
@col:   sta nat0+6              ; column
        txa
        lsr a
        ror a
        ror a                   ; third * 64
        ora nat0+5
        tay                     ; Apple row 0..191
        clc
        lda bm_row_lo,y
        adc nat0+6
        sta nat0
        lda bm_row_hi,y
        adc #0
        sta nat0+1
        clc
        rts
@hole:  sec
        rts

        .segment "CODE"
