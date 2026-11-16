import multiprocessing, time
import ifcopenshell.geom
from brunelleschi.ifc import export_ifc
from meshes import grid
f = export_ifc(grid(15))
for n in (1, multiprocessing.cpu_count()):
    s = ifcopenshell.geom.settings(); s.set("use-world-coords", True)
    t = time.perf_counter()
    it = ifcopenshell.geom.iterator(s, f, n, include=f.by_type("IfcElement")); it.initialize()
    c = 0
    while True:
        it.get(); c += 1
        if not it.next(): break
    print(f"threads={n}: {time.perf_counter()-t:.2f}s for {c} elements")
