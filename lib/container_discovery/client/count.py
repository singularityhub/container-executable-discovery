import os
import sys

import container_discovery.metrics as metrics
import container_discovery.utils as utils


def main(args, parser, extra, subparser):

    # Ensure it exists!
    if not args.root or not os.path.exists(args.root):
        sys.exit(f"{args.root} does not exist!")

    root = os.path.abspath(args.root)
    if not args.counts_json:
        args.counts_json = os.path.join(root, "counts.json")

    # Show args to the user
    print("    root: %s" % root)
    print("  counts: %s" % args.counts_json)

    # Use provided library function to get counts
    counts = metrics.get_total_counts(root)

    # Update and save to file!
    print(f"Writing counts to {args.counts_json}")
    utils.write_json(counts, args.counts_json)
