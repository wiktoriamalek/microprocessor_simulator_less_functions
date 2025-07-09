

import sys, pathlib, shlex, readline
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Union

REG16 = ["AX", "BX", "CX", "DX"]
REG8H = {r: r[0] + "H" for r in REG16}
REG8L = {r: r[0] + "L" for r in REG16}
REG8  = list(REG8H.values()) + list(REG8L.values())
ALLREG = REG16 + REG8

def is_int(tok: str) -> bool:
    try:
        int(tok, 0)
        return True
    except ValueError:
        return False

@dataclass
class CPU:
    regs: Dict[str, int] = field(default_factory=lambda: {r: 0 for r in REG16})

    def _hi(self, r): return (self.regs[r] >> 8) & 0xFF
    def _lo(self, r): return self.regs[r] & 0xFF
    def _set_hi(self, r, v): self.regs[r] = ((v & 0xFF) << 8) | self._lo(r)
    def _set_lo(self, r, v): self.regs[r] = (self._hi(r) << 8) | (v & 0xFF)

    def read(self, name: str) -> int:
        name = name.upper()
        if name in REG16: return self.regs[name]
        if name in REG8H.values():
            base = name[0] + "X"
            return self._hi(base)
        if name in REG8L.values():
            base = name[0] + "X"
            return self._lo(base)
        raise KeyError(f"Nieznany rejestr {name}")

    def write(self, name: str, value: int):
        name = name.upper()
        if name in REG16:
            self.regs[name] = value & 0xFFFF
        elif name in REG8H.values():
            base = name[0] + "X"
            self._set_hi(base, value)
        elif name in REG8L.values():
            base = name[0] + "X"
            self._set_lo(base, value)
        else:
            raise KeyError(f"Nieznany rejestr {name}")

    def dump(self):
        row = []
        for r in REG16:
            row.append(f"{r}={self.regs[r]:04X}h")
        print("  ".join(row))

@dataclass
class Instruction:
    op: str
    dst: str = ""
    src: str = ""
    lineno: int = 0

class AsmParser:
    @staticmethod
    def parse_line(line: str, lineno: int) -> Union[Instruction, None]:
        line = line.split(";")[0].strip()   # usuń komentarz
        if not line:
            return None
        parts = shlex.split(line.replace(",", " "))
        op = parts[0].upper()
        if op not in {"MOV", "ADD", "SUB"}:
            raise SyntaxError(f"Nieobsługiwane polecenie '{op}' w linii {lineno}")
        if len(parts) != 3:
            raise SyntaxError(f"Błędny format w linii {lineno}: {line}")
        return Instruction(op, parts[1].upper(), parts[2].upper(), lineno)

    @staticmethod
    def parse_program(src: List[str]) -> List[Instruction]:
        prog = []
        for i, ln in enumerate(src, 1):
            instr = AsmParser.parse_line(ln, i)
            if instr:
                prog.append(instr)
        return prog

class Simulator:
    def __init__(self):
        self.cpu = CPU()
        self.prog: List[Instruction] = []
        self.pc = 0

    def load_source(self, src_lines: List[str]):
        self.prog = AsmParser.parse_program(src_lines)
        self.pc = 0

    def reset(self):
        self.cpu = CPU()
        self.pc = 0

    def step(self) -> bool:
        if self.pc >= len(self.prog):
            print("== KONIEC PROGRAMU ==")
            return True
        ins = self.prog[self.pc]
        self.execute(ins)
        self.pc += 1
        return False

    def run(self):
        while not self.step():
            pass

    def execute(self, ins: Instruction):
        size_dst = 16 if ins.dst in REG16 else 8
        val_src = self.resolve_operand(ins.src, size_dst)
        val_dst = self.cpu.read(ins.dst)

        if ins.op == "MOV":
            result = val_src
        elif ins.op == "ADD":
            result = (val_dst + val_src)
        elif ins.op == "SUB":
            result = (val_dst - val_src)
        else:
            raise RuntimeError("Niemożliwa komenda")

        mask = 0xFFFF if size_dst == 16 else 0xFF
        self.cpu.write(ins.dst, result & mask)

        print(f"[{ins.lineno:03}] {ins.op} {ins.dst},{ins.src:<6} --> ", end="")
        self.cpu.dump()

    def resolve_operand(self, token: str, expected_bits: int) -> int:
        if token in ALLREG:
            val = self.cpu.read(token)
            return val & (0xFFFF if expected_bits == 16 else 0xFF)
        if is_int(token):
            val = int(token, 0)
            return val & (0xFFFF if expected_bits == 16 else 0xFF)
        raise ValueError(f"Niepoprawny operand '{token}'")


