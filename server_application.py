#!/usr/bin/python3
# Built in Python 3.8
__author__ = "Kemp Langhorne"
__copyright__ = "Copyright (C) 2021 AskKemp.com"
__license__ = "agpl-3.0"

import subprocess
import logging
import json
#import argparse
import tarfile
from pathlib import Path
#import boto3
from botocore.exceptions import ClientError
from boto3.session import Session
from watchtower import CloudWatchLogHandler
from ec2_metadata import ec2_metadata, NetworkInterface
from urllib.parse import urlparse # url validation
import os # for environment variable access and file size collection

#
# DYNAMIC CONFIGURATION SECTION
#
AWS_CLOUDWATCH_LOG_GROUP = os.environ['ENV_CLOUDWATCH_LOG_GROUP']
AWS_CLOUDWATCH_LOG_STREAM = f'{ec2_metadata.instance_id}-{ec2_metadata.region}' # e.g. i-0d4276fc8ab7dee65-eu-west-1
#AWS_SQS_QUEUE_NAME = "website_downloader_jobs"
AWS_SQS_URL = os.environ['ENV_SQS_URL']
AWS_S3_BUCKET_NAME = os.environ['ENV_S3_BUCKET_NAME']


#
# START SCRIPT
# 

# AWS boto3 session set for Cloudwatch, SQS, S3
boto3_session = Session(region_name=ec2_metadata.region) # requires region to be set

# AWS Cloudwath setup as log handler
logger = logging.getLogger()
logging.getLogger('botocore').setLevel(logging.INFO)
logging.getLogger('s3transfer').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)
cloudwatch_handler = CloudWatchLogHandler(create_log_group=False, create_log_stream=True, log_group=AWS_CLOUDWATCH_LOG_GROUP,stream_name=AWS_CLOUDWATCH_LOG_STREAM,boto3_session=boto3_session)
console_handler = logging.StreamHandler()
logger.addHandler(cloudwatch_handler)
logger.addHandler(console_handler)

logging.debug(f"EC2 instance metadata: Type: {ec2_metadata.instance_type} Region: {ec2_metadata.region} | Interface MAC: {ec2_metadata.mac} | Public IPv4: {ec2_metadata.public_ipv4} | Private IPv4: {ec2_metadata.private_ipv4} | Global IPv6: {NetworkInterface(ec2_metadata.mac).ipv6s}")

def sqs_delete_message(sqs_queue_url, receipt_handle):
    """Delete message from sqs queue"""
    # Return to SQS that the job is done
    try:
        sqs.delete_message(
            QueueUrl = sqs_queue_url,
            ReceiptHandle = receipt_handle
        )
    except ClientError as e:
        logging.error(f"ERROR on sqs delete message: {e}")
    except Exception as e:
        logging.error(f"ERROR on sqs delete message: {e}")
    return

def do_shutdown():
    """Use subprocess to shutdown the host"""

    # Option 1 - Linux shutdown. Auto scale group will create new instance
    # Notice it will stay up for 1 minute after shutdown initated
    #logging.debug("Shutdown method: Shutting down host via Linux shutdown command...")
    #subprocess.run(['sudo shutdown -h +1'], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    # Option 2 - print that it would shutdown i.e. it is done
    #logging.debug("Shutdown method: NOT shutting down...")
    #print("-->WOULD HAVE SHUTDOWN HERE<---")

    # Option 3 - Use AWS API to terminate the instance and decrease the desired capacity
    logging.debug("Shutdown method: Terminating instance...")

    cloudwatch_handler.flush()
    cloudwatch_handler.close()
    #subprocess.run(['sudo systemctl restart rsyslog'], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True) # flush all syslog queues to disk?
    autoscale = boto3_session.client('autoscaling')
    response = autoscale.terminate_instance_in_auto_scaling_group(
        InstanceId=ec2_metadata.instance_id,
        ShouldDecrementDesiredCapacity=True
    )

    exit() # otherwise it will run other parts of the script that dont need to now be ran
    return

# Check if proxy is running
proxystate = subprocess.run(["systemctl", "is-active", "--quiet", "sslsplit"])
if proxystate.returncode != 0:
    logging.error(f"ERROR: Proxy not running!")
    do_shutdown()

# Create SQS client
sqs = boto3_session.client('sqs')

# Pull SQS queue stats
queue_status = sqs.get_queue_attributes(
    QueueUrl=AWS_SQS_URL,
    AttributeNames=['All']
)
logging.debug(f"SQS queue status: ApproximateNumberOfMessages: {queue_status['Attributes']['ApproximateNumberOfMessages']} ApproximateNumberOfMessagesNotVisible: {queue_status['Attributes']['ApproximateNumberOfMessagesNotVisible']} ApproximateNumberOfMessagesDelayed: {queue_status['Attributes']['ApproximateNumberOfMessagesDelayed']}")

