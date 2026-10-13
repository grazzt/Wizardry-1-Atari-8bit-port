; SYSTEM.STARTUP support: two programs, two volumes, Pascal file reads,
; CHAINSTUFF, the title picture decompressor, and p-code access to Apple I/O.
; Assembled into the high area ($B000), which the boot routine loads.
;
; Program 0 is SYSTEM.STARTUP (title, options) with the boot volume as drive
; 1, read-only. When it ends after SETCHAIN, program 1 (WIZARDRY.CODE) starts
; with the scenario volume as drive 1, as if the player had swapped disks.

program:    .byte 0
pic_on:     .byte 0             ; a picture is coloured (picture.s, game only)
stack_floor: .byte 0            ; high byte the stack must stay at or above
chain:      .byte 0
vol_ro:     .byte 0
volbase:    .word 0             ; first sector of the volume in drive 1
codebase:   .word 0             ; first sector of the running program's volume
file_first: .word 0
file_count: .word 0
fblocks:    .byte 0

; A = program number. Resets the p-machine and enters the program body.
start_program:
        sta program
        ldx #$FF                ; nothing on the evaluation stack carries over
        txs
        cmp #0
        bne @game
        lda #<BOOTVOL
        sta volbase
        lda #>BOOTVOL
        sta volbase+1
        lda #1
        sta vol_ro
        lda #>(OVERLAY_END + $FF)   ; keep the stack off the overlay
        sta stack_floor
        jsr music_start           ; the NES title theme
        jsr color_init
        ldx #31
@s:     lda startup_block_lo,x
        sta seg_block_lo,x
        lda startup_block_hi,x
        sta seg_block_hi,x
        lda startup_len_lo,x
        sta seg_len_lo,x
        lda startup_len_hi,x
        sta seg_len_hi,x
        dex
        bpl @s
        bmi @common
@game:  jsr music_stop
        lda #0
        sta stack_floor
        jsr build_gfx_dl          ; monochrome graphics from now on
        lda #$40
        sta NMIEN
        lda #<GOVL_SECTOR         ; picture colour
        sta sector
        lda #>GOVL_SECTOR
        sta sector+1
        lda #<PICTURE
        sta DBUFLO
        lda #>PICTURE
        sta DBUFHI
        lda #GOVL_SECTORS
        sta t0
        jsr load_sectors
        jsr pic_init
.ifdef DISK2
.if MUSIC_PRESENT
        jsr music_prepare       ; player code from disk 1, before the swap
.endif
.endif
.if SPRITES_PRESENT
        lda #SPRITE_LIT         ; a softer white: the pictures' light colours share it
        sta COLOR1
.endif
.ifdef DISK2
        jsr disk_change         ; prompt, verify, then set volbase and vol_ro
.ifdef SCENCMP
        lda #3
        jsr comp_call           ; load the compressed volume map
.endif
.if MUSIC_PRESENT
        jsr music_init_game     ; jingles from disk 2, then enable the VBI player
.endif
.else
        lda #<SCENVOL
        sta volbase
        lda #>SCENVOL
        sta volbase+1
        lda #0
        sta vol_ro
.endif
        ldx #31
@g:     lda game_block_lo,x
        sta seg_block_lo,x
        lda game_block_hi,x
        sta seg_block_hi,x
        lda game_len_lo,x
        sta seg_len_lo,x
        lda game_len_hi,x
        sta seg_len_hi,x
        dex
        bpl @g
@common:
        lda volbase
        sta codebase
        lda volbase+1
        sta codebase+1
        ldx #31
        lda #0
@z:     sta seg_base_lo,x
        sta seg_base_hi,x
        sta seg_refs,x
        dex
        bpl @z
        sta chain
        jmp start_body

; The program body returned.
program_end:
        lda program
        bne @end
        lda chain
        beq @end
        lda #1                  ; SETCHAIN('WIZARDRY') was called: run the game
        jmp start_program
@end:   lda #14
        jmp vmerror

