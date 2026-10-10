"""Record a demo video of the Atari port: title, character creation, shopping,
the maze, fights with spells and a treasure chest, with the game's music.

    python3 port/atari/build.py --test-images
    python3 port/atari/demo.py            # -> port/atari/build/demo.mp4

Needs ffmpeg and numpy. Each scene runs in its own process (libatari800 sets
up its sound once per process) and writes video and audio; ffmpeg joins them.
The game scenes run in lockstep with pvm, which makes them repeatable and
lets the script read the text the game draws on the hi-res screen.
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT / 'tools'))

FPS = 1789772.5 / 29868              # NTSC frames per second
CROP = (16, 0, 352, 240)            # x, y, width, height of the recorded picture
SCALE = 3
PLAYED = PROJECT / 'appleII/images/wizardry_i/wizardry_i_scenario.dsk'
TESTPOLLS, WAITING = 0x05F2, 0x05F4


class Recorder:
    """Pipes the emulator's frames to ffmpeg and keeps the matching sound."""

    def __init__(self, atari, out):
        import numpy as np
        self.np, self.atari, self.out = np, atari, Path(out)
        self.palette = np.frombuffer(b''.join(atari.palette()), dtype=np.uint8).reshape(256, 3)
        x, y, w, h = CROP
        self.ffmpeg = subprocess.Popen(
            ['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}',
             '-r', f'{FPS:.6f}', '-i', '-', '-vf', f'scale={w * SCALE}:{h * SCALE}:flags=neighbor',
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p',
             str(self.out.with_suffix('.mkv'))], stdin=subprocess.PIPE)
        self.sound = bytearray()
        self.heard = len(atari.audio)
        self.on = False
        self.frames = 0
        atari.on_frame = self.frame

    def frame(self):
        audio = self.atari.audio
        if self.on:
            np = self.np
            x, y, w, h = CROP
            screen = np.frombuffer(self.atari.screen(), dtype=np.uint8).reshape(240, 384)[y:y + h, x:x + w]
            self.ffmpeg.stdin.write(self.palette[screen].tobytes())
            self.sound += audio[self.heard:]
            self.frames += 1
        self.heard = len(audio)

    def close(self):
        self.atari.on_frame = None
        self.ffmpeg.stdin.close()
        self.ffmpeg.wait()
        with wave.open(str(self.out.with_suffix('.wav')), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(bytes(self.sound))
        return self.frames


# --- reading the hi-res screen (pvm) --------------------------------------------------

class GfxText:
    """The text the game draws on the hi-res screen, tracked from pvm's calls:
    PRGRCHR (WIZARDRY.32) draws the glyph whose address it is given at the
    cursor MVCURSOR (.31) set, and CLRRECT (.30) clears cells. PRINTCHR (.22)
    gives one glyph's character, which fixes the character set's address."""

    def __init__(self, vm):
        self.grid = [[' '] * 40 for _ in range(24)]
        self.col = self.row = 0
        self.pending, self.base, self.fresh = ' ', None, False
        call, native = vm.call, vm._call_native

        def on_call(seg, proc):
            if (seg, proc) == (1, 22) and vm.stack:
                self.pending, self.fresh = chr(vm.stack[-1] & 0x7F), True
            return call(seg, proc)

        def on_native(seg, proc):
            key, s = (seg.number, proc.number), vm.stack
            if key == (1, 31) and len(s) >= 2 and s[-2] < 80:
                self.col, self.row = s[-2], s[-1]
            elif key == (1, 32):
                if self.base is None and self.fresh:
                    self.base = s[-1] - 8 * ord(self.pending)
                ch = chr((s[-1] - self.base) // 8 & 0x7F) if self.base is not None else '?'
                self.fresh = False
                if 0 <= self.row < 24 and 0 <= self.col < 40:
                    self.grid[self.row][self.col] = ch
                self.col += 1
            elif key == (1, 30) and len(s) >= 4:
                x, y, w, h = s[-4:]
                for r in range(y, min(24, y + h)):
                    for c in range(x, min(40, x + w)):
                        self.grid[r][c] = ' '
            return native(seg, proc)
        vm.call, vm._call_native = on_call, on_native

    def region(self, r0, r1, c0=1, c1=39):
        return '\n'.join(''.join(row[c0:c1]) for row in self.grid[r0:r1])


MAGE_SPELLS = ['MAHALITO', 'LAHALITO', 'HALITO', 'MADALTO', 'KATINO', 'TILTOWAIT']
PRIEST_SPELLS = ['BADIOS', 'MONTINO', 'BADIAL']


class Agent:
    """Plays the maze from the screen: walks and kicks doors at random, fights
    with the front rank, casts with the priest and mage, opens chests."""

    def __init__(self, gfx, seed):
        self.g, self.rnd = gfx, random.Random(seed)
        self.cast = {'JASON': 0, 'BOB': 0}
        self.chest_step, self.spell = 0, None

    def next_keys(self):
        """(keys, label) for the screen as it is."""
        g = self.g
        box, opt, msg = g.region(1, 5, 13), g.region(6, 10, 13), g.region(11, 15)
        every = box + '\n' + opt + '\n' + msg
        if 'WHO (#)' in every:
            return '4', 'chest-who'             # HENRY, the thief
        if 'O)PEN' in every:
            self.chest_step += 1
            return ('I' if self.chest_step == 1 else 'O'), 'chest'
        if 'GROUP' in opt and '?' in opt:
            return '1', 'group'
        if 'SPELL NAME' in opt and self.spell:
            return self.spell + '\r', 'spell-name'
        if "'S OPTIONS" in opt:
            name = opt.split("'S OPTIONS")[0].split('\n')[-1].strip()
            if name in self.cast and 'S)PELL' in opt:
                book = MAGE_SPELLS if name == 'JASON' else PRIEST_SPELLS
                self.spell = book[self.cast[name] % len(book)]
                self.cast[name] += 1
                return 'S', 'spell'
            return ('F', 'fight') if 'F)IGHT' in opt else ('P', 'parry')
        if 'PRESS [RETURN] TO FIGHT' in opt:
            return '\r', 'fight!'
        if 'L)EAVE IN PEACE' in every:
            return 'L', 'friendly'
        if '(Y/N)' in every:
            return 'N', 'yes/no'
        if '[RET' in every:
            return '\r', 'return'
        if 'F)ORWARD' in box:
            return self.rnd.choice('FFFFKKLR'), 'walk'
        return '\r', 'unknown'


# --- scenes ---------------------------------------------------------------------------

class Session:
    """A lockstep run being recorded: keys go to pvm, then to the Atari at a
    watchable pace."""

    def __init__(self, atr, scenario, out):
        from lockstep import Lockstep
        self.run = Lockstep(atr=atr, scenario=scenario, sound=True)
        self.vm, self.atari = self.run.vm, self.run.atari
        self.gfx = GfxText(self.vm)
        self.rec = Recorder(self.atari, out)

    def settle(self, shown=None):
        """Run until the Atari waits for a key. With `shown`, record only that
        many frames of the wait (a cut: the game's long pauses and loads)."""
        was, count = self.rec.on, 0
        for _ in range(20000):
            self.atari.frame(10)
            count += 10
            if shown is not None and count >= shown:
                self.rec.on = False
            if self.atari.peek(WAITING) or self.run.error:
                self.atari.frame(2)
                break
        self.rec.on = was

    def press(self, keys, hold=40, typing=7, shown=None):
        """Wait `hold` frames on the current screen, then type `keys`."""
        self.vm.send(keys)
        for i, ch in enumerate(keys):
            self.settle(shown)
            self.atari.frame(hold if i == 0 else typing)
            polls = self.vm.poll_log.get(self.run.typed, 0)
            self.atari.memory[TESTPOLLS] = polls & 0xFF
            self.atari.memory[TESTPOLLS + 1] = polls >> 8
            self.atari.type(ch)
            self.run.typed += 1
            if self.run.error:
                raise RuntimeError(f'execution error after {keys!r}')

    def wait(self, frames, shown=None):
        self.settle(shown)
        self.atari.frame(frames)

    def close(self):
        """Finish; the Atari must still show what pvm shows."""
        from lockstep import bitmap_diff
        self.settle()
        host_gfx, atari_gfx = self.run.graphics
        assert host_gfx == atari_gfx, 'display modes differ'
        if host_gfx:
            assert bitmap_diff(self.vm, self.atari) == [], 'the Atari bitmap differs from pvm'
        else:
            assert self.atari.text_memory() == self.vm.console.text(), 'the Atari text differs from pvm'
        frames = self.rec.close()
        self.run.close()
        return frames


def scene_title(out):
    """The title animation with its music, the options screen, S)tart."""
    from harness import Atari
    work = tempfile.TemporaryDirectory()
    atr = Path(work.name) / 'wizardry.atr'
    shutil.copyfile(HERE / 'build/title.atr', atr)
    atari = Atari(atr, sound=True)
    rec = Recorder(atari, out)
    atari.frame(20)
    rec.on = True
    atari.frame(round(50 * FPS))          # the smoke becomes the logo at about 45 s
    atari.type(' ')
    atari.frame(round(3.5 * FPS))
    atari.type('S')
    atari.frame(50)
    return rec.close()


def scene_create(out):
    """Create MAGE, an elf mage, at the training grounds."""
    s = Session(HERE / 'build/test.atr', None, out)
    s.rec.on = True
    s.wait(50)
    for keys, hold in (('\r', 40), ('\r', 50), ('E', 90), ('T', 60), ('MAGE\r', 70), ('Y', 80),
                       ('\r', 60), ('\r', 40), ('B', 90), ('A', 70)):
        s.press(keys, hold, typing=9)
    points = int(re.search(r'POINTS\s+(\d+)', s.vm.console.text()).group(1))
    s.press('\r', 90)                                   # on to I.Q.
    s.press('+' * points, 25, typing=10)
    for keys, hold in (('\x1b', 70), ('B', 80), ('Y', 90), ('MAGE\r', 60), ('\r', 30), ('I', 70)):
        s.press(keys, hold, typing=9)
    s.wait(200)
    return s.close()


# (keys, frames to wait first, options): record=False leaves the key out of the
# video; shown=N records only N frames of the game's wait before the key.
TOWN = ([('\r', 40), ('\r', 40), ('G', 90)]
        + [k for name in ('ROB', 'JAKE') for k in (('A', 28), (name + '\r', 16), ('\r', 14))]
        + [k for name in ('GIMLI', 'HENRY', 'BOB', 'JASON')                      # (cut: four more join)
           for k in (('A', 5, {'record': False}), (name + '\r', 5, {'record': False}), ('\r', 5, {'record': False}))]
        + [('6', 70), ('R', 90), ('M', 60), ('L', 170), ('L', 25), ('L', 25), ('\r', 40),    # JASON's spells
           ('B', 70), ('3', 60), ('B', 70), ('P', 80), ('1', 35), ('F', 60), ('P', 60), ('6', 35),
           ('L', 60), ('L', 50), ('\r', 40),                                                # GIMLI shops
           ('G', 50), ('3', 50), ('E', 90), ('1', 60), ('1', 50), ('L', 150), ('\r', 70),     # and equips
           ('E', 70), ('M', 80), ('L', 110, {'shown': 150})])                                # the maze: camp
AGENT_SEED = 36         # from --find-seed: fights at steps 39 and 52, the chest opened at step 61
MAZE_HOLD = {'walk': 9, 'yes/no': 30, 'fight': 20, 'parry': 20, 'spell': 20, 'spell-name': 30, 'group': 20,
             'fight!': 50, 'chest': 110, 'chest-who': 50, 'friendly': 80, 'return': 90, 'unknown': 60}


def scene_adventure(out):
    """The party forms, shops and equips; then the maze: fights and a chest."""
    s = Session(HERE / 'build/played.atr', PLAYED, out)
    s.rec.on = True
    s.wait(30)
    for keys, hold, *options in TOWN:
        options = options[0] if options else {}
        s.rec.on = options.get('record', True)
        s.press(keys, hold, shown=options.get('shown'))
    s.rec.on = True
    print(f'  town: {s.rec.frames / FPS:.1f} s')
    agent = Agent(s.gfx, AGENT_SEED)
    step, fights, done = 0, 0, None
    in_fight = False
    while done is None or step < done:
        keys, label = agent.next_keys()
        fighting = label in ('fight', 'parry', 'spell', 'spell-name', 'group', 'fight!')
        was = in_fight
        if fighting and not in_fight:
            fights += 1
        in_fight = fighting or (in_fight and label not in ('walk', 'yes/no'))
        # Show the first steps, each fight with the walk up to it, and the chest;
        # skip the long walks between.
        if label in ('fight!', 'chest', 'chest-who') or (fighting and not was):
            print(f'  step {step} {label}: {s.rec.frames / FPS:.1f} s')
        # The second fight's round of messages: its first 15 s, then the outcome.
        shown = 900 if label == 'chest' and agent.chest_step == 1 else 150 if step == 0 else None
        s.press(keys, MAZE_HOLD[label], typing=6, shown=shown)
        step += 1
        if label == 'chest-who' and agent.chest_step >= 2 and done is None:
            done = step + 5                     # the chest opens; a few steps more
        s.rec.on = WINDOWS(step)
        if step > 400:
            raise RuntimeError('no chest found: the maze run has changed')
    s.wait(120)
    return s.close()


def WINDOWS(step):
    """Maze steps that are recorded (the walk is cut between them)."""
    return step <= 12 or step >= 31


def find_seed(limit=60):
    """Search agent seeds on pvm alone for maze runs that reach a chest: prints
    the step of the first fight, the rounds fought and the chest's step."""
    from ucsd.disk import PascalDisk
    from pvm.tests.test_pvm import machine
    for seed in range(1, limit + 1):
        vm = machine(PascalDisk.open(PLAYED))
        gfx = GfxText(vm)
        for keys, *_ in TOWN:
            vm.send(keys)
        agent, first, rounds, fights = Agent(gfx, seed), None, 0, []
        for step in range(260):
            keys, label = agent.next_keys()
            if label in ('fight', 'spell', 'parry') and (not fights or step - fights[-1] > 12):
                fights.append(step)
            rounds += label == 'fight!'
            try:
                vm.send(keys)
            except Exception:           # (typing 30 characters at "SPELL NAME" breaks the game)
                break
            if label == 'chest-who' and agent.chest_step >= 2:
                print(f'seed {seed}: fights begin at steps {fights}, {rounds} rounds, chest opened at step {step}')
                break


SCENES = {'title': scene_title, 'create': scene_create, 'adventure': scene_adventure}
CAPTIONS = {'title': 'WIZARDRY ON THE ATARI 65XE   -   TITLE, WITH THE NES THEME ON POKEY',
            'create': 'THE TRAINING GROUNDS: CREATING A CHARACTER',
            'adventure': "GILGAMESH'S TAVERN, BOLTAC'S, THEN THE MAZE"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--scene', choices=SCENES)
    parser.add_argument('--find-seed', action='store_true', help='search for a maze run with a chest (AGENT_SEED)')
    parser.add_argument('--out', default=HERE / 'build/demo.mp4')
    args = parser.parse_args()
    if args.find_seed:
        return find_seed()
    work = HERE / 'build/demo'
    work.mkdir(parents=True, exist_ok=True)
    if args.scene:
        frames = SCENES[args.scene](work / args.scene)
        print(f'{args.scene}: {frames} frames, {frames / FPS:.1f} s')
        return
    seconds = 0
    for scene in SCENES:
        subprocess.run([sys.executable, __file__, '--scene', scene], check=True)
        with wave.open(str(work / f'{scene}.wav')) as w:
            seconds += w.getnframes() / w.getframerate()
    inputs, filters, labels = [], [], ''
    font = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
    for i, scene in enumerate(SCENES):
        inputs += ['-i', work / f'{scene}.mkv', '-i', work / f'{scene}.wav']
        text = CAPTIONS[scene].replace("'", '’').replace(':', r'\:')
        filters.append(f"[{2 * i}:v]drawtext=fontfile={font}:text='{text}':fontcolor=0xB0B0B0:fontsize=22:"
                       f"x=(w-text_w)/2:y=h-46[v{i}]")
        labels += f'[v{i}][{2 * i + 1}:a]'
    filters.append(f'{labels}concat=n={len(SCENES)}:v=1:a=1[cv][ca]')
    filters.append(f'[cv]fade=t=in:d=0.5,fade=t=out:st={seconds - 1.5:.2f}:d=1.5[v]')
    filters.append(f'[ca]afade=t=out:st={seconds - 1.5:.2f}:d=1.5[a]')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(filters),
                    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
                    args.out], check=True)
    print(f'{args.out}: {seconds:.0f} s')


if __name__ == '__main__':
    main()