HELP = """\
Dostępne polecenia interfejsu:
  load <plik.asm>   – wczytaj źródło
  save <plik.asm>   – zapisz (ostatnio wczytane lub edytowane) źródło
  list              – pokaż kod z numerami linii
  edit              – otwórz prosty wbudowany edytor linii
  run               – uruchom cały program
  step              – wykonaj jedną instrukcję
  regs              – pokaż rejestry
  reset             – zeruj rejestry i licznik PC
  help              – to samo co teraz
  quit              – wyjście
"""

class Shell:
    def __init__(self):
        self.sim = Simulator()
        self.source_lines: List[str] = []

    def cmdloop(self):
        print("Symulator CPU – wpisz 'help' aby zobaczyć komendy.")
        while True:
            try:
                line = input("cpu> ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            if not line: continue
            cmd, *args = shlex.split(line)
            cmd = cmd.lower()
            try:
                {
                    "help": self.do_help,
                    "load": self.do_load,
                    "save": self.do_save,
                    "list": self.do_list,
                    "edit": self.do_edit,
                    "run":  self.do_run,
                    "step": self.do_step,
                    "regs": self.do_regs,
                    "reset":self.do_reset,
                    "quit": self.do_quit,
                    "exit": self.do_quit
                }[cmd](args)
            except KeyError:
                print("Nieznana komenda. help aby uzyskać listę.")
            except Exception as e:
                print("BŁĄD:", e)

    def do_help(self, _):  print(HELP)
    def do_quit(self,_):   sys.exit(0)

    def do_load(self, args):
        if not args: raise ValueError("podaj nazwę pliku")
        path = pathlib.Path(args[0]).expanduser()
        self.source_lines = path.read_text(encoding="utf-8").splitlines()
        self.sim.load_source(self.source_lines)
        print(f"Wczytano {len(self.source_lines)} linii z {path}")

    def do_save(self, args):
        if not args: raise ValueError("podaj nazwę pliku")
        path = pathlib.Path(args[0]).expanduser()
        path.write_text("\n".join(self.source_lines), encoding="utf-8")
        print(f"Zapisano do {path}")

    def do_list(self, _):
        if not self.source_lines:
            print("(brak wczytanego programu)")
            return
        for i,l in enumerate(self.source_lines,1):
            print(f"{i:3}: {l}")

    def do_edit(self, _):
        print("Tryb edycji – pusta linia zakończy.")
        self.source_lines=[]
        while True:
            ln=input(f"{len(self.source_lines)+1:3}> ")
            if ln=="": break
            self.source_lines.append(ln)
        self.sim.load_source(self.source_lines)

    def do_run(self, _):
        if not self.source_lines: print("Brak programu"); return
        self.sim.reset(); self.sim.load_source(self.source_lines)
        self.sim.run()

    def do_step(self, _):
        if not self.source_lines: print("Brak programu"); return
        if self.sim.pc==0:
            self.sim.reset(); self.sim.load_source(self.source_lines)
        self.sim.step()

    def do_regs(self, _): self.sim.cpu.dump()
    def do_reset(self,_): self.sim.reset(); print("Reset OK")


if __name__ == "__main__":
    Shell().cmdloop()