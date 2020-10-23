#!/usr/bin/env pytest -vs
"""Tests for ade."""

# Standard Python Libraries
from collections import OrderedDict
import os
import sys
from unittest.mock import patch

# Third-Party Libraries
import pytest

# cisagov Libraries
import ade

# define sources of versions trings
RELEASE_TAG = os.getenv("RELEASE_TAG")
PROJECT_VERSION = ade.__version__


def test_stdout_version(capsys):
    """Verify that version string sent to stdout agrees with the module version."""
    with pytest.raises(SystemExit):
        with patch.object(sys, "argv", ["bogus", "--version"]):
            ade.assessment_data_export.main()
    captured = capsys.readouterr()
    assert (
        captured.out == f"{PROJECT_VERSION}\n"
    ), "standard output by '--version' should agree with module.__version__"


def test_running_as_module(capsys):
    """Verify that the __main__.py file loads correctly."""
    with pytest.raises(SystemExit):
        with patch.object(sys, "argv", ["bogus", "--version"]):
            # F401 is a "Module imported but unused" warning. This import
            # emulates how this project would be run as a module. The only thing
            # being done by __main__ is importing the main entrypoint of the
            # package and running it, so there is nothing to use from this
            # import. As a result, we can safely ignore this warning.
            # cisagov Libraries
            import ade.__main__  # noqa: F401
    captured = capsys.readouterr()
    assert (
        captured.out == f"{PROJECT_VERSION}\n"
    ), "standard output by '--version' should agree with module.__version__"


@pytest.mark.skipif(
    RELEASE_TAG in [None, ""], reason="this is not a release (RELEASE_TAG not set)"
)
def test_release_version():
    """Verify that release tag version agrees with the module version."""
    assert (
        RELEASE_TAG == f"v{PROJECT_VERSION}"
    ), "RELEASE_TAG does not match the project version"


def test_field_values_to_list_single_value():
    """Test a single value being passed."""
    test_value = OrderedDict([("@key", 12345), ("$", "Single Value")])
    result = ade.assessment_data_export.field_values_to_list(test_value)
    assert len(result) == 1
    assert result[0] == "Single Value"


def test_field_values_to_list_multiple_values():
    """Test when multiple values in a list are passed."""
    test_value = [
        OrderedDict([("@key", 12345), ("$", "First Value")]),
        OrderedDict([("@key", 23456), ("$", "Second Value")]),
    ]
    result = ade.assessment_data_export.field_values_to_list(test_value)
    assert len(result) == 2
    assert result[0] == "First Value"
    assert result[1] == "Second Value"


# More coming soon maybe!
