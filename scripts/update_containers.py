#!/usr/bin/env python3

import argparse
import os
from container_guts.main import ManifestGenerator
import shpc.utils
import shutil
import requests
import glob
from bs4 import BeautifulSoup

import pipelib.steps as step
import pipelib.pipeline as pipeline


def get_parser():
    parser = argparse.ArgumentParser(
        description="Container Executable Discovery",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("containers", help="Path to text file with containers.")
    parser.add_argument("--root", help="Path to cache root.", default=os.getcwd())
    parser.add_argument(
        "--namespace",
        help="Add a namespace prefix to containers in list (e.g., quay.io/biocontainers)",
    )
    parser.add_argument(
        "--org-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the org name",
    )
    parser.add_argument(
        "--registry-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the registry name",
    )
    parser.add_argument(
        "--repo-letter-prefix",
        action="store_true",
        default=False,
        help="Add a prefix (letter) for the repository name",
    )
    return parser


# A pipeline to process docker tags
steps = (
    # Scrub commits from version string
    step.filters.CleanCommit(),
    # Parse versions, return sorted ascending, and taking version major.minor.patch into account
    step.container.ContainerTagSort(),
)
p = pipeline.Pipeline(steps)


def get_cache_entry(image, args, tag):
    """
    Get a cache entry name for a given tag.
    """
    cache_path = get_cache_path(image, args)
    return f"{cache_path}:{tag}.json"


def has_cache_entry(image, args):
    """
    Determine if a cache entry exists for any tag.
    """
    cache_path = get_cache_path(image, args)
    return len(glob.glob("%s*.json" % cache_path)) > 0


def search_cache_prefix(image, args):
    """
    Determine if a cache entry exists for any tag.
    """
    cache_path = get_cache_path(image, args)
    return glob.glob("%s*.json" % cache_path)


def get_cache_prefix(image, args):
    """
    Get a cache prefix (without any tag or json file)
    """
    # Split image into registry, namespace, repo
    namespace = ""
    registry = ""
    repo = ""

    if image.count("/") == 1:
        namespace, repo = image.split("/")
    elif image.count("/") == 2:
        registry, namespace, repo = image.split("/")
    else:
        sys.exit(f"Cannot parse {image}, not properly formatted with namespace.")

    cache_path = None

    # We can only derive a cache path with a specific letter if the
    if args.org_letter_prefix and namespace:
        letter = namespace.lower()[0]
        cache_path = os.path.join(args.root, registry, letter, namespace, repo)
    elif args.registry_letter_prefix and registry:
        letter = registry.lower()[0]
        cache_path = os.path.join(args.root, letter, registry, namespace, repo)
    elif args.repo_letter_prefix and repo:
        letter = repo.lower()[0]
        cache_path = os.path.join(args.root, registry, namespace, letter, repo)

    # If we don't have a cache path by the time we get here, fallback to default
    if not cache_path:
        cache_path = os.path.join(args.root, registry, namespace, repo)
    return cache_path


def main():

    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    # Show args to the user
    print("            containers: %s" % args.containers)
    print("            cache root: %s" % args.root)
    print("             namespace: %s" % args.namespace)
    print("     org letter prefix: %s" % args.org_letter_prefix)
    print("registry letter prefix: %s" % args.registry_letter_prefix)
    print("    repo letter prefix: %s" % args.repo_letter_prefix)

    # Only one specified prefix allowed
    if (
        len(
            [
                x
                for x in [
                    args.org_letter_prefix,
                    args.registry_letter_prefix,
                    args.repo_letter_prefix,
                ]
                if x
            ]
        )
        > 1
    ):
        sys.exit("Only one type of prefix is allowed!")

    # We must have an existing containers text file
    if not args.containers or not os.path.exists(args.containers):
        sys.exit(f"{args.containers} does not exist.")

    # Read into listing of containers
    containers = [
        x.strip()
        for x in shpc.utils.read_file(args.containers).split("\n")
        if x.strip()
    ]

    # Are we adding a namespace?
    if args.namespace:
        containers = ["%s/%s" % (args.namespace, x) for x in containers]

    # Ensure our alias cache exists
    if not os.path.exists(args.root):
        shpc.utils.mkdir_p(args.root)

    # Read in the URIs to skip
    skips_file = os.path.join(args.root, "skips.json")
    skips = set()
    if os.path.exists(skips_file):
        skips = set(shpc.utils.read_json(skips_file))

    # Get lookup of container images to tags
    uris = {}

    # Use the latest for each unique
    for image in containers:
        if ":" in image:
            image, _ = image.split(":", 1)

        # Don't do repeats
        if has_cache_entry(image, args) or image in uris or uri in skips:
            continue

        print(f"Retrieving tags for {image}")
        tags = requests.get(f"https://crane.ggcr.dev/ls/quay.io/biocontainers/{image}")
        tags = [x for x in tags.text.split("\n") if x]
        uris[image] = tags

        # If we couldn't get tags, add to skips and continue
        if "UNAUTHORIZED" in tags[0]:
            skips.add(image)
            continue

        # The updated and transformed items
        try:
            ordered = p.run(list(tags), unwrap=False)
        except:
            continue

        # If we aren't able to order versions.
        if not ordered:
            skips.add(image)
            continue

        tag = ordered[0]._original
        container = f"{image}:{tag}"
        print(f"Looking up aliases for {container}")
        try:
            cache_aliases(image, args, tag)
        except:
            skips.add(image)
            # Stop and remove running containers, then prune
            os.system("docker stop $(docker ps -a -q)")
            os.system("docker rm $(docker ps -a -q)")
            os.system("docker system prune --all --force")
            for path in glob.glob("/tmp/guts*"):
                shutil.rmtree(path)
        # Save as we go
        shpc.utils.write_json(sorted(list(skips)), skips_file)

    # Write skips back to file for faster parsing
    shpc.utils.write_json(sorted(list(skips)), skips_file)


def include_path(path):
    """
    Filter out binaries in system bins, and various manual filters
    """
    for ending in [
        "post-link.sh",
        ".debug",
        "pre-link.sh",
        ".so",
        ".dll",
        ".gz",
        ".dna",
        ".dox",
        ".db",
        ".db3",
        ".config",
        ".defaults",
        ".dat",
        ".dn",
        ".d",
        ".md",
    ]:
        if path.endswith(ending):
            return False
    if os.path.basename(path).startswith("_"):
        return False
    if os.path.basename(path).startswith("."):
        return False
    if "[" in path or "]" in path or "README" in path:
        return False
    return "sbin" not in path and "/usr/bin" not in path and not path.startswith("/bin")


def cache_aliases(image, args, tag):
    """
    Keep a cache of aliases to use later
    """
    filename = get_cache_entry(image, args, tag)

    # Case 1: we already have this exact tag!
    if os.path.exists(filename):
        return shpc.utils.read_json(filename)

    # Case 2: we have a starter recipe from another tag to update
    matches = search_cache_prefix(image, args)
    if matches:
        return shpc.utils.read_json(matches[0])

    # Generate guts if we haven't seen it yet
    gen = ManifestGenerator()
    manifests = gen.diff(container)

    # Assemble aliases
    aliases = {}
    for path in list(manifests.values())[0]["diff"]["unique_paths"]:
        name = os.path.basename(path)
        if not include_path(path):
            continue

        if name in aliases:
            print(f"Warning, duplicate alias {name}")
        print(path)
        aliases[name] = path

    parent = os.path.dirname(filename)
    shpc.utils.mkdir_p(parent)
    print(f"Writing {filename} with aliases")
    shpc.utils.write_json(aliases, filename)
    return aliases


if __name__ == "__main__":
    main()
