#!/usr/bin/env python3

"""
Parse Loudspeaker Processor Interchange Format (LPIF) format.
https://eclipseaudio.com/lpif/
Opinionated for the dbx DriveRack.
"""

import json
from typing import Type, Optional, TextIO, Self

from types import TracebackType
from collections import Counter

# Constants
BlockTypeEq = "eq"
BlockTypeInput = "input"
BlockTypeOutputA = "output-a"
BlockTypeOutputB = "output-b"
PlatformGeneric = "generic"
EqParametric = "parametric"
EqHighShelf = "high-shelf"
EqLowShelf = "low-shelf"
XoverLpBw = "lowpass-butterworth"
XoverLpLw = "lowpass-lr"
XoverHpBw = "highpass-butterworth"
XoverHpLw = "highpass-lr"


class LpifPeq:
    def __init__(
        self,
        type: str,
        frequency: float,
        gain: float,
        q: float,
    ) -> None:

        # self.type = type

        self.type = type
        self.frequency = frequency
        self.gain = gain
        self.q = q

    def __str__(self) -> str:
        return f"LPIF PEQ {self.type} {self.frequency}Hz {self.gain}dB {self.q}"


class LpifCrossover:
    def __init__(
        self,
        frequency: float,
        type: str,
        order: int,
    ) -> None:
        self.frequency = frequency
        self.type = type
        self.order = order

    def __str__(self) -> str:
        return f"LPIF XOver {self.type} {self.frequency} {self.order}"


class LpifProcessingBlock:
    def __init__(self, name: str) -> None:
        pass
        self.name = name
        self.gain: float = 0.0
        self.delay: float = 0.0
        self.invert: bool = False
        self.type: str = "undefined"
        self.hpf: Optional[LpifCrossover] = None
        self.lpf: Optional[LpifCrossover] = None
        self.iir: list[LpifPeq] = []

    def __str__(self) -> str:
        return f"LPIF Block: {self.name} Gain: {self.gain} Delay: {self.delay} Invert: {self.invert}"


class Lpif:
    def __init__(self) -> None:
        self.presetTitle = None
        self.processingBlocks: dict[str, LpifProcessingBlock] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        type: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        pass

    def loadFile(self, filename: str) -> None:
        with open(filename, "r") as f:
            self.data = json.load(f)

        self.parse()

    def loadHandle(self, handle: TextIO) -> None:
        self.data = json.load(handle)

        self.parse()

    def loadString(self, string: str) -> None:
        self.data = json.loads(string)

        self.parse()

    def parse(self) -> None:
        try:
            self.data["preset"]
        except KeyError:
            raise ValueError("Missing 'preset' key in LPIF data")
        preset = self.data["preset"]

        if "title" in preset:
            self.presetTitle = preset["title"]
        else:
            self.title = "Untitled"

        if "processing-blocks" not in preset:
            raise ValueError("No processing-blocks specified in LPIF preset data")
        processingBlocks = preset["processing-blocks"]

        # determine if there are any EQ blocks with the same name
        eqCounts = Counter(
            b["channel-name"]
            for b in processingBlocks
            if "channel-name" in b and b["type"] == BlockTypeEq
        )
        if any(c > 1 for c in eqCounts.values()):
            raise ValueError("Multiple EQ blocks with the same name")

        # TODO: ensure there is only one HPF or LPF per block

        # create processing blocks
        self.processingBlocks = {}
        for block in processingBlocks:
            if block["type"] == BlockTypeEq and "channel-name" in block:
                blk = LpifProcessingBlock(block["channel-name"])
                blk.type = block["type"]

                if "gain" in block:
                    blk.gain = block["gain"]
                if "delay" in block:
                    blk.delay = block["delay"]
                if "invert" in block:
                    blk.invert = block["invert"]

                if "iir" in block:
                    for iir in block["iir"]:
                        if "enable" in iir and not iir["enable"]:
                            continue
                        if "platform" not in iir or iir["platform"] != PlatformGeneric:
                            continue
                        if "type" not in iir or iir["type"] not in [
                            EqParametric,
                            EqHighShelf,
                            EqLowShelf,
                            XoverLpBw,
                            XoverLpLw,
                            XoverHpBw,
                            XoverHpLw,
                        ]:
                            continue
                        if iir["type"] in [XoverLpBw, XoverLpLw, XoverHpBw, XoverHpLw]:
                            if "frequency" not in iir or "order" not in iir:
                                continue

                            if (
                                iir["type"] in [XoverLpLw, XoverHpLw]
                                and int(iir["order"]) % 2 != 0
                            ):
                                raise ValueError(
                                    "Linkwitz-Riley crossover order must be even"
                                )

                            xover = LpifCrossover(
                                iir["frequency"], iir["type"], iir["order"]
                            )

                            if iir["type"] in [XoverLpBw, XoverLpLw]:
                                blk.lpf = xover
                            else:
                                blk.hpf = xover

                        elif iir["type"] in [EqParametric, EqHighShelf, EqLowShelf]:
                            if (
                                "frequency" not in iir
                                or not ("q" in iir or "bandwidth" in iir)
                                or "gain" not in iir
                            ):
                                continue

                            if "bandwidth" in iir:
                                q = bw2q(iir["bandwidth"])
                            else:
                                q = iir["q"]

                            peq = LpifPeq(
                                type=iir["type"],
                                frequency=iir["frequency"],
                                gain=iir["gain"],
                                q=q,
                            )
                            blk.iir.append(peq)

                self.processingBlocks[blk.name] = blk


def bw2q(bw: float) -> float:
    """
    Convert bandwidth to Q factor (approx.)
    """
    return float(1.3767 * bw**-1.023)


def q2slope(q: float) -> float:
    """
    Convert shelving Q factor to PA2 slope (approx.)
    """
    return float(12.304 * q**1.9316)
