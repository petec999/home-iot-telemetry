#!/usr/bin/env python3
"""Offline Viomi section audit, based on PiotrMachowski's Viomi parser.
Unknown section boundaries are inferred from the repeated map ID, not decoded.
No network, writes or robot commands.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

LIMIT = 32 * 1024 * 1024
SECTIONS = [(1,"robot_status"),(2,"image"),(4,"history"),(8,"charge_station"),
            (16,"restricted_areas"),(32,"cleaning_areas"),(64,"navigate"),
            (128,"realtime"),(0x800,"unknown_1"),(0x1000,"rooms"),
            (0x2000,"unknown_2"),(0x4000,"room_outlines")]

class Reader:
    def __init__(self,data):
        self.data, self.pos = data, 0
    def take(self,n):
        if n < 0 or self.pos+n > len(self.data):
            raise ValueError(f"Truncated data at offset {self.pos}, requested {n}")
        start=self.pos
        self.pos+=n
        return self.data[start:self.pos]
    def u32(self):
        return struct.unpack("<I",self.take(4))[0]
    def u8(self):
        return self.take(1)[0]
    def string(self):
        return self.take(self.u8()).decode("utf-8")
    def position(self,angle=False):
        a=struct.unpack("<fff" if angle else "<ff",self.take(12 if angle else 8))
        if not all(math.isfinite(x) for x in a) or 1100 in a[:2]:
            return None
        return {"x":a[0],"y":a[1],**({"angle_rad":a[2]} if angle else {})}
    def count(self,item_size):
        n=self.u32()
        if n*item_size > len(self.data)-self.pos:
            raise ValueError(f"Invalid count {n} at offset {self.pos-4}")
        return n

def audit(raw):
    stream=zlib.decompressobj()
    data=stream.decompress(raw,LIMIT+1)
    if len(data)>LIMIT or not stream.eof or stream.unused_data or len(data)<8:
        raise ValueError("Invalid or oversized zlib stream")
    r=Reader(data)
    flags=r.u32()
    mid=struct.unpack_from("<I",data,4)[0]
    magic=struct.pack("<I",mid)
    active=[name for bit,name in SECTIONS if flags&bit]
    out={"map_header_id":mid,"feature_flags":hex(flags),
         "sha256":hashlib.sha256(raw).hexdigest(),
         "uncompressed_bytes":len(data),"sections":{},
         "unknown_flag_bits":hex(flags&~sum(bit for bit,_ in SECTIONS)),
         "restore_supported":False}
    for i,name in enumerate(active):
        start=r.pos
        try:
            if r.take(4)!=magic:
                raise ValueError("Section map ID mismatch")
            info={}
            if name=="robot_status":
                info["opaque_payload_hex"]=r.take(40).hex()
            elif name=="image":
                r.take(8)
                h,w=r.u32(),r.u32()
                r.take(20)
                if not (0<h<=16384 and 0<w<=16384 and h*w<=LIMIT):
                    raise ValueError("Invalid image dimensions")
                counts=Counter(r.take(h*w))
                rooms=Counter()
                for pixel,n in counts.items():
                    if 10<=pixel<=109:
                        rooms[pixel if pixel<60 else pixel-50]+=n
                info.update(width=w,height=h,room_cells=dict(sorted(rooms.items())),
                            pixel_histogram=dict(sorted(counts.items())))
            elif name=="history":
                r.take(4)
                n=r.count(9)
                modes=Counter()
                for _ in range(n):
                    modes[r.u8()]+=1
                    r.position()
                info.update(points=n,modes=dict(modes))
            elif name=="charge_station":
                info["position"]=r.position(True)
            elif name in ("restricted_areas","cleaning_areas"):
                r.take(4)
                n=r.count(92)
                entries=[]
                for _ in range(n):
                    r.take(12)
                    p=[r.position() for j in range(4)]
                    r.take(48)
                    entries.append({"points":p,"wall":all(x is not None for x in p) and p[0]==p[1] and p[2]==p[3]})
                info.update(count=n,entries=entries)
            elif name=="navigate":
                r.take(4)
                info["position"]=r.position()
                r.take(4)
            elif name=="realtime":
                r.take(5)
                info["position"]=r.position(True)
            elif name.startswith("unknown_"):
                end=data.find(magic,r.pos) if i+1<len(active) else len(data)
                if end<0:
                    raise ValueError("Cannot infer next section boundary")
                payload=r.take(end-r.pos)
                info.update(boundary="inferred",payload_bytes=len(payload),
                            sha256=hashlib.sha256(payload).hexdigest(),prefix_hex=payload[:64].hex())
            elif name=="rooms":
                names=[]
                while True:
                    label=r.string()
                    arg=r.u32()
                    names.append({"name":label,"arg":arg})
                    if arg<=1:
                        break
                n=r.count(11)
                rooms=[]
                for _ in range(n):
                    room_id=r.u8()
                    label=r.string()
                    r.take(1)
                    rooms.append({"id":room_id,"name":label,"label_position":r.position()})
                r.take(6)
                info.update(map_names=names,count=n,rooms=rooms)
            elif name=="room_outlines":
                r.take(51)
                n=r.count(8)
                outlines=[]
                for _ in range(n):
                    room_id=r.u32()
                    count=r.count(5)
                    r.take(count*5)
                    outlines.append({"id":room_id,"segments":count})
                info.update(count=n,rooms=outlines)
            out["sections"][name]={"offset":start,"bytes":r.pos-start,**info}
        except (ValueError,UnicodeError,struct.error) as exc:
            out["parse_error"]={"section":name,"offset":r.pos,"message":str(exc)}
            break
    out["remaining_bytes"]=len(data)-r.pos
    out["layout_consumed"]=not out.get("parse_error") and out["remaining_bytes"]==0 and out["unknown_flag_bits"]=="0x0"
    return out

def self_test():
    p=lambda *v:struct.pack("<"+"I"*len(v),*v)
    mid=12345
    m=p(mid)
    flags=sum(bit for bit,_ in SECTIONS)
    data=p(flags)+m+bytes(40)
    data+=m+bytes(8)+p(2,2)+bytes(20)+bytes([0,10,60,255])
    data+=m+bytes(4)+p(1)+bytes(9)
    data+=m+bytes(12)
    data+=m+bytes(4)+p(0)
    data+=m+bytes(4)+p(0)
    data+=m+bytes(16)+m+bytes(17)
    data+=m+b"opaque"
    data+=m+b"\x06Parter"+p(1)+p(1)+bytes([10,3])+b"ABC"+bytes(9)+bytes(6)
    data+=m+b"opaque2"
    data+=m+bytes(51)+p(1)+p(10,1)+bytes(5)
    result=audit(zlib.compress(data))
    assert result["layout_consumed"],result
    assert result["sections"]["image"]["room_cells"]=={10:2}
    assert result["sections"]["rooms"]["rooms"][0]["name"]=="ABC"
    assert result["sections"]["room_outlines"]["rooms"][0]["segments"]==1
    assert not audit(zlib.compress(data[:-1]))["layout_consumed"]
    print("PASS: synthetic 12-section map and truncated-map detection")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path,nargs="?")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        self_test()
    if args.file:
        with args.file.open("rb") as f:
            raw=f.read(LIMIT+1)
        if len(raw)>LIMIT:
            parser.error("Compressed map exceeds limit")
        print(json.dumps(audit(raw),ensure_ascii=False,indent=2))
    elif not args.self_test:
        parser.error("Supply saved map or --self-test")

if __name__=="__main__":
    main()
