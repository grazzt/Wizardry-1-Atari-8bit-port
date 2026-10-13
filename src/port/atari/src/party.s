; --party: form the seeded roster once after INITGAME clears PARTYCNT.
; Read live records, validate all six, and persist the original tavern's OUT
; flag before publishing PARTYCNT. No synthetic keys or stat resets.
; The transient 1KB read buffer is allocated below SP, then released. Game
; IOCACHE/CACHEBL are untouched, so later GETREC uses its normal cache.
.if PARTY_PRESENT
party_src = nat0
party_dst = nat0+2
party_disk = nat0+4
party_once: .byte 0
party_formed: .byte 0
party_failed: .byte 0
party_index: .byte 0
party_name_end: .byte 0
party_saved_sp: .word 0
party_stage: .word 0
party_cache: .word $FFFF

party_auto_form:
        lda party_once
        bne @return
        lda cseg
        cmp #16
        bne @return
        lda cproc
        cmp #1
        beq @start
@return:rts
@start: inc party_once
        lda ioresult
        pha
        lda sp
        sta party_saved_sp
        lda sp+1
        sta party_saved_sp+1
        lda #0
        sta t7
        lda #4
        sta t7+1
        jsr stack_alloc_w
        lda sp
        sta party_stage
        lda sp+1
        sta party_stage+1
        clc
        lda base
        adc #<(MSCW-2+74*2)    ; CHARACTR[0]
        sta party_dst
        lda base+1
        adc #>(MSCW-2+74*2)
        sta party_dst+1
        clc
        lda base
        adc #<(MSCW-2+68*2)    ; CHARDISK[0]
        sta party_disk
        lda base+1
        adc #>(MSCW-2+68*2)
        sta party_disk+1
        lda #0
        sta party_index
@member:
        jsr party_read
        beq :+
        jmp party_abort
:       jsr party_record
        jsr party_validate
        bcs :+
        jmp party_finish       ; missing, unavailable or changed identity
:       ldy #0
@copy:  lda (party_src),y
        sta (party_dst),y
        iny
        cpy #208
        bne @copy
        ldy #32
        lda #1
        sta (party_dst),y
        ldx party_index
        txa
        asl a
        tay
        lda party_slots,x
        sta (party_disk),y
        iny
        lda #0
        sta (party_disk),y
        clc
        lda party_dst
        adc #208
        sta party_dst
        bcc @next
        inc party_dst+1
@next:  inc party_index
        lda party_index
        cmp #6
        bne @member

        ; Validation succeeded for all six. Update each whole roster cache
        ; once, retaining other characters and all padding byte for byte.
        lda #0
        sta party_index
@mark:  jsr party_read
        bne party_abort
        jsr party_record
        ldy #32
        lda #1
        sta (party_src),y
        ldx party_index
        inx
        cpx #6
        beq @write
        lda party_block_lo,x
        cmp party_cache
        bne @write
        lda party_block_hi,x
        cmp party_cache+1
        beq @marked
@write: jsr party_io
        jsr disk_write
        lda ioresult
        bne party_abort
@marked:
        inc party_index
        lda party_index
        cmp #6
        bne @mark
        ldy #MSCW-2+3*2        ; PARTYCNT = 6 (original global word 3)
        lda #6
        sta (base),y
        iny
        lda #0
        sta (base),y
        inc party_formed
        jmp party_finish
party_abort:
        lda ioresult
        sta party_failed
party_finish:
        lda party_saved_sp
        sta sp
        lda party_saved_sp+1
        sta sp+1
        pla
        sta ioresult
        rts

party_read:
        ldx party_index
        lda party_block_lo,x
        cmp party_cache
        bne @load
        lda party_block_hi,x
        cmp party_cache+1
        bne @load
        lda #0
        rts
@load:  lda party_block_lo,x
        sta party_cache
        lda party_block_hi,x
        sta party_cache+1
        jsr party_io
        jsr disk_read
        lda ioresult
        rts
party_io:
        lda #0
        sta ioresult
        sta cnt
        lda #4
        sta cnt+1
        lda party_stage
        sta t2
        lda party_stage+1
        sta t2+1
        lda party_cache
        sta t4
        lda party_cache+1
        sta t4+1
        rts
party_record:
        ldx party_index
        clc
        lda party_stage
        adc party_offset_lo,x
        sta party_src
        lda party_stage+1
        adc party_offset_hi,x
        sta party_src+1
        rts
party_validate:
        ; Never revive dead characters or pull an OUT/disbanded party home.
        ldy #32
        lda (party_src),y
        iny
        ora (party_src),y
        ldy #40
        ora (party_src),y
        iny
        ora (party_src),y
        ldy #204               ; LOSTXYL.LOCATION[3]
        ora (party_src),y
        iny
        ora (party_src),y
        bne @bad
        lda party_index
        asl a
        asl a
        asl a
        asl a
        tax
        lda party_names,x
        clc
        adc #1
        sta party_name_end
        ldy #0
@name:  lda (party_src),y
        cmp party_names,x
        bne @bad
        inx
        iny
        cpy party_name_end
        bne @name
        sec
        rts
@bad:   clc
        rts

        .include "party_tables.inc"
.endif
