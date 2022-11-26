import requests
from container_discovery.pipelines import tags_pipeline as p


def iter_tags(containers, existing=None):
    """
    Given a listing of containers, diff against existing and yield new tags.
    """

    existing = existing or []
    for image in containers:

        # Keep original name with tag
        container = image
        if ":" in image:
            image, _ = image.split(":", 1)

        if image in existing or container in existing:
            continue

        print(f"Contender image {image}")

        print(f"Retrieving tags for {image}")
        tags = requests.get(f"https://crane.ggcr.dev/ls/{image}")
        tags = [x for x in tags.text.split("\n") if x]

        # If we couldn't get tags
        if "UNAUTHORIZED" in tags[0]:
            print(f"Skipping {image}, UNAUTHORIZED in tag.")
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
            continue

        tag = ordered[0]._original
        yield f"{image}:{tag}"
