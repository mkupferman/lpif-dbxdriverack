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
    "--muted/--no-muted",
    is_flag=True,
    help="Apply settings while muted. Restores previous mute states after",
    default=True,
)
@click.option(
    "--reset-unmapped",
    "-r",
    is_flag=True,
    help="Reset unmapped bands to have no processing",
    default=False,
)
@click.option(
    "--crossover/--no-crossover",
    is_flag=True,
    help="Apply crossover filters, gain, and polarity settings",
    default=True,
)
@click.option(
    "--peq/--no-peq",
    is_flag=True,
    help="Apply parametric band-EQ settings",
    default=True,
)
@click.option(
    "--delay/--no-delay",
    is_flag=True,
    help="Apply alignment delay settings",
    default=True,
)
@click.option(
    "--room-eq",
    is_flag=True,
    help="Apply a single LPIF block to the AutoEQ PEQ. Implies --no-crossover, --no-peq, and --no-delay",
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
@click.option(
    "--map-room",
    help="Map DriveRack AutoEQ to this LPIF block name without prompting. Used with --room-eq",
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

        if params["room_eq"]:
            roomMap = None
            if params["map_room"]:
                roomMap = params["map_room"]
            converter.mapRoomEq(roomMap)

            with l2d.ProgressIndicator("Converting LPIF parameters"):
                converter.convert()

            if params["muted"]:
                with l2d.ProgressIndicator("Muting DriveRack"):
                    converter.preMute()

            with l2d.ProgressIndicator("Applying AutoEQ manual EQ"):
                converter.applyRoomEq()

            if params["muted"]:
                with l2d.ProgressIndicator("Restoring DriveRack mute states"):
                    converter.postUnmute()
        else:
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

            if params["muted"]:
                with l2d.ProgressIndicator("Muting DriveRack"):
                    converter.preMute()

            if params["crossover"]:
                with l2d.ProgressIndicator("Applying crossover settings"):
                    converter.applyCrossOver()

            if params["peq"]:
                with l2d.ProgressIndicator("Applying parametric EQ settings"):
                    converter.applyPeq()

            if params["delay"]:
                with l2d.ProgressIndicator("Applying delay settings"):
                    converter.applyDelay()

            if params["muted"]:
                with l2d.ProgressIndicator("Restoring DriveRack mute states"):
                    converter.postUnmute()