# Get item from SQS queue
try:
    sqs_messages = sqs.receive_message(
        QueueUrl=AWS_SQS_URL,
        MessageAttributeNames=['All'],
        MaxNumberOfMessages=1,
        WaitTimeSeconds=1
    )

    if sqs_messages.get('Messages'): # key only appears if there is a message
        sqs_ReceiptHandle = sqs_messages['Messages'][0]['ReceiptHandle'] # Taking first from list and should only be one item in list
        sqs_id = sqs_messages['Messages'][0]['MessageId'] # output to disk will use this value
        sqs_body = json.loads(sqs_messages['Messages'][0]['Body'])

        sqs_url = sqs_body['url']['StringValue']
        sqs_useragent = sqs_body['useragent']['StringValue']
        sqs_force_ip_version = sqs_body['force_ip_version']['StringValue']
        sqs_wget_mode = sqs_body['wget_mode']['StringValue'] # singlepage or recursive
        sqs_recursive_level = sqs_body['recursive_level']['StringValue'] # str

        logging.debug(f"SQS job: {sqs_id} {sqs_force_ip_version} {sqs_url} {sqs_useragent} {sqs_wget_mode} {sqs_recursive_level}")

        # Check for bad values
        # Input Validation for job
        if not sqs_useragent: # missing user-agent
            logging.error("ERROR: Missing user-agente value")
            sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
            do_shutdown()
        if sqs_recursive_level: # only exists with recursive job otherwise None
            if int(sqs_recursive_level) < 1 or int(sqs_recursive_level) > 20: # i.e. infinite recursion or very high
                msg = "ERROR: Neither infinite nor very high recursion is enabled"
                sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
                do_shutdown()
        if sqs_wget_mode != "singlepage" and sqs_wget_mode != "recursive":
            logging.error("ERROR: Mode must be singlepage or recursive")
            sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
            do_shutdown()
        if sqs_force_ip_version != "ipv4" and sqs_force_ip_version != "ipv6":
            logging.error("ERROR: Force ip version must be ipv4 of ipv6")
            sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
            do_shutdown()
        urlcheck = urlparse(sqs_url) # validate URL
        if not all([urlcheck.scheme, urlcheck.netloc]):
            logging.error("ERROR: URL did not validate. E.g. must start with http:// or https://")
            sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
            do_shutdown()
    else:
        logging.error(f"ERROR: Forcing shutdown due to: Nothing in SQS queue")
        do_shutdown()

except ClientError as error:
    logging.error(f"ERROR: Forcing shutdown due to: {error}")
    do_shutdown()

except Exception as error:
    logging.error(f"ERROR: Forcing shutdown due to: {error}")
    do_shutdown()

# Output locations
job_root = "/website_download/" # must end in /
debug_path = job_root + "debug/"
certificate_path = job_root + "certificates/"
wget_path = job_root + "wget_saved/" # wget will auto make this directory
output_targz_path = job_root
output_targz_filename = sqs_id + '-' + ec2_metadata.region + '.tar.gz'

# Post processing SQS message: wget IP protocol forcing
if sqs_force_ip_version == "ipv4":       # wget connect only to IPv4 addresses
    ip_version_command = "--inet4-only" 
if sqs_force_ip_version == "ipv6":     # wget connect only to IPv6 addresses
    ip_version_command = "--inet6-only"

# Build wget command
wget_options_list = []
wget_options_list.append("sudo")         # 1
wget_options_list.append("-u")           # 1
wget_options_list.append("proxy_client") # 1 ensure app starts as correct user so iptables rules work
wget_options_list.append("wget")
wget_options_list.append(ip_version_command)
#wget_options_list.append(f"--output-file={debug_path}wget.log") # Log all messages to logfile.  The messages are normally reported to standard error.
wget_options_list.append("--no-check-certificate") # Don't check the server certificate against the available certificate authorities.  Also don't require the URL host name to match the common name presented by the certificate.
wget_options_list.append(f"--directory-prefix={wget_path}") # Location to save files
wget_options_list.append("--force-directories") # Create a hierarchy of directories for downloaded content
wget_options_list.append("-e")         # 2
wget_options_list.append("robots=off") # 2 Does not download robots.txt for that domain
wget_options_list.append(f"--user-agent={sqs_useragent}") # Custom UA

if sqs_wget_mode == "singlepage":
    wget_options_list.append("--page-requisites") # causes Wget to download all the files that are necessary to properly display a given HTML page
    wget_options_list.append("--span-hosts") # Recursive to other domains besides just the domain within the url provided to wget. Will pull content for any host referenced by a link, image, etc. --recursive does not need to be set up for this work.

