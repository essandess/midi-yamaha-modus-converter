#!/usr/bin/env python3

# Display MIDI Header Data as a tsv

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

import mido, os, pandas as pd, re, sys
import multiprocessing as mp, multiprocessing.pool as mppool

headers_default: list = [
    'filename',
    'track_name',
    'instrument_name',
    'text',
    'copyright',
]

headers_attr: dict = {
    'filename': None,
    'track_name': 'name',
    'instrument_name': 'name',
    'text': 'text',
    'copyright': 'text',
}

midi_re: re.Pattern = re.compile(r'\.midi?$',re.IGNORECASE)

field_sep: str = '\t'
multi_sep: str = '; '

control_and_program_change_types: set = {
    'control_change',
    'program_change',
}

def midi_display_header(midi_filepath: str,
        headers: list=headers_default,
        multi_sep: str=multi_sep) -> list:
    mid = mido.MidiFile(midi_filepath)
    # convert from MIDI type 1 to type 0
    track = mido.merge_tracks(mid.tracks)
    header_messages = []
    for msg in track:
        if hasattr(msg,'channel') \
                and not msg.type in control_and_program_change_types:
            break
        else:
            header_messages.append(msg)
    header_values = []
    for hdr in headers:
        if hasattr(mid, hdr): val = getattr(mid, hdr)
        else: val = multi_sep.join([getattr(m,headers_attr[hdr]) for m in header_messages if m.type == hdr])
        header_values.append(val)
    return header_values

def midi_display_header_in_names(names: list,
        headers: list=headers_default,
        field_sep: str=field_sep,
        multi_sep: str=multi_sep) -> pd.core.frame.DataFrame:
    midi_headers = []
    if len(names) == 1 and os.path.isfile(names[0]):
        midi_headers.append(midi_display_header(names[0]))
    else:
        all_filepaths = []
        for name in names:
            if os.path.isfile(name):
                all_filepaths.append(name)
            elif os.path.isdir(name):
                for root, directories, files in os.walk(name):
                    for file in [f for f in files if bool(midi_re.findall(f))]:
                        all_filepaths.append(os.path.join(root, file))
    pool = mppool.Pool(mp.cpu_count()-2)
    midi_headers += pool.starmap(midi_display_header,[(fp, headers, multi_sep) for fp in all_filepaths])
    pool.close()
    pool.join()
    df_midi = pd.DataFrame(midi_headers, columns=headers)
    return df_midi

if __name__=='__main__':
    if len(sys.argv) > 1:
        df_midi = midi_display_header_in_names(sys.argv[1:],headers=headers_default)
        print(df_midi.to_csv(sep=field_sep, index=False))
