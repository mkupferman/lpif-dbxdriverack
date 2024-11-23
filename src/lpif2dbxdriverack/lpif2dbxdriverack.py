#!/usr/bin/env python3

import click
from typing import Any

import lpif2dbxdriverack.lpif as lpif
import dbxdriverack.pa2 as pa2
import lpif2dbxdriverack as l2d
import sys


@click.command()
@click.argument("lpif_file", type=click.File("r"))
@click.option("--model", type=click.Choice(["pa2"]), default="pa2", required=True)
@click.option(
    "--connect-single",
    is_flag=True,
    help="When exactly 1 DriveRack discovered, connect to it without prompting",
    default=False,
)
@click.option(
    "--address",
    help="IP/host address of the DriveRack PA2. Bypasses discovery scanning",
)
@click.option(
    "--scan-time",
    type=click.INT,
    default=5,
    help="Seconds to scan for DriveRack PA2 devices",
)
@click.option(
    "--while-muted",
    "-m",
    is_flag=True,
    help="Apply settings while muted. Restores previous mute states after",
    default=False,
)
@click.option(
    "--reset-unmapped",
    "-r",
    is_flag=True,
    help="Reset unmapped bands to have no processing",
    default=False,
)
@click.option(
    "--map-high",
    help="Map DriveRack high output to this LPIF block name without prompting",
)
@click.option(
    "--map-mid",
    help="Map DriveRack mid output to this LPIF block name without prompting",
)
@click.option(
    "--map-low",
    help="Map DriveRack low output to this LPIF block name without prompting",
)
def lpif2dbxdriverack(**params: Any) -> None:
    """
    Sends compatible Loudspeaker Processor Interchange Format (LPIF)
    file parameters to supported dbx DriveRack loudspeaker management systems
    """

    lpifFile = params["lpif_file"]
    lpifData = lpif.Lpif()
    lpifData.loadHandle(lpifFile)

    with pa2.PA2() as drack:
        converter = l2d.LpifConverterPa2(drack, lpifData)
        if params["address"]:
            address = params["address"]
        else:
            address = converter.discover(
                params["scan_time"], useFirst=params["connect_single"]
            )
        if address is None:
            sys.exit("Aborting")
        drack.connect(address)

        highMap = None
        midMap = None
        lowMap = None
        if params["map_high"]:
            highMap = params["map_high"]
        if params["map_mid"]:
            midMap = params["map_mid"]
        if params["map_low"]:
            lowMap = params["map_low"]

        if params["reset_unmapped"]:
            resetUnmapped = True
        else:
            resetUnmapped = False

        converter.mapBands(high=highMap, mid=midMap, low=lowMap)

        with l2d.ProgressIndicator("Converting LPIF parameters"):
            converter.convert(resetUnmapped=resetUnmapped)

        if params["while_muted"]:
            with l2d.ProgressIndicator("Muting DriveRack"):
                converter.preMute()

        with l2d.ProgressIndicator("Applying crossover settings"):
            converter.applyCrossOver()

        with l2d.ProgressIndicator("Applying parametric EQ settings"):
            converter.applyPeq()

        with l2d.ProgressIndicator("Applying delay settings"):
            converter.applyDelay()

        if params["while_muted"]:
            with l2d.ProgressIndicator("Restoring DriveRack mute states"):
                converter.postUnmute()
