; Shared compression support, available during both SYSTEM.STARTUP and game.
; COMP code and scratch live under the OS ROM. Normal-RAM wrappers restore
; the ROM and interrupts for every SIO; no emulator fast-patching is needed.
.ifdef SCENCMP
        .segment "TABLES"
comp_target: .word 0
comp_nmi:    .byte 0
map_valid:   .byte 0

; ANTIC reads the OS font even when CPU interrupts are disabled. Keep ROM
; visible during the picture: enter ROM-RAM after the VBI (line 248) or in
; the first 16 scanlines. The display's three blank lines leave room
; for decoder control work between byte copies. Runs in ordinary RAM.
comp_wait_blank:
@wait:  lda VCOUNT
        cmp #8
        bcc @ready
        cmp #124
        bcc @wait
@ready: rts

; Preserve A, X, Y and flags, including the decoder's carry. Long ROM-RAM
; loops yield at byte boundaries, with ROM, VBI and DLIs restored while they
; wait for the next blank. The mapped decoder stays suspended under ROM.
comp_yield:
        php
        pha
        lda PORTB
        and #1
        bne @done              ; an ordinary raw read needs no banking
        lda VCOUNT
        cmp #8
        bcc @done
        cmp #124
        bcs @done
        lda PORTB
        ora #1
        sta PORTB
        lda comp_nmi
        sta NMIEN
        cli
        jsr comp_wait_blank
        sei
        lda #0
        sta NMIEN
        lda PORTB
        and #$FE
        sta PORTB
@done:  pla
        plp
        rts

comp_boot_ptr = t1
comp_boot:
        lda #<COMP_ADDR
        sta comp_boot_ptr
        lda #>COMP_ADDR
        sta comp_boot_ptr+1
        lda #<COMP_SECTOR
        sta sector
        lda #>COMP_SECTOR
        sta sector+1
        lda #COMP_SECTORS
        sta t0
comp_copy:
        lda #$40
        sta comp_nmi
@sector:
        lda #<SECBUF
        sta DBUFLO
        lda #>SECBUF
        sta DBUFHI
        lda #$52
        jsr sio
        php
        jsr comp_wait_blank
        sei
        lda #0
        sta NMIEN
        lda PORTB
        and #$FE
        sta PORTB
        ldy #127
@copy:  lda SECBUF,y
        jsr comp_yield
        sta (comp_boot_ptr),y
        dey
        bpl @copy
        lda PORTB
        ora #1
        sta PORTB
        lda #$40
        sta NMIEN
        plp
        clc
        lda comp_boot_ptr
        adc #128
        sta comp_boot_ptr
        bcc @next
        inc comp_boot_ptr+1
@next:  inc sector
        bne @count
        inc sector+1
@count: dec t0
        bne @sector
        rts

; A = dispatch index: map I/O, picture load, picture sector, map load.
comp_call:
        asl a
        tax
        lda comp_vectors,x
        sta comp_target
        lda comp_vectors+1,x
        sta comp_target+1
        php
        lda gfx_mode
        beq @text
        lda program
        beq @graphics
        lda pic_on
        beq @text
@graphics:
        lda #$C0
        bne @save
@text:  lda #$40
@save:  sta comp_nmi
        jsr comp_wait_blank
        sei
        lda #0
        sta NMIEN
        lda PORTB
        pha
        and #$FE
        sta PORTB
        jsr comp_jump
        pla
        sta PORTB
        lda comp_nmi
        sta NMIEN
        plp
        rts
comp_jump:
        jmp (comp_target)
comp_vectors:
        .word map_io, cmp_picture, cmp_picture_read, map_load, cmp_music

; Called from normal-RAM sio. Must return with SIO's N flag intact.
        .segment "CODE"
comp_sio:
        lda PORTB
        and #1
        beq @banked
        jmp SIOV