; SYSTEM.STARTUP's utilities ask the player to swap disks in drive 1:
; RDSCNTOC (UTILS.9) "PLACE SCENARIO IN DRIVE 1" and EXITUTIL (UTILS.7)
; "PLACE BOOT DISK IN DRIVE 1". Both volumes are on our one disk, so drive 1
; switches as each procedure starts (pvm does the same).
disk_swap:
        lda cseg
        cmp #7
        bne @r
        lda cproc
        cmp #9
        beq @scen
        cmp #7
        bne @r
        lda #<BOOTVOL
        sta volbase
        lda #>BOOTVOL
        sta volbase+1
        lda #1
        sta vol_ro
@r:     rts
@scen:  lda #<SCENVOL
        sta volbase
        lda #>SCENVOL
        sta volbase+1
        lda #0
        sta vol_ro
.ifdef SCENCMP
        sta map_valid           ; utilities may have inserted a different scenario disk
.endif
        rts

; --- Two-disk build: the "CHANGE TO DISK" prompt --------------------------------
; In the two-disk build the scenario volume is a separate physical disk. At the
; chain into the game the player must swap it in: this shows the prompt, waits
; for a key, and verifies the inserted disk by reading its Pascal directory
; (block 2) for SCENARIO.DATA, looping on the wrong disk. It runs at native
; level between procedures: no p-machine state is touched and no RNG is stirred.
; DISKPROMPT is 1 while it waits, so the tests know to swap the disk in the
; emulator. The utilities' swaps (RDSCNTOC/EXITUTIL) need no prompt here: the
; game itself shows "PLACE ... IN DRIVE 1, PRESS RETURN" and loops on FINDFILE
; until the right disk is in drive 1.
.ifdef DISK2
bad_disk:     .byte 0
        .segment "OVERLAY"
prompt_ok:    .byte "CHANGE TO DISK 2", 0
prompt_ok_len = * - prompt_ok
prompt_bad:   .byte "WRONG DISK - CHANGE TO DISK 2", 0
prompt_bad_len = * - prompt_bad
prompt_ready: .byte "PRESS ANY KEY WHEN READY", 0
prompt_ready_len = * - prompt_ready
        .segment "TABLES"
DIRBUF = SECBUF                 ; verification runs between programs

; t1 = row, t2 = string, t0 = length: print centred on row t1.
put_row:
        lda t0
        clc
        adc #1
        lsr a
        sta nat0+6              ; (length+1)/2
        lda #20
        sec
        sbc nat0+6
        sta con_x
        lda t1
        sta con_y
        lda t2
        sta t3
        lda t2+1
        sta t3+1
@pr:    ldy #0
        lda (t3),y
        jsr con_put
        inc t3
        bne @pc
        inc t3+1
@pc:    dec t0
        bne @pr
        rts

; Z set if the volume at volbase lists SCENARIO.DATA. The directory's file
; count is a word at block 2 offset 16; entries follow at 26 bytes each, the
; 16-byte Pascal name (length at +6) at +7. One sector holds the count and
; four entries, which covers every volume this build verifies (three files).
.ifdef SCENCMP
        .segment "GAMEOVL"     ; called after the game overlay is loaded
.endif
scen_name:    .byte 13, "SCENARIO.DATA"
verify_scen:
        lda #<SCENVOL
        clc
        adc #8                  ; block 2's first sector
        sta sector
        lda #>SCENVOL
        adc #0
        sta sector+1
        lda #<DIRBUF
        sta DBUFLO
        lda #>DIRBUF
        sta DBUFHI
        lda #0
        sta ioresult
        lda #$52
        jsr sio
        lda ioresult
        beq @v2
        jmp @no
@v2:    lda DIRBUF + 16         ; file count
        bne @vc
        jmp @no
@vc:    cmp #5
        bcs @no
        lda DIRBUF + 17
        bne @no
        lda #<DIRBUF
        sta t2
        lda #>DIRBUF
        sta t2+1
        ldy #26 + 6              ; entry 1: the name's length byte
