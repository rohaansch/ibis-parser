"""Tests for ibis_parser — sample: io_buffer.ibs (8-model I/O buffer)."""

import os
import tempfile
import pytest

from ibis_parser import IBISParser, IBISError, IBISBlock, IBISNode
from ibis_parser import (
    TextBlock, TitledTextBlock, MultiLineParamBlock, VarColumnTableBlock,
    TitledModelBlock, SingleLineParamBlock, IVTableBlock, WrapTextBlock,
    WrapIndentTextBlock, DictNode, TableNode, StrNode, VTTableBlock,
    TitledMultiLineParamBlock,
)

SAMPLE = os.path.join(os.path.dirname(__file__), "sample.ibs")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ibis():
    obj = IBISParser(SAMPLE)
    obj.reader()
    return obj


@pytest.fixture(scope="module")
def model(ibis):
    """First model: PAD_PA0_PB0_PS1."""
    return ibis.get_block('Model', title='PAD_PA0_PB0_PS1')


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

class TestBasicParsing:
    def test_returns_ibisparser(self, ibis):
        assert isinstance(ibis, IBISParser)

    def test_name_set(self, ibis):
        assert ibis.name == "sample.ibs"

    def test_blocks_non_empty(self, ibis):
        assert len(ibis.blocks) > 0

    def test_all_expected_top_level_blocks(self, ibis):
        names = {b.name for b in ibis.blocks}
        for expected in ('HEADER COMMENT', 'IBIS Ver', 'File Name', 'Component',
                         'Model Selector', 'End'):
            assert expected in names, f"Missing top-level block: {expected}"

    def test_correct_block_classes(self, ibis):
        assert isinstance(ibis.get_blocks('IBIS Ver')[0], TextBlock)
        assert isinstance(ibis.get_blocks('Component')[0], TitledTextBlock)
        assert isinstance(ibis.get_blocks('Copyright')[0], WrapTextBlock)
        assert isinstance(ibis.get_blocks('Disclaimer')[0], WrapIndentTextBlock)
        assert isinstance(ibis.get_blocks('Model Selector')[0], TitledMultiLineParamBlock)


# ---------------------------------------------------------------------------
# File-level metadata blocks
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_ibis_ver(self, ibis):
        ver_block = ibis.get_block('IBIS Ver')
        assert '4.1' in ver_block.value.get()

    def test_file_name(self, ibis):
        fn_block = ibis.get_block('File Name')
        assert 'io_buffer' in fn_block.value.get()

    def test_file_rev(self, ibis):
        rev_block = ibis.get_block('File Rev')
        assert '1.0' in rev_block.value.get()

    def test_date_present(self, ibis):
        assert ibis.get_block('Date') is not None

    def test_source_present(self, ibis):
        src_block = ibis.get_block('Source')
        assert 'XYZ Semiconductor' in src_block.value.get()

    def test_notes_present(self, ibis):
        notes = ibis.get_block('Notes')
        assert notes is not None

    def test_disclaimer_present(self, ibis):
        disc = ibis.get_block('Disclaimer')
        assert isinstance(disc, WrapIndentTextBlock)

    def test_copyright_present(self, ibis):
        copy = ibis.get_block('Copyright')
        assert isinstance(copy, WrapTextBlock)


# ---------------------------------------------------------------------------
# Component block
# ---------------------------------------------------------------------------