@banked:
        lda PORTB
        ora #1
        sta PORTB
        lda comp_nmi
        sta NMIEN
        cli
        jsr SIOV
        php
        cli
        jsr comp_wait_blank
        sei
        lda #0
        sta NMIEN
        lda PORTB
        and #$FE
        sta PORTB
        plp
        sei
        rts

        .segment "COMP"
; Request counters belong to the mapper, not to the decoder or raw walk.
map_count: .word 0
map_dest:  .word 0
map_block: .word 0
map_part:  .word 0
map_ctl:   .byte 0

map_io:
        lda t4+1
        bne @mapped
        lda t4
        cmp #7
        bcs @mapped
        jmp disk_base          ; header, directory and code header are raw
@mapped:
        jsr map_load
        lda ioresult
        beq @request
        rts
@request:
        lda dcode
        bpl @blocks
        jmp cmp_seg
@blocks:
        lda cnt
        sta map_count
        lda cnt+1
        sta map_count+1
        lda t2
        sta map_dest
        lda t2+1
        sta map_dest+1
        lda t4
        sta map_block
        lda t4+1
        sta map_block+1
@block: lda map_count
        ora map_count+1
        bne @more
        rts
@more:  lda map_count
        sta map_part
        lda map_count+1
        cmp #2
        bcc @partial
        lda #0
        sta map_part
        lda #2
@partial:
        sta map_part+1
        sec
        lda map_block
        sbc MAPTBL+7
        sta lz_offlo
        lda map_block+1
        sbc MAPTBL+8
        bne @message
        lda lz_offlo
        cmp MAPTBL+5
        bcs @message
        lda #<MAP_DATA
        ldx #>MAP_DATA
        jmp @entry
@message:
        sec
        lda map_block
        sbc MAPTBL+9
        sta lz_offlo
        lda map_block+1
        sbc MAPTBL+10
        beq :+
        jmp map_error
:
        lda lz_offlo
        cmp MAPTBL+6
        bcc :+
        jmp map_error
:
        lda #<MAP_MESG
        ldx #>MAP_MESG
@entry: sta lz_e
        stx lz_e+1
        lda lz_offlo
        sta lz_offhi
        lda #0
        sta lz_src+1
        asl lz_offlo
        rol lz_src+1
        clc
        lda lz_offlo
        adc lz_offhi
        sta lz_offlo
        lda lz_src+1
        adc #0
        sta lz_offhi
        clc
        lda lz_e
        adc lz_offlo
        sta lz_e
        lda lz_e+1
        adc lz_offhi
        clc
        adc #>MAPTBL
        sta lz_e+1
        ldy #0
        lda (lz_e),y
        sta sector
        iny
        lda (lz_e),y
        sta sector+1
        iny
        lda (lz_e),y
        sta map_ctl
        lda map_dest
        sta t2
        lda map_dest+1
        sta t2+1
        lda map_part
        sta cnt
        lda map_part+1
        sta cnt+1
        lda sector
        ora sector+1
        bne @unit
        lda map_block
        sta t4
        lda map_block+1
        sta t4+1
        jsr disk_base
        jmp @advance
@unit:  lda map_ctl
        bpl @compressed
@raw:   lda sector
        sta dvol
        lda sector+1
        sta dvol+1
        lda #0
        sta t4
        sta t4+1
        jsr disk_base          ; relocated, writable raw block
        jmp @advance
@compressed:
        lda dcmd
        cmp #$57
        bne :+
        jmp map_error
:
        lda #<LZOUT
        sta lz_dst
        lda #>LZOUT
        sta lz_dst+1
        lda #0
        sta lz_left
        lda #2
        sta lz_left+1
        jsr cmp_unit
        lda #<LZOUT
        sta lz_src
        lda #>LZOUT
        sta lz_src+1
@copy:  jsr copy_part
@advance:
        lda ioresult
        bne @done
        clc
        lda map_dest
        adc map_part
        sta map_dest
        lda map_dest+1
        adc map_part+1
        sta map_dest+1
        sec
        lda map_count
        sbc map_part
        sta map_count
        lda map_count+1
        sbc map_part+1
        sta map_count+1
        inc map_block
        bne @again
        inc map_block+1
