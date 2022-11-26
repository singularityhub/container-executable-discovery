import os


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