class TestComponent:
    def test_component_title(self, ibis):
        comp = ibis.get_block('Component')
        assert comp.title == 'io_buffer'

    def test_manufacturer_is_subblock_of_component(self, ibis):
        comp = ibis.get_block('Component')
        mfr = comp.get_block('Manufacturer')
        assert mfr is not None
        assert 'XYZ Semiconductor' in mfr.value.get()

    def test_package_is_subblock_of_component(self, ibis):
        comp = ibis.get_block('Component')
        pkg = comp.get_block('Package')
        assert pkg is not None
        assert isinstance(pkg, MultiLineParamBlock)

    def test_package_r_pkg(self, ibis):
        comp = ibis.get_block('Component')
        pkg = comp.get_block('Package')
        assert hasattr(pkg, 'R_pkg')
        vals = pkg.R_pkg.get()
        assert 'typ' in vals and 'min' in vals and 'max' in vals

    def test_package_r_pkg_as_number(self, ibis):
        comp = ibis.get_block('Component')
        pkg = comp.get_block('Package')
        r_typ = pkg.R_pkg.get(conditions=['typ'], as_number=True)
        assert isinstance(r_typ['typ'], float)

    def test_pin_table_exists(self, ibis):
        comp = ibis.get_block('Component')
        pin = comp.get_block('Pin')
        assert isinstance(pin, VarColumnTableBlock)

    def test_pin_table_has_rows(self, ibis):
        comp = ibis.get_block('Component')
        pin = comp.get_block('Pin')
        assert hasattr(pin, 'table')
        assert len(pin.table.content) == 3  # PAD, OGND, OPWR

    def test_pin_table_columns(self, ibis):
        comp = ibis.get_block('Component')
        pin = comp.get_block('Pin')
        data = pin.table.get()
        assert 'signal_name' in data
        assert 'model_name' in data

    def test_pin_table_signal_names(self, ibis):
        comp = ibis.get_block('Component')
        pin = comp.get_block('Pin')
        data = pin.table.get(['signal_name'])
        assert data['signal_name'] == ['PAD', 'OGND', 'OPWR']


# ---------------------------------------------------------------------------
# Model Selector block
# ---------------------------------------------------------------------------

class TestModelSelector:
    def test_model_selector_exists(self, ibis):
        ms = ibis.get_block('Model Selector')
        assert isinstance(ms, TitledMultiLineParamBlock)

    def test_model_selector_title(self, ibis):
        ms = ibis.get_block('Model Selector')
        assert ms.title == 'PAD_model_selector'

    def test_model_selector_count(self, ibis):
        # There is one Model Selector in this file
        assert len(ibis.get_blocks('Model Selector')) == 1


# ---------------------------------------------------------------------------
# Model block
# ---------------------------------------------------------------------------

class TestModel:
    def test_model_count(self, ibis):
        assert len(ibis.get_blocks('Model')) == 8

    def test_model_title(self, model):
        assert model.title == 'PAD_PA0_PB0_PS1'

    def test_model_class(self, model):
        assert isinstance(model, TitledModelBlock)

    def test_model_type_node(self, model):
        assert hasattr(model, 'Model_type')
        assert 'I/O' in model.Model_type.get()

    def test_c_comp_node(self, model):
        assert hasattr(model, 'C_comp')
        assert isinstance(model.C_comp, DictNode)

    def test_c_comp_values(self, model):
        vals = model.C_comp.get()
        assert set(vals.keys()) == {'typ', 'min', 'max'}

    def test_c_comp_as_number(self, model):
        vals = model.C_comp.get(as_number=True)
        assert isinstance(vals['typ'], float)
        assert vals['typ'] < 1e-9   # sub-nF capacitance

    def test_vinl_node(self, model):
        assert hasattr(model, 'Vinl')
        assert '0.54' in model.Vinl.get()

    def test_vinh_node(self, model):
        assert hasattr(model, 'Vinh')
        assert '1.26' in model.Vinh.get()

    def test_vmeas_node(self, model):
        assert hasattr(model, 'Vmeas')
        assert '0.9' in model.Vmeas.get()

    def test_all_eight_models_have_titles(self, ibis):
        expected = {
            'PAD_PA0_PB0_PS1', 'PAD_PA0_PB1_PS1',
            'PAD_PA1_PB0_PS1', 'PAD_PA1_PB1_PS1',
            'PAD_PA0_PB0_PS0', 'PAD_PA0_PB1_PS0',
            'PAD_PA1_PB0_PS0', 'PAD_PA1_PB1_PS0',
        }
        titles = {m.title for m in ibis.get_blocks('Model')}
        assert titles == expected


