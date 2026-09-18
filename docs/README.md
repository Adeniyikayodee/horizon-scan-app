# How the scan works, as a diagram

`how_the_scan_works.excalidraw` opens at excalidraw.com and explains both scans in five panels:
the steps a run goes through, the two scans side by side, how marks become a score in the horizon
scan, how the evidence ladder works in the YES scan, and how funders are ranked and the writing is
checked.

Every number on it comes from the code: the criteria weights in `scan/spec.py`, the ladder and its
caps in `scan/ladder.py`, the posture gates and windows in `profiles/yes/profile.json`, the funder
points in `scan/funders.py`, the language checks in `scan/plain.py`, and the model routing in
`scan/config.py`. Change any of those and the diagram needs the same change.

To redraw it after an edit:

```
SCENE=./scene_system.mjs OUT=how_the_scan_works node render.mjs
```

`render.mjs` needs `puppeteer-core` and a local Chrome. It writes the `.excalidraw` file, an SVG,
and a PNG.