@again: jmp @block
@done:  rts

map_error:
        lda #16
        sta ioresult
        rts

copy_part:
        lda map_part
        sta cnt
        lda map_part+1
        sta cnt+1
@loop:  lda cnt
        ora cnt+1
        beq @done
        ldy #0
        lda (lz_src),y
        jsr comp_yield
        sta (t2),y
        inc lz_src
        bne @src
        inc lz_src+1
@src:   inc t2
        bne @dst
        inc t2+1
@dst:   lda cnt
        bne @low
        dec cnt+1
@low:   dec cnt
        jmp @loop
@done:  rts

cmp_seg:
        lda #<(MAPTBL+MAP_CODE)
        sta lz_e
        lda #>(MAPTBL+MAP_CODE)
        sta lz_e+1
        ldx MAPTBL+4
@scan:  ldy #0
        jsr comp_yield
        lda (lz_e),y
        cmp t4
        beq @found
        clc
        lda lz_e
        adc #6
        sta lz_e
        bcc @next
        inc lz_e+1
@next:  dex
        bne @scan
        jmp map_error
@found: lda t4+1
        beq :+
        jmp map_error
:
        lda cnt
        sta lz_left
        lda cnt+1
        sta lz_left+1
        lda t2
        sta lz_dst
        lda t2+1
        sta lz_dst+1
        ldy #3
        lda (lz_e),y
        sta sector
        iny
        lda (lz_e),y
        sta sector+1
        iny
        lda (lz_e),y
        sta map_ctl
cmp_unit:
        jsr lz_fill
        lda map_ctl
        and #$7F
        sta lz_ix
        lda map_ctl
        bpl @compressed
@raw:   lda lz_left
        ora lz_left+1
        beq @done
        jsr lz_next
        jsr lz_put
        jmp @raw
@compressed:
        jmp lz_decode
@done:  rts

map_load:
        lda map_valid
        bne @done
        lda #<MAP_START
        sta sector
        lda #>MAP_START
        sta sector+1
        lda #<MAPTBL
        sta lz_dst
        lda #>MAPTBL
        sta lz_dst+1
        ldx #MAP_SECTORS
        stx lz_run
@sector:
        jsr lz_fill
        ldy #127
@copy:  lda LZSTAGE,y
        jsr comp_yield
        sta (lz_dst),y
        dey
        bpl @copy
        clc
        lda lz_dst
        adc #128
        sta lz_dst
        bcc @count
        inc lz_dst+1
@count: dec lz_run
        bne @sector
        lda ioresult
        bne @done
        ldx #3
@magic: lda MAPTBL,x
        cmp map_magic,x
        bne @error
        dex
        bpl @magic
        inc map_valid
@done:  rts
@error: jmp map_error
map_magic: .byte "WZC3"

cmp_music:
        lda lz_token+1
        sta map_ctl
        jmp cmp_unit

cmp_picture:
        lda lz_ix              ; byte offset in the first sector
        pha
        jsr lz_fill
        pla
        sta lz_ix
        lda lz_token+1
        bmi @raw
        jsr lz_next
        sta lz_left
        jsr lz_next
        sta lz_left+1
        lda #<PICOUT
        sta lz_dst
        lda #>PICOUT
        sta lz_dst+1
        jsr lz_decode
        jmp @ready
@raw:   lda #<PICOUT
        sta lz_dst
        lda #>PICOUT
        sta lz_dst+1
@byte:  jsr lz_next
        jsr lz_put
        lda lz_left
        ora lz_left+1
        bne @byte
@ready: lda #<PICOUT
        sta lz_src
        lda #>PICOUT
        sta lz_src+1
        rts
cmp_picture_read:
        ldy #127
@copy:  lda (lz_src),y
        jsr comp_yield
        sta SECBUF,y
        dey
        bpl @copy
        clc
        lda lz_src
        adc #128
        sta lz_src
        bcc @done
        inc lz_src+1
@done:  rts
.endif
