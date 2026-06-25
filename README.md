# acoustic_modem
ACOUSTIC FINITE GEOMETRY TRANSPORT LAYER (AFGTL)
================================================

An acoustic covert channel modem built using projective planes, Steiner
systems, and block codes. Transmits data through air-gapped systems using
ultrasonic FSK modulation with selectable error-correcting codes.


DEPENDENCIES
------------

Python 3.9+
numpy
scipy


USAGE
-----

Transmit a string:

    python acoustic_modem_aux.py tx -q 5 --ecc sqs16 "HELLO" -o transmit.wav

Transmit a file:

    python acoustic_modem_aux.py tx -q 5 --ecc sqs16 -f payload.txt -o transmit.wav

Receive via microphone:

    python acoustic_modem_aux.py rx -q 5 --ecc sqs16 -i MIC -d 30

Receive via pre-recorded WAV file:

    python acoustic_modem_aux.py rx -q 5 --ecc sqs16 -i captured.wav


## OPTIONS

* **`-q`**
    Singer plane order (2, 3, 5, or 7). Default: 5

* **`--ecc`**
    Error-correcting code. Choices:
    * `hamming` [7,4,3] (baseline)
    * `selfdual` [8,4,4] (detects double errors)
    * `qr` [7,3,4] (strong distance for rate)
    * `pg23` [13,9,3] (high rate, projective plane)
    * `sts9` [9,5,3] (compact, affine design)
    * `sts15` [15,11,3] (high density, PG(3,2))
    * `sqs16` [16,11,4] (flagship, best overall balance). 
    *Default: sqs16*

* **`--extended`**
    Use 16-bit header for payloads larger than 255 bytes

* **`-o`**
    Output WAV filename (tx only). Default: transmit.wav

* **`-i`**
    Input source (rx only). "MIC" for live recording, or a WAV path

* **`-d`**
    Recording duration in seconds (rx only). Default: 25


QUICK TEST
----------

Open two terminals on the same machine, or use two devices. On the
transmitter:

    python acoustic_modem_aux.py tx -q 5 --ecc hamming "TEST MESSAGE"

Play the resulting transmit.wav through speakers. On the receiver:

    python acoustic_modem_aux.py rx -q 5 --ecc hamming -i MIC -d 30

Press Enter, then immediately play the audio. A successful decode prints
the message to stdout with a CRC32 confirmation to stderr.


HOW IT WORKS
------------

The modem uses a Singer difference set to construct a preamble with a
sharp autocorrelation peak. The receiver slides a local copy of the
preamble across incoming audio and locks onto the correlation spike.

Payload data is protected by a selectable error-correcting code derived
from a t-design or finite geometry. Each code lives in its own engine
class with a uniform string_to_bits() / bits_to_string() interface.

Bits are modulated with 4-ary FSK at 17-18.5 kHz. A PI tracking loop
corrects for clock drift between the transmitter and receiver sound
cards. Encryption is a simple XOR cipher with a repeating key. Integrity
is verified with CRC32.


HARDWARE NOTES
--------------

Most laptop speakers and smartphone microphones handle 17-18.5 kHz
without issue. The signal is inaudible to most adults. For best results
at range, keep the transmitter volume high but not clipping, and place
the receiver microphone with a clear line of sight to the speaker.


PORTABLE DEPLOYMENT
-------------------

To run on a locked-down Windows workstation that blocks installers:

    python -m venv --copies portable_env
    portable_env/bin/pip install numpy scipy
    cp acoustic_modem_aux.py portable_env/
    zip -9 -r portable.zip portable_env/

Transfer the zip (split into pieces if needed due to email limits) and
extract on the target machine. Run with:

    .\python acoustic_modem_aux.py tx -q 5 --ecc sqs16 "HELLO"
