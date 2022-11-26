#!/usr/bin/env python

import argparse
import os
import sys

import container_discovery


def get_parser():
    parser = argparse.ArgumentParser(
        description="Container Executable Discovery Tool",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--version",
        dest="version",
        help="show software version.",
        default=False,
        action="store_true",
    )

    subparsers = parser.add_subparsers(
        help="actions",
        title="actions",
        description="actions",
        dest="command",
    )

    # print version and exit
    subparsers.add_parser("version", description="show software version")

    count = subparsers.add_parser(
        "update-counts",
        description="Update global counts file.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    count.add_argument(
        "--root",
        help="Root of cache with json files to discover and count.",
        default=os.getcwd(),
    )
    count.add_argument(
        "--counts-json",
        dest="counts_json",
        help="Counts json file (defaults to counts.json in root)",
    )

    cache = subparsers.add_parser(
        "update-cache",
        description="Update cache from a containers.txt (or similar) file.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    cache.add_argument("containers", help="Path to text file with containers.")
    cache.add_argument("--root", help="Path to cache root.", default=os.getcwd())
    cache.add_argument(
        "--namespace",
        help="Add a namespace prefix to containers in list (e.g., quay.io/biocontainers)",
    )
    cache.add_argument(
        "--skips_file",
        help="Path to skips.json file (defaults to be in root at skips.json)",
    )
    cache.add_argument(
        "--org-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the org name",
    )
    cache.add_argument(
        "--registry-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the registry name",
    )
    cache.add_argument(
        "--repo-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the repository name",
    )
    cache.add_argument(
        "--no-cleanup",
        dest="no_cleanup",
        action="store_true",
        default=False,
        help="Don't run cleanup (e.g., if doing local work)",
    )

    return parser


def run_main():

    parser = get_parser()

    def help(return_code=0):
        version = container_discovery.__version__
        print("\nContainer Discovery Client v%s" % version)
        parser.print_help()
        sys.exit(return_code)

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    # Show the version and exit
    if args.command == "version" or args.version:
        print(container_discovery.__version__)
        sys.exit(0)

    # retrieve subparser (with help) from parser
    helper = None
    subparsers_actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    for subparsers_action in subparsers_actions:
        for choice, subparser in subparsers_action.choices.items():
            if choice == args.command:
                helper = subparser
                break

    # Does the user want a shell?
    if args.command == "update-counts":
        from .count import main
    elif args.command == "update-cache":
        from .cache import main

    # Pass on to the correct parser
    return_code = 0
    try:
        main(args=args, parser=parser, extra=extra, subparser=helper)
        sys.exit(return_code)
    except UnboundLocalError:
        return_code = 1
    help(return_code)


if __name__ == "__main__":
    run_main()
