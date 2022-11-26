import collections
import os

import container_discovery.utils as utils


def get_total_counts(root):
    """
    Given a registry root, parse json files and return a summary of total counts.
    """
    counts = {}

    # Allow developer to provide tags in root
    for filename in utils.recursive_find(os.path.join(root), ".json"):

        # json files at the root are not valid
        if os.path.basename(filename) in ["skips.json", "counts.json"]:
            print(f"Skipping {filename}")
            continue
        aliases = utils.read_json(filename)
        for alias in aliases:
            if alias not in counts:
                counts[alias] = 0
            counts[alias] += 1

    return collections.OrderedDict(sorted(counts.items()))
