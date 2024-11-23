#!/usr/bin/env python3

import threading
from typing import Type, Optional, Self
from types import TracebackType

from prompt_toolkit.shortcuts import radiolist_dialog, ProgressBar
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts.progress_bar import formatters

import lpif2dbxdriverack.lpif as lpif
import dbxdriverack as dr
import dbxdriverack.pa2 as pa2
import dbxdriverack.pa2.outputband as ob
import dbxdriverack.pa2.crossover as xo
import dbxdriverack.pa2.peq as peq
import dbxdriverack.pa2.outputdelay as odly


class ProgressIndicator:
    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self) -> Self:
        print(f"{self.label}...", end=" ")
        return self

    def __exit__(
        self,
        type: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        print("done.")


class Timer:
    def __init__(self, seconds: int, label: str = ""):
        self.seconds = seconds
        self.timer = threading.Thread(target=self._timer, daemon=True)
        self.label = label

    def _timer(self) -> None:
        with ProgressBar(
            style=Style.from_dict(
                {
                    "label": "bg:#ffff00 #000000",
                    "percentage": "bg:#ffff00 #000000",
                    "current": "#448844",
                    "bar": "",
                }
            ),
            formatters=[
                formatters.Label(),
                formatters.Text(": [", style="class:percentage"),
                formatters.Percentage(),
                formatters.Text("]", style="class:percentage"),
                formatters.Text(" "),
                formatters.Bar(sym_a="#", sym_b="#", sym_c="."),
                formatters.Text("  "),
            ],
        ) as pb:
            for _ in pb(range(self.seconds * 10), label=self.label):
                threading.Event().wait(0.1)

    def __enter__(self) -> threading.Thread:
        self.timer.start()
        return self.timer

    def __exit__(
        self,
        type: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        while self.timer and self.timer.is_alive():
            self.timer.join(timeout=0.5)


class LpifConverterPa2:
    def __init__(self, drack: pa2.PA2, lpifData: lpif.Lpif) -> None:
        self.drack = drack
        self.lpifData = lpifData
        self.crossover = xo.PA2Crossover()
        self.bandMap: dict[str, lpif.LpifProcessingBlock] = {}

    def _listAvailableBands(self) -> list[str]:
        bands = [ob.BandHigh]
        if self.drack.hasMids():
            bands.append(ob.BandMid)
        if self.drack.hasSubs():
            bands.append(ob.BandLow)
        return bands

    def _allBandMapped(self) -> bool:
        # always a high band
        try:
            self.bandMap[ob.BandHigh]
        except:
            return False

        if self.drack.hasMids():
            try:
                self.bandMap[ob.BandMid]
            except:
                return False

        if self.drack.hasSubs():
            try:
                self.bandMap[ob.BandLow]
            except:
                return False

        return True

    def _mapXoverFilter(self, filter: lpif.LpifCrossover) -> str:
        if filter.type in [lpif.XoverLpBw, lpif.XoverHpBw]:
            if filter.order == 1:
                return xo.XoverBW6
            elif filter.order == 2:
                return xo.XoverBW12
            elif filter.order == 3:
                return xo.XoverBW18
            elif filter.order == 4:
                return xo.XoverBW24
            elif filter.order == 5:
                return xo.XoverBW30
            elif filter.order == 6:
                return xo.XoverBW36
            elif filter.order == 7:
                return xo.XoverBW42
            elif filter.order == 8:
                return xo.XoverBW48
            else:
                raise ValueError(
                    f"Unsupported Butterworth filter order: {filter.order}"
                )

        elif filter.type in [lpif.XoverHpLw, lpif.XoverLpLw]:
            if filter.order == 2:
                return xo.XoverLR12
            elif filter.order == 4:
                return xo.XoverLR24
            elif filter.order == 6:
                return xo.XoverLR36
            elif filter.order == 8:
                return xo.XoverLR48
            else:
                raise ValueError(f"Unsupported Linkfilter order: {filter.order}")
        else:
            raise ValueError(f"Unsupported Linkwitz-Riley filter type: {filter.type}")

    def discover(self, scanTime: int, useFirst: bool = False) -> str:
        with Timer(scanTime, label="Scanning for online DriveRack PA2 units"):
            devices = self.drack.discoverDevices(timeout=scanTime)

        if len(devices) == 0:
            raise Exception("No DriveRack PA2s found")

        deviceList = [(addr, str(device)) for addr, device in devices]

        if len(devices) == 1 and useFirst:
            return deviceList[0][0]

        device = radiolist_dialog(
            title="Choose a DriveRack",
            text="Connect to which DriveRack?",
            values=deviceList,
        ).run()

        return device

    def mapBands(
        self,
        high: Optional[str] = None,
        mid: Optional[str] = None,
        low: Optional[str] = None,
    ) -> dict[str, lpif.LpifProcessingBlock]:
        """
        Map the DriveRack bands (e.g. High, Mid, Low) to the LPIF processing blocks.
        LPIF blocks represent a band's processing, including EQ, delay, and multiple filters.
        """
        unmappedBlocks = [block for block in self.lpifData.processingBlocks.keys()]

        if high is not None and high in unmappedBlocks:
            self.bandMap[ob.BandHigh] = self.lpifData.processingBlocks[high]
            unmappedBlocks.remove(high)

        if mid is not None and mid in unmappedBlocks:
            self.bandMap[ob.BandMid] = self.lpifData.processingBlocks[mid]
            unmappedBlocks.remove(mid)

        if low is not None and low in unmappedBlocks:
            self.bandMap[ob.BandLow] = self.lpifData.processingBlocks[low]
            unmappedBlocks.remove(low)

        for band in self._listAvailableBands():
            if self._allBandMapped() or len(unmappedBlocks) == 0:
                break

            blockName = radiolist_dialog(
                title=f"Map Band: {band}",
                text=f"Map '{self.drack.getName()}' DriveRack {band} band to:",
                values=[(False, "(No band processing)")]
                + [(v, f"'{v}' LPIF block") for v in unmappedBlocks],
            ).run()

            if isinstance(blockName, str):
                self.bandMap[band] = self.lpifData.processingBlocks[blockName]
                unmappedBlocks.remove(blockName)

        return self.bandMap

    def convert(self, resetUnmapped: bool = False) -> None:
        """
        Take the parameters from the LPIF processing blocks and apply them to the DriveRack PA2 model.
        Parametric EQs and delays will be applied at the PA2 band level (H, M, L),
        while high and low-pass filters will be applied within the PA2's crossover block.
        """

        for band, block in self.bandMap.items():

            # PEQ

            ## check if the number of LPIF block filters are within the limits of the DriveRack PA2
            if len(block.iir) > peq.FiltMaxCount:
                raise ValueError(
                    f"Block '{block.name}' has {len(block.iir)} filters. PA2 limit is {peq.FiltMaxCount}"
                )
            if len(block.iir) > 0:
                bandPeq = peq.PA2Peq(enabled=True)

                # apply the block's EQ filters to the band's PEQ
                i = 0
                for peqFilter in block.iir:
                    i += 1

                    # determine the PEQ filter type
                    if peqFilter.type == lpif.EqParametric:
                        filterType = peq.Bell
                    elif peqFilter.type == lpif.EqHighShelf:
                        filterType = peq.HighShelf
                    elif peqFilter.type == lpif.EqLowShelf:
                        filterType = peq.LowShelf
                    else:
                        raise ValueError(
                            f"Block '{block.name}' has an unsupported filter type: {peqFilter.type}"
                        )

                    q = peqFilter.q

                    # determine the Q/slope
                    if peqFilter.type in [lpif.EqHighShelf, lpif.EqLowShelf]:
                        slope = round(lpif.q2slope(q), 1)
                        if not (peq.ShelfMinSlope <= slope <= peq.ShelfMaxSlope):
                            raise ValueError(
                                f"Block '{block.name}' shelf filter {i} (type={peqFilter.type}, gain={peqFilter.gain}, q={q} [slope={slope}]) is out of PA2's slope range"
                            )
                        q = slope

                    bandPeq.addFilter(
                        peq.PA2PeqFilter(
                            filterType, peqFilter.frequency, peqFilter.gain, q
                        ),
                        i,
                    )

                self.drack.setPeq(band, bandPeq, apply=False)

            # DELAY

            bandDelay = odly.PA2OutputDelay()
            bandDelay.setDelay(block.delay)
            if block.delay == 0:
                bandDelay.disable()
            else:
                bandDelay.enable()

            self.drack.setOutputDelay(band, bandDelay, apply=False)

            # CROSSOVER
            blockCrossoverBand = xo.PA2CrossoverBand()
            if block.invert:
                blockCrossoverBand.setPolarity(dr.PolarityInverted)
            else:
                blockCrossoverBand.setPolarity(dr.PolarityNormal)
            blockCrossoverBand.setGain(block.gain)

            if block.lpf is not None:
                lpf = self._mapXoverFilter(block.lpf)
                blockCrossoverBand.setLpfType(lpf)
                blockCrossoverBand.setLpfFreq(block.lpf.frequency)

            if block.hpf is not None:
                hpf = self._mapXoverFilter(block.hpf)
                blockCrossoverBand.setHpfType(hpf)
                blockCrossoverBand.setHpfFreq(block.hpf.frequency)

            if band == ob.BandHigh:
                self.crossover.setHigh(blockCrossoverBand)
            elif band == ob.BandMid:
                self.crossover.setMid(blockCrossoverBand)
            elif band == ob.BandLow:
                self.crossover.setLow(blockCrossoverBand)

        if resetUnmapped:
            for band in [ob.BandHigh, ob.BandMid, ob.BandLow]:
                if band not in self.bandMap:
                    emptyPeq = peq.PA2Peq(enabled=False)
                    emptyDelay = odly.PA2OutputDelay()
                    emptyCrossoverBand = xo.PA2CrossoverBand()

                    if band == ob.BandHigh:
                        self.crossover.setHigh(emptyCrossoverBand)
                    if band == ob.BandMid:
                        if not self.drack.hasMids():
                            continue
                        self.crossover.setMid(emptyCrossoverBand)
                    if band == ob.BandLow:
                        if not self.drack.hasSubs():
                            continue
                        self.crossover.setLow(emptyCrossoverBand)

                    self.drack.setPeq(band, emptyPeq, apply=False)
                    self.drack.setOutputDelay(band, emptyDelay, apply=False)

        self.drack.setCrossover(self.crossover, apply=False)

    def preMute(self) -> None:
        """
        Mute all bands before applying settings. Store settings to restore after.
        """
        self.drack.bulkMute(dr.CmdMuteAll, updateState=False)

    def postUnmute(self) -> None:
        """
        Restore mute states after applying settings.
        """
        self.drack.bulkMute(dr.CmdMuteRestore)

    def applyPeq(self) -> None:
        self.drack.applyPeqs()

    def applyDelay(self) -> None:
        self.drack.applyOutputDelays()

    def applyCrossOver(self) -> None:
        self.drack.applyCrossover()
