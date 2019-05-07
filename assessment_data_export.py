#!/usr/bin/env python

"""assessment_data_export: A tool for exporting assessment data.

The source of the assessment data is Jira.
The destination of the data is a JSON file stored in an AWS S3 bucket.
The destination S3 bucket can be created via:
  https://github.com/cisagov/assessment-data-import-terraform

Usage:
  assessment_data_export.py --jira-credentials-file=FILE --jira-filter=FILTER --s3-bucket=BUCKET --output-filename=FILENAME [--log-level=LEVEL]
  assessment_data_export.py (-h | --help)
  assessment_data_export.py --version

Options:
  -h --help                     Show this message.
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

# Standard libraries
from collections import OrderedDict
import json
import logging
import os
import re
import subprocess
import tempfile

# Third-party libraries (install with pip)
import boto3
from docopt import docopt
from xmljson import badgerfish as bf
from xml.etree import ElementTree


def export_jira_data(jira_credentials_file, jira_filter, xml_filename):
    """Export XML assessment data from Jira to a file.

    Parameters
    ----------
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
    None

    """
    # Grab Jira credentials from jira_credentials_file
    f = open(jira_credentials_file, "r")
    lines = f.readlines()
    username = lines[0].rstrip()
    password = lines[1].rstrip()
    f.close()

    # Export XML data from Jira
    subprocess.call(
        [
            f"curl -k -u{username}:{password} https://jira.ncats.cyber.dhs.gov"
            f"/sr/jira.issueviews:searchrequest-xml/{jira_filter}/"
            f"SearchRequest-{jira_filter}.xml -o {xml_filename}"
        ],
        shell=True,
    )


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
    None

    """
    # Open XML file and grab the data
    xml_handle = open(xml_filename, "r")
    xml_data = bf.data(ElementTree.fromstring(xml_handle.read()))
    assessment_data = xml_data["rss"]["channel"]["item"]
    all_assessments_json = []

    # RegEx for OperatorXX customfieldnames
    operator_regex = re.compile("^Operator[0-9]{2}[:.,-]?$")

    # Iterate through XML data and build JSON data
    for assessment in assessment_data:
        assessment_json = {
            'Requested Services': [],
            'Operators': []
        }

        # Grab data from key required fields
        for field in ("summary", "created", "updated", "status"):
            assessment_json[field] = assessment[field].get("$")

        # Grab optional "resolved" data
        if assessment.get("resolved"):
            assessment_json["resolved"] = assessment["resolved"].get("$")

        # Process custom field data
        for node in assessment["customfields"]["customfield"]:
            key = node.get("customfieldname").get("$")
            custom_field_values = node.get("customfieldvalues", {}).get(
                "customfieldvalue")

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
            # Gobble up POC info; we don't want to pass it on
            elif key in ["POC Name", "POC Email", "POC Phone"]:
                assessment_json[key] = None
            # Build the list of Requested Services
            elif key == "Requested Services":
                if type(custom_field_values) == OrderedDict:
                    # There's only one requested service
                    assessment_json['Requested Services'].append(
                        custom_field_values.get("$"))
                elif type(custom_field_values) == list:
                    # There are multiple requested services
                    for service in custom_field_values:
                        assessment_json['Requested Services'].append(service.get("$"))
            # Build the list of Operators
            elif operator_regex.match(key):
                assessment_json["Operators"].append(custom_field_values.get('$'))
            else:
                try:
                    # Grab as many other custom fields as we can
                    assessment_json[key] = custom_field_values.get('$')
                except AttributeError:
                    # If we want any fields that end up here, we will have
                    # to add elif clauses for them above
                    pass
        all_assessments_json.append(assessment_json)

    # Write JSON data to output_filename
    assessment_json_file = open(output_filename, "w")
    assessment_json_file.write(json.dumps(all_assessments_json))
    assessment_json_file.close()


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
    None

    """
    # Boto3 client for S3
    s3 = boto3.client("s3")

    # Upload file to S3 bucket
    s3.upload_file(output_filename, bucket_name, output_filename)

    logging.info(f"Successfully uploaded {output_filename} to S3 bucket {bucket_name}")


def main():
    """Call the functions that export data from Jira and upload it to S3."""
    global __doc__
    __doc__ = re.sub("COMMAND_NAME", __file__, __doc__)
    args = docopt(__doc__, version="v0.0.1")

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
        return 1

    # Securely create a temporary file to store the XML data in
    temp_xml_file_descriptor, temp_xml_filepath = tempfile.mkstemp()

    try:
        export_jira_data(
            args["--jira-credentials-file"], args["--jira-filter"], temp_xml_filepath
        )
        convert_xml_to_json(temp_xml_filepath, args["--output-filename"])
        upload_to_s3(args["--s3-bucket"], args["--output-filename"])
    finally:
        # Delete local temp XML data file regardless of whether or not
        # any exceptions were thrown in the try block above
        os.remove(f"{temp_xml_filepath}")

        # Stop logging and clean up
        logging.shutdown()


if __name__ == "__main__":
    main()
