#!/usr/bin/env python3
"""Read-only Viomi cloud map header inspection, no network or device writes.
Header layout based on PiotrMachowski/Python-package-vacuum-map-parser-viomi
(src/vacuum_map_parser_viomi/map_data_parser.py and parsing_buffer.py).
A decoded cloud map is not proof of a restorable SLAM backup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

LIMIT=32*1024*1024
FLAGS={1:"robot_status",2:"image",4:"history",8:"charge_station",
       16:"restricted_areas",32:"cleaning_areas",64:"navigate",128:"realtime",
       0x800:"unknown_1",0x1000:"rooms",0x2000:"unknown_2",0x4000:"room_outlines"}

def inspect(raw):
    stream=zlib.decompressobj()
    data=stream.decompress(raw,LIMIT+1)
    if len(data)>LIMIT or not stream.eof or stream.unused_data or len(data)<8:
        raise ValueError("Invalid or oversized zlib stream")
    flags,mid=struct.unpack_from("<II",data)
    report={"compressed_bytes":len(raw),"uncompressed_bytes":len(data),
            "sha256":hashlib.sha256(raw).hexdigest(),
            "feature_flags":f"0x{flags:08x}","map_header_id":mid,
            "sections_declared":[name for bit,name in FLAGS.items() if flags&bit],
            "unknown_flag_bits":f"0x{flags&~sum(FLAGS):08x}",
            "restore_supported":False}
    pos=4
    if flags&1:
        pos+=44
    if flags&2 and len(data)>=pos+40:
        magic=struct.unpack_from("<I",data,pos)[0]
        if magic==mid:
            height,width=struct.unpack_from("<II",data,pos+12)
            report["image_header"]={"width":width,"height":height,
                                    "grid_cells":width*height,
                                    "section_id_matches":True,
                                    "dimensions_plausible":0<width<=16384 and 0<height<=16384 and width*height<=LIMIT}
        else:
            report["image_header"]={"section_id_matches":False}
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("file",nargs="?",type=Path)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    sample=struct.pack("<II",3,123)+bytes(40)+struct.pack("<I",123)+bytes(8)+struct.pack("<II",800,800)+bytes(20)
    r=inspect(zlib.compress(sample))
    assert r["map_header_id"]==123 and r["image_header"]["grid_cells"]==640000
    if args.self_test:
        print("PASS: header flags, little-endian map ID and image dimensions")
        return
    if args.file is None:
        p.error("provide saved .bin file")
    with args.file.open("rb") as f:
        raw=f.read(LIMIT+1)
    if len(raw)>LIMIT:
        raise SystemExit("Compressed map exceeds limit")
    print(json.dumps(inspect(raw),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
