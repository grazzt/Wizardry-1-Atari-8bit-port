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
.if SPRITES_PRESENT
        lda #SPRITE_LIT         ; a softer white: the pictures' light colours share it
        sta COLOR1
.endif
        lda #<SCENVOL
        sta volbase
        lda #>SCENVOL
        sta volbase+1
        lda #0
        sta vol_ro
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
        rts

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

