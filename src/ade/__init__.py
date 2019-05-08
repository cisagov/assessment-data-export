"""A tool for exporting assessment data from Jira to an AWS S3 bucket."""
from .assessment_data_export import assessment_data_export
from ._version import __version__  # noqa: F401

__all__ = ["assessment_data_export"]
