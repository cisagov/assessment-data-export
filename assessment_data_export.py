#!/usr/bin/env python

"""assessment_data_export: A tool for exporting assessment data.

The source of the assessment data is Jira.
The destination of the data is a JSON file stored in an AWS S3 bucket.
The destination S3 bucket can be created via:
  https://github.com/cisagov/assessment-data-import-terraform

Usage:
  assessment_data_export.py [FILTER]
  assessment_data_export.py (-h | --help)
  assessment_data_export.py --version

Options:
  -h --help                      Show this screen.
  --version                      Show version.
"""

# Standard libraries
import json
import os
import re
import subprocess

# Third-party libraries (install with pip)
import boto3
from docopt import docopt
from xmljson import badgerfish as bf
from xml.etree import ElementTree

JIRA_FILE = 'assessment-data.xml'
BUCKET_NAME = 'assessment-data-production'
OPERATOR_LIST = ['Operator01', 'Operator02', 'Operator03', 'Operator04', 'Operator05', 'Operator06', 'Operator07', 'Operator08', 'Operator09']

# pull XML data from JIRA
def retrieve_data(filter):
    f = open('./account.txt','r')
    lines = f.readlines()
    username = lines[0].rstrip()
    password = lines[1].rstrip()
    f.close()

    subprocess.call(['curl -k {}:{} https://jira.ncats.cyber.dhs.gov/sr/jira.issueviews:searchrequest-xml/{}/SearchRequest-{}.xml -o {}'.format(username,password,filter,filter,JIRA_FILE)], shell=True)

# translate the XML into a JSON file
def convert_xml_json():
    xml_string = open('assessment-data.xml','r')
    data = bf.data(ElementTree.fromstring(xml_string.read()))
    assessment_data = data['rss']['channel']['item']

    data = []
    for assessment in assessment_data:
        item = {'id': 'placeholder'}
        for field in ('summary', 'created', 'updated', 'status'):
            item[field] = assessment[field].get('$')

        try:
            item['resolved'] = assessment['resolved'].get('$')
        except:
            pass

        for node in assessment['customfields']['customfield']:
            key = node.get('customfieldname').get('$')

            try:
                value = node.get('customfieldvalues').get('customfieldvalue').get('$')
            except:
                value = None

            if key == 'Asmt ID':
                item['id'] = value

            if value != None:
                item[key] = value

            if key == 'Election':
                if value == 'Yes':
                    item['Election'] = True
                elif value == 'No':
                    item['Election'] = False
                else:
                    item['Election'] = None

            if key == 'POC Name' or key == 'POC Email' or key == 'POC Phone':
                item[key] = None

            if key == 'Requested Services':
                try:
                    i = 0
                    services_array = []
                    while i < len(node.get('customfieldvalues').get('customfieldvalue')):
                        services_array.append(node.get('customfieldvalues').get('customfieldvalue')[i].get('$'))
                        i=i+1
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
        item['Operators'] = operator_array

        for i in OPERATOR_LIST:
            try:
                del item[i]
            except:
                pass
        data.append(item)

    assessment_json = open('assessment-data.json', 'w')
    assessment_json.write(json.dumps(data))
    assessment_json.close()

# Drop it into the S3 bucket
def update_bucket(bucket_name, local_file, remote_file_name):
    # update the s3 bucket with the new contents
    s3 = boto3.client('s3')
    s3.upload_file(local_file, bucket_name, remote_file_name)

    print('\n\nSuccessfully uploaded JSON to S3 bucket')

def main():
    global __doc__
    __doc__ = re.sub('COMMAND_NAME', __file__, __doc__)
    args = docopt(__doc__, version='v0.0.1')

    retrieve_data(args['FILTER'])
    convert_xml_json()

    #OUTPUT_DIR = config.get('DEFAULT', 'OUTPUT_DIR')
    # Check if OUTPUT_DIR exists; if not, bail out
    #if not os.path.exists(OUTPUT_DIR):
        #print('''ERROR: Output directory '{!s}' does not exist - exiting!'''.format(OUTPUT_DIR))
        #sys.exit(1)

    file_name = 'assessment-data.json'
    #full_path_filename = os.path.join(OUTPUT_DIR, file_name)
    update_bucket(BUCKET_NAME, os.path.join('./assessment-data.json'), 'remote-assessment-data.json')

if __name__=='__main__':
    main()
