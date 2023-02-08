"""assessment_data_export: A tool for exporting assessment data.

The source of the assessment data is Jira.
The destination of the data is a JSON file stored in an AWS S3 bucket.
The destination S3 bucket can be created via:
  https://github.com/cisagov/assessment-data-import-terraform

Usage:
  assessment_data_export.py --jira-base-url=URL --jira-credentials-file=FILE --jira-filter=FILTER --s3-bucket=BUCKET --output-filename=FILENAME [--log-level=LEVEL]
  assessment_data_export.py (-h | --help)
  assessment_data_export.py --version

Options:
  -h --help                     Show this message.
  --jira-base-url=URL           The base URL of the Jira server that houses
                                the assessment data.
  --jira-credentials-file=FILE  The text file containing the username and
                                password for the Jira account with access to
                                the specified Jira FILTER.
                                File format:
                                username
                                password
  --jira-filter=FILTER          The ID of the Jira filter that produces the
                                desired XML assessment data output.
  --s3-bucket=BUCKET            The AWS S3 bucket where the exported JSON
                                assessment data will be copied to.
  --output-filename=FILENAME    The name of the output JSON file that will be
                                created in the S3 bucket above.
  --version                     Show version.
  --log-level=LEVEL             If specified, then the log level will be set to
                                the specified value.  Valid values are "debug",
                                "info", "warning", "error", and "critical".
                                [default: warning]
"""

# Standard Python Libraries
import json
import logging
import os
import re
import sys
import tempfile

# Third-Party Libraries
import boto3

# I cannot find a package that includes type stubs for defusedxml, so use
# "type: ignore" to tell mypy to ignore this library
from defusedxml import ElementTree  # type: ignore
from docopt import docopt
import requests

# I cannot find a package that includes type stubs for xmljson, so use
# "type: ignore" to tell mypy to ignore this library
from xmljson import badgerfish as bf  # type: ignore

from ._version import __version__


def field_values_to_list(field_values):
    """Convert provided field values to a list of strings.

    Parameters
    ----------
    field_values: OrderedDict or List[OrderedDict]
        The raw field values from the xml parser.

    Returns
    -------
    List[str] : Returns the values for the field as a list.
    """
    if not isinstance(field_values, list):
        field_values = [field_values]

    return [v.get("$") for v in field_values]


def export_jira_data(jira_base_url, jira_credentials_file, jira_filter, xml_filename):
    """Export XML assessment data from Jira to a file.

    Parameters
    ----------
    jira_base_url: str
        The base URL of the Jira server that houses the assessment data.

    jira_credentials_file : str
        The text file containing the username and password for the Jira
        account with access to the specified Jira FILTER.
        File format:
        username
        password

    jira_filter : str
        The ID of the Jira filter that produces the desired XML assessment
        data output.

    xml_filename : str
        The name of the file to store the XML assessment data in.

    Returns
    -------
    bool : Returns a boolean indicating if the assessment data export was
    successful.

    """
    # Grab Jira credentials from jira_credentials_file
    f = open(jira_credentials_file, "r")
    lines = f.readlines()
    jira_username = lines[0].rstrip()
    jira_password = lines[1].rstrip()
    f.close()

    jira_url = (
        f"{jira_base_url}/sr/jira.issueviews:searchrequest-xml/"
        f"{jira_filter}/SearchRequest-{jira_filter}.xml"
    )

    # Export XML data from Jira
    try:
        response = requests.get(
            jira_url,
            auth=(jira_username, jira_password),
            # We need to add a nosec tag here because we are manually disabling
            # certificate verification. We have to do this because the requests
            # package is unable to verify the certificate used by the Jira
            # server.
            verify=False,  # nosec
        )

        with open(xml_filename, "w") as xml_output:
            xml_output.write(response.text)
        logging.info(
            f"Successfully downloaded assessment XML data from {jira_base_url}"
        )
        return True
    except (requests.exceptions.RequestException, Exception) as err:
        logging.critical(
            f"Error downloading assessment XML data from {jira_base_url}\n\n{err}\n"
        )
        return False


