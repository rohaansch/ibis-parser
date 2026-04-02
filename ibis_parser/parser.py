"""Core IBIS (.ibs) file parser.

Parses IBIS files into a navigable in-memory object tree.

Example::

    from ibis_parser import IBISParser

    ibis = IBISParser("device.ibs")
    ibis.reader()

    for model in ibis.get_blocks('Model'):
        print(model.title, model.C_comp.get())

    with open("out.ibs", "w") as fh:
        ibis.printer(fh)
"""

from __future__ import annotations

import os
import re
import logging
from textwrap import fill
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class IBISError(Exception):
    """Raised for any IBIS parsing or navigation error."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"IBISError: {self.message}"


# ---------------------------------------------------------------------------
# Navigation mixin
# ---------------------------------------------------------------------------

class Navigation:
    """Mixin that adds get_blocks() / get_block() to IBISParser and IBISBlock."""

    def get_blocks(self, block_name_regexp: str, **kwargs) -> List["IBISBlock"]:
        """Return all sub-blocks whose name matches *block_name_regexp*.

        Args:
            block_name_regexp: Full block name or a regex that matches it
                (e.g. ``'Model'``, ``'Rising Waveform'``).
            **kwargs: Extra filters.  Use ``title=<value>`` to filter by block
                title, or ``<node_name>=<value>`` to filter by a string node's
                value.  Add ``quiet=True`` to suppress the not-found warning.

        Returns:
            List of matching :class:`IBISBlock` objects (may be empty).

        Example::

            for model in ibis.get_blocks('Model', Model_type='I/O'):
                print(model.title)
        """
        quiet = kwargs.pop('quiet', False)

        matched: List[IBISBlock] = []
        for b in self.blocks:
            if re.fullmatch(block_name_regexp, b.name):
                hits = 0
                for key, val in kwargs.items():
                    node = getattr(b, key, None)
                    if node:
                        if key == 'title' and node == val:
                            hits += 1
                        elif key != 'title' and node._matches(val):
                            hits += 1
                if hits == len(kwargs):
                    matched.append(b)

        if not matched and not quiet:
            logging.warning(
                f"No matches in '{self.name}'/'{self.title}' "
                f"for block_name_regexp='{block_name_regexp}' filters={kwargs}"
            )
        return matched

    def get_block(self, block_name_regexp: str, **kwargs) -> "IBISBlock":
        """Return exactly one matching sub-block.

        Raises:
            IBISError: If zero or more than one block is found.

        Example::

            rw = ibis.get_block('Model', title='INV').get_block('Rising Waveform')
        """
        matched = self.get_blocks(block_name_regexp, **kwargs)
        if len(matched) == 0:
            raise IBISError(
                f"No matches in '{self.name}'/'{self.title}' "
                f"for block_name_regexp='{block_name_regexp}' filters={kwargs}"
            )
        if len(matched) > 1:
            raise IBISError(
                f"More than one match in '{self.name}'/'{self.title}' "
                f"for block_name_regexp='{block_name_regexp}' filters={kwargs}"
            )
        return matched[0]


# ---------------------------------------------------------------------------
# Node classes
# ---------------------------------------------------------------------------

class IBISNode:
    """A single data item inside an :class:`IBISBlock`.

    Attributes:
        name:         Node name (e.g. ``'C_comp'``).
        parent:       Parent :class:`IBISBlock` or :class:`IBISParser`.
        content:      Raw content (``str``, ``dict``, or ``list``).
        line_number:  Source line number.
        table_header: Column header list for table nodes.
    """

    def __init__(
        self,
        name: str,
        parent: Any,
        table_header: Optional[list],
        content: Any,
        line_number: Optional[int],
    ) -> None:
        self.name = name
        self.parent = parent
        self.content = content
        self.line_number = line_number
        if table_header:
            self.table_header = table_header
            if table_header[0] == '[Series Pin Mapping]':
                self._row_match_regexp = re.compile(
                    r'(\S+)\s+(\S+)\s+(\S+)\s*(\S*)'
                )
            else:
                self._row_match_regexp = re.compile(
                    r'\s+'.join(r'(\S+)' for _ in table_header)
                )
            self._column_widths = [IBISParser._get_column_width(h) for h in table_header]

    def _matches(self, text: str) -> bool:
        raise IBISError(f"Match not supported for {self.__class__.__name__}")

    def get(self, as_number: bool = False, die_on_error: bool = False):
        """Return the node's content.

        Args:
            as_number:    Convert to float when ``True``.
            die_on_error: Raise on conversion failure when ``True``.
        """
        if as_number:
            return IBISParser.string2float(self.content, die_on_error)
        return self.content

    def dumper(self, prefix: str = '|') -> str:
        """Return a human-readable debug string for this node."""
        out = (
            f"{prefix} Node: {self.name}  "
            f"(line {self.line_number},  obj.{self.name}.get())\n"
        )
        if self.name.startswith('table') and hasattr(self, 'table_header'):
            out += f"{prefix}     table_header: {self.table_header}\n"
        snippet = re.sub(r'\n', r'\\n', str(self.content))
        if len(snippet) > 100:
            snippet = snippet[:100] + '...'
        out += f"{prefix}     content: '{snippet}'\n"
        return out

    def print_content(self) -> str:
        return f"Error: UNDER CONSTRUCTION {self.name}={self.content}\n"


class StrNode(IBISNode):
    """String node (e.g. value of ``[File Name]``)."""

    def append(self, value: str) -> None:
        self.content = self.content + '\n' + value

    def _matches(self, text: str) -> bool:
        return self.content == str(text)

    def print_content(self) -> str:
        return f"{self.content.rstrip()}\n"


class CommentStrNode(StrNode):
    """Comment line node (lines starting with ``|``)."""

    def print_content(self) -> str:
        if not self.name.startswith('comment'):
            raise IBISError(
                f"Comment node name must start with 'comment': "
                f"[{self.parent.name}]/{self.name}"
            )
        out = ''
        for line in self.content.splitlines():
            mo = re.fullmatch(
                r'\|\s*(\S+)\s+(\S*typ\S*)\s+(\S*min\S*)\s+(\S*max\S*)\s*',
                line,
                flags=re.I,
            )
            if mo:
                c1 = '{:<{w}}'.format('| ' + mo.group(1), w=IBISParser._get_column_width(mo.group(1)))
                c2 = '{:<{w}}'.format(mo.group(2), w=IBISParser._get_column_width(mo.group(2)))
                c3 = '{:<{w}}'.format(mo.group(3), w=IBISParser._get_column_width(mo.group(3)))
                out += f'{c1} {c2} {c3} {mo.group(4)}\n'
            else:
                out += f'{line}\n'
        return f'{out.rstrip()}\n'


class EqSignStrNode(StrNode):
    """Equal-sign attribute node (e.g. ``R_fixture  =  50``)."""

    def print_content(self) -> str:
        return f'{self.name}  =  {self.content}\n'


class SpaceSignStrNode(StrNode):
    """Space-separated attribute node (e.g. ``Model_type I/O``)."""

    def print_content(self) -> str:
        return f'{self.name} {self.content}\n'


class WrapIndentStrNode(StrNode):
    """Wrapped and indented text node (e.g. ``[Disclaimer]``)."""

    def print_content(self) -> str:
        indent = ' ' * (IBISParser._get_column_width('[') + 1)
        return fill(
            self.content,
            width=IBISParser._total_line_length,
            subsequent_indent=indent,
            initial_indent=indent,
        ).strip() + '\n'


class WrapStrNode(StrNode):
    """Wrapped text node (e.g. ``[Copyright]``)."""

    def print_content(self) -> str:
        out = ''
        for para in re.split(r'\n\s*\n', self.content):
            if para:
                out += fill(para, width=IBISParser._total_line_length).rstrip() + '\n\n'
            else:
                out += '\n'
        return f'{out.rstrip()}\n'


class DictNode(IBISNode):
    """Three-corner dictionary node (e.g. ``C_comp typ min max``)."""

    def _matches(self, text: str) -> bool:
        return False

    def print_content(self) -> str:
        if self.parent._can_have_title3cornvalue:
            out = ''
        else:
            out = '{:<{w}} '.format(self.name, w=IBISParser._get_column_width(self.name))
        for cond in IBISParser._condition_columns:
            if cond not in self.content:
                raise IBISError(
                    f"Condition '{cond}' missing in [{self.parent.name}]/{self.name}"
                )
            out += '{:<{w}} '.format(
                self.content[cond], w=IBISParser._get_column_width(cond)
            )
        return f'{out.rstrip()}\n'

    def get(
        self,
        conditions: list = [],
        as_number: bool = False,
        die_on_error: bool = False,
    ) -> dict:
        """Return ``{'typ': ..., 'min': ..., 'max': ...}`` or a subset.

        Args:
            conditions:   List of keys to return (default: all three corners).
            as_number:    Convert values to float when ``True``.
            die_on_error: Raise on conversion failure when ``True``.
        """
        cols = conditions if conditions else IBISParser._condition_columns
        result: dict = {}
        for cond in cols:
            if cond not in self.content:
                raise IBISError(
                    f"Condition '{cond}' missing in [{self.parent.name}]/{self.name}"
                )
            result[cond] = (
                IBISParser.string2float(self.content[cond], die_on_error)
                if as_number
                else self.content[cond]
            )
        return result


class TableNode(IBISNode):
    """Table node (e.g. ``[GND Clamp]`` IV table, ``[Pin]`` table)."""

    def append(self, value: list) -> None:
        self.content.extend(value)

    def print_content(self) -> str:
        out = ''
        if hasattr(self, 'table_header') and self.table_header[0].startswith('['):
            for ci, col in enumerate(self.table_header):
                w = self._column_widths[ci] if ci < len(self._column_widths) else 10
                out += f'{col:<{w}} '
            out = out.rstrip() + '\n'
        for row in self.content:
            for ci, col in enumerate(row):
                w = self._column_widths[ci] if hasattr(self, '_column_widths') and ci < len(self._column_widths) else 15
                out += f'{col:<{w}} '
            out = out.rstrip() + '\n'
        return f'{out.rstrip()}\n'

    def get(
        self,
        columns: list = [],
        as_number: bool = False,
        die_on_error: bool = False,
    ) -> dict:
        """Return column data as ``{column_name: [val1, val2, ...]}``.

        Args:
            columns:      Column names to return (default: all columns).
            as_number:    Convert values to float when ``True``.
            die_on_error: Raise on conversion failure when ``True``.
        """
        if columns:
            col_indexes = []
            for col in columns:
                try:
                    col_indexes.append((self.table_header.index(col), col))
                except ValueError:
                    raise IBISError(
                        f"Column '{col}' not found in [{self.parent.name}]/{self.name} "
                        f"table_header={self.table_header}"
                    )
        else:
            col_indexes = [(i, c) for i, c in enumerate(self.table_header)]

        result: dict = {col: [] for _, col in col_indexes}
        for row in self.content:
            for ci, col in col_indexes:
                val = row[ci] if ci < len(row) else ''
                result[col].append(
                    IBISParser.string2float(val, die_on_error) if as_number else val
                )
        return result

    def set_all_rows(self, **kwargs) -> None:
        """Set one or more columns to a given value for every row.

        Args:
            **kwargs: ``column_name=new_value`` pairs.

        Example::

            diff_pin.table.set_all_rows(tdelay_typ='0', tdelay_min='NA', tdelay_max='NA')
        """
        col_indexes = []
        for col, val in kwargs.items():
            try:
                col_indexes.append((self.table_header.index(col), val))
            except ValueError:
                raise IBISError(
                    f"Column '{col}' not found in [{self.parent.name}]/{self.name} "
                    f"table_header={self.table_header}"
                )
        for ci, new_val in col_indexes:
            for row in self.content:
                row[ci] = new_val


# ---------------------------------------------------------------------------
# Block classes
# ---------------------------------------------------------------------------

class IBISBlock(Navigation):
    """A parsed IBIS keyword block (e.g. ``[Model]``, ``[GND Clamp]``).

    Attributes:
        name:              Block name (e.g. ``'Model'``).
        title:             Block title string (e.g. ``'INV_X1'``), or ``None``.
        line_number_range: ``[start, end]`` source line numbers.
        parent:            Parent :class:`IBISParser` or :class:`IBISBlock`.
        blocks:            List of child :class:`IBISBlock` objects.
        nodes:             List of :class:`IBISNode` objects in this block.
    """

    def __init__(
        self,
        name: str,
        parent: Any,
        line_number_range: list,
    ) -> None:
        self.name = name
        self.title = None
        self.line_number_range = line_number_range
        self.parent = parent
        self.blocks: List[IBISBlock] = []
        self.nodes: List[IBISNode] = []

        self._current_node: Optional[IBISNode] = None
        self._base_name_counter: dict = {}
        self._current_line_number: Optional[int] = None

        self._init_parser_config()
        self._node_parser_configure()

    def _init_parser_config(self) -> None:
        self._can_have_emptyline = None
        self._can_have_comment = None
        self._can_have_titlevalue = None
        self._can_have_title3cornvalue = None
        self._can_have_text = None
        self._can_have_eqsignparam = None
        self._can_have_spacesignparam = None
        self._can_have_3cornparam = None
        self._can_have_paramtable = None
        self._can_have_ivtable = None
        self._can_have_vttable = None

    def _node_parser_configure(self) -> None:
        pass  # overridden by subclasses

    def dumper(self, prefix: str = '|') -> str:
        """Return a recursive debug string for this block and all sub-blocks."""
        n_blocks = len(self.blocks)
        n_nodes = len(self.nodes)
        title_filter = f", title='{self.title}'" if n_blocks and self.title else ''
        out = (
            f"{prefix} Block: [{self.name}]  title='{self.title}'\n"
            f"{prefix}  (parent={self.parent.name}, sub-blocks={n_blocks}, "
            f"nodes={n_nodes}, lines={self.line_number_range},  "
            f"get_blocks('{self.name}'{title_filter}))\n"
            f"{prefix}   Attributes:\n"
        )
        if not n_nodes:
            out += f'{prefix}\n'
        for node in self.nodes:
            out += node.dumper(prefix + '    ') + f'{prefix}\n'
        if n_blocks:
            out += f'{prefix}   Sub-Blocks:\n'
        for block in self.blocks:
            out += block.dumper(prefix + '    ')
        return out

    def printer(self, outfh: Any) -> None:
        """Write this block (and all sub-blocks) to *outfh* in IBIS format."""
        if self.name == IBISParser._first_block_name or self._can_have_paramtable:
            title_prefix = ''
        else:
            kw = f'[{self.name}]'
            w = IBISParser._get_column_width(kw)
            title_prefix = f'{kw:<{w}} '
            if self.title:
                title_prefix += f' {self.title}'
            if not self._can_have_text and not self._can_have_title3cornvalue:
                title_prefix = title_prefix.strip() + '\n'

        content = title_prefix
        for node in self.nodes:
            content += node.print_content()
        outfh.write(content)
        for block in self.blocks:
            block.printer(outfh)

    def list_nodes(self) -> list:
        """Return ``[[name, node], ...]`` for all nodes in this block."""
        return [[n.name, n] for n in self.nodes]

    def get_node(self, node_name: str) -> Optional[IBISNode]:
        """Return the node with the given name, or ``None``."""
        for node in self.nodes:
            if node.name == node_name:
                return node
        return None

    # ------------------------------------------------------------------
    # Internal line processing
    # ------------------------------------------------------------------

    def _process_line(self, line: str) -> int:
        if hasattr(self, '_under_construction'):
            return 0

        # Empty line
        mo = re.fullmatch(r'(?P<spaces>\s*)', line)
        if self._can_have_emptyline and mo:
            self._add_node(
                attr_name=self._inc_name('emptyline'),
                value=mo.group('spaces'),
                node_type=self._can_have_emptyline,
            )
            return 1

        # Comment
        mo = re.match(r'(?P<text>\|.*)', line)
        if self._can_have_comment and mo:
            self._add_node(
                attr_name=self._inc_name('comment'),
                value=mo.group('text'),
                node_type=self._can_have_comment,
            )
            return 1

        # Own block header
        mo = re.fullmatch(rf'\[(?P<block_name>{self.name})\]\s*(?P<text>.*)', line)
        if mo:
            if self._can_have_titlevalue:
                self.title = mo.group('text').strip()
                return 1
            elif self._can_have_text:
                txt = mo.group('text') or '\n'
                self._add_node(attr_name='value', value=txt, node_type=self._can_have_text)
                return 1
            elif self._can_have_title3cornvalue:
                mo2 = re.fullmatch(
                    rf'\[(?P<block_name>{self.name})\]\s+'
                    r'(?P<typ>\S+)\s+(?P<min>\S+)\s+(?P<max>\S+)',
                    line,
                )
                if mo2:
                    self._add_node(
                        attr_name='value',
                        value={'typ': mo2.group('typ'), 'min': mo2.group('min'), 'max': mo2.group('max')},
                        node_type=self._can_have_title3cornvalue,
                    )
                    return 1
                return 0
            elif self._can_have_paramtable:
                header = [f'[{mo.group("block_name")}]']
                for col in re.split(r'\s+', mo.group('text')):
                    if col:
                        header.append(col)
                self._add_node(attr_name='table', value=[], table_header=header, node_type=self._can_have_paramtable)
                return 1
            elif not mo.group('text'):
                return 1
            return 0

        # Three-corner param
        if self._can_have_3cornparam:
            mo = re.fullmatch(r'(?P<name>\S+)\s+(?P<typ>\S+)\s+(?P<min>\S+)\s+(?P<max>\S+)', line)
            if mo:
                self._add_node(
                    attr_name=mo.group('name'),
                    value={'typ': mo.group('typ'), 'min': mo.group('min'), 'max': mo.group('max')},
                    node_type=self._can_have_3cornparam,
                )
                return 1

        # IV table row
        if self._can_have_ivtable:
            mo = re.fullmatch(r'(?P<v>\S+)\s+(?P<it>\S+)\s+(?P<im>\S+)\s+(?P<ix>\S+)', line)
            if mo:
                self._add_node(
                    attr_name='table',
                    value=[[mo.group('v'), mo.group('it'), mo.group('im'), mo.group('ix')]],
                    table_header=['Voltage', 'Ityp', 'Imin', 'Imax'],
                    node_type=self._can_have_ivtable,
                )
                return 1

        # VT table row
        if self._can_have_vttable:
            mo = re.fullmatch(r'(?P<t>\S+)\s+(?P<vt>\S+)\s+(?P<vm>\S+)\s+(?P<vx>\S+)', line)
            if mo:
                self._add_node(
                    attr_name='table',
                    value=[[mo.group('t'), mo.group('vt'), mo.group('vm'), mo.group('vx')]],
                    table_header=['Time', 'Vtyp', 'Vmin', 'Vmax'],
                    node_type=self._can_have_vttable,
                )
                return 1

        # Eq-sign param
        if self._can_have_eqsignparam:
            mo = re.fullmatch(r'(?P<name>\S+)\s+=\s+(?P<val>\S+)', line)
            if mo:
                self._add_node(attr_name=mo.group('name'), value=mo.group('val'), node_type=self._can_have_eqsignparam)
                return 1

        # Space-sign param
        if self._can_have_spacesignparam:
            mo = re.fullmatch(r'(?P<name>\S+)\s+(?P<val>.+)', line)
            if mo:
                self._add_node(attr_name=mo.group('name'), value=mo.group('val'), node_type=self._can_have_spacesignparam)
                return 1

        # Continuation of text node
        if self._can_have_text and hasattr(self, 'value'):
            self._add_node(attr_name='value', value=line, node_type=self._can_have_text)
            return 1

        # Param table data row
        if self._can_have_paramtable and hasattr(self, 'table'):
            if hasattr(self.table, '_row_match_regexp'):
                mo = self.table._row_match_regexp.fullmatch(line)
                if mo:
                    self._add_node(
                        attr_name='table',
                        value=[list(mo.groups())],
                        node_type=self._can_have_paramtable,
                    )
                    return 1
            return 0

        return 0

    def _add_node(self, **kwargs) -> None:
        attr_name  = kwargs.get('attr_name')  or (_ for _ in ()).throw(IBISError("'attr_name' required"))
        value      = kwargs['value']
        node_type  = kwargs['node_type']
        table_header = kwargs.get('table_header')

        try:
            node = getattr(self, attr_name)
        except AttributeError:
            if node_type is None:
                raise IBISError(f"Cannot add attribute '{attr_name}'")
            node = node_type(attr_name, self, table_header, value, self._current_line_number)
            setattr(self, attr_name, node)
            self.nodes.append(node)
            self._current_node = node
            return
        node.append(value)

    def _inc_name(self, base: str) -> str:
        if self._current_node is None or not self._current_node.name.startswith(base):
            self._base_name_counter[base] = self._base_name_counter.get(base, 0) + 1
        return base + str(self._base_name_counter[base])


# ---------------------------------------------------------------------------
# Concrete block sub-classes
# ---------------------------------------------------------------------------

class CommentBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_comment = CommentStrNode


class TextBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_comment = CommentStrNode
        self._can_have_text = StrNode
        self._can_have_emptyline = StrNode


class WrapIndentTextBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_comment = CommentStrNode
        self._can_have_text = WrapIndentStrNode


class WrapTextBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_comment = CommentStrNode
        self._can_have_text = WrapStrNode


class TitledTextBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_comment = CommentStrNode
        self._can_have_titlevalue = 1
        self._can_have_emptyline = StrNode


class MultiLineParamBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_eqsignparam = EqSignStrNode
        self._can_have_3cornparam = DictNode
        self._can_have_spacesignparam = SpaceSignStrNode


class TitledMultiLineParamBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_titlevalue = 1
        self._can_have_eqsignparam = EqSignStrNode
        self._can_have_3cornparam = DictNode
        self._can_have_spacesignparam = SpaceSignStrNode


class VarColumnTableBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_paramtable = TableNode


class IVTableBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_ivtable = TableNode


class VTTableBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_eqsignparam = EqSignStrNode
        self._can_have_vttable = TableNode


class SingleLineParamBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_title3cornvalue = DictNode


class TitledModelBlock(IBISBlock):
    def _node_parser_configure(self):
        self._can_have_emptyline = StrNode
        self._can_have_comment = CommentStrNode
        self._can_have_titlevalue = 1
        self._can_have_eqsignparam = EqSignStrNode
        self._can_have_spacesignparam = SpaceSignStrNode
        self._can_have_3cornparam = DictNode


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class IBISParser(Navigation):
    """Parse an IBIS (``.ibs``) file into a navigable object tree.

    Usage::

        ibis = IBISParser("device.ibs")
        ibis.reader()

        # Navigate
        comp = ibis.get_block('Component')
        print(comp.title)              # 'n344_n1a_stb'

        for model in ibis.get_blocks('Model'):
            print(model.title)

        # Get a node value
        c_comp = ibis.get_block('Model').C_comp.get()

        # Write back
        with open("out.ibs", "w") as fh:
            ibis.printer(fh)

    Keyword → block-class mapping:

    ============================================  =======================
    Keyword                                       Block class
    ============================================  =======================
    ``HEADER COMMENT``                            CommentBlock
    ``IBIS Ver``, ``File Name``, ``File Rev``,    TextBlock
    ``Date``, ``Source``, ``Manufacturer``
    ``Notes``, ``Disclaimer``                     WrapIndentTextBlock
    ``Copyright``                                 WrapTextBlock
    ``Component``                                 TitledTextBlock
    ``Package``, ``Ramp``                         MultiLineParamBlock
    ``Pin``, ``Diff Pin``,                        VarColumnTableBlock
    ``Series Pin Mapping``
    ``Model Selector``                            TitledMultiLineParamBlock
    ``Model``, ``Submodel``                       TitledModelBlock
    ``GND/POWER/Pulldown/Pullup Reference``,      SingleLineParamBlock
    ``Temperature Range``, ``Voltage Range``
    ``GND Clamp``, ``POWER Clamp``,               IVTableBlock
    ``Pullup``, ``Pulldown``
    ``Rising Waveform``, ``Falling Waveform``     VTTableBlock
    ============================================  =======================
    """

    _condition_columns = ['typ', 'min', 'max']
    _total_line_length = 80
    _first_block_name  = 'HEADER COMMENT'

    _keyword_class_map: Dict[str, type] = {
        'HEADER COMMENT'            : CommentBlock,
        'IBIS Ver'                  : TextBlock,
        'File Name'                 : TextBlock,
        'File Rev'                  : TextBlock,
        'Date'                      : TextBlock,
        'Source'                    : TextBlock,
        'Notes'                     : WrapIndentTextBlock,
        'Disclaimer'                : WrapIndentTextBlock,
        'Copyright'                 : WrapTextBlock,
        'Component'                 : TitledTextBlock,
        'Manufacturer'              : TextBlock,
        'Package'                   : MultiLineParamBlock,
        'Pin'                       : VarColumnTableBlock,
        'Diff Pin'                  : VarColumnTableBlock,
        'Series Pin Mapping'        : VarColumnTableBlock,
        'Model Selector'            : TitledMultiLineParamBlock,
        'Model'                     : TitledModelBlock,
        'Add Submodel'              : MultiLineParamBlock,
        'Submodel'                  : TitledModelBlock,
        'GND Clamp Reference'       : SingleLineParamBlock,
        'POWER Clamp Reference'     : SingleLineParamBlock,
        'Pulldown Reference'        : SingleLineParamBlock,
        'Pullup Reference'          : SingleLineParamBlock,
        'Temperature Range'         : SingleLineParamBlock,
        'Voltage Range'             : SingleLineParamBlock,
        'R Series'                  : SingleLineParamBlock,
        'GND Clamp'                 : IVTableBlock,
        'POWER Clamp'               : IVTableBlock,
        'Pullup'                    : IVTableBlock,
        'Pulldown'                  : IVTableBlock,
        'Ramp'                      : MultiLineParamBlock,
        'Rising Waveform'           : VTTableBlock,
        'Falling Waveform'          : VTTableBlock,
        'End'                       : TextBlock,
    }

    _subblock_to_parent_map: Dict[str, list] = {
        'Manufacturer'          : ['Component'],
        'Package'               : ['Component'],
        'Pin'                   : ['Component'],
        'Diff Pin'              : ['Component'],
        'Series Pin Mapping'    : ['Component'],
        'GND Clamp Reference'   : ['Model'],
        'POWER Clamp Reference' : ['Model'],
        'Pulldown Reference'    : ['Model'],
        'Pullup Reference'      : ['Model'],
        'Temperature Range'     : ['Model'],
        'Voltage Range'         : ['Model'],
        'R Series'              : ['Model'],
        'GND Clamp'             : ['Model', 'Submodel'],
        'POWER Clamp'           : ['Model', 'Submodel'],
        'Pullup'                : ['Model', 'Submodel'],
        'Pulldown'              : ['Model', 'Submodel'],
        'Ramp'                  : ['Model', 'Submodel'],
        'Rising Waveform'       : ['Model', 'Submodel'],
        'Falling Waveform'      : ['Model', 'Submodel'],
        'Add Submodel'          : ['Model'],
    }

    _parent_block_names = set(
        name for parents in _subblock_to_parent_map.values() for name in parents
    )

    def __init__(self, ibis_file_path: str) -> None:
        self.ibis_file_path = ibis_file_path
        self.name  = os.path.basename(ibis_file_path)
        self.title = None
        self.blocks: List[IBISBlock] = []

        self._cur_block_content: list = []
        self._cur_block_name: str = IBISParser._first_block_name
        self._parent_blocks: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reader(self, uncomment_header_keywords: bool = False) -> None:
        """Parse the IBIS file and populate the block/node tree.

        Args:
            uncomment_header_keywords: When ``True``, lines like
                ``|[Copyright]`` are treated as ``[Copyright]``.

        Raises:
            IBISError: On file-not-found, I/O error, or malformed content.
        """
        if not os.path.exists(self.ibis_file_path):
            raise IBISError(f"IBIS file not found: {self.ibis_file_path}")

        try:
            self._cur_block_content = []
            self._cur_block_name = IBISParser._first_block_name
            self._cur_block_start = 0
            self._parent_blocks = {}

            block_pat = re.compile(r'\[(?P<name>.+)\]', re.I)
            uncomment_pat = re.compile(
                r'\|\s*(\[(?:Source|Notes|Disclaimer|Copyright)\])'
            )

            with open(self.ibis_file_path, 'r') as fh:
                for lnum, raw in enumerate(fh):
                    line = raw.strip()
                    if uncomment_header_keywords:
                        line = uncomment_pat.sub(r'\1', line)

                    mo = block_pat.match(line)
                    if mo:
                        self._flush_block([self._cur_block_start + 1, lnum])
                        self._cur_block_content = [line]
                        self._cur_block_name = mo.group('name')
                        self._cur_block_start = lnum
                    else:
                        self._cur_block_content.append(line)

                if self._cur_block_name == 'End':
                    self._flush_block([self._cur_block_start + 1, lnum + 1])
                else:
                    raise IBISError(
                        f"Last block must be '[End]', got '[{self._cur_block_name}]'"
                    )

        except OSError as exc:
            raise IBISError(str(exc)) from exc

    def dumper(self) -> str:
        """Return a recursive debug string of the entire parsed file."""
        out = f"Dumping {self.ibis_file_path}\n"
        for i, block in enumerate(self.blocks):
            out += block.dumper(f'{i}.')
        return out

    def printer(self, outfh: Any, quiet: bool = True) -> None:
        """Write the parsed file back to *outfh* in IBIS format.

        Args:
            outfh:  Open file object for writing.
            quiet:  When ``False``, print a progress message to stdout.
        """
        if not quiet:
            print(f'Writing {self.ibis_file_path} → {outfh.name}')
        for block in self.blocks:
            block.printer(outfh)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_number(string: str) -> bool:
        """Return ``True`` if *string* is a plain number (int or float).

        Example::

            IBISParser.is_number('3.14e-9')  # True
            IBISParser.is_number('1.5nH')    # False
        """
        return bool(re.fullmatch(r'-?\d+\.?\d*(?:[Ee][-+]?\d+)?', string))

    @staticmethod
    def string2float(string: str, die_on_error: bool = False) -> float:
        """Convert an IBIS value string (with optional SI suffix) to float.

        Supported suffixes: ``m``, ``u``/``micro``, ``n``, ``p``, ``f``,
        ``G``, ``M``, ``K``.

        Args:
            string:       Value string (e.g. ``'1.5nH'``, ``'3.3V'``).
            die_on_error: When ``True``, raise :exc:`IBISError` on failure;
                          otherwise re-raise with a message.

        Raises:
            IBISError: If the string cannot be parsed as a number.
        """
        multipliers = (
            (r'm(?:ili?)?[A-Za-z]?$',   1e-3),
            (r'(?:u|micro)[A-Za-z]?$',  1e-6),
            (r'n(?:ano?)?[A-Za-z]?$',   1e-9),
            (r'p(?:ico?)?[A-Za-z]?$',   1e-12),
            (r'(?:femto|f)[A-Za-z]?$',  1e-15),
            (r'G(?:iga?)?[A-Za-z]?$',   1e+9),
            (r'M(?:ega?)?[A-Za-z]?$',   1e+6),
            (r'K(?:ilo?)?[A-Za-z]?$',   1e+3),
        )
        # 1. Plain number (decimal or scientific notation)
        if IBISParser.is_number(string):
            return float(string)
        # 2. Try SI multiplier prefix (may have trailing physical unit like H, V, A)
        for pattern, mult in multipliers:
            co = re.compile(pattern)
            if co.search(string):
                base = co.sub('', string)
                base = re.sub(r'[A-Za-z]$', '', base)
                if IBISParser.is_number(base):
                    return float(base) * mult
        # 3. Trailing physical unit only (e.g. '3.3V', '-0.0F')
        s = re.sub(r'[A-Za-z]$', '', string)
        if IBISParser.is_number(s):
            return float(s)
        raise IBISError(f"Cannot convert '{string}' to a number.")

    @staticmethod
    def _get_column_width(column_name: str) -> int:
        if column_name == 'model_name':            return 25
        if column_name == 'signal_name':           return 12
        if column_name in ('[Pin]', 'pin_2'):      return 5
        if column_name.startswith('tdelay') or column_name == 'inv_pin': return 10
        if column_name in ('Voltage', 'Time'):     return 20
        if re.search(r'typ|min|max', column_name, re.I): return 15
        if column_name in ('Capacitance', 'C_comp'): return 13
        if (column_name == 'Variables'
                or column_name.endswith('Range]')
                or column_name.endswith('Reference]')):
            return 25
        if column_name.startswith('['):            return 15
        return 10

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flush_block(self, line_number_range: list) -> IBISBlock:
        name = self._cur_block_name

        if name not in IBISParser._keyword_class_map:
            raise IBISError(
                f"Block '[{name}]' is not supported "
                f"(lines {line_number_range}). "
                f"Supported: {list(IBISParser._keyword_class_map)}"
            )

        block_class = IBISParser._keyword_class_map[name]

        # Determine parent
        parent: Any = None
        if name in IBISParser._subblock_to_parent_map:
            for candidate in IBISParser._subblock_to_parent_map[name]:
                if candidate in self._parent_blocks:
                    parent = self._parent_blocks[candidate]
                    break
        if parent is None:
            parent = self
            self._parent_blocks.clear()

        block = block_class(name, parent, line_number_range)
        parent.blocks.append(block)

        if name in IBISParser._parent_block_names:
            self._parent_blocks[name] = block

        for rel, line in enumerate(self._cur_block_content):
            block._current_line_number = line_number_range[0] + rel
            if not block._process_line(line):
                raise IBISError(
                    f"Unexpected line '{line}' in [{name}] "
                    f"at line {block._current_line_number} "
                    f"(range {line_number_range})"
                )

        return block
