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

import csv
import re
import subprocess

from cyhy.db import database
import dateutil.parser
from docopt import docopt


FMT = '%m/%d/%y %H:%M'
JIRA_FILE = 'exported-rva-data.csv'


# Pull the data fresh from JIRA
def grab_csv_from_jira(filter):
    f = open('../account.txt', 'r')
    lines = f.readlines()
    username = lines[0].rstrip()
    password = lines[1].rstrip()
    f.close()

    subprocess.call([
        'curl -k {}:{} https://jira.ncats.cyber.dhs.gov/sr/jira.issueviews:'
        'searchrequest-csv-current-fields/{}/SearchRequest-{}.csv\?'
        'delimiter\=, -o {}'.format(
            username, password, filter, filter, JIRA_FILE
        )
    ], shell=True)


# Strip out custom fields & consolidate column names
def prep_and_import_csv(db):
    assessments = open(JIRA_FILE)
    # Create a writer so we have a list of our unique agencies
    domains_processed = 0

    firstline = True
    for row in csv.reader(assessments):
        if firstline:    # skip first line
            firstline = False
            continue
        # parse the line
        for j in (2, 3, 4, 8, 9, 11, 13, 18, 33, 41, 43, 50):
            row[j] = dateutil.parser.parse(row[j])
        for k in (5, 6, 20):
            if row[k].upper() == 'TRUE':
                row[k] = True
            elif row[k].upper() == 'FALSE':
                row[k] = False
            else:
                row[k] = None
        for o in (19, 40, 42):
            try:
                row[o] = int(float(row[o]))
            except ValueError:
                continue

        # 'Summary','Status','Created','Updated','Appendix A Date',
        # 'Appendix A Signed','Appendix B Signed','Assessment Type',
        # 'External Testing Begin Date','External Testing End Date',
        # 'Group/Project','Internal Testing Begin Date',
        # 'Internal Testing City','Internal Testing End Date','Mgmt Req',
        # 'POC Email','POC Name','POC Phone','ROE Date','ROE Number',
        # 'ROE Signed','_id','Asmt Name','Requested Services1',
        # 'Requested Services2','Requested Services3','Requested Services4',
        # 'Requested Services5','Requested Services6','Requested Services7',
        # 'Requested Services8','Stakeholder Name','State',
        # 'Testing Complete Date','Testing Phase','Election','Testing Sector',
        # 'CI Type', 'CI Systems', 'Fed Lead','Contractor Operator Count',
        # 'Draft w/ POC Date','Fed Operator Count','Report Final Date',
        # 'Operator1', 'Operator2', 'Operator3', 'Operator4', 'Operator5',
        # 'Stakeholder ID','Testing Begin Date'
        try:
            db.rva.insert_one({
                '_id': row[21],  # switched with 21
                "status": row[1],
                "created": row[2],
                "updated": row[3],
                "appendix_a_date": row[4],
                "appendix_a_signed": row[5],
                "appendix_b_signed": row[6],
                "assessment_type": row[7],
                "external_testing_begin_date": row[8],
                "external_testing_end_date": row[9],
                "group": row[10],
                "internal_testing_begin_date": row[11],
                "internal_testing_city": row[12],
                "internal_testing_end_date": row[13],
                "mgmt_req": row[14],
                'poc_email': row[15],
                'poc_name': row[16],
                'poc_phone': row[17],
                'roe_date': row[18],
                'roe_number': row[19],
                'roe_signed': row[20],
                "summary": row[0],
                'asmt_name': row[22],
                'requested_services': [
                    row[23], row[24], row[25], row[26],
                    row[27], row[28], row[29], row[30]
                ],
                'stakeholder_name': row[31],
                'state': row[32],
                'testing_complete_date': row[33],
                'testing_phase': row[34],
                'election': row[35],
                'testing_sector': row[36],
                'ci_type': row[37],
                'ci_systems': row[38],
                'fed_lead': row[39],
                'contractor_operator_count': row[40],
                'draft_poc_date': row[41],
                'fed_operator_count': row[42],
                'report_final_date': row[43],
                'operators': [
                    row[44], row[45], row[46], row[47], row[48]
                ],
                'stakeholder_id': row[49],
                'testing_begin_date': row[50]
            })
            domains_processed += 1
        except:
            # It seems awfully presumptuous to assume the problem is
            # that the key is already in the database, since you're
            # literally catching any possible exception here.
            #
            # I suggest that you only catch the specific exception
            # that indicates a duplicate key here.  I would change it
            # myself, but I don't know what exception that is.
            #
            # jsf9k
            print(row[0] + ' is already a key in the DB')

    print('Successfully imported {} documents to "{}" database on {}'.format(
        domains_processed, db.name, db.client.address[0]
    ))


def main():
    global __doc__
    __doc__ = re.sub('COMMAND_NAME', __file__, __doc__)
    args = docopt(__doc__, version='v0.0.1')
    db = database.db_from_config(args['--section'])

    grab_csv_from_jira(args['FILTER'])
    prep_and_import_csv(db)


if __name__ == '__main__':
    main()