# ---------------------------------------------------------------------------
# SingleLineParam blocks (references, ranges)
# ---------------------------------------------------------------------------

class TestSingleLineParams:
    def test_gnd_clamp_reference(self, model):
        ref = model.get_block('GND Clamp Reference')
        assert isinstance(ref, SingleLineParamBlock)
        vals = ref.value.get()
        assert vals['typ'] == '0'

    def test_power_clamp_reference(self, model):
        ref = model.get_block('POWER Clamp Reference')
        vals = ref.value.get()
        assert vals['typ'] == '1.8'
        assert vals['min'] == '1.62'
        assert vals['max'] == '1.98'

    def test_voltage_range(self, model):
        vr = model.get_block('Voltage Range')
        vals = vr.value.get(as_number=True)
        assert vals['typ'] == pytest.approx(1.8)
        assert vals['min'] == pytest.approx(1.62)

    def test_temperature_range(self, model):
        tr = model.get_block('Temperature Range')
        vals = tr.value.get(as_number=True)
        assert vals['typ'] == pytest.approx(25.0)
        assert vals['max'] == pytest.approx(-40.0)

    def test_pulldown_reference(self, model):
        ref = model.get_block('Pulldown Reference')
        assert isinstance(ref, SingleLineParamBlock)
        vals = ref.value.get()
        assert vals['typ'] == '0'

    def test_pullup_reference(self, model):
        ref = model.get_block('Pullup Reference')
        vals = ref.value.get(as_number=True)
        assert vals['typ'] == pytest.approx(1.8)


# ---------------------------------------------------------------------------
# IV Table blocks
# ---------------------------------------------------------------------------

class TestIVTable:
    def test_gnd_clamp_exists(self, model):
        clamp = model.get_block('GND Clamp')
        assert isinstance(clamp, IVTableBlock)

    def test_gnd_clamp_has_table(self, model):
        clamp = model.get_block('GND Clamp')
        assert hasattr(clamp, 'table')
        assert len(clamp.table.content) > 0

    def test_gnd_clamp_columns(self, model):
        data = model.get_block('GND Clamp').table.get()
        assert 'Voltage' in data
        assert 'Ityp' in data
        assert 'Imin' in data
        assert 'Imax' in data

    def test_gnd_clamp_column_lengths_equal(self, model):
        data = model.get_block('GND Clamp').table.get()
        lengths = [len(v) for v in data.values()]
        assert len(set(lengths)) == 1

    def test_power_clamp_exists(self, model):
        clamp = model.get_block('POWER Clamp')
        assert isinstance(clamp, IVTableBlock)
        assert len(clamp.table.content) > 0

    def test_pullup_exists(self, model):
        pullup = model.get_block('Pullup')
        assert isinstance(pullup, IVTableBlock)
        assert len(pullup.table.content) > 0

    def test_pulldown_exists(self, model):
        pulldown = model.get_block('Pulldown')
        assert isinstance(pulldown, IVTableBlock)
        assert len(pulldown.table.content) > 0

    def test_iv_table_as_number(self, model):
        data = model.get_block('GND Clamp').table.get(['Voltage', 'Ityp'], as_number=True)
        assert all(isinstance(v, float) for v in data['Voltage'])


# ---------------------------------------------------------------------------
# Ramp block
# ---------------------------------------------------------------------------

class TestRamp:
    def test_ramp_exists(self, model):
        ramp = model.get_block('Ramp')
        assert isinstance(ramp, MultiLineParamBlock)

    def test_ramp_r_load(self, model):
        ramp = model.get_block('Ramp')
        assert hasattr(ramp, 'R_load')


# ---------------------------------------------------------------------------
# VT Waveform blocks
# ---------------------------------------------------------------------------

