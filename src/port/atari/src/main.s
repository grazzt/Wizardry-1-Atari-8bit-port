; Wizardry I p-machine for the Atari 65XE.
;
; The evaluation stack is the 6502 hardware stack, as on the Apple: a word
; is pushed high byte first, so PLA yields the low byte first. Handlers are
; entered by JMP with the evaluation stack untouched and end with NEXT.
; Subroutines they JSR to must not touch evaluation-stack words.

        .include "defs.inc"

        .segment "CODE"

; ---------------------------------------------------------------------------
; Boot. The OS boot loader reads BOOT_SECTORS sectors from sector 1 to $06FA
; (this header first), sets DOSINI from the header, and calls $0700. That
; loads the tables to $B000 and points DOSVEC at `start`, where the OS goes
; once the boot completes. build.py supplies BOOT_SECTORS, TABLE_SECTOR and
; TABLE_SECTORS; the two Pascal volumes follow (BOOTVOL, SCENVOL).
        .byte 0, BOOT_SECTORS
        .word $06FA, boot_rts

boot:   lda #<TABLE_SECTOR
        sta sector
        lda #>TABLE_SECTOR
        sta sector+1
        lda #<TABLES_ADDR
        sta DBUFLO
        lda #>TABLES_ADDR
        sta DBUFHI
        lda #TABLE_SECTORS
        sta t0
        jsr load_sectors
        lda #<OVL_SECTOR        ; the start-up overlay
        sta sector
        lda #>OVL_SECTOR
        sta sector+1
        lda #<OVERLAY
        sta DBUFLO
        lda #>OVERLAY
        sta DBUFHI
        lda #OVL_SECTORS
        sta t0
        jsr load_sectors
.ifdef SCENCMP
        jsr comp_boot
.endif
.if MUSIC_PRESENT
.ifndef DISK2
        jsr music_boot          ; the music, into the RAM under the OS ROM
.endif
.endif
        lda #<start
        sta DOSVEC
        lda #>start
        sta DOSVEC+1
        clc
boot_rts:
        rts

; Read t0 sectors from `sector` on to DBUFLO/HI (the boot routine, and the
; game overlay when WIZARDRY.CODE starts).
load_sectors:
        lda #$52
        jsr sio
        clc
        lda DBUFLO
        adc #128
        sta DBUFLO
        bcc @n
        inc DBUFHI
@n:     inc sector
        bne @s
        inc sector+1
@s:     dec t0
        bne load_sectors
        rts

start:
        cld
        ldx #$FF
        txs
        lda #0
        ldx #$7F
@zp:    sta $80,x
        dex
        bpl @zp
        jsr con_init
        jsr kbd_init
.ifdef TESTMODE_ON
        lda #1                  ; lockstep testing: key waits stir a set amount
        sta TESTMODE
.endif
.ifdef NO_TITLE
        lda #1                  ; straight into WIZARDRY.CODE
.else
        lda #0                  ; SYSTEM.STARTUP: title and options first
.endif
        jmp start_program

; Called by start_program once the segment tables and drive 1 are set.
start_body:
        lda #<STACKTOP
        sta sp
        lda #>STACKTOP
        sta sp+1
        lda #$00
        sta heap
        lda #$53                ; above the game's picture colour memory
        sta heap+1

        ; The Pascal OS frame (lexical level -1). The game reads only its
        ; word 2 (INPUT) and word 3 (OUTPUT); their values are file ids.
        lda #MSCW+6
        jsr stack_alloc
        lda sp
        sta mp
        sta osf
        lda sp+1
        sta mp+1
        sta osf+1
        ldy #MSCW+6-1
        lda #0
@clr:   sta (mp),y
        dey
        bpl @clr
        ldy #8                  ; MYJTAB -> a fake attribute table, lex $FF
        lda #<os_jtab
        sta (mp),y
        iny
        lda #>os_jtab
        sta (mp),y
        ldy #MSCW+2             ; word 2 = INPUT
        lda #1
        sta (mp),y
        ldy #MSCW+4             ; word 3 = OUTPUT
        lda #2
        sta (mp),y
        lda #<os_jtab
        sta jtab
        lda #>os_jtab
        sta jtab+1

        ldx #1                  ; segment 1 stays resident
        jsr load_segment
        inc seg_refs+1

        lda #0                  ; the program body takes 2 parameter words
        pha
        pha
        pha
        pha
        sta base
        sta base+1
        sta curseg
        lda #1
        sta cseg
        sta cproc
        jmp docall

os_jtab:
        .byte 0, $FF            ; procedure 0, lexical level -1

