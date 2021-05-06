#!/bin/bash
# Website Downloader server build script
# Author = "Kemp Langhorne"
# copyright = "Copyright (C) 2021 AskKemp.com"
# license = "agpl-3.0"

# Add proper users
useradd -r proxy_client # all wget traffic comes from this user
useradd -r proxy_server # sslplit runs as this user

# to ensure files can be written/read
groupadd proxy          
usermod -a -G proxy proxy_client
usermod -a -G proxy proxy_server
usermod -a -G proxy ec2-user
#newgrp proxy # Use when not running as script so ec2-user does not have to relogin. Mainly for testing.

# Required applications
amazon-linux-extras install epel python3.8 -y
yum install sslsplit iptables-services -y
pip3.8 install boto3 ec2-metadata watchtower

# Create job storage location
mkdir /website_download
chown root:proxy /website_download/
chmod g+w /website_download/
chmod g+s /website_download/
setfacl -d -m g::rwx /website_download/
mkdir /website_download/proxy_streams/
mkdir /website_download/debug/
mkdir /website_download/debug/certificates/
mkdir /website_download/certificates/

# Proxy certificate for interception
openssl req -new -newkey rsa:1024 -sha256 -days 4000 -nodes -x509 -subj "/C=US/ST=CO/L=Southpark/O=Dis/CN=www.notreal.com" -keyout /website_download/debug/ca_priv_key.pem -out /website_download/debug/cacrt.pem
openssl x509 -in /website_download/debug/cacrt.pem -outform DER -out /website_download/debug/cacrt.der
mv /website_download/debug/cacrt.der /etc/pki/ca-trust/source/anchors/cacrt.der
update-ca-trust extract

# Only user root can go direct to the internet. Local processes go through OUTPUT chain.
# ipv4
iptables -t nat -F
iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 8080 -j REDIRECT --to-port 9080
iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 80 -j REDIRECT --to-port 9080
iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 443 -j REDIRECT --to-port 9443

service iptables save
systemctl enable iptables
systemctl start iptables

# ipv6
ip6tables -t nat -F
ip6tables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 8080 -j REDIRECT --to-port 9080
ip6tables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 80 -j REDIRECT --to-port 9080
ip6tables -t nat -A OUTPUT -p tcp -m owner --uid-owner proxy_client --dport 443 -j REDIRECT --to-port 9443

service ip6tables save
systemctl enable ip6tables
systemctl start ip6tables


# Syslog monitoring
echo ':programname, isequal, "sslsplit" /website_download/debug/sslsplit_daemon.log
& stop' > /tmp/sslsplit.conf
cp /tmp/sslsplit.conf /etc/rsyslog.d/sslsplit.conf

echo ':programname, isequal, "websitedownloader" /website_download/debug/server_daemon.log
& stop' > /tmp/websitedownloader.conf
cp /tmp/websitedownloader.conf /etc/rsyslog.d/websitedownloader.conf
systemctl restart rsyslog

# SSLSPLIT service
echo '
[Unit]
Description=sslsplit proxy
After=network.target

[Service]
SyslogIdentifier=sslsplit
Type=simple
User=root
ExecStart=/usr/bin/sslsplit -u proxy_server -D -k /website_download/debug/ca_priv_key.pem  -l /website_download/proxy.log -c /website_download/debug/cacrt.pem  -S /website_download/proxy_streams -X /website_download/proxy.pcap -M /website_download/debug/SSLKEYLOGFILE -W /website_download/debug/certificates/ -Z  ssl 0.0.0.0 9443 tcp 0.0.0.0 9080 ssl ::1 9443 tcp ::1 9080
KillSignal=SIGINT
FinalKillSignal=SIGTERM

[Install]
WantedBy=multi-user.target' > /tmp/sslsplit.service
cp /tmp/sslsplit.service /etc/systemd/system/sslsplit.service

systemctl daemon-reload
systemctl enable sslsplit
systemctl start sslsplit

# Get python file to server

# websitedownloader service
echo '
[Unit]
Description=websitedownloader
After=sslsplit.service

[Service]
SyslogIdentifier=websitedownloader
Type=simple
EnvironmentFile=/etc/sysconfig/wdenv.conf
User=ec2-user
ExecStart=/usr/bin/python3.8 /home/ec2-user/tls-intercept-website-downloader/server_application.py
KillSignal=SIGINT
FinalKillSignal=SIGTERM

[Install]
WantedBy=multi-user.target' > /tmp/websitedownloader.service
cp /tmp/websitedownloader.service /etc/systemd/system/websitedownloader.service
systemctl daemon-reload
systemctl enable websitedownloader
systemctl start websitedownloader
