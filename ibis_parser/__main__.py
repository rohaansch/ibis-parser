"""CLI entry point: python -m ibis_parser  or  ibis-parser (installed script)."""

import argparse
import sys

from .parser import IBISParser, IBISError


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ibis-parser",
        description="Parse an IBIS (.ibs) file and print its content.",
        epilog=(
            "Examples:\n"
            "  ibis-parser device.ibs\n"
            "  ibis-parser device.ibs --blocks Model\n"
            "  ibis-parser device.ibs --block Component\n"
            "  ibis-parser device.ibs --dump\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", help="Path to an .ibs IBIS file")
    parser.add_argument(
        "--blocks", "-b",
        metavar="BLOCK_NAME",
        help="List all blocks with this name (e.g. 'Model', 'Pin')",
    )
    parser.add_argument(
        "--block",
        metavar="BLOCK_NAME",
        help="Print the single block with this name",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Dump the full parsed tree for debug",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    args = parser.parse_args()

    if args.version:
        from ibis_parser import __version__
        print(__version__)
        return

    try:
        ibis = IBISParser(args.path)
        ibis.reader()
    except IBISError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dump:
        print(ibis.dumper())
        return

    if args.blocks:
        blocks = ibis.get_blocks(args.blocks)
        if not blocks:
            print(f"No blocks named '{args.blocks}' found.", file=sys.stderr)
            sys.exit(1)
        for b in blocks:
            print(f"[{b.name}] {b.title or ''}")
        return

    if args.block:
        try:
            b = ibis.get_block(args.block)
        except IBISError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        print(b.dumper())
        return

    # Default: summary
    comp_blocks = ibis.get_blocks('Component', quiet=True)
    comp_title = comp_blocks[0].title if comp_blocks else '(unknown)'
    ibis_ver = ibis.get_blocks('IBIS Ver', quiet=True)
    ver = ibis_ver[0].value1.get().strip() if ibis_ver and hasattr(ibis_ver[0], 'value1') else '?'

    models = ibis.get_blocks('Model', quiet=True)
    pins_blocks = ibis.get_blocks('Pin', quiet=True)
    pin_count = len(pins_blocks[0].table.content) if pins_blocks and hasattr(pins_blocks[0], 'table') else 0

    print(f"File:      {ibis.name}")
    print(f"Component: {comp_title}")
    print(f"IBIS Ver:  {ver}")
    print(f"Models:    {len(models)}")
    print(f"Pins:      {pin_count}")
    if models:
        print("Model list:")
        for m in models:
            print(f"  {m.title}")


if __name__ == "__main__":
    main()
