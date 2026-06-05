"""Argus: a framework-free, horizontally-autoscaled multi-agent deep-research engine."""

import os

# LiteLLM probes AWS Bedrock/SageMaker stream decoders at import and logs noisy
# warnings via its own "LiteLLM" logger when botocore is absent ("could not pre-load
# bedrock-runtime response stream shape ... No module named 'botocore'"). Argus uses
# neither, so silence everything below ERROR before litellm is first imported.
# setdefault lets an explicit LITELLM_LOG=DEBUG win when actually debugging LiteLLM.
os.environ.setdefault("LITELLM_LOG", "ERROR")

__version__: str = "0.0.1"