class TestWaveforms:
    def test_rising_waveform_exists(self, model):
        wf_blocks = model.get_blocks('Rising Waveform')
        assert len(wf_blocks) >= 1
        assert isinstance(wf_blocks[0], VTTableBlock)

    def test_falling_waveform_exists(self, model):
        wf_blocks = model.get_blocks('Falling Waveform')
        assert len(wf_blocks) >= 1
        assert isinstance(wf_blocks[0], VTTableBlock)

    def test_rising_waveform_has_table(self, model):
        wf = model.get_blocks('Rising Waveform')[0]
        assert hasattr(wf, 'table')
        assert len(wf.table.content) > 0

    def test_rising_waveform_columns(self, model):
        data = model.get_blocks('Rising Waveform')[0].table.get()
        assert 'Time' in data
        assert 'Vtyp' in data
        assert 'Vmin' in data
        assert 'Vmax' in data

    def test_waveform_table_as_number(self, model):
        data = model.get_blocks('Rising Waveform')[0].table.get(['Time', 'Vtyp'], as_number=True)
        assert all(isinstance(v, float) for v in data['Time'])

    def test_two_rising_waveforms_per_model(self, model):
        assert len(model.get_blocks('Rising Waveform')) == 2

    def test_two_falling_waveforms_per_model(self, model):
        assert len(model.get_blocks('Falling Waveform')) == 2


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_get_blocks_returns_list(self, ibis):
        result = ibis.get_blocks('Model')
        assert isinstance(result, list)
        assert len(result) == 8

    def test_get_block_returns_single(self, ibis):
        result = ibis.get_block('Component')
        assert isinstance(result, IBISBlock)

    def test_get_block_raises_on_missing(self, ibis):
        with pytest.raises(IBISError):
            ibis.get_block('NONEXISTENT_BLOCK')

    def test_get_blocks_empty_on_missing(self, ibis):
        result = ibis.get_blocks('NONEXISTENT_BLOCK', quiet=True)
        assert result == []

    def test_get_block_filter_by_title(self, ibis):
        model = ibis.get_block('Model', title='PAD_PA0_PB0_PS1')
        assert model.title == 'PAD_PA0_PB0_PS1'

    def test_navigate_to_base(self, ibis):
        comp = ibis.get_block('Component')
        mfr = comp.get_block('Manufacturer')
        assert mfr.parent.name == 'Component'

    def test_list_nodes(self, model):
        nodes = model.list_nodes()
        assert isinstance(nodes, list)
        assert all(len(item) == 2 for item in nodes)

    def test_get_node(self, model):
        node = model.get_node('C_comp')
        assert node is not None
        assert node.name == 'C_comp'

    def test_get_node_missing_returns_none(self, model):
        assert model.get_node('NONEXISTENT') is None


# ---------------------------------------------------------------------------
# string2float / is_number
# ---------------------------------------------------------------------------

