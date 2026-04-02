# Changelog

All notable changes to **ibis-parser** will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2025-04-02

### Added
- Initial release of `ibis-parser`
- Pure-Python IBIS 4.x parser with zero mandatory dependencies
- Full block-hierarchy model: `Component`, `Package`, `Pin`, `Model`, `GND Clamp`, `POWER Clamp`, `Voltage Range`, `Temperature Range`, `GND/POWER Clamp Reference`, `Pullup/Pulldown Reference`, `Rising/Falling Waveform`, `Ramp`
- Three-corner data model — `DictNode.get(as_number=True)` returns `{'typ': float, 'min': float, 'max': float}`
- `TableNode.get(columns, as_number=False)` for IV and VT tables
- `IBISParser.string2float()` — SI suffix conversion (f, p, n, u, m, K, M, G) with trailing unit stripping (V, H, F, A, Ω)
- `IBISParser.is_number()` — strict decimal/scientific check
- `printer(fh)` — round-trip write back to `.ibs`
- `dumper()` — hierarchical debug string
- `get_block()` / `get_blocks()` navigation with `title` and `quiet` filters at every level
- CLI entry point `ibis-parser` with `--block`, `--blocks`, `--dump`, `--version`
- 69 pytest tests covering parsing, navigation, string conversion, error handling, and round-trip fidelity
