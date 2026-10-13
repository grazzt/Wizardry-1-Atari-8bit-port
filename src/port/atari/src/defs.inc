; Wizardry I p-machine for the Atari 65XE: definitions shared by all modules.
;
; Memory map (64 KB, OS ROM in, BASIC off):
;   $0080-$00FF  zero page: p-machine registers and scratch
;   $0100-$01FF  6502 stack = p-machine evaluation stack (as on the Apple)
;   $0479        copy-protection marker the game tests (see build.py)
;   $0500-$05FF  sector buffer and runtime variables
;   $06FA-$1FFF  boot header and runtime code (no DOS, so page 7 is free)
;   $2000-$3E0F  320x192 bitmap; the game also loads 512 bytes at $2000
;   $4000-$52FF  game: picture colour overlay ($4000), players and missiles
;                ($4B00), picture shadow ($5000), trace buffer ($5200)
;                (start-up: title shadow at $4000, overlay at $6000)
;   $5300        heap start (set by the game; it never allocates)
;   $5300-$AFFF  p-machine memory stack: frames and code segments
;   $B000-$B9FF  runtime tables and variables
;   $BA00        graphics display list, $BB00 text display list
;   $BC00-$BFBF  40x24 text screen

STACKTOP    = $B000
DL_GFX      = $BA00
DL_TEXT     = $BB00
TEXTSCR     = $BC00
BITMAP      = $2000
BITMAP2     = $3000         ; second LMS block (lines 102-191)

SECBUF      = $0500         ; 128-byte sector buffer
OVERLAY     = $6000         ; start-up overlay (program 0 only; the game's stack later)
ERRINFO     = $0580         ; error code, segment, IPC (for the test harness)
TESTMODE    = $05F0         ; nonzero: key waits stir the RNG TESTPOLLS+1 times
TESTPOLLS   = $05F2         ; (set by the harness to match pvm exactly)
WAITING     = $05F4         ; 1 while the runtime waits for a key
DISKPROMPT  = $05F5         ; 1 while the two-disk build waits at its change-disk prompt
CALLLOG     = $0600         ; ring of (segment, procedure) per call, for debugging
TRACEBUF    = $5200         ; build.py --trace: ring of (IPC, opcode, TOS)
PICTURE     = $4000         ; game overlay: picture colour (picture.s)
calllog_i   = $D4           ; next ring index
clip_xlo    = $D6           ; DRAWLINE clipping box, set by CLRPICT
clip_ylo    = $D7           ; ($679, $6F9, $779, $7F9 on the Apple)
clip_xhi    = $D8
clip_yhi    = $D9

; --- compressed scenario scratch, in RAM under the OS ROM -----------------
MAPTBL      = $C000         ; 512-byte map
LZSTAGE     = $C200         ; 128-byte input stage
LZOUT       = $C280         ; decoded 512-byte Pascal block
PICOUT      = $C280         ; decoded picture (at most 1,664 bytes)
COMP_ADDR   = $C900         ; shared decoder, loaded at boot
lz_flags    = $F7
lz_n        = $F8
lz_src      = $F9           ; 2: match/copy source
lz_dst      = $FB           ; 2: output
lz_left     = $FD           ; 2: output bytes remaining
lz_ix       = $FF
lz_e        = $DC           ; 2: map entry pointer
lz_offlo    = $DE
lz_offhi    = $DF
lz_token    = $DA           ; 2: packed match
lz_run      = $F8           ; match bytes remaining
; --- Atari OS ------------------------------------------------------------
SDMCTL      = $022F
SDLSTL      = $0230
CH          = $02FC
SHFLOK      = $02BE
COLOR1      = $02C5
COLOR2      = $02C6
COLOR4      = $02C8
CRSINH      = $02F0
DDEVIC      = $0300
DUNIT       = $0301
DCOMND      = $0302
DSTATS      = $0303
DBUFLO      = $0304
DBUFHI      = $0305
DTIMLO      = $0306
DBYTLO      = $0308
DBYTHI      = $0309
DAUX1       = $030A
DAUX2       = $030B
ICCOM       = $0342
ICBAL       = $0344
ICBAH       = $0345
ICBLL       = $0348
ICBLH       = $0349
ICAX1       = $034A
ICAX2       = $034B
DOSVEC      = $000A
TABLES_ADDR = $B000
SIOV        = $E459
VDSLST      = $0200
WSYNC       = $D40A
NMIEN       = $D40E
VCOUNT      = $D40B          ; scanline / 2; ROM-RAM work uses vertical blank
COLPF0      = $D016
COLPF1      = $D017
COLPF2      = $D018
CIOV        = $E456

; --- p-machine registers -----------------------------------------------
ipc         = $80           ; instruction pointer (absolute)
jtab        = $82           ; current procedure's attribute table
mp          = $84           ; current frame (its mark-stack word)
base        = $86           ; program-body frame (globals)
sp          = $88           ; memory stack pointer (lowest used byte)
heap        = $8A           ; heap top
curseg      = $8C           ; current segment number
opcode      = $8D           ; opcode being executed
vec         = $8E           ; dispatch vector

t0          = $90           ; 16-bit scratch registers
t1          = $92
t2          = $94
t3          = $96
t4          = $98
t5          = $9A
t6          = $9C
t7          = $9E

cseg        = $A0           ; call target segment / procedure
cproc       = $A1
newmp       = $A2
lexwant     = $A4
fp          = $A5           ; frame walked by LOD/LDA/STR and calls
ad          = $A7           ; computed address
cnt         = $A9           ; 16-bit counter
sector      = $AB           ; SIO sector number
ioresult    = $AD
eoln        = $AE
oscnt       = $AF

con_x       = $B0           ; console cursor (may exceed 39)
con_y       = $B1
con_ptr     = $B2           ; 2 bytes
gfx_mode    = $B4
cur_col     = $B5           ; PRGRCHR cursor ($4F9 / $579 on the Apple)
cur_row     = $B6
nat0        = $B8           ; native routine scratch, 8 bytes
rng         = $C0           ; RANDOM state: $47A $4FA $57A $5FB on the Apple
rngpad      = $C4           ; $47B-$47D: where MVCURSOR(80)'s carries land
mulx        = $C8           ; multiply/divide scratch (8 bytes)
sign        = $D0           ; 2 bytes
osf         = $D2           ; the Pascal OS frame (2 bytes)

MSCW        = 12            ; mark-stack word: see calls.s

; --- macros --------------------------------------------------------------
.macro PUSHW zp_
        lda zp_+1
        pha
        lda zp_
        pha
.endmacro

.macro POPW zp_
        pla
        sta zp_
        pla
        sta zp_+1
.endmacro

.macro PUSHAX               ; push A (low) / X (high)
        tay
        txa
        pha
        tya
        pha
.endmacro

.macro CASE value_, target_     ; if A = value_ then jump to target_
        cmp #value_
        bne :+
        jmp target_
:
.endmacro

.macro NEXT
        jmp next
.endmacro
