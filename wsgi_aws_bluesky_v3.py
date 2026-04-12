from wsgi_aws import application as _application
import bluesky_runtime_patch_v3  # noqa: F401

application = _application
