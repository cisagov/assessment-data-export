"""A tool for exporting assessment data from Jira to an AWS S3 bucket."""
from ._version import __version__  # noqa: F401
from .assessment_data_export import export_assessment_data

__all__ = ["export_assessment_data"]
