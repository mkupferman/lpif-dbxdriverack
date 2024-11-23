# LPIF to dbx DriveRack converter/applicator

This command-based application takes a
[Loudspeaker Processor Interchange Format](https://eclipseaudio.com/lpif/)
(LPIF) file, containing audio filters for bands of a loudspeaker system, and
applies these to a networked dbx DriveRack&reg; loudspeaker management device.

Presently, only the [DriveRack PA2](https://dbxpro.com/en-US/products/driverack-pa2)
model is supported.

## Requirements

* Python (>= 3.11)
* A compatible DriveRack hardware unit:

  * DriveRack PA2 (firmware version 1.2.0.1)

* Network connectivity between this client and the device.

* A properly-formatted LPIF file with at least one labeled processing block
and DriveRack-compatible filters.

## Quick start

```shell
pip install lpif2dbxdriverack

lpif2dbxdriverack /path/to/file.lpif
```

### DriveRack compatibility

While this software was designed for use with
[Smaart&reg; Data Modeler](https://www.rationalacoustics.com/products/smaart-data-modeler),
any LPIF file generated with correct parameters should be compatible. The
guidelines given here however are based on experience with Smaart Data Modeler.

#### Compatible filters & parameters

When using Smaart Data Modeler, selecting the *Generic* filter reference mode
will allow any type of filter to be used. Any processing block attributes
other than those that follow will be ignored. Automatic converstion is done
between Q and bandwidth units, so either can be used.

##### Block ("DSP channel") attributes

* Polarity (applied in the DriveRack crossover section)
* Level (applied in the DriveRack crossover section)
* Delay

##### EQ filters

* Up to 8 filters per DriveRack output band
* Gain between -20 and 20 dB
* Frequency between 20 Hz and 22 kHz
* High & low shelf BW roughly up to 2.7 (or Q down to 0.5)
* Parametric Q between 0.1 and 16 (or BW roughly between 12 and 0.1)

##### Crossover filters

* One high-pass and one low-pass filter per DriveRack output band

  * Crossover filters are mandatory in the DriveRack so if none are specified,
    the DriveRack will be set to use a Butterworth 6dB/oct filter set at the
    maximum or minimum ("Out") frequency.

* Linkwitz-Riley 12, 24, 36, and 48 dB/octave (even ordered 2-8) filters
* Butterworth 6, 12, 18, 24, 30, 36, 42, and 48 dB/octave (order 1-8) filters

## Command usage & behavior

```plaintext
Usage: lpif2dbxdriverack [OPTIONS] LPIF_FILE
```

### Options

* `--model` - The DriveRack model to connect to. Currently only `pa2` is
  supported so this may be left out.
* `--connect-single` - When using the discovery feature, and only one
  DriveRack is found, connect to it without prompting.
* `--address` - The IP address or hostname of the DriveRack PA2 to connect to. If
  this is provided, the discovery feature is bypassed.
* `--scan-time` - The number of seconds to wait for devices to respond after a
  discovery scan is initiated. The default is 5 seconds.
* `-m`, `--while-muted` - This will temporarily mute the DriveRack outputs
  while applying the settings, then restore the previous mute states after, to
  potentially avoid unwanted noise during adjustment.
* `-r`, `--reset-unmapped` - Normally, any bands that are not mapped to a
  DriveRack output will be left alone. This option will reset any unmapped
  bands to have no processing.
* `--map-high`, `--map-mid`, `--map-low` - Normally, an interactive prompt
  will ask you to map each DriveRack output to an LPIF block. If you know in
  advance what the name of the LPIF block is, you can use these options to
  specify which DriveRack band should be mapped and bypass the prompt.

## Contributing

Any DriveRack PA2 users are encouraged to test this module and provide
bug reports or code contributions. I am seeking anyone with other
DriveRack models (such as the VENU360) to help develop support for
this and other devices.

## Acknowledgements

Loudspeaker Processor Interchange Format (LPIF) is a trademark of
Eclipse Audio Pty Ltd.

Smaart&reg; and Smaart&reg; Data Modeler are trademarks of
Rational Acoustics LLC.

dbx, DriveRack&reg;, and other brand names are trademarks of
Harman International Industries, Inc., a subsidiary of
Samsung Electronics Co., Ltd.

This project is not affiliated with or endorsed by any of these companies,
and the use of their trademarks is for identification purposes only.
