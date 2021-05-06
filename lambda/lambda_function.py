#!/usr/bin/python3
# Built in Python 3.8
__author__ = "Kemp Langhorne"
__copyright__ = "Copyright (C) 2021 AskKemp.com"
__license__ = "agpl-3.0"

import logging
from urllib.parse import urlparse # url validation
from boto3.session import Session
from botocore.exceptions import ClientError
import json
import os # for environment variable access

# logging setup
logger = logging.getLogger()
logger.setLevel(logging.DEBUG) # DEBUG is all the data
logging.debug("Script starting...")
logging.getLogger('botocore').setLevel(logging.INFO)
logging.getLogger('s3transfer').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)

#
# DYNAMIC CONFIGURATION SECTION
#
AWS_S3_BUCKET_NAME = os.environ['ENV_S3_BUCKET_NAME']
AWS_S3_LINK_EXPIRATION = os.environ['ENV_S3_LINK_EXPIRATION']  # amount of seconds that S3 presigned URL will be valid to download file
AWS_AUTOSCALE_ADD_CAPACITY_ARN = os.environ['ENV_ADD_CAPACITY_POLICY_ARN']
AWS_AUTOSCALEGROUP_NAME = os.environ['ENV_AUTOSCALEGROUP_NAME']
AWS_SQS_URL = os.environ['ENV_SQS_URL']
AWS_REGION = os.environ['AWS_REGION'] # provided by AWS itself

#
# START SCRIPT
# 

# AWS boto3 session set for SQS, S3, EC2
boto3_session = Session() # determins region on its own
s3_client = boto3_session.client('s3')
sqs_client = boto3_session.client('sqs')
autoscaling_client = boto3_session.client('autoscaling')

# create_presigned_url heavily based on https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html#presigned-urls
def create_presigned_url(bucket_name, object_name, expiration=AWS_S3_LINK_EXPIRATION):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    # The response contains the presigned URL
    return response
def sqs_queue_stats():
    """ Pull SQS queue stats and extract specific key value pairs

    Returns:
        dict of specific sqs que attributes 
        
        Example: {'ApproximateNumberOfMessages': '3', 'ApproximateNumberOfMessagesNotVisible': '0', 'ApproximateNumberOfMessagesDelayed': '0'}

    """

    queue_status = sqs_client.get_queue_attributes(
            QueueUrl=AWS_SQS_URL,
            AttributeNames=['All']
        )

    return {'ApproximateNumberOfMessages': queue_status['Attributes']['ApproximateNumberOfMessages'], 'ApproximateNumberOfMessagesNotVisible': queue_status['Attributes']['ApproximateNumberOfMessagesNotVisible'], 'ApproximateNumberOfMessagesDelayed': queue_status['Attributes']['ApproximateNumberOfMessagesDelayed']}

def sqs_add_job(input_url, input_useragent, input_recursivelevel, input_forceipver, input_wgetmode):
    """
    Connects to AWS Gateway API to to submit a website download job

    Args:
        input_url (str):
        input_useragent (str):
        input_recursivelevel (str):
        input_forceipver (str):
        input_wgetmode (str):

    Returns:
         json str with keys

         Example:
             {"status": "success", "jobid": "c57120e1-6fb5-45d0-b4df-79a21c3e6be9"}
             {"status": "failure", "message": "Input URL did not validate. E.g. must start with http:// or https://"}
    """

    # Body going to the API
    request_body = {
        'url': {
            'DataType': 'String',
            'StringValue': input_url
        },
        'useragent': {
            'DataType': 'String',
            'StringValue': input_useragent
        },
        'recursive_level': {
            'DataType': 'Number',
            'StringValue': input_recursivelevel # String of whole number. For the Number data type, you must use StringValue.
        },
        'force_ip_version': {
            'DataType': 'String',
            'StringValue': input_forceipver
        },
        'wget_mode': {
            'DataType': 'String',
            'StringValue': input_wgetmode # singlepage or recursive
        }
    }

    logging.debug(request_body)

    output_dict = {} # captures information that gets returned by function

    # Send message to SQS queue
    response_dict = sqs_client.send_message(
        QueueUrl=AWS_SQS_URL,
        MessageBody=json.dumps(request_body)
    ) # e.g. {'MD5OfMessageBody': '8e2316817500d9e2705433ed0de0649c', 'MessageId': 'c57120e1-6fb5-45d0-b4df-79a21c3e6be9', 'ResponseMetadata': {'RequestId': '7e4525cb-f45f-563a-969c-7d2855adca94', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': '7e4525cb-f45f-563a-969c-7d2855adca94', 'date': 'Sun, 04 Apr 2021 11:14:58 GMT', 'content-type': 'text/xml', 'content-length': '378'}, 'RetryAttempts': 0}}

    job_id = response_dict['MessageId']
    return job_id

