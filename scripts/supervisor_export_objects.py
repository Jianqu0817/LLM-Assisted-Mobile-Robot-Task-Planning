#!/usr/bin/env python3
"""Webots Supervisor controller: export world object transforms to JSON.

Run this as an extern controller for a supervisor robot named MapExporter.
It writes maps/supervisor_objects.json and exits after one step.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from controller import Supervisor

OUT = Path("/mnt/d/DS_workspace/Liqingbiao/assignment/maps/supervisor_objects.json")


def main() -> int:
    sup = Supervisor()
    root = sup.getRoot()
    children = root.getField("children")
    n = children.getCount()

    objects = []
    for i in range(n):
        node = children.getMFNode(i)
        if node is None:
            continue
        tname = node.getTypeName()
        if tname in ["TexturedBackground", "TexturedBackgroundLight", "CeilingSpotLight", "CeilingLight"]:
            continue
        tf = node.getField("translation")
        if tf is None:
            continue
        pos = tf.getSFVec3f()
        x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        if abs(z) > 3.0:  # skip ceiling lights, etc.
            continue

        sf = node.getField("size")
        size = None
        if sf is not None:
            try:
                sv = sf.getSFVec3f()
            except Exception:
                sv = []
            if len(sv) >= 3:
                size = [float(sv[0]), float(sv[1]), float(sv[2])]
            elif len(sv) == 2:
                size = [float(sv[0]), float(sv[1]), 0.0]
            elif len(sv) == 1:
                size = [float(sv[0]), float(sv[0]), 0.0]

        rf = node.getField("rotation")
        rot = [0.0, 0.0, 1.0, 0.0]
        if rf is not None:
            rv = rf.getSFRotation()
            rot = [float(rv[0]), float(rv[1]), float(rv[2]), float(rv[3])]

        objects.append({
            "type": tname,
            "translation": [x, y, z],
            "size": size,
            "rotation": rot,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(objects, indent=2), encoding="utf-8")
    print(f"wrote {OUT} with {len(objects)} objects", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
