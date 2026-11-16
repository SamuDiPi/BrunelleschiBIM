# Spikes

Throwaway measurement scripts behind architecture decisions. They are kept so that the
numbers in the ADRs can be reproduced, not maintained as code: they are excluded from
lint and type checks and may stop working as dependencies move.

- `m8/`: 3D view candidates and packaging (ADRs 0008 and 0009). Each probe runs in its own
  throwaway environment (see the ADRs for the packages); `meshes.py` builds the test
  models; `runexe.py` runs a packaged program with no console window, no Python on the
  PATH and a hard timeout.
