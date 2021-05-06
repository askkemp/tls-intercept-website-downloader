#!/usr/bin/python3
# Built in Python 3.8
__author__ = "Kemp Langhorne"
__copyright__ = "Copyright (C) 2021 AskKemp.com"
__license__ = "agpl-3.0"
__version__ = "v1.0"

from pathlib import Path
import requests
import logging
import argparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

#
# API CONFIGURATION SECTION
#
# Fill out this section with output of Cloudformation API URL and the API key present in each regions API Gateway
# Example:
#   {'ap-northeast-1': {'name': 'Asia Pacific (Tokyo)',
#                       'key': "abcdefg",
#                       'url': "https://1234567890.execute-api.ap-northeast-1.amazonaws.com/Prod/websitedownloader/"
#                      }
AWS_API_DATA = [
    {'af-south-1':     {'name': 'Africa (Cape Town)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-east-1':      {'name': 'Asia Pacific (Hong Kong)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-northeast-1': {'name': 'Asia Pacific (Tokyo)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-northeast-2': {'name': 'Asia Pacific (Seoul)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-northeast-3': {'name': 'Asia Pacific (Osaka)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-south-1':     {'name': 'Asia Pacific (Mumbai)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-southeast-1': {'name': 'Asia Pacific (Singapore)',
                        'key': None,
                        'url': None
                       }
    },
    {'ap-southeast-2': {'name': 'Asia Pacific (Sydney)',
                        'key': None,
                        'url': None
                       }
    },
    {'ca-central-1':   {'name': 'Canada (Central)',
                        'key': None,
                        'url': None
                       }
    },
    {'cn-north-1':     {'name': 'China (Beijing)',
                        'key': None,
                        'url': None
                       }
    },
    {'cn-northwest-1': {'name': 'China (Ningxia)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-central-1':   {'name': 'Europe (Frankfurt)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-north-1':     {'name': 'Europe (Stockholm)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-south-1':     {'name': 'Europe (Milan)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-west-1':      {'name': 'Europe (Ireland)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-west-2':      {'name': 'Europe (London)',
                        'key': None,
                        'url': None
                       }
    },
    {'eu-west-3':      {'name': 'Europe (Paris)',
                        'key': None,
                        'url': None
                       }
    },
    {'me-south-1':     {'name': 'Middle East (Bahrain)',
                        'key': None,
                        'url': None
                       }
    },
    {'sa-east-1':      {'name': 'South America (São Paulo)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-east-1':      {'name': 'US East (N. Virginia)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-east-2':      {'name': 'US East (Ohio)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-gov-east-1':  {'name': 'AWS GovCloud (US-East)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-gov-west-1':  {'name': 'AWS GovCloud (US-West)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-west-1':      {'name': 'US West (N. California)',
                        'key': None,
                        'url': None
                       }
    },
    {'us-west-2':      {'name': 'US West (Oregon)',
                        'key': None,
                        'url': None
                       }
    }
]

#
# Script Starts Below
#

# logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO) # DEBUG is all the data
logging.debug("Script starting...")
logging.getLogger('urllib3').setLevel(logging.INFO)

def available_apis():
    """
    Provides a list of all configured AWS api endpoints

    Args:
        None
    Returns:
        list of dicts e.g. [{'ap-northeast-1': {'name': 'Asia Pacific (Tokyo)', 'key': 'xy', 'url': 'https://abc-api.ap-northeast-1.amazonaws.com/Prod/websitedownloader/'}}]
    """

    available_apis_list = []
    for item in AWS_API_DATA:
        for region, data in item.items():
            if data['key'] and data['url']:
                temp_dict = {}
                temp_dict[region] = data
                available_apis_list.append(temp_dict)

    return available_apis_list

def get_api_info(region_name):
    """
    Given a AWS region name, return API information

    Args:
        region_name (str): AWS region name

    Returns
        tuple
        [0] boolean, If region is available
        [1] None or str of API Key for region
        [2] None or str of API URL for region
        [3] str of region which is the same as the input region
    """
    region_available, regionapi, regionurl = False, None, None
    for item in available_apis():
        for region, data in item.items():
            if region_name == region:
                region_available = True
                regionapi = data['key']
                regionurl = data['url']
    return (region_available, regionapi, regionurl, region_name)

def display_useragent_options(apikey, apiurl, apiregion):
    """
    Connects to the AWS Gateway API to collect available user-agent options.
    These options are used by the user when defining the website download job.

    Args:
        apikey (str): AWS API key for url
        apiurl (str): AWS API url
        apiregion (str): AWS region name
    Returns:
        None but prints output to stdout
    """
    print(apiregion + ":")

    # Body going to the API
    request_body = {}

    # Info Request - all availale user-agents
    request_body['display_useragents'] = True

    r = requests.post(apiurl,
                             headers={'x-api-key': apikey},
                             json=request_body
                            )
    # logging.debug(f'Outbound request body: {r.request.body}')

    if r.status_code == requests.codes.ok:
        response_dict =  r.json() # e.g. {'message': {'firefox_nt10': '"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0"'}}
        print("{:<20} USER-AGENT".format("OPTION"))

        for k, v in response_dict['message'].items():
            print(f"{k: <20} {v}")
    else:
        logging.error(r.text)

def sqs_autoscaling_stats(apikey, apiurl, apiregion):
    """
    Connects to twice separately to the AWS Gateway API to:
    1. Print the status of the SQS Queue
    2. Print the status of the EC2 Autoscaling group

    Args:
        apikey (str): AWS API key for url
        apiurl (str): AWS API url
        apiregion (str): AWS region name
    Returns:
        None but prints output to stdout
    """
    print(apiregion + ":")
    #
    # 1. SQS
    #
    # Body going to the API
    request_body = {}

    # Stats Request - SQS
    request_body['sqs_queue_stats'] = True

    r = requests.post(apiurl,
                             headers={'x-api-key': apikey},
                             json=request_body
                            )
    #logging.debug(f'Outbound request body: {r.request.body}')

    if r.status_code == requests.codes.ok:
        response_dict = r.json() # e.g. {'message': {'ApproximateNumberOfMessages': '0', 'ApproximateNumberOfMessagesNotVisible': '0', 'ApproximateNumberOfMessagesDelayed': '0'}}
        print(f"  * Jobs waiting in queue: {response_dict['message']['ApproximateNumberOfMessages']}")
        print(f"  * Jobs currently being worked: {response_dict['message']['ApproximateNumberOfMessagesNotVisible']}")
    else:
        logging.error(r.text)

    #
    # 2. Autoscaling
    #
    # Body going to the API
    request_body = {}

    # Stats Request - EC2 Autoscaling
    request_body['autoscaling_status'] = True

    r = requests.post(apiurl,
                             headers={'x-api-key': apikey},
                             json=request_body
                            )
    #logging.debug(f'Outbound request body: {r.request.body}')

    if r.status_code == requests.codes.ok:
        response_dict = r.json() # e.g. {'message': {'MinSize': 0, 'MaxSize': 3, 'DesiredCapacity': 0, 'instances': []}}
        print(f"  * Number of running EC2 workers: {response_dict['message']['DesiredCapacity']}")
        print(f"  * Max number of allowed EC2 workers: {response_dict['message']['MaxSize']}")
        print(f"  * State of EC2 workers:")
        for instance in response_dict['message']['instances']:
            print(f"                         {instance}")
    else:
        logging.error(r.text)

    return


def submit_website_download_job(apikey, apiurl, input_url, input_useragent, input_recursivelevel, input_forceipver, input_wgetmode):
    """
    Connects to AWS Gateway API to to submit a website download job

    Args:
        apikey (str): AWS API key for url
        apiurl (str): AWS API url
        input_url (str): full url
        input_useragent (str): option value mapping and not actual full user-agent
        input_recursivelevel (str): 1-9
        input_forceipver (str): ipv6 or ipv4
        input_wgetmode (str): singlepage or recursive

    Returns:
         touple s3_link, s3_filename
           s3_link (str): AWS S3 pre-signed URL to download file from S3
           s3_filename (str): Name of file within S3 e.g. 33fbce02-20e6-4120-b955-c79cc4126c0e.tar.gz'
    """

    # Body going to the API
    request_body = {}

    # Download Website
    request_body['downloadjob'] = True
    request_body['downloadjob_details'] = {}
    request_body['downloadjob_details']['url'] = input_url
    request_body['downloadjob_details']['useragent'] = input_useragent
    request_body['downloadjob_details']['recursivelevel'] = input_recursivelevel
    request_body['downloadjob_details']['forceipver'] = input_forceipver
    request_body['downloadjob_details']['wgetmode'] = input_wgetmode

    r = requests.post(apiurl,
                             headers={'x-api-key': apikey},
                             json=request_body
                            )
    logging.debug(f'Outbound request body: {r.request.body}')
    logging.debug(r.request.headers)

    if r.status_code == requests.codes.ok:
        response_dict = r.json()    # e.g. {"status": "failure", "message": "Input URL did not validate. E.g. must start with http:// or https://"}
                                    # e.g. {'status': 'success', 'url': 'https://website-download.s3.amazonaws.com/...', 'filename': '33fbce02-20e6-4120-b955-c79cc4126c0e-regionname.tar.gz',
        logging.debug(response_dict)

        s3_link = response_dict["url"]
        s3_filename = response_dict["filename"]

    else: # something wrong
        logging.error(r.text)
        s3_link = None
        s3_filename = None

    return s3_link, s3_filename

def download_file(signed_url, output_filename):
    """Downloads file from an AWS S3 signed URL.
    The URL will exist before the job and its file is uploaded to S3.
    This code continuously checks if the file is available using a back_off interval.

    Args:
        signed_url (str):
        output_filename (str):

    Returns:
        None but prints output to stdout
    """
    print(f"* Continously checking for download availability at URL: {signed_url}")

    filetest = Path(output_filename) # create pathlib object
    if filetest.is_file(): # file exists
        print("Error: Output file already exists. Will not overwrite. Provided URL is still valid to download job results.")
        return

    http = requests.Session()
    retries = Retry(total=12, backoff_factor=10, status_forcelist=[404])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = http.get(signed_url, timeout=5)
        logging.debug(response.headers)

        if response.status_code == requests.codes.ok:
            with open(output_filename, 'wb') as w:
                w.write(response.content)
            print(f"* Job results downloaded to: {filetest.absolute()}")
        else:
            logging.error(f"Unknown error. Unable to download content from link. HTTP status code: {response.status_code}")

    except Exception as e:
        logging.error(e)
        print("Unable to download job results from URL. This could be because the job is still running or because the job has failed. Try the URL again later and if it still does not work, the job likely failed. Contact your system administrator.")

    return

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description='\
Overview:\n\
Given a URL, downloads its contents and record all network data (proxy logs, pcap) with transparent SSL/TLS\n\
interception. This all occurs on an AWS EC2 instance using Wget and SSLsplit. Each download will occur from\n\
a newly created EC2 instance and should have a different public IP address. All contents from the dowlnoad\n\
are archived, put into an S3 bucket, and a download link provided. This script will poll the download link\n\
until the file appears and download it to disk. The contents of the archive contain proxy logs, pcap,\n\
wget logs, application logs, SSL certificates, and all files downloaded by Wget.\n\
\n\
    Download type:\n\
      1. Recursive   - Follow links and directory stucture. The level of recursion must be defined. This option is the\n\
                       equivalent of https://www.gnu.org/software/wget/manual/wget.html#Recursive-Download.\n\
                       Warning: Too high a level of recursion will cause a very large amount of data to dowlnoad.\n\
      2. Single page - Download all files needed to display the webpage. This includes images, css, files, etc. \n\
                       This option is equivalent to Wget option --page-requisites.\n\
\n\
    IP version option:\n\
      Force connecting to the URL on its IPv6 or IPv4 addresses.\n\
\n\
    User-agent:\n\
      Control which User-agent will be used to connect to the URL. Options are fixed and can be determined by running\n\
      --useragentoptions.\n\
\n\
    AWS regions:\n\
      Discover which AWS regions are configured to use this script by running --regionoptions\n\
\n\
Examples:\n\
    Download all content (images, css, etc.) from single page  using IPv4, a specific user agent and from AWS region Tokyo:\n\
        $ %(prog)s --url https://www.google.com --ipversion ipv4 --type singlepage --useragent firefox_nt10 --awsregion ap-northeast-1 \n\
\n\
    Download a whole lot of content recursively from http://mirror.centos.org/centos/8/AppStream/ utilzing an EC2 instance in Tokyo:\n\
        $ %(prog)s --ipversion ipv4 --type recursive --recursivelevel 2 --url http://mirror.centos.org/centos/8/AppStream/  --useragent firefox_nt10 --awsregion ap-northeast-1\n\
\n\
')

    groupA = parser.add_argument_group("Download Type")
    groupA.add_argument('--type',
                        required=False,
                        dest='in_downloadtype',
                        choices=['singlepage', 'recursive'],
                        help='Download type')

    groupB = parser.add_argument_group("Download Options")
    groupB.add_argument('--url',
                        required=False,
                        action='store',
                        dest='in_url',
                        metavar='',
                        help='URL to download')

    groupB.add_argument('--ipversion',
                        required=False,
                        dest='in_ipversion',
                        choices=['ipv4', 'ipv6'],
                        help='Force connecting to the URL on its IPv6 or IPV4 addresses')

    groupB.add_argument('--useragent',
                        action='store',
                        required=False,
                        dest='in_useragent',
                        metavar='<option name>',
                        help='User-agent to connect to the URL. See --useragentoptions for options.')

    groupB.add_argument('--recursivelevel',
                        action='store',
                        required=False,
                        #type=int,
                        dest='in_recursivelevel',
                        metavar='<1-9>',
                        help='Use with recursive download type. A number to define the level of recursion. The higher the number, the more recursion.')

    groupB.add_argument('--awsregion',
                        required=False,
                        dest='in_awsregion',
                        choices=['all-regions',
                                 'us-east-2',
                                 'us-east-1',
                                 'us-west-1',
                                 'us-west-2',
                                 'af-south-1',
                                 'ap-east-1',
                                 'ap-south-1',
                                 'ap-northeast-3',
                                 'ap-northeast-2',
                                 'ap-southeast1',
                                 'ap-southeast-2',
                                 'ap-northeast-1',
                                 'ca-central-1',
                                 'cn-north-1',
                                 'cn-northwest-1',
                                 'eu-central-1',
                                 'eu-west-1',
                                 'eu-west-2',
                                 'eu-south-1',
                                 'eu-west-3',
                                 'eu-north-1',
                                 'me-south-1',
                                 'sa-east-1',
                                 'us-gov-east-1',
                                 'us-gov-west-1'],
                        help='AWS region to conduct download from. See --regionoptions for enabled regions.')

    groupC = parser.add_argument_group("Additonal Features")
    groupC.add_argument('--useragentoptions',
                        required=False,
                        dest='in_useragentoptions',
                        action='store_true',
                        help='Display all available user-agent options')

    groupC.add_argument('--status',
                        required=False,
                        dest='in_status',
                        action='store_true',
                        help='Display overall application status')

    groupC.add_argument('--regionoptions',
                        required=False,
                        dest='in_regionoptions',
                        action='store_true',
                        help='Display which AWS regions are available to use this script ')

    args = parser.parse_args()

    if args.in_downloadtype and not args.in_awsregion:
        parser.error("--awsregion must be specified with --type")

    if args.in_downloadtype and not args.in_url:
        parser.error("--url must be specified with --type")

    if args.in_downloadtype and not args.in_useragent:
        parser.error("--useragent must be specified with --type")

    if args.in_downloadtype and not args.in_ipversion:
        parser.error("--ipversion must be specified with --type")

    if args.in_url and not args.in_awsregion:
        parser.error("--url must be specified with --awsregion")

    if args.in_url and not args.in_downloadtype:
        parser.error("--type must be specified with --url")

    if args.in_useragent and not args.in_url:
        parser.error("--url  must be specified with --useragent")

    if args.in_downloadtype == "recursive" and not args.in_recursivelevel:
        parser.error("Download type rescursive requires --recursivelevel")

    if args.in_status and not args.in_awsregion:
        parser.error("Status requires --awsregion")

    if args.in_useragentoptions and not args.in_awsregion:
        parser.error("User agent options requires --awsregion")

    if not args.in_downloadtype and not args.in_useragentoptions and not args.in_status and not args.in_awsregion and not args.in_regionoptions:
        parser.error("Improper combination of options.")

    if args.in_awsregion:
        api_info = get_api_info(region_name=args.in_awsregion)
        if api_info[0] == False and not args.in_awsregion == "all-regions": # True if api is enabled for the region provided by the user
            parser.error("Provided AWS Region is not enabled. See --regionoptions for enabled regions.")

    # Submit Download Job
    if args.in_downloadtype and args.in_awsregion and args.in_url and args.in_useragent and args.in_ipversion:
        if args.in_awsregion == "all-regions":
            download_urls_list = [] # holds list of all pre-signed URLs that need to be downloaded
            for item in available_apis(): # kick off download jobs for each region
                for region, data in item.items():
                    print(f'Submitting job for {region}')
                    job_file_url, job_filename = submit_website_download_job(apikey=data['key'], apiurl=data['url'], input_url=args.in_url, input_useragent=args.in_useragent, input_recursivelevel=args.in_recursivelevel, input_forceipver=args.in_ipversion, input_wgetmode=args.in_downloadtype)
                    if job_file_url and job_filename: # Download file
                        download_urls_list.append((job_file_url, job_filename)) # add touple to list
            # Download files
            for url, filename in download_urls_list:
                download_file(signed_url=url, output_filename=filename)
        else:
            job_file_url, job_filename = submit_website_download_job(apikey=api_info[1], apiurl=api_info[2], input_url=args.in_url, input_useragent=args.in_useragent, input_recursivelevel=args.in_recursivelevel, input_forceipver=args.in_ipversion, input_wgetmode=args.in_downloadtype)
            if job_file_url and job_filename: # Download file
                download_file(signed_url=job_file_url, output_filename=job_filename)

    # UA options
    if args.in_useragentoptions and args.in_awsregion:
        if args.in_awsregion == "all-regions":
            for item in available_apis():
                for region, data in item.items():
                    display_useragent_options(apikey=data['key'], apiurl=data['url'], apiregion=region)
        else:
            display_useragent_options(apikey=api_info[1], apiurl=api_info[2])

    # Get Status
    if args.in_status and args.in_awsregion:
        if args.in_awsregion == "all-regions":
            for item in available_apis():
                for region, data in item.items():
                    sqs_autoscaling_stats(apikey=data['key'], apiurl=data['url'], apiregion=region)
        else:
            sqs_autoscaling_stats(apikey=api_info[1], apiurl=api_info[2], apiregion=api_info[3])

    # Show enabled AWS Regions
    if args.in_regionoptions:
        print("{:20s} {:30s} {:20s}".format("Region Name", "AWS Region", "Status"))
        for item in available_apis():
            for region, data in item.items():
                if data['key'] and data['url']:
                    print("{:20s} {:30s} {:20s}".format(region, data['name'], "API Enabled"))

if __name__ == "__main__":
    main()