import pipelib.steps as step
import pipelib.pipeline as pipeline

# A pipeline to process docker tags
steps = (
    # Scrub commits from version string
    step.filters.CleanCommit(),
    # Parse versions, return sorted ascending, and taking version major.minor.patch into account
    step.container.ContainerTagSort(),
)

# Tag parsing pipeline
tags_pipeline = pipeline.Pipeline(steps)
