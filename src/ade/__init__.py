"""A tool for exporting assessment data from Jira to an AWS S3 bucket."""
from ._version import __version__  # noqa: F401
from .assessment_data_export import assessment_data_export

__all__ = ["assessment_data_export"]
