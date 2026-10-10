; Start-up overlay (loaded at $6000, used only by SYSTEM.STARTUP): Pascal file
; reads from the boot volume and the title picture decompressor. color.s
; follows: colour for the title.

; --- Pascal files, read-only, on the boot volume ---------------------------------
os_finit:                       ; FINIT(f, window, record size)
        ldx #3
        jmp drop_words
os_fclose:                      ; FCLOSE(f, mode)
        ldx #2
        jmp drop_words

drop_words:                     ; discard X argument words
        pla
        pla
        dex
        bne drop_words
        NEXT

os_fopen:                       ; FOPEN(f, name, isold, junk)
        pla
        pla
        pla
        pla
        POPW t1                 ; name
        pla
        pla
        lda #<boot_files
        sta t2
        lda #>boot_files
        sta t2+1
@entry: ldy #0
        lda (t2),y
        beq @missing
        tax                     ; compare length byte and characters
@cmp:   lda (t1),y
        cmp (t2),y
        bne @next
        iny
        dex
        bpl @cmp
        ldy #16
        lda (t2),y
        sta file_first
        iny
        lda (t2),y
        sta file_first+1
        iny
        lda (t2),y
        sta file_count
        iny
        lda (t2),y
        sta file_count+1
        lda #0
        sta ioresult
        NEXT
@next:  clc
        lda t2
        adc #20
        sta t2
        bcc @entry
        inc t2+1
        bne @entry
@missing:
        lda #10                 ; no such file
        sta ioresult
        NEXT

os_fblockio:                    ; FBLOCKIO(f, buf, offset, nblocks, rblock, doread)
        pla                     ; two function result words
        pla
        pla
        pla
        pla                     ; doread (reads only)
        pla
        POPW t4                 ; relative block
        POPW cnt                ; blocks wanted
        POPW t3                 ; offset
        POPW t2                 ; buffer
        pla                     ; file
        pla
        jsr t2_plus_t3
        sec                     ; blocks available = count - rblock
        lda file_count
        sbc t4
        sta t5
        lda file_count+1
        sbc t4+1
        sta t5+1
        bmi @none
        lda cnt+1               ; take min(wanted, available); both < 256 here
        bne @avail
        lda cnt
        ldx t5+1
        bne @take
        cmp t5
        bcc @take
@avail: lda t5
@take:  sta fblocks
        clc                     ; absolute block on the volume
        lda t4
        adc file_first
        sta t4
        lda t4+1
        adc file_first+1
        sta t4+1
        lda #0
        sta cnt
        lda fblocks
        asl a                   ; bytes = blocks * 512
        sta cnt+1
        jsr disk_read
        jmp @done
@none:  lda #0
        sta fblocks
@done:  lda #0
        pha
        lda fblocks
        pha
        NEXT

; --- LZDECOMP(var a1, a2): decompress title frame records from a1[a2] ------------
; Records: a row (< $C0) with five column masks and the bytes they select;
; a single byte ($C0 + column, row, value); $FE rotates rows 0-48 left by a
; byte; $FD flips their Apple palette bit (a colour change); $FF ends.
; Apple bytes go to the shadow; changed lines are redrawn in colour at the end.
lzmask: .res 5

nat_lzdecomp:
        POPW t0                 ; a2: index
        POPW t1                 ; a1: address
        clc
        lda t1
        adc t0
        sta t1
        lda t1+1
        adc t0+1
        sta t1+1
@rec:   ldy #0
        lda (t1),y
        cmp #$C0
        bcc @row
        cmp #$FD
        bcc @single
        beq @flip
        cmp #$FE
        beq @rotate
        jsr render_dirty
        NEXT
@flip:  jsr lz_flip
        jsr render_dirty
        NEXT
@rotate:
        jsr lz_rotate
        jsr render_dirty
        NEXT

@single:
        sec
        sbc #$C0
        sta nat0+4              ; column
        ldy #1
        lda (t1),y
        tax                     ; row
        jsr lz_line
        ldy #2
        lda (t1),y
        ldy nat0+4
        cpy #40
        bcs @s3
        sta (nat0),y
        lda nat0+4
        jsr mark
@s3:    clc
        lda t1
        adc #3
        sta t1
        bcc @rec
        inc t1+1
        bne @rec

@row:   tax
        stx nat0+3              ; row
        jsr lz_line
        ldy #5
@m:     lda (t1),y
        sta lzmask-1,y
        dey
        bne @m
        clc
        lda t1
        adc #6
        sta t1
        bcc @cols
        inc t1+1
@cols:  lda #0
        sta nat0+4              ; column
        sta nat0+5              ; mask index
@mask:  ldx nat0+5
        lda lzmask,x
        sta nat0+6
        ldx #8
@bit:   lsr nat0+6
        bcc @skip
        ldy #0
        lda (t1),y
        ldy nat0+4
        sta (nat0),y
        stx nat0+7
        ldx nat0+3
        tya
        jsr mark
        ldx nat0+7
        inc t1
        bne @skip
        inc t1+1
@skip:  inc nat0+4
        dex
        bne @bit
        inc nat0+5
        lda nat0+5
        cmp #5
        bne @mask
        jmp @rec

; nat0 := shadow line X.
lz_line:
        lda bm_row_lo,x
        sta nat0
        lda bm_row_hi,x
        clc
        adc #SHADOW_OFS
        sta nat0+1
        rts

lz_rotate:                      ; shadow rows 48..0: rotate left one byte
        ldx #48
@r:     jsr lz_line
        jsr mark_line
        ldy #0
        lda (nat0),y
        sta nat0+2
@b:     iny
        lda (nat0),y
        dey
        sta (nat0),y
        iny
        cpy #39
        bne @b
        lda nat0+2
        sta (nat0),y
        dex
        bpl @r
        rts

lz_flip:                        ; shadow rows 48..0: flip the palette bits
        ldx #48
@r:     jsr lz_line
        ldy #39
@b:     lda (nat0),y
        eor #$80
        sta (nat0),y
        dey
        bpl @b
        dex
        bpl @r
        ; A flip changes only hues (purple<->blue, green<->orange), not which
        ; dots are lit: bands 0-5 (lines 0-47) keep their pixels and swap their
        ; chosen hues and colours. Line 48 shares band 6 with unflipped lines.
        ldx #48
        jsr mark_line
        ldx #5
@band:  lda band_ha,x
        beq @nb                 ; not drawn yet
        jsr counterpart
        sta band_ha,x
        tay
        lda hue_color,y
        sta band_c0,x
        lda band_hb,x
        jsr counterpart
        sta band_hb,x
        tay
        lda hue_color,y
        sta band_c1,x
@nb:    dex
        bpl @band
        ldx #47                 ; and the cached counts
@cnt:   lda line_n2,x
        ldy line_n4,x
        sta line_n4,x
        tya
        sta line_n2,x
        lda line_n3,x
        ldy line_n5,x
        sta line_n5,x
        tya
        sta line_n3,x
        dex
        bpl @cnt
        rts

counterpart:                    ; hue 2<->4, 3<->5
        cmp #4
        bcs @down
        adc #2
        rts
@down:  sbc #2                  ; carry set
        rts