def convert_xml_to_json(xml_filename, output_filename):
    """Create a JSON file based on XML assessment data.

    Parameters
    ----------
    xml_filename : str
        The name of the source XML assessment data file.

    output_filename : str
        The name of the target JSON assessment data file.

    Returns
    -------
    bool : Returns a boolean indicating if the data conversion to JSON was
    successful.

    """
    # Open XML file and grab the data
    xml_handle = open(xml_filename, "r")
    xml_data = bf.data(ElementTree.fromstring(xml_handle.read()))
    assessment_data = xml_data["rss"]["channel"]["item"]
    all_assessments_json = []

    # list of field types that may have multiple values
    multi_fields = [
        "com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes",
        "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
    ]

    # RegEx for OperatorXX customfieldnames
    operator_regex = re.compile("^Operator[0-9]{2}[:.,-]?$")

    # Iterate through XML data and build JSON data
    for assessment in assessment_data:
        assessment_json = {"Operators": []}

        # Grab data from key required fields
        for field in ("summary", "created", "updated", "status"):
            assessment_json[field] = assessment[field].get("$")

        # Grab optional "resolved" data
        if assessment.get("resolved"):
            assessment_json["resolved"] = assessment["resolved"].get("$")

        # Process custom field data
        for node in assessment["customfields"]["customfield"]:
            field_type = node.get("@key")
            key = node.get("customfieldname").get("$")
            custom_field_values = node.get("customfieldvalues", {}).get(
                "customfieldvalue"
            )

            # Make the Assessment ID our primary id
            if key == "Asmt ID":
                assessment_json["id"] = custom_field_values.get("$")
            # Turn Election value into a true boolean
            elif key == "Election":
                value = custom_field_values.get("$")
                if value == "Yes":
                    assessment_json["Election"] = True
                elif value == "No":
                    assessment_json["Election"] = False
                else:
                    assessment_json["Election"] = None
            # Build the list of Operators
            elif operator_regex.match(key):
                assessment_json["Operators"].append(custom_field_values.get("$"))
            # Gobble up POC info; we don't want to pass it on
            elif key in ["POC Name", "POC Email", "POC Phone"]:
                assessment_json[key] = None
            # Handle any fields that may have multiple values.
            elif field_type in multi_fields:
                assessment_json[key] = field_values_to_list(custom_field_values)
            else:
                try:
                    # Grab as many other custom fields as we can
                    assessment_json[key] = custom_field_values.get("$")
                except AttributeError:
                    # If we want any fields that end up here, we will have
                    # to add elif clauses for them above
                    pass
        all_assessments_json.append(assessment_json)

    # Write JSON data to output_filename
    assessment_json_file = open(output_filename, "w")
    assessment_json_file.write(json.dumps(all_assessments_json))
    assessment_json_file.close()
    logging.info(
        f"Successfully converted assessment XML to JSON and wrote {output_filename}"
    )
    return True


def upload_to_s3(bucket_name, output_filename):
    """Upload a file to an AWS S3 bucket.

    Parameters
    ----------
    bucket_name : str
        The name of the target S3 bucket.

    output_filename : str
        The name of the file to upload and also the name of the object to
        create in the target S3 bucket.

    Returns
    -------
    bool : Returns a boolean indicating if the S3 upload was successful.

    """
    # Boto3 client for S3
    s3 = boto3.client("s3")

    # Upload file to S3 bucket
    s3.upload_file(output_filename, bucket_name, output_filename)

    logging.info(f"Successfully uploaded {output_filename} to S3 bucket {bucket_name}")
    return True


def export_assessment_data(
    jira_base_url, jira_credentials_file, jira_filter, s3_bucket, output_filename
):
    """Export assessment data from Jira and upload it to an S3 bucket.

    Parameters
    ----------
    jira_base_url: str
        The base URL of the Jira server that houses the assessment data.

    jira_credentials_file : str
        The text file containing the username and password for the Jira
        account with access to the specified Jira FILTER.
        File format:
        username
        password

    jira_filter : str
        The ID of the Jira filter that produces the desired XML assessment
        data output.

    s3_bucket : str
        The name of the target S3 bucket.

    output_filename : str
        The name of the assessment data JSON object to create in the
        target S3 bucket.

    Returns
    -------
    bool : Returns a boolean indicating if the assessment data export was
    successful.

    """
    # Securely create a temporary file to store the XML data in
    temp_xml_file_descriptor, temp_xml_filepath = tempfile.mkstemp()

    try:
        if not export_jira_data(
            jira_base_url, jira_credentials_file, jira_filter, temp_xml_filepath
        ):
            logging.critical("Exiting here!")
            return False
        if not convert_xml_to_json(temp_xml_filepath, output_filename):
            logging.critical("Exiting here!")
            return False
        if not upload_to_s3(s3_bucket, output_filename):
            logging.critical("Exiting here!")
            return False
    finally:
        # Delete local temp XML data file regardless of whether or not
        # any exceptions were thrown in the try block above
        os.remove(f"{temp_xml_filepath}")
        return True


def main():
    """Call the function that exports data from Jira and uploads it to S3."""
    global __doc__
    __doc__ = re.sub("COMMAND_NAME", __file__, __doc__)
    args = docopt(__doc__, version=__version__)

    # Set up logging
    log_level = args["--log-level"]
    try:
        logging.basicConfig(
            format="%(asctime)-15s %(levelname)s %(message)s", level=log_level.upper()
        )
    except ValueError:
        logging.critical(
            f'"{log_level}" is not a valid logging level.  Possible values '
            "are debug, info, warning, error, and critical."
        )
        sys.exit(1)

    success = export_assessment_data(
        args["--jira-base-url"],
        args["--jira-credentials-file"],
        args["--jira-filter"],
        args["--s3-bucket"],
        args["--output-filename"],
    )

    # Stop logging and clean up
    logging.shutdown()

    if not success:
        sys.exit(1)
