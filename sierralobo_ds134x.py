""" 

* Author: Caden Hillis
"""

from time import struct_time, mktime, localtime
from micropython import const
from adafruit_bus_device.spi_device import SPIDevice

try:
    from typing import Union
    from busio import SPI
    from digitalio import DigitialInOut
except ImportError:
    pass

_S_REG = const(0x0)
_CTRL_REG = const(0x0F)

_BUFFER = bytearray(8)


class DS1343:
    """device class for SPI-based RTC DS1343"""

    def __init__(self, spi: SPI, cs_pin: DigitialInOut):
        self._spi = spi
        self._cs = cs_pin
        self._device = SPIDevice(
            self._spi, self._cs, cs_active_value=True, polarity=1, phase=1
        )

        # allow battery backup
        ctrl = self._read_u8(_CTRL_REG)
        self._write_u8(_CTRL_REG, ctrl & 0x7F)

    @property
    def time(self) -> int:
        """time in seconds since epoch (Jan 1, 1970)"""
        return mktime(self.datetime)

    @property
    def datetime(self) -> struct_time:
        """The current date and time of the RTC as a time.struct_time."""
        self._read_into(_S_REG, _BUFFER, 7)
        tsec = _bcd_to_int(_BUFFER[0])
        tmin = _bcd_to_int(_BUFFER[1])
        thr = _bcd_to_int(_BUFFER[2])
        dwd = _BUFFER[3] & 0x7
        dmd = _bcd_to_int(_BUFFER[4])
        dym = _bcd_to_int(_BUFFER[5])
        y = _bcd_to_int(_BUFFER[6]) + 2000
        return struct_time([y, dym, dmd, thr, tmin, tsec, dwd, -1, -1])

    @datetime.setter
    def datetime(self, set_time: Union[struct_time, int] = None) -> None:
        """set the RTC's date and time of the as a
        input time.struct_time or an int (sec since J1, 1970)"""
        if set_time is not None:
            if isinstance(set, struct_time):
                time_struct = set_time
            else:
                time_struct = localtime(set_time)
        else:
            time_struct = localtime(0)

        # print("setting time...", str(time_struct))

        tsec = _int_to_bcd(time_struct.tm_sec) & 0x7F
        self._write_u8(0x00, tsec)
        # print(f"sec: wr {tsec}, rb {self._read_u8(0x00)}")

        tmn = _int_to_bcd(time_struct.tm_min) & 0x7F
        self._write_u8(0x01, tmn)
        # print(f"min: wr {tmn}, rb {self._read_u8(0x01)}")

        thr = _int_to_bcd(time_struct.tm_hour) & 0x3F
        self._write_u8(0x02, thr)
        # print(f"hr: wr {thr}, rb {self._read_u8(0x02)}")

        dwd = time_struct.tm_wday & 0x3
        self._write_u8(0x03, dwd)
        # print(f"wd: wr {dwd}, rb {self._read_u8(0x03)}")

        dmd = _int_to_bcd(time_struct.tm_mday) & 0x3F
        self._write_u8(0x04, dmd)
        # print(f"md: wr {dmd}, rb {self._read_u8(0x04)}")

        dym = _int_to_bcd(time_struct.tm_mon) & 0x1F
        self._write_u8(0x05, dym)
        # print(f"ym: wr {dym}, rb {self._read_u8(0x05)}")

        y = _int_to_bcd(time_struct.tm_year - 2000) & 0xFF
        self._write_u8(0x06, y)
        # print(f"y: wr {y}, rb {self._read_u8(0x06)}")

        # clear OSF bit to indicate time is valid
        stat = self._read_u8(0x10)
        self._write_u8(0x10, stat & 0x7F)

    @property
    def valid(self) -> bool:
        "if time if valid (oscillator has stopped at some point since last set time)"
        return not (self._read_u8(0x10) & 0x80) == 0x80

    def _read_into(self, address, buf, length=None):
        # Read a number of bytes from the specified address into the provided
        # buffer.  If length is not specified (the default) the entire buffer
        # will be filled.
        if length is None:
            length = len(buf)
        with self._device as device:
            _BUFFER[0] = address & 0x7F  # Strip out top bit to set 0
            # value (read).
            device.write(_BUFFER, end=1)
            device.readinto(buf, end=length)

    def _read_u8(self, address):
        # Read a single byte from the provided address and return it.
        self._read_into(address, _BUFFER, length=1)
        return _BUFFER[0]

    def _write_from(self, address, buf, length=None):
        # Write a number of bytes to the provided address and taken from the
        # provided buffer.  If no length is specified (the default) the entire
        # buffer is written.
        if length is None:
            length = len(buf)
        with self._device as device:
            _BUFFER[0] = (address | 0x80) & 0xFF  # Set top bit to 1 to
            # indicate a write.
            device.write(_BUFFER, end=1)
            device.write(buf, end=length)

    def _write_u8(self, address, val):
        # Write a byte register to the chip.  Specify the 7-bit address and the
        # 8-bit value to write to that address.
        with self._device as device:
            _BUFFER[0] = (address | 0x80) & 0xFF  # Set top bit to 1 to
            # indicate a write.
            _BUFFER[1] = val & 0xFF
            device.write(_BUFFER, end=2)


def _bcd_to_int(val: int) -> int:
    tens = (val & 0xF0) >> 4
    ones = val & 0x0F
    return (tens * 10) + ones


def _int_to_bcd(val: int) -> int:
    if not isinstance(val, int):
        val = int(val)
    thou = val // 1000
    hund = val // 100
    tens = val // 10
    ones = val % 10
    return (
        ((thou & 0x0F) << 0x12)
        | ((hund & 0x0F) << 0x8)
        | ((tens & 0x0F) << 0x4)
        | (ones & 0x0F)
    )
