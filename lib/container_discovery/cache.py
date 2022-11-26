import glob
import os
import re
import shutil
import sys

import container_discovery.filters as filters
import container_discovery.utils as utils
import requests
from container_discovery.pipelines import tags_pipeline as p
from container_guts.main import ManifestGenerator


def get_cache_entry(image, args, tag):
    """
    Get a cache entry name for a given tag.
    """
    cache_path = get_cache_prefix(image, args)
    return f"{cache_path}:{tag}.json"


def has_cache_entry(image, args):
    """
    Determine if a cache entry exists for any tag.
    """
    cache_path = get_cache_prefix(image, args)
    return len(glob.glob("%s*.json" % cache_path)) > 0


def search_cache_prefix(image, args):
    """
    Determine if a cache entry exists for any tag.
    """
    cache_path = get_cache_prefix(image, args)
    return glob.glob("%s*.json" % cache_path)


def get_cache_prefix(image, args):
    """
    Get a cache prefix (without any tag or json file)
    """
    # Split image into registry, namespace, repo
    namespace = ""
    registry = ""
    repo = ""

    # assume docker library namespace
    if image.count("/") == 0:
        repo = image
    elif image.count("/") == 1:
        namespace, repo = image.split("/")
    elif image.count("/") == 2:
        registry, namespace, repo = image.split("/")
    else:
        sys.exit(f"Cannot parse {image}, not properly formatted with namespace.")

    cache_path = None

    # We can only derive a cache path with a specific letter if the
    if args.org_prefix and namespace:
        letter = namespace.lower()[0]
        cache_path = os.path.join(args.root, registry, letter, namespace, repo)
    elif args.registry_prefix and registry:
        letter = registry.lower()[0]
        cache_path = os.path.join(args.root, letter, registry, namespace, repo)
    elif args.repo_prefix and repo:
        letter = repo.lower()[0]
        cache_path = os.path.join(args.root, registry, namespace, letter, repo)

    # If we don't have a cache path by the time we get here, fallback to default
    if not cache_path:
        cache_path = os.path.join(args.root, registry, namespace, repo)
    return cache_path


def ensure_unique_prefix(org_prefix, registry_prefix, repo_prefix):
    """
    Ensure we only have one prefix type requested.
    """
    # Only one specified prefix allowed
    if (
        len(
            [
                x
                for x in [
                    org_prefix,
                    registry_prefix,
                    repo_prefix,
                ]
                if x
            ]
        )
        > 1
    ):
        return False
    return True


def cleanup():
    """
    Cleanup command for running in action - will remove all containers.
    """
    for cmd in [
        "docker stop $(docker ps -a -q)",
        "docker rm $(docker ps -a -q)",
        "docker system prune --all --force",
    ]:
        try:
            os.system(cmd)
        except Exception:
            continue
    for path in glob.glob("/tmp/guts*"):
        shutil.rmtree(path)


class Options:
    """
    Helper class to add options to (emulating args)
    """

    def add_option(self, key, value):
        setattr(self, key, value)


class CacheEntry:
    """
    A loaded cache entry that can be used to parse aliases.
    """

    def __init__(self, cache_file, cache, counts):
        self.aliases = utils.read_json(cache_file)
        self.file = cache_file

        # Get the path relative to root
        registry_uri = os.path.relpath(cache_file, cache)

        # We really only need the container uri,
        image, tag = registry_uri.replace(".json", "").split(":", 1)
        self.image = image
        self.tag = tag
        self.counts = counts

    @property
    def image_name(self):
        """
        The image name is just the image (without registry)
        """
        return os.path.basename(self.image)

    def filter_aliases(self, add_count=25, min_count=10, max_count=1000):
        """
        Filter down aliases to sorted set of "keepers"
        """
        # Derive this once
        image_name = self.image_name

        # Look up counts and always take the number under a threshold (10)
        keepers = {}
        for x, path in self.aliases.items():

            if not filters.include_path(path):
                continue

            # Always use a regular expression of the image name to include
            if re.search(image_name.lower(), path.lower()):
                keepers[x] = path

            # Always take the very unique ones!
            elif self.counts[x] <= min_count and filters.include_path(path):
                keepers[x] = path

        # of the remaining we have, sorted by count, keep top N (lower numbers == more unique)
        alias_counts = {x: self.counts[x] for x in self.aliases if x not in keepers}

        # Sort lowest to highest
        sorted_counts = {}
        sorted_keys = sorted(alias_counts, key=alias_counts.get)
        for x in sorted_keys:
            sorted_counts[x] = alias_counts[x]

        # Turn into tuples
        sorted_counts = list(sorted_counts.items())

        while add_count > 0 and sorted_counts:
            keeper, keeper_count = sorted_counts.pop(0)
            if filters.include_path(keeper) and keeper_count < max_count:
                keepers[keeper] = self.aliases[keeper]
                add_count -= 1
        return keepers