class TestStringConversion:
    def test_plain_float(self):
        assert IBISParser.string2float('3.14') == pytest.approx(3.14)

    def test_scientific(self):
        assert IBISParser.string2float('1.5e-9') == pytest.approx(1.5e-9)

    def test_nano_suffix(self):
        assert IBISParser.string2float('1.5n') == pytest.approx(1.5e-9)

    def test_pico_suffix(self):
        assert IBISParser.string2float('100p') == pytest.approx(100e-12)

    def test_micro_suffix(self):
        assert IBISParser.string2float('2.5u') == pytest.approx(2.5e-6)

    def test_milli_suffix(self):
        assert IBISParser.string2float('3.3m') == pytest.approx(3.3e-3)

    def test_femto_suffix(self):
        assert IBISParser.string2float('500f') == pytest.approx(500e-15)

    def test_kilo_suffix(self):
        assert IBISParser.string2float('1K') == pytest.approx(1e3)

    def test_mega_suffix(self):
        assert IBISParser.string2float('2M') == pytest.approx(2e6)

    def test_giga_suffix(self):
        assert IBISParser.string2float('1G') == pytest.approx(1e9)

    def test_value_with_unit(self):
        assert IBISParser.string2float('3.3V') == pytest.approx(3.3)
        assert IBISParser.string2float('-0.0F') == pytest.approx(0.0)
        assert IBISParser.string2float('1.5nH') == pytest.approx(1.5e-9)

    def test_negative_value(self):
        assert IBISParser.string2float('-5') == pytest.approx(-5.0)

    def test_bad_string_raises(self):
        with pytest.raises(IBISError):
            IBISParser.string2float('not-a-number')

    def test_is_number_true(self):
        assert IBISParser.is_number('3.14') is True
        assert IBISParser.is_number('-1.5e9') is True

    def test_is_number_false(self):
        assert IBISParser.is_number('1.5n') is False
        assert IBISParser.is_number('abc') is False

    def test_ibis_milli_suffix_in_iv_table(self):
        # Values like -95.1137m appear in GND Clamp IV tables
        assert IBISParser.string2float('-95.1137m') == pytest.approx(-95.1137e-3)

    def test_ibis_micro_suffix_in_iv_table(self):
        assert IBISParser.string2float('38.3273u') == pytest.approx(38.3273e-6)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrors:
    def test_missing_file_raises(self):
        with pytest.raises(IBISError, match="not found"):
            IBISParser("/nonexistent/device.ibs").reader()

    def test_get_block_single_ok(self, ibis):
        ibis.get_block('Component')  # should not raise

    def test_ibis_error_is_exception(self):
        err = IBISError("test")
        assert isinstance(err, Exception)
        assert "test" in str(err)


# ---------------------------------------------------------------------------
# Round-trip write
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_printer_produces_file(self, ibis):
        with tempfile.NamedTemporaryFile(suffix='.ibs', delete=False, mode='w') as fh:
            out = fh.name
            ibis.printer(fh)
        try:
            assert os.path.isfile(out)
            assert os.path.getsize(out) > 0
        finally:
            os.unlink(out)

    def test_roundtrip_reparseable(self, ibis):
        with tempfile.NamedTemporaryFile(suffix='.ibs', delete=False, mode='w') as fh:
            out = fh.name
            ibis.printer(fh)
        try:
            ibis2 = IBISParser(out)
            ibis2.reader()
            assert ibis2.get_block('Component').title == ibis.get_block('Component').title
        finally:
            os.unlink(out)

    def test_roundtrip_model_count_preserved(self, ibis):
        with tempfile.NamedTemporaryFile(suffix='.ibs', delete=False, mode='w') as fh:
            out = fh.name
            ibis.printer(fh)
        try:
            ibis2 = IBISParser(out)
            ibis2.reader()
            assert len(ibis2.get_blocks('Model')) == 8
        finally:
            os.unlink(out)

    def test_roundtrip_model_title_preserved(self, ibis):
        with tempfile.NamedTemporaryFile(suffix='.ibs', delete=False, mode='w') as fh:
            out = fh.name
            ibis.printer(fh)
        try:
            ibis2 = IBISParser(out)
            ibis2.reader()
            assert ibis2.get_block('Model', title='PAD_PA0_PB0_PS1').title == 'PAD_PA0_PB0_PS1'
        finally:
            os.unlink(out)


# ---------------------------------------------------------------------------
# dumper
# ---------------------------------------------------------------------------

class TestDumper:
    def test_dumper_returns_string(self, ibis):
        result = ibis.dumper()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_dumper_contains_component(self, ibis):
        result = ibis.dumper()
        assert 'Component' in result

    def test_block_dumper(self, ibis):
        comp = ibis.get_block('Component')
        result = comp.dumper()
        assert 'Component' in result
        assert 'io_buffer' in result

    def test_node_dumper(self, model):
        result = model.C_comp.dumper()
        assert 'C_comp' in result
