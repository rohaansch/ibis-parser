"""ibis_parser — Pure-Python parser for IBIS (.ibs) files."""

from .parser import (
    IBISParser,
    IBISError,
    IBISBlock,
    IBISNode,
    # node types
    StrNode,
    CommentStrNode,
    EqSignStrNode,
    SpaceSignStrNode,
    WrapIndentStrNode,
    WrapStrNode,
    DictNode,
    TableNode,
    # block types
    CommentBlock,
    TextBlock,
    WrapIndentTextBlock,
    WrapTextBlock,
    TitledTextBlock,
    MultiLineParamBlock,
    TitledMultiLineParamBlock,
    VarColumnTableBlock,
    IVTableBlock,
    VTTableBlock,
    SingleLineParamBlock,
    TitledModelBlock,
)

__version__ = "0.1.0"

__all__ = [
    "IBISParser",
    "IBISError",
    "IBISBlock",
    "IBISNode",
    "StrNode",
    "CommentStrNode",
    "EqSignStrNode",
    "SpaceSignStrNode",
    "WrapIndentStrNode",
    "WrapStrNode",
    "DictNode",
    "TableNode",
    "CommentBlock",
    "TextBlock",
    "WrapIndentTextBlock",
    "WrapTextBlock",
    "TitledTextBlock",
    "MultiLineParamBlock",
    "TitledMultiLineParamBlock",
    "VarColumnTableBlock",
    "IVTableBlock",
    "VTTableBlock",
    "SingleLineParamBlock",
    "TitledModelBlock",
]
