; Streaming, bounded ZX02 decoder adapted from Daniel Serpell's 132-byte
; zx02-optim.asm, revision 7ffa0e782c9f5718a8d77ba021c6babc78c7fe19.
; Copyright (c) 2020 Daniel Serpell. MIT license: tools/zx02/LICENSE.
; Modified for the Atari port: SIO input provider, output-length bound,
; preserved provider registers, and explicit failure on premature EOF.
; In: lz_dst / lz_left, sector / lz_ix. Executes with the OS ROM disabled.
.ifdef SCENCMP
        .segment "COMP"
zx_offhi = $F4
zx_bits  = $F5
zx_ptr   = $F6              ; 2: low holds inverted offset-1

lz_decode:
        lda #0
        sta zx_offhi
        lda #$FF
        sta zx_ptr
        lda #$80
        sta zx_bits
        ldy #0
        ldx #0
zx_literal:
        inx
        jsr zx_elias
@copy:  jsr lz_next
        jsr lz_put
        beq zx_done
        dex
        bne @copy
        asl zx_bits
        bcs zx_offset
        inx
        jsr zx_elias
zx_match:
        lda lz_dst+1
        sbc zx_offhi           ; C=0 from Elias: subtract the extra byte
        sta zx_ptr+1
@copy:  ldy lz_dst
        lda (zx_ptr),y
        jsr lz_put
        beq zx_done
        lda lz_dst
        bne @same
        inc zx_ptr+1
@same:  dex
        bne @copy
        asl zx_bits
        bcc zx_literal
zx_offset:
        inx
        jsr zx_elias
        beq zx_early_end
        dex
        txa
        lsr a
        sta zx_offhi
        jsr lz_next            ; must preserve C from LSR
        ror a
        eor #$FF
        sta zx_ptr
        ldx #1
        jsr zx_skip
        inx
        bcc zx_match
zx_early_end:
        lda #16
        sta ioresult           ; valid output reaches its bound before EOF
zx_done:
        rts
zx_data_bit:
        asl zx_bits
        rol a
        tax
zx_elias:
        asl zx_bits
        bne zx_skip
        jsr lz_next            ; must preserve C=1 (sentinel bit shifted out)
        rol a
        sta zx_bits
zx_skip:
        txa
        bcs zx_data_bit
        rts

; Emit A and return Z when the complete requested output has been produced.
; Keeps X and carry, which the ZX02 state machine uses across copies.
lz_put:
        jsr comp_yield          ; never expose ROM-RAM font data on the screen
        ldy #0
        sta (lz_dst),y
        inc lz_dst
        bne @count
        inc lz_dst+1
@count: lda lz_left
        bne @low
        dec lz_left+1
@low:   dec lz_left
        lda lz_left
        ora lz_left+1
        rts

; Next input byte. Preserve X, carry and Y=0 even across an SIO refill.
lz_next:
        php
        txa
        pha
        ldx lz_ix
        cpx #128
        bcc @byte
        jsr lz_fill
        ldx #0
@byte:  lda LZSTAGE,x
        inc lz_ix
        sta lz_token
        pla
        tax
        plp
        lda lz_token
        ldy #0
        rts

lz_fill:
        lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda #$52
        jsr sio
        ldy #127
@copy:  lda SECBUF,y
        jsr comp_yield
        sta LZSTAGE,y
        dey
        bpl @copy
        inc sector
        bne @done
        inc sector+1
@done:  lda #0
        sta lz_ix
        rts
.endif
