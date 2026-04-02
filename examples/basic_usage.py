"""Basic usage examples for ibis_parser."""

from ibis_parser import IBISParser

# --- 1. Parse a file ---
ibis = IBISParser("../tests/sample.ibs")
ibis.reader()

# --- 2. Get component name ---
comp = ibis.get_block('Component')
print(f"Component: {comp.title}")
# Component: n344_n1a_stb

# --- 3. Get manufacturer ---
mfr = comp.get_block('Manufacturer')
print(f"Manufacturer: {mfr.value.get()}")
# Manufacturer: XYZ Semiconductor

# --- 4. Get all model names ---
for model in ibis.get_blocks('Model'):
    print(f"Model: {model.title}")
# Model: MIN

# --- 5. Read C_comp (three-corner dictionary) ---
model = ibis.get_block('Model')
c_comp = model.C_comp.get()
print(f"C_comp typ={c_comp['typ']} min={c_comp['min']} max={c_comp['max']}")

# --- 6. Get C_comp as float ---
c_comp_num = model.C_comp.get(as_number=True)
print(f"C_comp typ (float): {c_comp_num['typ']:.3e} F")

# --- 7. Read Voltage Range ---
vr = model.get_block('Voltage Range').value.get(as_number=True)
print(f"Voltage Range: typ={vr['typ']}V  min={vr['min']}V  max={vr['max']}V")

# --- 8. Read Pin table ---
pin = comp.get_block('Pin')
pin_data = pin.table.get(['signal_name', 'model_name'])
for sig, mdl in zip(pin_data['signal_name'], pin_data['model_name']):
    print(f"  {sig:<12} {mdl}")

# --- 9. Read GND Clamp IV table ---
gnd_clamp = model.get_block('GND Clamp')
iv = gnd_clamp.table.get(['Voltage', 'Ityp'])
for v, i in list(zip(iv['Voltage'], iv['Ityp']))[:5]:
    print(f"  V={v:<12} Ityp={i}")

# --- 10. Convert an IBIS value string to float ---
print(IBISParser.string2float('1.5nH'))   # 1.5e-9
print(IBISParser.string2float('100p'))    # 1e-10
print(IBISParser.is_number('3.14'))       # True
print(IBISParser.is_number('1.5n'))       # False

# --- 11. Write back to a new file ---
with open("/tmp/sample_out.ibs", "w") as fh:
    ibis.printer(fh)
print("Written to /tmp/sample_out.ibs")