if sqs_wget_mode == "recursive":
    wget_options_list.append("--recursive") # Turn on recursive retrieving
    wget_options_list.append(f"--level={sqs_recursive_level}") # Recursion maximum depth level depth. The default maximum depth is 5 which is A LOT!

wget_options_list.append(sqs_url)

logging.debug(f'wget command: {wget_options_list}')


# Website Download
try: 
    popen = subprocess.Popen(wget_options_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True) # stderror combined with stdout
    output_of_interest = ["Saving to:", "saved", "FINISHED", "Downloaded"]

    # All log lines go to a file and the ones needed for real-time monitoring go to Cloudwatch
    for stdout_line in iter(popen.stdout.readline, ""):
        with open(debug_path + "wget.log", "a+") as wget_f: # append if exists
            wget_f.write(stdout_line)
            if any(x in stdout_line for x in output_of_interest):
                logging.debug(f'wget output: {stdout_line}') # will go to Cloudwatch
    popen.stdout.close()
    returncode = popen.wait()

# Specific exit codes
    wget_exit = {}
    wget_exit[0] = 'No problems occurred'
    wget_exit[1] = 'Generic error code'
    wget_exit[2] = 'Parse error'
    wget_exit[3] = 'File I/O error'
    wget_exit[4] = 'Network failure'
    wget_exit[5] = 'SSL verification failure' # need to us --no-check-certificate
    wget_exit[6] = 'Username/password authentication failure'
    wget_exit[7] = 'Protocol errors'
    wget_exit[8] = 'Server issued an error response' # will fire when doing recursive when server 404s

    # taking action on exit code 1 and 3
    if returncode == 1 or returncode == 3:
        logging.error(f"ERROR: wget with exit code {returncode}:{wget_exit.get(returncode)}")

    # Not taking action all other exit codes. Just logging.
    if returncode != 0:
        logging.error(f"ERROR when running options {wget_options_list} with exit code {returncode}:{wget_exit.get(returncode)}")

except Exception as e:
    logging.error(f"ERROR: Exception running wget subprocess: {e}")

# Make the internet-side certificates human readable
# Only should occure when files are present which means there was a ssl connection
if len(list(Path(debug_path + "/certificates/").rglob('*.crt'))) > 0: # directory contains certs
    try:
        result = subprocess.run(f'for file in {debug_path}/certificates/[A-Z0-9]???????????????????????????????????????.crt; do openssl x509 -in "$file" -text > "$file".text; mv "$file".text {certificate_path}; done', shell=True, capture_output=True, text=True)
        logging.debug(f"Certificate transform stdout: {result.stdout} stderr: {result.stderr}" )
    except Exception as e:
        logging.error(f"ERROR: Exception running openssl subprocess: {e}")

# Compress folder
def set_permissions(tarinfo):
    """Changes information in the created tar. Security by obscurity."""
    tarinfo.uname = "user"
    tarinfo.gname = "group"
    tarinfo.uid = 0
    tarinfo.gid = 0
    return tarinfo

try:
    finished_job_size = sum(f.stat().st_size for f in Path(job_root).glob('**/*') if f.is_file()) >> 20 # Get size of and log. This is mainly for troubleshooting purposes.
    logging.debug(f'Compressing job results of {finished_job_size}MB into {output_targz_path + output_targz_filename}')
    with tarfile.open(output_targz_path + output_targz_filename, mode='w:gz') as archive:
        archive.add(job_root, recursive=True, arcname=output_targz_filename.replace('.tar.gz', ''), filter=set_permissions)
        logging.debug(f"Archive written to: {output_targz_path + output_targz_filename}")
        logging.debug(f'Size of job results tar.gz: {os.path.getsize(output_targz_path + output_targz_filename) >> 20}MB') # Get size of and log. This is mainly for troubleshooting purposes.
except Exception as e:
    logging.error(f"ERROR creating job output tar.gz: {e}")
    do_shutdown()

# Upload the tar.gz into s3
s3_client = boto3_session.client('s3')

try:
    s3_client.upload_file(output_targz_path + output_targz_filename, AWS_S3_BUCKET_NAME, output_targz_filename)
    logging.info(f"Uploaded to S3: {s3_client.meta.endpoint_url}/{AWS_S3_BUCKET_NAME}/{output_targz_filename}")
except ClientError as e:
    logging.error(f"ERROR uploading job {output_targz_filename} to s3 {AWS_S3_BUCKET_NAME}. Error: {e}")
except Exception as e:
    logging.error(f"ERROR uploading job {output_targz_filename} to s3 {AWS_S3_BUCKET_NAME}. Error: {e}")

# All is complete
sqs_delete_message(AWS_SQS_URL, sqs_ReceiptHandle)
do_shutdown()