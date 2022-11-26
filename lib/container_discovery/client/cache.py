import os
import sys

import container_discovery.cache as cache
import container_discovery.utils as utils


def main(args, parser, extra, subparser):

    # Show args to the user
    print("            containers: %s" % args.containers)
    print("            cache root: %s" % args.root)
    print("            no cleanup: %s" % args.no_cleanup)
    print("             namespace: %s" % args.namespace)
    print("            skips file: %s" % args.skips_file)
    print("     org letter prefix: %s" % args.org_letter_prefix)
    print("registry letter prefix: %s" % args.registry_letter_prefix)
    print("    repo letter prefix: %s" % args.repo_letter_prefix)

    # We must have an existing containers text file
    if not args.containers or not os.path.exists(args.containers):
        sys.exit(f"{args.containers} does not exist.")

    # Read into listing of containers
    containers = [
        x.strip() for x in utils.read_file(args.containers).split("\n") if x.strip()
    ]

    uris, skips = cache.update(
        containers,
        root=args.root,
        org_prefix=args.org_letter_prefix,
        registry_prefix=args.registry_letter_prefix,
        repo_prefix=args.repo_letter_prefix,
        namespace=args.namespace,
        skips_file=args.skips_file,
        no_cleanup=args.no_cleanup,
    )
    print(f"Found {len(uris)} container identifiers.")
    print(f"Skipped {len(skips)} identifiers.")