@ve:    ldx #0
        sty t0                   ; save the entry's name-field start
@vn:    lda (t2),y
        cmp scen_name,x
        bne @next
        inx
        iny
        cpx #14
        bne @vn
        sec
        rts
@next:  lda t0                   ; advance from the entry start, not the mismatch point
        clc
        adc #26
        tay
        cpy #26 * 4 + 6          ; past the last entry that fits in the sector
        bcc @ve
@no:    clc
        rts

; Show the message, wait for a key, verify the disk; loop on the wrong disk.
; Sets volbase and vol_ro on success.
        .segment "TABLES"
disk_change:
        lda #1
        sta DISKPROMPT
        lda #0
        sta bad_disk
@msg:   jsr con_textmode
        jsr con_clear
        lda #8
        sta t1
        lda bad_disk
        beq @ok
        lda #<prompt_bad
        sta t2
        lda #>prompt_bad
        sta t2+1
        lda #prompt_bad_len
        sta t0
        jmp @row
@ok:    lda #<prompt_ok
        sta t2
        lda #>prompt_ok
        sta t2+1
        lda #prompt_ok_len
        sta t0
@row:   jsr put_row
        lda #10
        sta t1
        lda #<prompt_ready
        sta t2
        lda #>prompt_ready
        sta t2+1
        lda #prompt_ready_len
        sta t0
        jsr put_row
        jsr get_key
        jsr verify_scen
        bcc @wrong
        lda #0
        sta ioresult
.ifdef SCENCMP
        sta map_valid           ; reload the map from the verified game disk
.endif
        sta DISKPROMPT
        lda #<SCENVOL
        sta volbase
        lda #>SCENVOL
        sta volbase+1
        lda #0
        sta vol_ro
        rts
@wrong: lda #1
        sta bad_disk
        jmp @msg
.endif

; Hooks into the game overlay's picture colour. They do nothing until a
; picture is coloured, and the overlay is never entered while SYSTEM.STARTUP
; runs (it is not loaded yet).
pic_hook_off:                   ; CLRPICT, DRAWLINE
        lda pic_on
        beq hook_rts
        jmp pic_off
pic_hook_char:                  ; PRGRCHR
        lda pic_on
        beq hook_rts
        jmp pic_char
pic_hook_rect:                  ; CLRRECT
        lda pic_on
        beq hook_rts
        jmp pic_rect
pic_hook_vis:                   ; text/graphics switch
        lda program
        beq hook_rts
        jmp pm_vis
hook_rts:
        rts

; CXP 28,n: the CHAINSTUFF library unit.
chainstuff:
        lda cproc
        cmp #2
        bne @init
        pla                     ; SETCHAIN(name): the only target is WIZARDRY
        pla
        lda #1
        sta chain
@init:  NEXT                    ; procedure 1: unit initialisation

; --- p-code touching Apple I/O -----------------------------------------------------
; LDB from $BF00-$C0FF (ad = address): the title's KEYPRESS reads the keyboard
; at $C000 and the Pascal BIOS type-ahead pointers at $BF18/$BF19.
ldb_io: lda ad+1
        cmp #$C0
        bne @bf
        lda ad
        bne @zero
        jsr key_waiting
        beq @zero
        lda #0
        pha
        lda #$80                ; bit 7: a key is waiting
        pha
        NEXT
@bf:    lda ad
        cmp #$18
        beq @zero
        cmp #$19
        beq @zero
        lda #0                  ; anything else there is ordinary memory
        pha
        tay
        lda (ad),y
        pha
        NEXT
@zero:  lda #0
        pha
        pha
        NEXT

; STB to $C0xx: an Apple soft switch. Only text/graphics matter here.
stb_io: lda ad
        cmp #$50
        bne @t
        jsr con_gfxmode
        NEXT
@t:     cmp #$51
        bne @r
        jsr con_textmode
@r:     NEXT

