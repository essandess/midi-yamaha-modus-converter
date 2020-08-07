#!/usr/bin/env python3

# Convert MIDI files for compatibility with a Yamaha Modus Piano

# Emphasis on MIDI's transcribed using Magenta, and from
# Yamaha's Disklavier Education Network, http://yamahaden.com/midi-files

# Copyright 2020 Steven T. Smith <steve dot t dot smith at gmail dot com>, GPL

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__version__ = '0.1'

import argparse as ap, dataclasses as dc, mido, os, re, sys
import multiprocessing as mp, multiprocessing.pool as mppool

midi_re: re.Pattern = re.compile(r'^(.+)(\.midi?)$',re.IGNORECASE)
suffix_default = '_modus'

# Yamaha Clavinova / Modus F, H MIDI format
# https://usa.yamaha.com/files/download/other_assets/4/335434/f11_en_de_fr_es_dl_a0_v100.pdf

@dc.dataclass
class YamahaModusMIDI:
    """Adapted from the Yamaha Modus F11, F01 Data List,

    https://usa.yamaha.com/files/download/other_assets/4/335434/f11_en_de_fr_es_dl_a0_v100.pdf

    Notes:

    Yamaha Modus MIDI filenames must be less than 32 [perhaps] characters,
    excluding a .MID extension.

    Workflow:

        # Yamaha DEN MIDIs
        ~/bin/midi_yamaha_modus_convert.py ./midi-files
        find midi-files -type f -iname '*_modus.mid' -exec mv {} midi-files-modus ';'
        find midi-files-modus -type f -iname '*_modus.mid' | while read -r; do FNAME=$(echo "${REPLY}" | sed 's|^midi-files-modus/||' | sed -E -e 's|[[:space:]]+||g' | sed -E -e 's|:|_|g' | sed -E -e 's/(.+)_([[:digit:]]+)_([[:alnum:]]+)_modus(\.(mid|MID))$/\3_\1\4/' | sed -E -e 's/(.{1,30}).*(\.(mid|MID))/\1\2/' | iconv -c -f UTF-8 -t ASCII); mv "${REPLY}" midi-files-modus/"${FNAME}"; done

        # Magenta MIDIs
        find . -type f -name 'Johann Sebastian Bach, Goldberg Variations *_modus.midi' | while read -r; do FNAME=$(echo "${REPLY##*/}" | sed -E -e 's|Johann Sebastian Bach, Goldberg Variations (.+)(\.midi)|Gould_Bach_GV_\1.mid|g' | sed 's|:|_|g' | sed -E -e 's|_modus||' | sed -E -e 's|[[:space:]]+||g' | sed -E -e 's/\.([^m]|m[^i]|mi[^d])/\1/g' | sed -E -e 's|,||g' | sed -E -e 's|(.{1,30}).*(\.mid)|\1\2|' | iconv -c -f UTF-8 -t ASCII); cp "${REPLY}" ~/"Source/Yamaha MusicSoft/magenta/gould_bach/${FNAME}"; done

        # Yamaha compatible USB
        find ./midi-files-modus -type f -iname '*.mid' | perl -MList::Util=shuffle -wne 'print shuffle <>;' | head -990 | xargs -I{} cp {} /Volumes/USB
    """

    range15: set = dc.field(default_factory=lambda: {k for k in range(0,16)})
    range127: set = dc.field(default_factory=lambda: {k for k in range(0,128)})
    f7_hex = int('f7',16)

    # page 9
    program_change: set = dc.field(default_factory=lambda: {0,1,4,5,6,11,16,19,24,32,33,48,49,88,})
    # page 10
    control_change: dict = dc.field(default_factory=lambda: {
        0: {0,8,64,118,119,120,121,126,127,},
        120: {0,},
        121: {0,},
        122: {0,127,},
        123: {0,},
        124: {0,},
        125: {0,},
        126: {k for k in range(0,17)},
        127: {0,},
    })
    pitchwheel: bool = True
    # pages 18-21, 25
    sysex_master_volume: str = 'F0 7F 7F 04 01 7F F7'
    sysex_master_fine_tuning: str = 'F0 7F 7F 04 03 7F 7F F7'
    sysex_master_coarse_tuning: str = 'F0 7F 7F 04 04 00 7F F7'
    sysex_reverb_parameter: str = 'F0 7F 7F 04 05 01 01 01 01 02 7F'
    sysex_chorus_parameter: str = 'F0 7F 7F 09 01 0F 7F'
    sysex_channel_pressure: str = 'F0 7F 7F 09 03 0F'
    sysex_controller: str = 'F0 7F 7F 0A 01 0F 7F'
    sysex_key_based_instrument: str = 'F0 7E 7F 09 01 F7'
    sysex_gm1_system_on: str = 'F0 7E 7F 09 01 F7'
    sysex_gm2_system_on: str = 'F0 7E 7F 09 03 F7'
    sysex_general_midi_system_off: str = 'F0 7E 7F 09 02 F7'
    sysex_scale_octave_tuning : str = 'F0 7E 7F 08 08'
    sysex_internal_clock: str = 'F0 43 73 01 02 F7'
    sysex_external_clock: str = 'F0 43 73 01 03 F7'
    sysex_string_resonance_depth: str = 'F0 43 73 01 50 11 0F 02 3F F7'
    sysex_sustain_sample_depth: str = 'F0 43 73 01 50 11 0F 03 3F F7'
    sysex_key_off_sampling_depth: str = 'F0 43 73 01 50 11 0F 04 3F F7'
    sysex_soft_pedal_depth: str = 'F0 43 73 01 50 11 0F 05 3F F7'
    sysex_midi_master_tuning: str = 'F0 43 1F 27 30 00 00 0F 0F 7F F7'
    sysex_panel_data_transmit: str = 'F0 43 0F 7C'
    sysex_universal_realtime_message: str = 'F0 7F 7F 04 01 7F 7F F7'
    sysex_general_midi_mode_on: str = 'F0 7E 7F 09 01 F7'
    sysex_xg_native_parameter_change: str = 'F0 43 1F 4C 7F 7F 7F 7F F7'
    sysex_xg_native_bulk_data: str = 'F0 43 0F 4C 7F 7F 7F 7F 7F'

    # modus initial tempo messages
    modus_initial_tempo_messages: list = dc.field(default_factory=lambda: [
        mido.midifiles.meta.MetaMessage(type='set_tempo', tempo=600000, time=0),
        mido.midifiles.meta.MetaMessage(type='time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0),
    ])

    tempo_and_time_signature_types: set = dc.field(default_factory=lambda: {
        'set_tempo',
        'time_signature',
    })

    control_and_program_change_types: set = dc.field(default_factory=lambda: {
        'control_change',
        'program_change',
    })

    control_and_program_change_and_sysex_types: set = dc.field(default_factory=lambda: {
        'control_change',
        'program_change',
        'sysex',
    })

    copyright = None

    # modus sequencer_specific messages
    modus_sequencer_specific: list = dc.field(default_factory=lambda: [
        mido.midifiles.meta.MetaMessage(type='sequencer_specific',data=(67, 123, 0, 88, 70, 48, 50, 0, 27),time=0),
        mido.midifiles.meta.MetaMessage(type='sequencer_specific',data=(67, 113, 0, 1, 0, 1, 0),time=0),
        mido.midifiles.meta.MetaMessage(type='sequencer_specific',data=(67, 113, 0, 0, 0, 65),time=0),
        mido.midifiles.meta.MetaMessage(type='sequencer_specific',data=(67, 123, 12, 1, 0),time=0)
    ])

    # modus control and program changes
    modus_control_and_program_changes: list = dc.field(default_factory=lambda: [
        mido.Message(type='control_change', channel=0, control=0, value=0, time=960),
        mido.Message(type='control_change', channel=0, control=32, value=0, time=10),
        mido.Message(type='program_change', channel=0, program=0, time=10),
        mido.Message(type='control_change', channel=0, control=7, value=127, time=10),
        mido.Message(type='control_change', channel=0, control=11, value=127, time=10),
        mido.Message(type='control_change', channel=0, control=10, value=64, time=10),
        mido.Message(type='control_change', channel=0, control=91, value=22, time=10),
        mido.Message(type='control_change', channel=0, control=93, value=0, time=10),
    ])

    # modus header omit these messages from the original
    modus_omit_header_messages: set = dc.field(default_factory=lambda: {
        'sequencer_specific',
    })
    
    def __post_init__(self):
        self.zerox_re: re.Pattern = re.compile(r'^0x')
        self.note_re: re.Pattern = re.compile(r'^note_(?:on|off)')
        self.sysex_terminator_byte: int = self.f7_hex

        # page 9
        self.note: set = self.range127
        self.note_off: set = self.range127
        self.note_on: set = self.range127
        self.velocity: set = self.range127
        self.aftertouch: set = self.range15
        self.polytouch: set = self.range127

        # page 10
        self.control_change.update({k: self.range127 for k in [1,5,6,7,10,11,32,38,64,65,66,67,71,72,73,74,75,76,77,78,84,91,93,94,96,97,98,99,100,101,]})

        # check the 0 fields of all these bytes
        self.sysex_byte_masks: list = [[int(x,16) for x in l.split()] for l in [
            self.sysex_master_volume,
            self.sysex_master_fine_tuning,
            self.sysex_master_coarse_tuning,
            self.sysex_reverb_parameter,
            self.sysex_chorus_parameter,
            self.sysex_channel_pressure,
            self.sysex_controller,
            self.sysex_key_based_instrument,
            self.sysex_general_midi_system_off,
            self.sysex_scale_octave_tuning ,
            self.sysex_internal_clock,
            self.sysex_external_clock,
            self.sysex_string_resonance_depth,
            self.sysex_sustain_sample_depth,
            self.sysex_key_off_sampling_depth,
            self.sysex_soft_pedal_depth,
            self.sysex_midi_master_tuning,
            self.sysex_panel_data_transmit,
            self.sysex_universal_realtime_message,
            self.sysex_general_midi_mode_on,
            self.sysex_xg_native_bulk_data,
        ]]
        self.sysex_add_by_hand_byte_masks: list = [[int(x,16) for x in l.split()] for l in [
            self.sysex_gm1_system_on,
            self.sysex_gm2_system_on,
            self.sysex_xg_native_parameter_change,
        ]]

    def message_from_str(self, data_str: str, type: str='sysex', data_start: int=1, data_end: int=-1, time:int=0) -> mido.messages.messages.Message:
        return mido.Message(type=type, data=tuple(int(x,16) for x in data_str.split()[data_start:data_end]),time=time)

    def gm_system_on_exists(self, track: mido.midifiles.tracks.MidiTrack) -> bool:
        return any([self.data_in_byte_masks(m.bytes(), self.sysex_add_by_hand_byte_masks) for m in track if m.type == 'sysex'])

    def is_valid_message(self, msg):
        valid_flag = False
        if msg.is_meta:
            if msg.type == 'sequence_number':
                valid_flag = True
            elif msg.type == 'text':
                valid_flag = True
            elif msg.type == 'copyright':
                valid_flag = True
            elif msg.type == 'track_name':
                valid_flag = True
            elif msg.type == 'instrument_name':
                valid_flag = True
            elif msg.type == 'lyrics':
                valid_flag = True
            elif msg.type == 'marker':
                valid_flag = True
            elif msg.type == 'cue_marker':
                valid_flag = False
            elif msg.type == 'device_name':
                valid_flag = True
            elif msg.type == 'channel_prefix':
                valid_flag = True
            elif msg.type == 'midi_port':
                valid_flag = True
            elif msg.type == 'end_of_track':
                valid_flag = True
            elif msg.type == 'set_tempo':
                valid_flag = True
            elif msg.type == 'smpte_offset':
                valid_flag = True
            elif msg.type == 'time_signature':
                valid_flag = True
            elif msg.type == 'key_signature':
                valid_flag = True
            elif msg.type == 'sequencer_specific':
                valid_flag = False
        else:
            if bool(self.note_re.findall(msg.type)):
                valid_flag = msg.note in self.note and msg.velocity in self.velocity
            elif msg.type == 'polytouch':
                valid_flag = True
            elif msg.type == 'control_change':
                valid_flag = msg.control in self.control_change \
                    and msg.value in self.control_change[msg.control]
            elif msg.type == 'program_change':
                valid_flag = msg.program in self.program_change
            elif msg.type == 'aftertouch':
                valid_flag = msg.channel in self.aftertouch
            elif msg.type == 'pitchwheel':
                valid_flag = self.pitchwheel
            elif msg.type == 'sysex':
                valid_flag = not self.data_in_byte_masks(msg.bytes(),self.sysex_add_by_hand_byte_masks) \
                    and self.data_in_byte_masks(msg.bytes(),self.sysex_byte_masks)
        return valid_flag

    def data_in_byte_masks(self, data, byte_masks) -> bool:
        return any(len(data) == len(l) and not any(d & ~x for d, x in zip(data,l)) for l in byte_masks if l[-1] == self.sysex_terminator_byte) \
            or any(not any(d & ~x for d, x in zip(data,l)) for l in byte_masks if l[-1] != 247)

def midi_convert(midi_filepath: str, textlist: list=None,
                 suffix: str=suffix_default,
                 ymm=YamahaModusMIDI(),
                 debug: bool=False):
    mid_orig = mido.MidiFile(midi_filepath)
    # convert from MIDI type 1 to type 0
    track_orig = mido.merge_tracks(mid_orig.tracks)
    mid_new = mido.MidiFile()
    if hasattr(mid_orig,'ticks_per_beat'):
        mid_new.ticks_per_beat = mid_orig.ticks_per_beat
    track = mido.MidiTrack()
    mid_new.tracks.append(track)
    before_channel_messages_flag = True
    tempo_and_time_signature_messages = []
    control_and_program_change_and_sysex_messages = []
    # Modus initial tempo messages
    if bool(ymm.modus_initial_tempo_messages):
        for m in ymm.modus_initial_tempo_messages:
            track.append(m)
    # track_name
    if len([m for m in track_orig if m.is_meta and m.type == 'track_name']) == 0:
        track_name = midi_re.sub('\\1', os.path.basename(mid_orig.filename))
        track.append(mido.midifiles.meta.MetaMessage(type='track_name', name=track_name, time=0))
    # copyright
    if bool(ymm.copyright) and len([m for m in track_orig if m.is_meta and m.type == 'copyright']) == 0:
        track.append(mido.midifiles.meta.MetaMessage(type='copyright',text=ymm.copyright,time=0))
    # text
    if bool(textlist):
        for text in textlist:
            track.append(mido.midifiles.meta.MetaMessage(type='text',text=text,time=0))
    for msg in track_orig:
        # add these messages before the first channel information
        if before_channel_messages_flag \
                and msg.type in ymm.modus_omit_header_messages:
            if debug: print(f'Omitted {msg}')
            continue
        # add tempo and time signature messages later
        if before_channel_messages_flag \
                and msg.type in ymm.tempo_and_time_signature_types:
            tempo_and_time_signature_messages.append(msg)
            continue
        # add control and program change and sysex later
        if before_channel_messages_flag \
                and msg.type in ymm.control_and_program_change_and_sysex_types:
            control_and_program_change_and_sysex_messages.append(msg)
            continue
        if before_channel_messages_flag \
                and hasattr(msg,'channel') \
                and not msg.type in ymm.control_and_program_change_types:
            before_channel_messages_flag = False
            # add these messages by hand
            # Modus sequencer_specific
            if bool(ymm.modus_sequencer_specific):
                for m in ymm.modus_sequencer_specific:
                    track.append(m)
            # Modus sysex
            track.append(ymm.message_from_str(ymm.sysex_gm1_system_on, time=0))
            track.append(ymm.message_from_str('F0 43 10 4C 00 00 7E 00 F7', time=960))
            # Modus control and program changes
            if bool(ymm.modus_control_and_program_changes):
                for m in ymm.modus_control_and_program_changes:
                    track.append(m)
            # add tempo and time signature messages
            for m in tempo_and_time_signature_messages:
                if ymm.is_valid_message(m): track.append(m)
            # add control and program change and sysex messages
            for m in control_and_program_change_and_sysex_messages:
                if ymm.is_valid_message(m): track.append(m)
        if ymm.is_valid_message(msg): track.append(msg)
        elif debug: print(f'Omitted {msg}')

    mid_new.save(midi_re.sub(f'\\1{suffix}\\2',midi_filepath))

def midi_convert_in_names(names, textlist=None):
    if len(names) == 1 and os.path.isfile(names[0]):
        midi_convert(names[0], textlist=textlist)
        return
    all_filepaths = []
    for name in names:
        if os.path.isfile(name):
            all_filepaths.append(name)
        elif os.path.isdir(name):
            for root, directories, files in os.walk(name):
                for file in [f for f in files if bool(midi_re.findall(f))]:
                    all_filepaths.append(os.path.join(root, file))
    pool = mppool.Pool(mp.cpu_count()-2)
    pool.starmap(midi_convert, [(filepath,textlist) for filepath in all_filepaths])
    pool.close()
    pool.join()

def parseArgs():
    parser = ap.ArgumentParser()
    parser.add_argument('-t', '--text', action='append', nargs=1)
    parser.add_argument('names', nargs='*')
    args = parser.parse_args()
    if bool(args.text):
        args.text = [item for sublist in args.text for item in sublist]
    return args

if __name__=='__main__':
    args = parseArgs()
    if len(sys.argv) > 1: midi_convert_in_names(args.names, textlist=args.text)
