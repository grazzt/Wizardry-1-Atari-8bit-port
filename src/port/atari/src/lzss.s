; Bounded LZSS decoder. Runs with OS ROM disabled, from the COMP overlay.
; lz_dst/left select the output; lz_ix/sector select the streamed input.
.ifdef SCENCMP
        .segment "COMP"
lz_decode:
        lda #0
        sta lz_n
@item:  lda lz_left
        ora lz_left+1
        beq @done
        lda lz_n
        bne @have
        jsr lz_next
        sta lz_flags
        lda #8
        sta lz_n
@have:  asl lz_flags
        bcs @literal
        jsr lz_next
        sta lz_token
        jsr lz_next
        sta lz_token+1
        lda lz_token
        and #$1F
        clc
        adc #3
        sta lz_run
        lda lz_token
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        sta lz_offlo
        lda lz_token+1
        asl a
        asl a
        asl a
        ora lz_offlo
        sta lz_offlo
        lda lz_token+1
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        sta lz_offhi
        inc lz_offlo
        bne @offset
        inc lz_offhi
@offset:
        sec
        lda lz_dst
        sbc lz_offlo
        sta lz_src
        lda lz_dst+1
        sbc lz_offhi
        sta lz_src+1
@match: ldy #0
        lda (lz_src),y
        jsr lz_put
        inc lz_src
        bne @next
        inc lz_src+1
@next:  lda lz_left
        ora lz_left+1
        beq @done              ; a segment read can end inside its padding
        dec lz_run
        bne @match
        beq @tick
@literal:
        jsr lz_next
        jsr lz_put
@tick:  dec lz_n
        jmp @item
@done:  rts

lz_put: ldy #0
        sta (lz_dst),y
        inc lz_dst
        bne @count
        inc lz_dst+1
@count: lda lz_left
        bne @low
        dec lz_left+1
@low:   dec lz_left
        rts

lz_next:
        ldx lz_ix
        cpx #128
        bcc @byte
        jsr lz_fill
        ldx #0
@byte:  lda LZSTAGE,x
        inc lz_ix
        rts

; SIO runs with the ROM enabled, into normal RAM. Copy with ROM disabled.
lz_fill:
        lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda #$52
        jsr sio
        ldy #127
@copy:  lda SECBUF,y
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
