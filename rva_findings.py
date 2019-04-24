#!/usr/bin/env python
'''Translate exported data from JIRA to MongoDB.

Usage:
  rva_data_manager.py [--section SECTION] [FILTER]
  rva_data_manager.py (-h | --help)
  rva_data_manager.py --version

Options:
  -h --help                      Show this screen.
  --version                      Show version.
  -s SECTION --section=SECTION   Configuration section to use.
'''

from docopt import docopt
import csv
import os
import re
from cyhy.db import database
from cyhy.util import util
import subprocess
from datetime import datetime
import dateutil.parser


FMT = '%m/%d/%y %H:%M'
FINDINGS_FILE = 'exported-rva-data.csv'

def creds:
    f = open('../account.txt','r')
    lines = f.readlines()
    username = lines[0].rstrip()
    password = lines[1].rstrip()
    f.close()

def prep_and_import_csv(db):
    assessments = open(FINDINGS_FILE)
    # Create a writer so we have a list of our unique agencies
    domains_processed = 0
    
    firstline = True
    for row in csv.reader(assessments):
        if firstline:    #skip first line
            firstline = False
            continue
        # parse the line
        for j in (14,15):
            row[j] = dateutil.parser.parse(row[j])
        for k in (7):
            if row[k].upper() == 'TRUE':
                row[k] = True
            elif row[k].upper() == 'FALSE':
                row[k] = False
            else:
                row[k] = None
        for o in (2):
            try:
                row[o] = int(float(row[o]))
            except:
                continue
        
        try:    
            db.findings.insert_one({
                '_id': # need to ask devs for guidance on this one
                "rva_id": row[1],
                "ncats_id": row[2],
                "severity": row[3],
                "service": row[4],
                "man/tool": row[5],
                "internal/external": row[6],
                "std_text_modify": row[7],
                "default_finding_name": row[8],
                "default_finding_severity": row[9],
                "custom_finding_name": row[10],
                "asmt_type": row[11],
                "fy": row[12],
                "mitigated_status": row[13],
                "mitigation_req_date": row[14],
                'mitigation_response_date': row[15],
                'fed/sltt/ci': row[16],
                'ci_subtype': row[17],
                'NIST_800-53': [row[18],row[19],row[20],row[21]]
                'NCSF': [row[22],row[23],row[24],row[25],row[26]]
            })
            domains_processed += 1
        except:
            print row[0] + ' is already a key in the DB'

    print('Successfully imported {} documents to "{}" database on {}'.format(domains_processed, db.name, db.client.address[0]))

def main():
    global __doc__    
    __doc__ = re.sub('COMMAND_NAME', __file__, __doc__)
    args = docopt(__doc__, version='v0.0.1')
    db = database.db_from_config(args['--section'])
    
    creds()
    prep_and_import_csv(db)
    
if __name__=='__main__':
    main()