#!/usr/bin/env python

"""assessment_data_export: A tool for exporting assessment data.

The source of the assessment data is Jira.
The destination of the data is a JSON file stored in an AWS S3 bucket.
The destination S3 bucket can be created via:
  https://github.com/cisagov/assessment-data-import-terraform

Usage:
  assessment_data_export.py --jira-credentials-file=FILE --jira-filter=FILTER --s3-bucket=BUCKET --output-filename=FILENAME
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
"""

# Standard libraries
import json
import os
import re
import subprocess
import tempfile

# Third-party libraries (install with pip)
import boto3
from docopt import docopt
from xmljson import badgerfish as bf
from xml.etree import ElementTree

OPERATOR_LIST = [
    "Operator01",
    "Operator02",
    "Operator03",
    "Operator04",
    "Operator05",
    "Operator06",
    "Operator07",
    "Operator08",
    "Operator09",
]


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
    xml_string = open(xml_filename, "r")
    data = bf.data(ElementTree.fromstring(xml_string.read()))
    assessment_data = data["rss"]["channel"]["item"]

    # Iterate through XML data and build JSON data
    data = []
    for assessment in assessment_data:
        item = {"id": "placeholder"}
        for field in ("summary", "created", "updated", "status"):
            item[field] = assessment[field].get("$")

        try:
            item["resolved"] = assessment["resolved"].get("$")
        except:
            pass

        for node in assessment["customfields"]["customfield"]:
            key = node.get("customfieldname").get("$")

            try:
                value = node.get("customfieldvalues").get(
                    "customfieldvalue").get("$")
            except:
                value = None

            if key == "Asmt ID":
                item["id"] = value

            if value != None:
                item[key] = value

            if key == "Election":
                if value == "Yes":
                    item["Election"] = True
                elif value == "No":
                    item["Election"] = False
                else:
                    item["Election"] = None

            if key == "POC Name" or key == "POC Email" or key == "POC Phone":
                item[key] = None

            if key == "Requested Services":
                try:
                    i = 0
                    services_array = []
                    while i < len(
                        node.get("customfieldvalues").get("customfieldvalue")
                    ):
                        services_array.append(
                            node.get("customfieldvalues")
                            .get("customfieldvalue")[i]
                            .get("$")
                        )
                        i = i + 1
                    item[key] = services_array
                except:
                    pass

        operator_array = []
        for field in OPERATOR_LIST:
            try:
                if item[field]:
                    operator_array.append(item[field])
                    item.pop(key, None)
            except:
                pass
        item["Operators"] = operator_array

        for i in OPERATOR_LIST:
            try:
                del item[i]
            except:
                pass
        data.append(item)

    # Write JSON data to output_filename
    assessment_json = open(output_filename, "w")
    assessment_json.write(json.dumps(data))
    assessment_json.close()


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

    print("\n\nSuccessfully uploaded JSON to S3 bucket")


def main():
    """Call the functions that export data from Jira and upload it to S3."""
    global __doc__
    __doc__ = re.sub("COMMAND_NAME", __file__, __doc__)
    args = docopt(__doc__, version="v0.0.1")

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


if __name__ == "__main__":
    main()
