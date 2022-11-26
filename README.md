# Container Executable Discovery

This is a GitHub action that discovers 🗺️ container executables! It is used by
the [shpc-registry-cache](https://github.com/singularity/shpc-registry-cache). 


## What does it do?

You can provide a listing of container resource identifiers (via a text file)
and it will store namespaced (based on OCI or Docker registry)
identifiers from the repository root in your location of choice (defaults to
your repository root). In addition to the cache of json files with container
executables that are discovered on the path, we save a `counts.json` 
(essentially a summary across counts) and `skips.json` (a cache of containers 
that were not successful to extract the filesystem for and we should not try again).

## How does it work?

You will need to provide a text file with container URIs to check. An example
is provided in the repository here [containers.txt](containers.txt). The idea
would be that you might dynamically generate this file from a resource (e.g., for
the shpc registry cache we derive this list from the [BioContainers](https://depot.galaxyproject.org/singularity/)
depot. Once you have the list, the action does the following:

- We install [shpc](https://github.com/singularityhub/singularity-hpc) and the [guts software])(https://github.com/singularityhub/guts)
- We run the [update_biocontainers.py](scripts/update_biocontainers.py) script that:
  - Parses the latest listing of containers from the [BioContainers Depot](https://depot.galaxyproject.org/singularity/)
  - Generate a unique list of containers and latest (first appearing) tag [^1].
  - Read in the [skips.json](skips.json) - a cached list of containers that we skip because their guts were not extractable [^2].
  - For every new identifier to add: 
   - Prepare a directory to store the new cache entry (a json file)
   - Use the [pipelib](https://vsoch.github.io/pipelib/getting_started/user-guide.html) software to sort tags and get the latest.
   - Use the guts [ManifestGenerator](https://singularityhub.github.io/guts/getting_started/user-guide.html#manifest) to retrieve a listing of paths and associated files within.
   - Filter out known patterns that are not executables of interest.
   - Write this output of aliases to the filesystem under the container identifier as a json file.
- After new aliases are added, [calculate_frequency.py](.github/scripts/calculate_frequency.py) is run to update global [counts.json](counts.json)

The result is alias-level data for each container, along with a global set of counts.

[^1]: For the step that grabs the "latest" tag, since the container URI (without any tag) can be used to get a listing of all tags, it isn't important to be correct to get the latest tag - this can be easily obtained later in a workflow from the unique resource identifier without a tag.  
[^2]: There are several reasons for skipping a container. One is that the guts software is not able to extract every set of container guts to the filesystem. A container that attempts to extract particular locations, or that takes up too much space for the GitHub runner will be skipped. Another reason is the pipelib software failing to filter a meaningful set of versioned tags and sort them (e.g., the listing comes back empty and there are no tags known to retrieve). In practice this is a small number as a percentage of the total.


### Singularity Registry HPC

As an example of the usage of this cache, we use these cache entries to populate 
the [Singularity HPC Registry](https://github.com/singualrityhub/shpc-registry).
On a high level, shpc-registry is providing install configuration files for containers.
Docker or other OCI registry containers are installed to an HPC system via module software,
and to make this work really well, we need to know their aliases. This is where data from
the cache comes in! Specifically for this use case this means we:

- Identify a new container, C, not in the registry from the executable cache here
- Create a set of global executable counts, G
- Define a set of counts from G in C as S
- Rank order S from least to greatest}
- Include any entries in S that have a frequency < 10
- Include any entries in S that have any portion of the name matching the container identifier
- Above that, add the next 10 executables with the lowest frequencies, and < 1,000

The frequencies are calculated across the cache here, included in [counts.json](counts.json).
This produces a container configuration file with a likely good set of executables that
represent the most unique to that container, based on data from the cache.

To learn more about Singularity Registry HPC you can:

- 📖️ Read the [documentation](https://singularity-hpc.readthedocs.io/en/latest/) 📖️
- ⭐️ Browse the [container module collection](https://singularityhub.github.io/shpc-registry/) ⭐️

## Usage

You will minimally next a text file, with one container unique resource identifier (with or without a namespace) per line.
See [containers.txt](containers.txt) and [biocontainers.txt](biocontainers.txt) for examples. A table
of variables for the action is shown below, along with example usage. The assumption is that you are
running the action after having checked out the repository you want to store the cache in.

### Variables

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| token | a `${{ secrets.GITHUB_TOKEN }}` to open a pull request with updates | true | unset |
| root | Path of the cache roots (defaults to PWD) | false | pwd |
| listing | text file with listing of containers, one per line. | true | unset |
| namespace | namespace to add to each container in the listing | false | unset |
| org-letter-prefix | set to true to add a letter directory before the organzation name (e.g., docker.io/l/library/ubuntu:latest) | true | false |
| repo-letter-prefix: set to true to add a letter directory before the repository name (e.g., docker.io/library/u/ubuntu:latest) | true | false |
| registry-letter-prefix | set to true to add a letter directory before the registry name (e.g., d/docker.io/library/ubuntu:latest) | true | false |
| dry_run | don't push changes (dry run only) | false | false |
| branch | branch to push to | false | main |

As an example of namespace, see the [biocontainers.txt](biocontainers.txt) file. We would
want to define namespace as "quay.io/biocontainers" in the action, as the text file only has
partial names. For pushing, make sure your repository allows pushes from actions.


### Examples

Here is a "vanilla" example updating a container executable cache in the checked out
repository present working directory from the [containers.txt](containers.txt) file.

```yaml
name: Update Container Cache
on:
  workflow_dispatch:
  schedule:
  - cron: 0 0 * * 3

jobs:
  default-run:
    name: Update Cache
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          listing: containers.txt
          dry_run: true
```

The remaining recipes assume you have the "on" and "name" directive (these are just jobs):
Do the same, but for a dry run (no GitHub token required):


```yaml
jobs:
  dry-run:
    name: Update Cache
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          listing: containers.txt
          dry_run: true
```

Set a namespace (e.g., as we'd need for [biocontainers.txt](biocontainers.txt))

```yaml
jobs:
  namespace:
    name: Update Cache (Namespace)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          listing: biocontainers.txt
          namespace: quay.io/biocontainers
```

Set an organization (the repository organization or username) prefix, e.g.,
quay.io/vanessa/salad:latest would be stored under `quay.io/v/vanessa/salad:latest.json`.


```yaml
jobs:
  org-prefix:
    name: Update Cache (Org Prefix)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          org-letter-prefix: true
          listing: containers.txt
```
Or set a repository prefix, e.g., quay.io/vanessa/salad:latest would be stored under `quay.io/vanessa/s/salad:latest.json`:

```yaml
jobs:
  repo-prefix:
    name: Update Cache (Repo Prefix)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          repo-letter-prefix: true
          listing: containers.txt
```

Finally, set a registry prefix (more unlikely since there are few, but available)
e.g., quay.io/vanessa/salad:latest would be stored under `q/quay.io/vanessa/salad:latest.json`:

```yaml
jobs:
  registry-prefix:
    name: Update Cache (Registry Prefix)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
      - name: Update from Containers
        uses: singularityhub/container-executable-discovery@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          registry-letter-prefix: true
          listing: containers.txt
```

And that's it! If you have a dynamic listing of containers, you'll likely want to write a step
before using the action to generate the file. 

### Assets Saved

The pull request will update or create (within the cache root):

 - a counts.json file with total counts across the cache
 - a skips.json to store as a cache of containers to skip
 - a namespaced hierarchy (according to your preferences), e.g., `quay.io/vanessa/salad:latest.json`, each a lookup dictionary with paths as keys, and binaries / assets discovered there as values.

Note that we filter out patterns that are likely not executables. See the [scripts](scripts) folder to see this logic!

## Container Discovery Library

The action is powered by a python library [container_discovery](lib) that is provided
and installed alongside the action. Since this is primarily used here, we don't 
publish to pypi. If you want to install it for your own use:

```bash
$ git clone https://github.com/singularityhub/container-executable-discovery
$ cd container-executable-discovery/lib
$ pip install .
```

And then interact with the `container_discovery` module. You can look at 
examples under [scripts](scripts) - this is how the action runs!

## Contribution

This registry showcases a container executable cache, and specifically includes over 8K containers
from BioContainers. If you would like to add another source of container identifiers contributions are 
very much welcome! 

## License

This code is licensed under the MPL 2.0 [LICENSE](LICENSE).
