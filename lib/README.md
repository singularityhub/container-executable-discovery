# Container Discovery

Install from the repository here:

```bash
$ cd lib
$ pip install .
```

## Usage

### Update Cache

To update a cache:

```bash
container-discovery update-cache --root ${root} containers.txt
```

A counts.json and skips.json will be used in the root, and your containers.txt file
(single file listing containers) must be defined.

### Update Counts
Then you can cd to the root of a cache (with json files with binaries to count)
and update the counts:

```bash
$ container-discovery update-counts --help
```
```bash
$ container-discovery update-counts --root /path/to/my-cache
```

Or cd to your cache first and run:

```bash
$ container-discovery update-counts
```

You can also choose a custom location for the counts.json (which defaults to be found
in the root)

```bash
$ container-discovery update-counts --counts-json /tmp/counts.json
```