; ---------------------------------------------------------------------------
; Fetch and dispatch.
next:
.ifdef TRACE                    ; debugging: ring of (IPC, opcode, TOS) at TRACEBUF
        ldx trace_i
        lda ipc
        sta TRACEBUF,x
        lda ipc+1
        sta TRACEBUF+1,x
        ldy #0
        lda (ipc),y
        sta TRACEBUF+2,x
        stx trace_x
        tsx
        lda $0101,x
        ldx trace_x
        sta TRACEBUF+3,x
        txa
        clc
        adc #4
        sta trace_i
.endif
        ldy #0
        lda (ipc),y
        inc ipc
        bne @inc
        inc ipc+1
@inc:   cmp #$80
        bcs @op
        tax                     ; SLDC 0..127
        tya                     ; Y = 0
        pha
        txa
        pha
        jmp next
@op:    sta opcode
        asl a
        tax
        lda optab,x
        sta vec
        lda optab+1,x
        sta vec+1
        jmp (vec)

; Operand fetchers (do not touch the evaluation stack).
getb:   ldy #0                  ; returns with N/Z set from the byte
        lda (ipc),y
        inc ipc
        bne @r
        inc ipc+1
@r:     ora #0
        rts

getbig: jsr getb                ; t0 := big operand
        bmi @two
        sta t0
        lda #0
        sta t0+1
        rts
@two:   and #$7F
        sta t0+1
        jsr getb
        sta t0
        rts

getw:   jsr getb
        sta t0
        jsr getb
        sta t0+1
        rts

; ad := fp + MSCW - 2 + 2*t0   (address of local word t0 of frame fp)
frame_addr:
        lda t0
        asl a
        sta ad
        lda t0+1
        rol a
        sta ad+1
        clc
        lda ad
        adc #MSCW-2
        sta ad
        bcc @a
        inc ad+1
@a:     clc
        lda ad
        adc fp
        sta ad
        lda ad+1
        adc fp+1
        sta ad+1
        rts

; fp := frame A static levels out from mp
walk:   tax
        lda mp
        sta fp
        lda mp+1
        sta fp+1
        cpx #0
        beq @done
@up:    ldy #0
        lda (fp),y
        pha
        iny
        lda (fp),y
        sta fp+1
        pla
        sta fp
        dex
        bne @up
@done:  rts

; Allocate A bytes (A < 256) or t7 bytes (stack_alloc_w) on the memory stack.
stack_alloc:
        sta t7
        lda #0
        sta t7+1
stack_alloc_w:
        sec
        lda sp
        sbc t7
        sta sp
        lda sp+1
        sbc t7+1
        sta sp+1
        ; stack must stay above the heap (keep 256 bytes of margin) and above
        ; the start-up overlay while SYSTEM.STARTUP runs (stack_floor)
        sec
        lda sp
        sbc heap
        lda sp+1
        sbc heap+1
        bcc @over
        cmp #1
        bcc @over
        lda sp+1
        cmp stack_floor
        bcc @over
        rts
@over:  lda #4                  ; stack overflow
        jmp vmerror

; ---------------------------------------------------------------------------
; Execution error: A = error code. Shows it and stops; the test harness reads
; ERRINFO. Codes 0-15 follow UCSD; 11 = unimplemented instruction.
vmerror:
        sta ERRINFO
        lda curseg
        sta ERRINFO+1
        lda ipc
        sta ERRINFO+2
        lda ipc+1
        sta ERRINFO+3
        lda opcode
        sta ERRINFO+4
        lda #$EE
        sta ERRINFO+5           ; marker: error reported
        jsr con_textmode
        lda #0
        sta con_x
        lda #23
        sta con_y
        ldx #0
@msg:   lda errmsg,x
        beq @num
        jsr con_put
        inx
        bne @msg
@num:   lda ERRINFO
        jsr con_hex
        lda #' '
        jsr con_put
        lda ERRINFO+1
        jsr con_hex
        lda #' '
        jsr con_put
        lda ERRINFO+3
        jsr con_hex
        lda ERRINFO+2
        jsr con_hex
        lda #' '
        jsr con_put
        lda ERRINFO+4
        jsr con_hex
@hang:  jmp @hang

        .segment "TABLES"
errmsg: .byte "EXEC ERROR ", 0
trace_i: .byte 0
trace_x: .byte 0

        .segment "CODE"
        .include "pcode.s"
        .include "calls.s"
        .include "csp.s"
        .include "console.s"
        .include "disk.s"
        .include "zx02.s"
        .include "compressed.s"
        .segment "CODE"
        .include "natives.s"
        .segment "TABLES"
        .include "segtab.inc"
        .include "startup.s"
        .segment "OVERLAY"
        .include "overlay.s"
        .include "color.s"
        .segment "GAMEOVL"
        .include "picture.s"
        .include "musicgame.s"
        .include "music.s"
        .segment "GAMEOVL"
        .include "party.s"
