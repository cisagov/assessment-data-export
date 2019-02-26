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

FMT = '%m/%d/%y %H:%M'

# Pull the data fresh from JIRA
def grab_csv_from_jira(filter):
    f = open('account.txt','r')
    lines = f.readlines()
    username = lines[0]
    password = lines[1]
    f.close()
    # TODO 12603 - make sure last column shows (will need to be consolidated)
    # TODO add username and password
    subprocess.call(['curl -k {0}:{0} https://jira.ncats.cyber.dhs.gov/sr/jira.issueviews:searchrequest-csv-current-fields/{0}/SearchRequest-{0}.csv\?delimiter\=, -o exportedReport.csv'.format(username,password,filter,filter)], shell=True)

# Strip out custom fields & consolidate column names
def csv_refining():
    inputFileName = "exportedReport.csv"
    outputFileName = os.path.splitext(inputFileName)[0] + "_modified.csv"

    with open(inputFileName, 'rb') as inFile, open(outputFileName, 'wb') as outfile:
        r = csv.reader(inFile)
        w = csv.writer(outfile)

        next(r, None)  # skip the first row from the reader, the old header
        # write new header
        w.writerow(['Summary','Status','Created','Updated','Appendix A Date','Appendix A Signed','Appendix B Signed','Assessment Type','External Testing Begin Date','External Testing End Date','Group/Project','Internal Testing Begin Date','Internal Testing City','Internal Testing End Date','Mgmt Req','POC Email','POC Name','POC Phone','ROE Date','ROE Number','ROE Signed','_id','Asmt Name','Requested Services1','Requested Services2','Requested Services3','Requested Services4','Requested Services5','Requested Services6','Requested Services7','Requested Services8','Stakeholder Name','State','Testing Complete Date','Testing Phase','Election','Testing Sector', 'CI Type', 'CI Systems', 'Fed Lead','Contractor Operator Count','Draft w/ POC Date','Fed Operator Count','Report Final Date','Operator1', 'Operator2', 'Operator3', 'Operator4', 'Operator5','Stakeholder ID','Testing Begin Date'])

        # copy the rest
        for row in r:
            # Date row for strings into datetimes
            for cell in (3, 4, 5, 9, 10, 11, 12, 14, 18, 34):
                try:
                    row[cell-1] = datetime.strptime(row[cell-1], FMT).isoformat()
                except:
                    pass
            # Boolean row for strings into bools     
            for cell in (6, 7, 21):
                if row[cell-1] != '':
                    if row[cell-1] == 'True':
                        row[cell-1] = True
                    elif row[cell-1] == 'False':
                        row[cell-1] = False
            
            w.writerow(row)
            
        print '\n\nSuccessfully modified\n\n'
    
def import_csv_to_mongo(db):
    # mongoimport -d mydb -c rvaInput --type csv --file exportedReport.csv --headerline
    
    #import IPython; IPython.embed() #<<< BREAKPOINT >>>
    subprocess.call('mongoimport -d mydb -c rvaInput --type csv --file exportedReport_modified.csv --headerline'.format(db.name), shell=True)
    return 0
    
def change_ids_and_arrays(db):
    collection = db.rva
    
    for i in collection.find():
        print i        
        doc = i
        old_id = i['_id']
    
        requested_services = [
            i['Requested Services1'],
            i['Requested Services2'],
            i['Requested Services3'],
            i['Requested Services4'],
            i['Requested Services5'],
            i['Requested Services6'],
            i['Requested Services7'],
            i['Requested Services8']
        ]
    
        operators = [
            i['Operator1'],
            i['Operator2'],
            i['Operator3'],
            i['Operator4'],
            i['Operator5']
        ]
    
        # insert the document, using the new _id
        del doc['Requested Services1']
        del doc['Requested Services2']
        del doc['Requested Services3']
        del doc['Requested Services4']
        del doc['Requested Services5']
        del doc['Requested Services6']
        del doc['Requested Services7']
        del doc['Requested Services8']
        del doc['Operator1']
        del doc['Operator2']
        del doc['Operator3']
        del doc['Operator4']
        del doc['Operator5']
        
        collection.remove({'_id': old_id})
        collection.remove({'_id': doc['_id']})
        
        try:
            collection.insert(doc)
        except:
            collection.remove({'_id': doc['_id']})
            
        # mycollection.update({'_id':mongo_id}, {"$set": post}, upsert=False)
        for j in ['Mgmt Req','Appendix A Signed','ROE Signed']:
            if i[j].upper() == 'FALSE':
                collection.update({'_id':doc['_id']}, {'$set': {j:0}}, upsert=False)
                #i.update({'$set':{j:0}})
            elif i[j].upper() == 'TRUE':
                collection.update({'_id':doc['_id']}, {'$set': {j:0}}, upsert=False)
                #i.update({'$set':{j:1}})
        
        for k in ['External Testing End Date','External Testing Begin Date','Created','Internal Testing End Date','Internal Testing Begin Date','Testing Begin Date','Testing Complete Date','ROE Date','Updated']:
            collection.update({'_id': doc['_id'] },{'$set' : {k:datetime.strptime(doc[k], "%Y-%m-%d")}})
    
        collection.update({'_id': doc['_id'] },{'$set' : {'Requested Services':requested_services}})
        collection.update({'_id': doc['_id'] },{'$set' : {'Operators':operators}})
        
def sector_FY_stats():
    return 0

def main():
    global __doc__    
    __doc__ = re.sub('COMMAND_NAME', __file__, __doc__)
    args = docopt(__doc__, version='v0.0.1')
    db = database.db_from_config(args['--section'])
    
    grab_csv_from_jira(args['FILTER'])
    csv_refining()
    import_csv_to_mongo(db)
    change_ids_and_arrays(db)
    
if __name__=='__main__':
    main()