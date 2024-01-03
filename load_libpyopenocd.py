#!/usr/bin/env python3
import ctypes as ct
from pathlib import Path
from typing import Iterable
from enum import IntEnum


class TAPState(IntEnum):
    TAP_INVALID = -1

    TAP_DREXIT2 = 0x0
    TAP_DREXIT1 = 0x1
    TAP_DRSHIFT = 0x2
    TAP_DRPAUSE = 0x3
    TAP_IRSELECT = 0x4
    TAP_DRUPDATE = 0x5
    TAP_DRCAPTURE = 0x6
    TAP_DRSELECT = 0x7
    TAP_IREXIT2 = 0x8
    TAP_IREXIT1 = 0x9
    TAP_IRSHIFT = 0xa
    TAP_IRPAUSE = 0xb
    TAP_IDLE = 0xc
    TAP_IRUPDATE = 0xd
    TAP_IRCAPTURE = 0xe
    TAP_RESET = 0x0f


class OpenOCDError(Exception):
    pass


class CScanField(ct.Structure):
    _fields_ = [
        ("num_bits", ct.c_int),
        ("out_value", ct.c_char_p),
        ("in_value", ct.c_char_p),
        ("check_value", ct.c_char_p),
        ("check_mask", ct.c_char_p),
    ]


def div_round_up(val: int, div: int) -> int:
    return (val + (div - 1)) // div


class ScanField:

    def __init__(self, bitlen: int, out_value: int = None):
        self._bitlen = bitlen
        self._bytelen = div_round_up(bitlen, 8)
        self._in_buf = bytes(self._bytelen)
        self._out_buf = bytes(self._bytelen)

        if out_value is not None:
            self.out_value = out_value

    @property
    def bitlen(self) -> int:
        return self._bitlen

    @property
    def ctype(self) -> CScanField:
        cval = CScanField(
            num_bits=self._bitlen,
            out_value=self._out_buf,
            in_value=self._in_buf,
            check_value=None,
            check_mask=None,
        )
        return cval

    @property
    def in_value(self) -> int:
        return int.from_bytes(self._in_buf, byteorder="little")

    @property
    def out_value(self) -> int:
        return int.from_bytes(self._out_buf, byteorder="little")

    @out_value.setter
    def out_value(self, v: int) -> None:
        self._out_buf = v.to_bytes(self._bytelen, byteorder="little")


JtagTap = ct.POINTER(ct.c_uint)


class PyOpenOCD:

    def __init__(self, lib_path: Path):
        self._lib = self._load_and_prepare(lib_path)
        self._ctx = self._lib.create_command_handler(None)

    def _load_and_prepare(self, path: Path):
        lib = ct.cdll.LoadLibrary(str(path.resolve()))

        lib.create_command_handler.restype = ct.POINTER(ct.c_uint)

        lib.jtag_tap_by_string.restype = ct.POINTER(ct.c_uint)
        lib.jtag_tap_by_string.argtypes = [ct.c_char_p]

        lib.jtag_add_ir_scan.restype = None
        lib.jtag_add_ir_scan.argtypes = [JtagTap, ct.POINTER(CScanField), ct.c_uint]

        lib.jtag_add_dr_scan.restype = None
        lib.jtag_add_dr_scan.argtypes = [JtagTap, ct.c_int, ct.POINTER(CScanField),
                                         ct.c_uint]

        return lib

    def initialize(self, scripts: Iterable[Path]) -> None:
        script_argv = [b"script " + str(p).encode("ascii") + b'\x00' for p in scripts]
        argv = (ct.c_char_p * len(script_argv))(*script_argv)
        r = self._lib.openocd_init(self._ctx, len(argv), argv)

        if r != 0:
            raise OpenOCDError(r)

    def get_jtag_tap(self, name: str) -> JtagTap:
        name_bin = name.encode("ascii")
        tap = self._lib.jtag_tap_by_string(name_bin)

        if not tap:
            raise OpenOCDError(f"TAP {name} could not be found")

        return tap

    def add_irscan(self, tap: JtagTap, field: ScanField,
                   end_state: TAPState = TAPState.TAP_IDLE) -> None:
        self._lib.jtag_add_ir_scan(tap, field.ctype, end_state)

    def add_drscan(self, tap: JtagTap, *fields: ScanField,
                   end_state: TAPState = TAPState.TAP_IDLE):
        ct_fields = [f.ctype for f in fields]
        field_arr = (len(ct_fields) * CScanField)(*ct_fields)

        self._lib.jtag_add_dr_scan(tap, len(field_arr), field_arr, end_state)

    def execute_queue(self) -> None:
        r = self._lib.jtag_execute_queue()
        if r != 0x0:
            raise OpenOCDError(r)

    def close(self):
        self._lib.openocd_deinit(self._ctx)


def main():
    my_dir = Path(__file__).parent
    lib_path = my_dir / "src/.libs/libpyopenocd.so.0.0.0"

    oocd = PyOpenOCD(lib_path)
    oocd.initialize([
        my_dir / "tcl/interface/ftdi/flyswatter2.cfg",
        my_dir / "jtag.cfg",
    ])

    oocd_tap = oocd.get_jtag_tap("auto0.tap")

    field = ScanField(bitlen=4, out_value=0xE)
    oocd.add_irscan(oocd_tap, field)

    idcode_field = ScanField(bitlen=32)
    oocd.add_drscan(oocd_tap, idcode_field)

    oocd.execute_queue()

    print(hex(idcode_field.in_value))

    oocd.close()


if __name__ == "__main__":
    main()
