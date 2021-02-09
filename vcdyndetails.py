import sys
import argparse
import logging
import json
import datetime
import csv
from typing import List

import mdutils.mdutils as mdu
import anticrlf
#from veracode_api_py import VeracodeAPI as vapi
from helpers.api import VeracodeAPI as vapi

log = logging.getLogger(__name__)

def setup_logger():
    handler = logging.FileHandler('vcdyndetails.log', encoding='utf8')
    handler.setFormatter(anticrlf.LogFormatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'))
    logger = logging.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def creds_expire_days_warning():
    creds = vapi().get_creds()
    exp = datetime.datetime.strptime(creds['expiration_ts'], "%Y-%m-%dT%H:%M:%S.%f%z")
    delta = exp - datetime.datetime.now().astimezone() #we get a datetime with timezone...
    if (delta.days < 7):
        print('These API credentials expire ', creds['expiration_ts'])

def get_app(app_guid):
    return vapi().get_app(app_guid)

def get_findings(app_info, cwes:List[int], categories:List[int]):
    log.info('Getting findings for application {} (guid {})'.format(app_info['profile']['name'],app_info['guid']))
    all_findings = []

    if cwes != None:
        for cwe in cwes:
            params = {'cwe': cwe}
            these_findings = vapi().get_findings(app_info['guid'],scantype='DYNAMIC',annot='FALSE',request_params=params)
            all_findings.extend(these_findings)
    elif categories != None:
        for cat in categories:
            params = { 'finding_category': cat}
            these_findings = vapi().get_findings(app_info['guid'],scantype='DYNAMIC',annot='FALSE',request_params=params)
            all_findings.extend(these_findings)
    else:
        these_findings = vapi().get_findings(app_info['guid'], scantype='DYNAMIC', annot='FALSE')
        all_findings.extend(these_findings)

    return all_findings

def get_request_response(findings_list):
    # build a list of dicts containing the detailed finding info and request/response
    log.info('Getting finding details...')
    finding_details_list = []

    for finding in findings_list: 
        log.info('Getting finding details for flaw {})'.format(finding['issue_id']))
        finding_details = { 'finding': finding }
        finding_request_response = vapi().get_dynamic_flaw_info(finding['context_guid'],finding['issue_id'])
        finding_details['request_response'] = finding_request_response
        finding_details_list.append(finding_details)
    return finding_details_list

def write_findings_to_md(appinfo,findings_details_list):
    status = 'Writing findings information to vcdyndetails.md....'
    print(status)
    log.info(status)
    mdfile = mdu.MdUtils(file_name='vcdyndetails.md',title='Veracode Dynamic Findings Details')
    mdfile.new_paragraph("This document shows dynamic finding information and request/response information from Veracode.")
    mdfile.new_header(level=1, title="Application: {}".format(appinfo['profile']['name']),add_table_of_contents='n')
    # mdfile.new_table_of_contents(table_title='Table of Contents',depth=2)
    for finding in findings_details_list:
        fin = finding['finding']
        rr = finding['request_response']
        mdfile.new_header(level=2, title="Finding {}, CWE {}".format(fin['issue_id'],fin['finding_details']['cwe']['id']),add_table_of_contents='n')
        mdfile.new_paragraph('**First Found**: {}'.format(fin['finding_status']['first_found_date']))
        mdfile.new_paragraph('**Last Seen**: {}'.format(fin['finding_status']['last_seen_date']))
        mdfile.new_paragraph('**Hostname:Port**: {}:{}'.format(fin['finding_details']['hostname'],fin['finding_details']['port']))
        mdfile.new_paragraph('**Path**: {}'.format(fin['finding_details']['path']))
        mdfile.new_paragraph('**Vulnerable Parameter**: {}'.format(fin['finding_details']['vulnerable_parameter']))
        mdfile.new_paragraph("**Description**: {}".format(rr['issue_summary']['description']))
        mdfile.new_paragraph("**Recommendation**: {}".format(rr['issue_summary']['recommendation']))
        mdfile.new_header(level=3, title="Request",add_table_of_contents='n')
        vectors = rr['dynamic_flaw_info']['request']['attack_vectors']
        for vector in vectors:
            mdfile.new_paragraph("**Attack Vector**: {} ({})".format(vector['name'],vector['type']))
            mdfile.new_paragraph("**Original Value**: {}".format(vector['original_value']))
            mdfile.new_paragraph("**Injected Value**: {}".format(vector['injected_value']))
        mdfile.insert_code(rr['dynamic_flaw_info']['request']['raw_bytes'],language='text')
        mdfile.new_paragraph('')
        mdfile.new_header(level=3, title="Response",add_table_of_contents='n')
        mdfile.insert_code(rr['dynamic_flaw_info']['response']['raw_bytes'],language='html')
        mdfile.new_paragraph('')
    mdfile.create_md_file()


def main():
    parser = argparse.ArgumentParser(
        description='This script lists modules in which static findings were identified.')
    parser.add_argument('-a', '--application', required=True, help='Application guid to check for dynamic findings.')
    parser.add_argument('-w', '--cwe', required=False, type=int, nargs='+',help='List of CWEs to include in the output.') 
    parser.add_argument('-g', '--category', required=False, type=int, nargs='+', help='List of categories to include in the output.') 

    args = parser.parse_args()

    appguid = args.application
    cwelist = args.cwe
    categorylist = args.category
    setup_logger()

    # CHECK FOR CREDENTIALS EXPIRATION
    creds_expire_days_warning()

    status = "Checking application {} for a list of findings".format(appguid)
    log.info(status)
    print(status)

    appinfo = get_app(appguid)

    findings_list = get_findings(appinfo,cwelist,categorylist)

    findings_details = get_request_response(findings_list)

    write_findings_to_md(appinfo,findings_details)
    
if __name__ == '__main__':
    main()