def start_ec2_instance():
    """Uses the boto3 autoscaling client to execute a policy. The defined policy adds another EC2 instance."""

    response = autoscaling_client.execute_policy(
            #AutoScalingGroupName=AWS_AUTOSCALEGROUP_NAME, # Not needed when submitting ARN as policy name
            HonorCooldown=False,
            PolicyName=AWS_AUTOSCALE_ADD_CAPACITY_ARN,
        )
    return 

def autoscaling_status():
    """Uses boto3 to collect details on the EC2 autoscaling and presents a smaller view of the results"""

    autoscaling_details = autoscaling_client.describe_auto_scaling_groups()

    for group in autoscaling_details['AutoScalingGroups']:
        if group['AutoScalingGroupName'] == AWS_AUTOSCALEGROUP_NAME:
            temp_list = []
            if len(group['Instances']) > 0:
                for instance in group['Instances']:
                    temp_list.append(instance['InstanceId'] +", "+ instance['InstanceType'] +", "+ instance['LifecycleState'])
                     
            output_dict = {"MinSize": group['MinSize'], "MaxSize": group['MaxSize'], "DesiredCapacity": group['DesiredCapacity'], "instances": temp_list }

    return output_dict

def lambda_handler(event, context):
    """
    AWS Lambda function handler

    Args:
        event: dict, contains input from AWS API Gateway
        context

    Returns:
        json string

    """

    s_code = 200 # default http status set
    msg = "" # default to blank

    outputlist = [] # contains results for each jarm creation
    outputdict = {} # final results

    try:
        input_job = json.loads(event['body']) # from AWS API Gateway

    except Exception as e:
        outputdict['status'] = "failure"
        outputdict['message'] = f"Unable to parse data received from AWS API Gateway. Error: {e}"
        input_job = {} # blank so no below conditions match
        s_code = 400

    # Map raw user-agent to requested
    # User-agents should be maintained reguarly
    user_agent = {}
    user_agent['firefox_nt10'] = r'''Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0'''
    user_agent['chrome_nt10'] = r'''Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'''
    user_agent['edgechromium_nt10'] = r'''Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51'''

    # https://developers.google.com/search/docs/advanced/crawling/overview-google-crawlers
    user_agent['googlebot_desktop'] = r'''Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)''' # Googlebot Desktop
    user_agent['google_favicon'] = r'''Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36 Google Favicon'''# Google Favicon
    user_agent['google_image'] = r'''Googlebot-Image/1.0''' # Google image

    # https://help.yahoo.com/kb/search/slurp-crawling-page-sln22600.html
    user_agent['yahoo_slurp'] = r'''Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)''' # Yahoo Search robot Slurp

    # https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0
    user_agent['bing_bingbot'] = r'''Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)''' # Bingbot standard crawler

    # https://help.baidu.com/question?prod_id=99&class=476&id=2996
    user_agent['baidu_baiduspider'] = r'''Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)''' # PC search UA

    # https://yandex.com/support/webmaster/robot-workings/check-yandex-robots.html
    user_agent['yandex_main'] = r'''Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)''' # main indexing robot
    user_agent['yandex_favicon'] = r'''Mozilla/5.0 (compatible; YandexFavicons/1.0; +http://yandex.com/bots)''' # Downloads the sites favicon

    # https://developers.facebook.com/docs/sharing/webmasters/crawler
    user_agent['facebook_crawler'] = r'''facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'''

    if input_job.get('sqs_queue_stats') == True:
        try:
            outputdict['message'] = sqs_queue_stats()
        except Exception as e:
            outputdict['status'] = "failure"
            outputdict['message'] = f'ERROR: {str(e)}'
            s_code = 400

    elif input_job.get('autoscaling_status') == True:
        try:
            outputdict['message'] = autoscaling_status()
        except Exception as e:
            outputdict['status'] = "failure"
            outputdict['message'] = f'ERROR: {str(e)}'
            s_code = 400

    elif input_job.get('display_useragents') == True:
        outputdict['message'] = user_agent # return entire UA dict 

    elif input_job.get('downloadjob') == True:
        dl_job = input_job['downloadjob_details']
        provided_url = dl_job['url']
        provided_useragent = dl_job['useragent']
        provided_recursivelevel = dl_job['recursivelevel']
        provided_forceipver = dl_job['forceipver']
        provided_wgetmode = dl_job['wgetmode']

        # Input Validation for job
        if provided_recursivelevel: # only exists with recursive job otherwise None
            if int(provided_recursivelevel) < 1 or int(provided_recursivelevel) > 20: # i.e. infinite recursion or very high
                msg = "ERROR: Neither infinite nor very high recursion is enabled"

        if provided_wgetmode != "singlepage" and provided_wgetmode != "recursive":
            msg = "ERROR: Mode must be singlepage or recursive"

        if provided_forceipver != "ipv4" and provided_forceipver != "ipv6":
            msg = "ERROR: Force ip version must be ipv4 of ipv6"

        if provided_useragent not in user_agent.keys():
            msg = "ERROR: Non-supported user-agent provided"

        urlcheck = urlparse(provided_url) # validate URL
        if not all([urlcheck.scheme, urlcheck.netloc]):
            msg = "ERROR: URL did not validate. E.g. must start with http:// or https://"

        # Optional: Prevent the SQS queue from being too large. 
        # This could be due to a user trying to download 100s of sites at one time. This prevents additional jobs.
        if int(sqs_queue_stats()['ApproximateNumberOfMessages']) > 10:
            msg = "ERROR: Queue to large. You must wait."

        if msg: # there was a input validation or queue size issue
            outputdict['status'] = "failure"
            outputdict['message'] = msg
            s_code = 400

        else: # ALL GOOD
            # Based on user provided input, create job 
            try:
                sqs_job = sqs_add_job(input_url=provided_url,
                                  input_useragent=user_agent[provided_useragent], # Custom UA mapping
                                  input_recursivelevel=provided_recursivelevel,
                                  input_forceipver=provided_forceipver,
                                  input_wgetmode=provided_wgetmode
                                 )

                # Start up EC2 instance
                start_ec2_instance()

                # Create pre-signed S3 URL so user can download file. Must match format of filename in server_application.py
                s3filename = sqs_job + '-' + AWS_REGION + '.tar.gz' # file does not have to exist in S3 when created url created. It will provide access when file is created.
                presigned_url = create_presigned_url(AWS_S3_BUCKET_NAME, s3filename)
                #import urllib3
                #http = urllib3.PoolManager()
                #r = http.request('GET', presigned_url)

                outputdict['status'] = "success"
                outputdict['url'] = presigned_url
                outputdict['filename'] = s3filename
                #outputdict['extra']= str(r.data)
            except Exception as e:
                outputdict['status'] = "failure"
                outputdict['message'] = f'ERROR: {str(e)}'
                s_code = 400

    else: # Nothing matched in input dict
        outputdict['status'] = "failure"
        outputdict['message'] = "ERROR parsing input"
        s_code = 400

    return {"statusCode": s_code, \
        "headers": {"Content-Type": "application/json"}, \
        "body": json.dumps(outputdict)}