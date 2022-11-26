import container_discovery.utils as utils
from container_discovery.pipelines import tags_pipeline as p
import container_discovery.filters as filters

from container_guts.main import ManifestGenerator

import os
import sys
import shutil
import requests
import glob


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