def iter_new_cache(cache, registry):
    """
    Yield new entries in the cache, loaded.
    """
    # This assumes counts at the root
    counts = os.path.join(cache, "counts.json")

    # If we don't have cache or counts, no go
    for path in cache, counts:
        if not os.path.exists(path):
            sys.exit(f"{path} does not exist.")

    # Read in counts
    counts = utils.read_json(counts)

    # Keep track of those we've seen in the cache
    seen = set()

    # For each entry in the cache (which might not be in our registry) check for it!
    for cache_file in utils.recursive_find(cache, ".json"):
        basename = os.path.basename(cache_file)
        if basename in ["skips.json", "counts.json"]:
            continue

        # Prepare a cache entry (global counts help later)
        entry = CacheEntry(cache_file, cache, counts)
        seen.add(entry.image)

        # Look for same name in registry
        container_dir = os.path.join(registry, entry.image)
        if os.path.exists(container_dir):
            print(f"{container_dir} already exists.")
            continue

        print(f"Image {entry.image} found in cache and not in registry!")
        yield entry


def update(
    containers,
    root,
    namespace=None,
    org_prefix=False,
    registry_prefix=False,
    repo_prefix=False,
    skips_file=None,
    no_cleanup=False,
):
    """
    Update a container cache from a listing of containers
    """
    # Ensure we have unique set
    containers = list(set(containers))

    # Only one specified prefix allowed
    if not ensure_unique_prefix(org_prefix, registry_prefix, repo_prefix):
        sys.exit("Only one type of prefix is allowed!")

    # Are we adding a namespace?
    if namespace:
        containers = ["%s/%s" % (namespace, x) for x in containers]

    # Ensure our alias cache exists
    if not os.path.exists(root):
        utils.mkdir_p(root)

    # Read in the URIs to skip
    if not skips_file:
        skips_file = os.path.join(root, "skips.json")
    skips = set()
    if os.path.exists(skips_file):
        skips = set(utils.read_json(skips_file))

    # Get lookup of container images to tags
    uris = {}

    # Prepare options
    args = Options()
    args.add_option("root", root)
    args.add_option("org_prefix", org_prefix)
    args.add_option("registry_prefix", registry_prefix)
    args.add_option("repo_prefix", repo_prefix)

    # Use the latest for each unique
    for image in containers:
        if ":" in image:
            image, _ = image.split(":", 1)

        print(f"Contender image {image}")

        # Don't do repeats
        if has_cache_entry(image, args) or image in uris or image in skips:
            continue

        print(f"Retrieving tags for {image}")
        tags = requests.get(f"https://crane.ggcr.dev/ls/{image}")
        tags = [x for x in tags.text.split("\n") if x]
        uris[image] = tags

        # If we couldn't get tags, add to skips and continue
        if "UNAUTHORIZED" in tags[0]:
            print(f"Skipping {image}, UNAUTHORIZED in tag.")
            skips.add(image)
            continue

        # The updated and transformed items
        try:
            ordered = p.run(list(tags), unwrap=False)
        except Exception as e:
            print(f"Ordering of tag failed: {e}")
            continue

        # If we aren't able to order versions.
        if not ordered:
            print(f"No ordered tags for {image}, skipping.")
            skips.add(image)
            continue

        tag = ordered[0]._original
        container = f"{image}:{tag}"
        print(f"Looking up aliases for {container}")
        try:
            cache_aliases(image, args, tag)
        except:
            skips.add(image)
            if not no_cleanup:
                cleanup()
        # Save as we go
        utils.write_json(sorted(list(skips)), skips_file)

    # Write skips back to file for faster parsing
    utils.write_json(sorted(list(skips)), skips_file)

    # Return uris and skips
    return uris, skips


def cache_aliases(image, args, tag):
    """
    Keep a cache of aliases to use later
    """
    filename = get_cache_entry(image, args, tag)

    # Case 1: we already have this exact tag!
    if os.path.exists(filename):
        return utils.read_json(filename)

    # Case 2: we have a starter recipe from another tag to update
    matches = search_cache_prefix(image, args)
    if matches:
        return utils.read_json(matches[0])

    # Generate guts if we haven't seen it yet
    container = f"{image}:{tag}"
    gen = ManifestGenerator()
    manifests = gen.diff(container)

    # Assemble aliases
    aliases = {}
    for path in list(manifests.values())[0]["diff"]["unique_paths"]:
        name = os.path.basename(path)
        if not filters.include_path(path):
            continue

        if name in aliases:
            print(f"Warning, duplicate alias {name}")
        print(path)
        aliases[name] = path

    parent = os.path.dirname(filename)
    utils.mkdir_p(parent)
    print(f"Writing {filename} with aliases")
    utils.write_json(aliases, filename)
    return aliases
