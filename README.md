# ibis-parser

A pure-Python parser for IBIS (I/O Buffer Information Specification) `.ibs` signal-integrity model files.

[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **Zero dependencies** — pure Python standard library only
- **Full IBIS 4.x support** — parses all major block types: Component, Package, Pin, Model, IV/VT tables, Waveforms, Ramp
- **Three-corner data model** — typ / min / max values returned as typed dicts
- **Round-trip fidelity** — write back to `.ibs` with `printer()`
- **SI unit conversion** — `string2float('1.5nH')` → `1.5e-9`
- **Pythonic navigation** — `get_block()` / `get_blocks()` with optional title and node filters
- **CLI included** — inspect `.ibs` files from the terminal without writing a single line of Python

---

## Installation

```bash
pip install eda-ibis-parser
```
[![PyPI](https://img.shields.io/pypi/v/eda-ibis-parser)](https://pypi.org/project/eda-ibis-parser/)
[![Python](https://img.shields.io/pypi/pyversions/eda-ibis-parser)](https://pypi.org/project/eda-ibis-parser/)

Or install from source:

```bash
git clone https://github.com/rohaansch/ibis-parser.git
cd ibis-parser
pip install -e ".[dev]"
```

---

## Quick Start

```python
from ibis_parser import IBISParser

# Parse a file
ibis = IBISParser("device.ibs")
ibis.reader()

# Get component name
comp = ibis.get_block('Component')
print(comp.title)               # → n344_n1a_stb

# Get manufacturer
mfr = comp.get_block('Manufacturer')
print(mfr.value1.get())         # → XYZ Semiconductor

# List all models
for model in ibis.get_blocks('Model'):
    print(model.title)

# Read C_comp (typ / min / max)
model = ibis.get_block('Model')
c = model.C_comp.get(as_number=True)
print(f"C_comp typ = {c['typ']:.3e} F")

# Read a Pin table
pin = comp.get_block('Pin')
data = pin.table.get(['signal_name', 'model_name'])

# Read a GND Clamp IV curve
clamp = model.get_block('GND Clamp')
iv = clamp.table.get(['Voltage', 'Ityp'], as_number=True)

# Convert SI strings
IBISParser.string2float('100pF')   # → 1e-10
IBISParser.string2float('1.5nH')   # → 1.5e-9

# Write back to a new file
with open("out.ibs", "w") as fh:
    ibis.printer(fh)
```

---

## CLI

```
ibis-parser device.ibs                  # summary
ibis-parser device.ibs --dump           # full parsed tree
ibis-parser device.ibs --block Model    # print one block
ibis-parser device.ibs --blocks Model   # list all Model blocks
ibis-parser --version
```

---

## API Reference

### `IBISParser(path)`

| Method | Description |
|---|---|
| `reader()` | Parse the `.ibs` file |
| `printer(fh)` | Write parsed data back to a file handle |
| `dumper()` | Return a debug string representation |
| `get_block(name, title=None)` | Return the single matching block (raises `IBISError` if not found or ambiguous) |
| `get_blocks(name, title=None, quiet=False)` | Return a list of matching blocks |
| `string2float(s)` | Class method — parse an IBIS value string to `float` |
| `is_number(s)` | Class method — return `True` if `s` is a plain decimal number |

### Block navigation

Every `IBISBlock` exposes the same `get_block()` / `get_blocks()` methods, so navigation is uniform at every level:

```python
model = ibis.get_block('Model', title='MIN')
clamp = model.get_block('GND Clamp')
ref   = model.get_block('Voltage Range')
```

### Node access

Named parameters inside a block are exposed as attributes:

```python
model.C_comp          # DictNode  → .get() / .get(as_number=True)
model.Vinl            # StrNode   → .get()
model.Model_type      # StrNode   → .get()
pin.table             # TableNode → .get(columns, as_number=False)
```

### `DictNode.get(conditions=None, as_number=False)`

```python
vals = pkg.R_pkg.get()                          # {'typ': '0', 'min': 'NA', 'max': 'NA'}
vals = pkg.R_pkg.get(conditions=['typ', 'min']) # subset
vals = pkg.R_pkg.get(as_number=True)            # floats
```

### `TableNode.get(columns=None, as_number=False)`

```python
data = pin.table.get()                          # all columns as lists
data = pin.table.get(['signal_name'])           # subset
data = clamp.table.get(['Voltage'], as_number=True)
```

---

## Block Types

| Class | Used for |
|---|---|
| `TextBlock` | Single-value keyword lines (`IBIS Ver`, `File Name`, …) |
| `WrapTextBlock` | Multi-line wrapped text (`Copyright`) |
| `WrapIndentTextBlock` | Indented wrapped text (`Disclaimer`) |
| `TitledTextBlock` | Named blocks with sub-blocks (`Component`) |
| `MultiLineParamBlock` | Key = typ min max tables (`Package`) |
| `TitledModelBlock` | Full `Model` block with nodes and sub-blocks |
| `VarColumnTableBlock` | Variable-column tables (`Pin`, `Diff Pin`) |
| `IVTableBlock` | IV curve tables (`GND Clamp`, `POWER Clamp`) |
| `VTTableBlock` | VT waveform tables (`Rising Waveform`) |
| `SingleLineParamBlock` | Single-line typ min max (`Voltage Range`) |

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest -v
```

---

## IBIS Resources

- [IBIS Open Forum](https://www.ibis.org/)
- [IBIS 7.1 Specification](https://www.ibis.org/ver7.1/ver7_1.pdf)

---

## License

[MIT](LICENSE)