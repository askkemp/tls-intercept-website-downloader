# Introduction
Utilize a client-side Python script to download the contents of a URL using an AWS hosted application. The application conducts MitM tls-intercept to provide complete proxy logs, x509 certificates, and pcap. The results and files of the website download are provided to the client.

# Features
* Automatically deployable to any [AWS region](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html#concepts-available-regions) using [AWS Serverless Application Model (SAM)](https://aws.amazon.com/serverless/sam/) and easily tunable by changing `template.yaml`
* Download request initiates from client-side python script and results downloaded when the job is complete
* Supports single page or recursive downloads
* Force the use of IPv4 or IPv6
* Provides status of job and full Cloudwatch logging
* Unique public IP address for each download
* Specify desired user-agent
* Website downloads can total more than 1TB
* Choose which region to download from or download from all AWS regions at the same time
* Completed jobs available from S3 using pre-signed URL (i.e. anyone with the link can download it)
* Issue and control API keys via automatically generated usage plan
* Automatically generates inital API key
* Control autoscaling size and EC2 instance configuration
* Unlimited number of jobs can be ran in parallel

# Components
The application utilizes AWS Simple Queue Service (SQS), Lambda, API Gateway, Cloudwatch, AWS EC2 with autoscaling and launch templates. A general diagram of how the AWS components connect is below.
<img src="./diagram.png" height="400" />

The scripts within this repository serve the following functions. 
#### `client.py`
Script used locally by the client to create website download jobs and get job status. It communicates with `lambda/lambda_function.py` via the AWS API Gateway. Features include:
* Various website download command line options:
  * Download a single page with all contents on the page needed to display it correctly OR recursively
  * Specify an AWS region for the website download job OR have all AWS regions conduct the same job at nearly the same time
  * Force the connection to the URL to be over IPv4 or IPv6
  * Specify user-agent
  * Get general job status from a single or all regions at the same time
* Will continously attempt to download the job output file from API provided [S3 presigned URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html) using a backoff timer

#### `lambda/lambda_function.py`
AWS hosted Lambda function that receives requests from `client.py` via the AWS API Gateway. It can:
* Process the download request and place it into an Simple Queue Service (SQS) queue
* Run an EC2 Autoscaling policy to provide an EC2 instance to process the job
* Create an [S3 presigned URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html) to for `client.py` to use to download the completed job
* Provide overall status of jobs
* Provide listing of user-agents that can be used for website download jobs

#### `server_application.py`
Runs as service in Systemd on Amazon EC2 and conducts the website download. It is launched by `client.py` running an autoscale policy. Its workflow is: 
* Gets a download job from the SQS queue
* Builds a command argument based on input originating from `client.py` and executes [Wget](https://www.gnu.org/software/wget/manual/wget.html)
* Converts captures x509 certificates into a human readable format
* Compresses all contents into a tar.gz and upload it to S3. Contents include:
  * Files downloaded with Wget
  * unencrypted PCAP, HTTP(s) sessions (streams), proxy logs, x509 certificates
  * Application debug logs (Wget, SSLsplit, `server_application.py`)
* Logs in real-time to Cloudwatch
* Self-terminate EC2 instance and reduce the desired size of the autoscaling group

#### `server_install.sh`
A script executed by each launched EC2 instance which installs all necessary applications. It set within the UserData launchtemplate in `template.yml`. It:
* Creates necessary user accounts, groups, folders, and permissions
* Install pre-req applications
* Generates needed certificates for SSLsplit
* Uses iptables to create ipv4 and ipv6 rules to force all traffic for specific user accounts to go through SSLsplit
* Installs and runs [SSLsplit](https://www.roe.ch/SSLsplit) for man-in-the-middle capture of proxy logs, certificates, and pcap
* Installs and runs `server_application.py`

#### `template.yml`
A [AWS Serverless Application Model (SAM)](https://aws.amazon.com/serverless/sam/) designed to easily deployable to any desired AWS region. It creates:
* Lambda function and its additional IAM roles
* API Gateway with usage plan and pre-created random API key
* SQS queue
* Custom IAM roles and IAM profile for EC2 instances
* Cloudwatch log group
* EC2 launch template
* EC2 autoscaling group and necessary Cloudwatch alarms for autoscaling policy
* S3 bucket with 1 day file expiration
* Creates VPC with internet gateway, proper routes, and supports IPv4 and IPv6


# Quick Start
### Install
The application is automatically deployed utilizing AWS SAM. [Install](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) the proper command line tool for your OS. The only necessary configuration step is to configurae AWS credentials (there no need to install Docker). 

Clone a copy of this repository to the location you want to run the client from (`client.py`)
```bash
$ git clone https://github.com/askkemp/tls-intercept-website-downloader.git
```

Within the cloned repo, run [sam build](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html) to prepare the application to be deployed to the cloud. Note that this command must run each time you change something within `template.yml`.
```bash
$ sam build 
```

Run [sam deploy](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html) in guided mode to deploy the application. Default variable names are provided and can be utilized. Note that one of the variables is the destination AWS region eu-central-1. The output of the deployment is the url to the api endpoint. 
```bash
$ sam deploy --guided  --stack-name WebsiteDownloader --capabilities CAPABILITY_NAMED_IAM

Configuring SAM deploy
======================

        Looking for config file [samconfig.toml] :  Not found

        Setting default arguments for 'sam deploy'
        =========================================
        Stack Name [WebsiteDownloader]:
        AWS Region [eu-central-1]:
        Parameter sqsQueueBaseName [website_downloader_jobs]:
        Parameter s3BucketBaseName [website-downloader-output-files]:
        Parameter CloudWatchLogGroupBaseName [website-downloader-logs]:
        Parameter AutoScalingAutoScalingGroupName [website-downloader-Autoscale]:
        Parameter LatestAmiId [/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2]:
        #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
        Confirm changes before deploy [y/N]: Y
        #SAM needs permission to be able to create roles to connect to the resources in your template
        Allow SAM CLI IAM role creation [Y/n]: Y
        Save arguments to configuration file [Y/n]: n

        Looking for resources needed for deployment: Not found.
        Creating the required resources...

...

CloudFormation outputs from deployed stack
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Outputs
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Key                 APIURL
Description         Place this URL into client.py
Value               https://fml3qgqfd6.execute-api.eu-central-1.amazonaws.com/Prod/websitedownloader/
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Successfully created/updated stack - WebsiteDownloader in eu-central-1
```

### `client.py` Configure
The output of the above deployment is the API endpoint url that goes into `client.py`. Below is an example of a completed configuration within `client.py` for region eu-central-1. To understand where the API key can be found, see the FAQ.

```python
    {'eu-central-1':   {'name': 'Europe (Frankfurt)',
                        'key': "asd1234,
                        'url': "https://fml3qgqfd6.execute-api.eu-central-1.amazonaws.com/Prod/websitedownloader/"
                       }
    },
```

If it is setup correctly, then a status query against the AWS region will provide results. For example, like the below.
```bash
$ python3 client.py --status --awsregion eu-central-1
eu-central-1:
  * Jobs waiting in queue: 0
  * Jobs currently being worked: 0
  * Number of running EC2 workers: 0
  * Max number of allowed EC2 workers: 2
  * State of EC2 workers:
```

### Download Website
With the application deployed and `client.py` configured with the API url and key, a website download job can be submitted. The below example is downloading google.com from an EC2 instances in eu-central. Utilize the information in `client.py --help` to understand options and examples.

```bash
$ python3 client.py --url https://www.google.com --ipversion ipv4 --type singlepage --useragent firefox_nt10 --awsregion eu-central-1
* Continously checking for download availability at URL: https://website-downloader-output-files-eu-central-1-647080127563.s3.amazonaws.com/7562fa93-0a49-448c-89c6-8cc489bb54fd-eu-central-1.tar.gz?AWSAccessKeyId=ASIAZNKH3FRFSZV7VXNL&Signature=OV8...
* Job results downloaded to: /home/user/tls-intercept-website-downloader/7562fa93-0a49-448c-89c6-8cc489bb54fd-eu-central-1.gz
```

The contents of the provided tar.gz are extracted and a tree view of its contents shown.
```bash
$ tar xzf /home/user/tls-intercept-website-downloader/7562fa93-0a49-448c-89c6-8cc489bb54fd-eu-central-1.gz
$ tree 7562fa93-0a49-448c-89c6-8cc489bb54fd-eu-central-1
7562fa93-0a49-448c-89c6-8cc489bb54fd-eu-central-1
├── certificates
│   └── F0487A59653433F8A192C6C4FB9ACCC5AD0CB3E2.crt.text
├── debug
│   ├── cacrt.pem
│   ├── ca_priv_key.pem
│   ├── certificates
│   │   ├── E04EA93EFD444880B0222B4D4A85197EAB4D75EB.key
│   │   ├── F0487A59653433F8A192C6C4FB9ACCC5AD0CB3E2.crt
│   │   └── F0487A59653433F8A192C6C4FB9ACCC5AD0CB3E2-E7D1E02888FCB4BA0D030EFE9D93194E471E6374.crt
│   ├── server_daemon.log
│   ├── SSLKEYLOGFILE
│   ├── sslsplit_daemon.log
│   └── wget.log
├── proxy.log
├── proxy.pcap
├── proxy_streams
│   └── 20210502T170505Z-192.168.0.134,41314-172.217.161.36,443.log
└── wget_saved
    └── www.google.com
        ├── images
        │   ├── branding
        │   │   └── googlelogo
        │   │       └── 2x
        │   │           └── googlelogo_color_272x92dp.png
        │   ├── experiments
        │   │   └── wavy-underline.png
        │   └── searchbox
        │       └── desktop_searchbox_sprites302_hr.png
        ├── index.html
        └── xjs
            └── _
                └── js
                    └── k=xjs.s.ja.p_6j1u8Fhq0.O
                        └── m=cdos,cr,dpf,hsm,jsa,d,csi
                            └── am=gIEIAAAAIGCgAAAAABIBAAAAAAAUAMlgRACA4hkAAAEwBACSIxAAAABMYA0A8B8EAFzAJQYAAAAAAATQEmiUGpAICEAAAAAAWV2YAEGA
                                └── d=1
                                    └── ed=1
                                        └── dg=2
                                            └── rs=ACT90oFaeMwYxkDmf3tMtjaGkVv57zzIVA

21 directories, 18 files
```


# FAQ
**Where does the API key and url come from?**

The API key and URL are configured in `client.py`. The URL is provided as output when deploying this application with AWS SAM. Otherwise, go into the [AWS Management Console](https://aws.amazon.com/console/), select the desired region, then the API Gateway. Click the API created by AWS SAM which will be called `Website-Downloader-{aws region name}`. To get the key, click "API Keys" on the navigation and open the "WebsiteDownloaderAPIKey" key. The URL is listed under Stages. Click `Prod` and at the top of the page is the URL. Both the key and url go into `client.py` for the region in question.

**How to change user-agent?**

The user-agents are hard-coded into `lambda/lambda_function.py` and can be added and changed easily. The `client.py` has an argument to query the API to show which user-agents are available. In other words, whatever is put into `lambda/lambda_function.py` will be usable by `client.py`.

**What initiates the application and install in the EC2 instances?**

The configuration for the application install is controled within `template.yml` under `UserData` for the launch template.

**How do I kill a job?**
 
A job will run until it is complete or until the storage on the EC2 instance runs out of space. The only way to kill a job is to manualy terminate the EC2 instance. Knowing which instance to terminate can be determined by looking at the Cloudwatch logs and seeing if it contains the URL in question.

**What is logged by the EC2 in Cloudwatch?**
 
The EC2 instance logs:
  * The public IP address (IPv4 / IPv6), mac address, instance type, region
  * Number of jobs in the SQS queue
  * Configuration of the job
  * Constucted Wget command
  * Real-time specific Wget logs (e.g. when a file starts to download and when it is finished)
  * Total size of downloaded contents
  * Total size of compressed tar.gz archive
  * When the file is updated to S3
  * When the EC2 instance terminates 

# License for this project

    agpl-3.0
