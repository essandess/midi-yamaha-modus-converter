# midi-yamaha-modus-converter
Convert MIDI files for compatibility with a Yamaha Modus Piano

This repo contains a python script [midi_yamaha_modus_convert.py](./midi_yamaha_modus_convert.py)
that converts MIDI files for compatibility with Yamaha's Modus and Clavinova digital pianos.

It has been tested on Disklavier MIDI files from Yamaha's
[Yamaha's Disklavier Education Network](http://yamahaden.com/midi-files) (DEN), and from MIDI's transcribed
from `.wav` recordings using [Magenta](https://magenta.tensorflow.org/) trained on the
[MAESTRO](https://magenta.tensorflow.org/datasets/maestro) dataset, itself built using
these DEN MIDI's.

Example MIDI's transcribed from Glenn Gould performances of Bach's Goldberg Variations (1981)
and the Well-Tempered Clavier are included in the subdirectory [gould_bach](./gould_bach).

###### Fugue No. 20 in A minor, BWV 865
*Transcribed using [Magenta](https://github.com/magenta/magenta/tree/master/magenta/models/onsets_frames_transcription) v2.1.0; MAESTRO model pre-trained [checkpoint](https://storage.googleapis.com/magentadata/models/onsets_frames_transcription/maestro_checkpoint.zip)*

![Bach - Glenn Gould, The Well-Tempered Clavier, Fugue No. 20 in A minor, BWV 865](./Bach - Glenn Gould, The Well-Tempered Clavier, Fugue No 20 in A minor, BWV 865.png)
