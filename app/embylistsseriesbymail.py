# Name: embylistseriesbymail
# Coder: Marco Janssen (mastodon @marc0janssen@mastodon.online)
# date: 2024-02-25 20:36:00
# update: 2024-02-25 20:36:00

import imaplib
import email
import re
import logging
import sys
import configparser
import shutil
import smtplib
import os
from pathlib import Path

from datetime import datetime
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# from email.mime.base import MIMEBase
# from email import encoders
from socket import gaierror
from chump import Application


class ELBE():

    def __init__(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO)
        # allow directory overrides via environment variables
        config_dir = os.getenv("EMBYLISTS_CONFIG_DIR", "/config/")
        app_dir = os.getenv("EMBYLISTS_APP_DIR", "/app/")
        log_dir = os.getenv("EMBYLISTS_LOG_DIR", "/var/log/")

        self.config_file = "embylists.ini"
        self.exampleconfigfile = "embylists.ini.example"
        self.log_file = "embylistsseriesbymail.log"
        self.serieslist = "serieslist.txt"
        self.seriesdvlist = "seriesdvlist.txt"

        # use pathlib for paths
        self.config_filePath = Path(config_dir) / self.config_file
        self.log_filePath = Path(log_dir) / self.log_file
        self.list_filePath = Path(config_dir) / self.serieslist
        self.listdv_filePath = Path(config_dir) / self.seriesdvlist

        try:
            if not self.config_filePath.exists():
                logging.error(
                    f"Can't open file {self.config_filePath}, "
                    "creating example INI file."
                )
                src = Path(app_dir) / self.exampleconfigfile
                dst = Path(config_dir) / self.exampleconfigfile
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(src), str(dst))
                sys.exit(1)

            try:
                self.config = configparser.ConfigParser()
                self.config.read(self.config_filePath)

                # GENERAL
                self.enabled = self.config.getboolean(
                    'GENERAL', 'ENABLED', fallback=False
                )
                self.dry_run = self.config.getboolean(
                    'GENERAL', 'DRY_RUN', fallback=False
                )
                self.verbose_logging = self.config.getboolean(
                    'GENERAL', 'VERBOSE_LOGGING', fallback=False
                )

                # NODE
                self.nodename = self.config.get(
                    'NODE', 'NODE_NAME', fallback=''
                )

                # MAIL
                self.mail_port = self.config.getint(
                    'MAIL', 'MAIL_PORT', fallback=0
                )
                self.mail_server = self.config.get(
                    'MAIL', 'MAIL_SERVER', fallback=''
                )
                self.mail_login = self.config.get(
                    'MAIL', 'MAIL_LOGIN', fallback=''
                )
                self.mail_password = self.config.get(
                    'MAIL', 'MAIL_PASSWORD', fallback=''
                )
                self.mail_sender = self.config.get(
                    'MAIL', 'MAIL_SENDER', fallback=''
                )

                # SERIES
                self.keyword = self.config.get(
                    'SERIES', 'KEYWORD', fallback=''
                )
                allowed = self.config.get(
                    'SERIES', 'ALLOWED_SENDERS', fallback=''
                )
                allowed_dv = self.config.get(
                    'SERIES', 'ALLOWED_SENDERSDV', fallback=''
                )
                self.allowed_senders = [
                    s.strip() for s in allowed.split(',') if s.strip()
                ]
                self.allowed_sendersdv = [
                    s.strip() for s in allowed_dv.split(',') if s.strip()
                ]

                # PUSHOVER
                self.pushover_user_key = self.config.get(
                    'PUSHOVER', 'USER_KEY', fallback=''
                )
                self.pushover_token_api = self.config.get(
                    'PUSHOVER', 'TOKEN_API', fallback=''
                )
                self.pushover_sound = self.config.get(
                    'PUSHOVER', 'SOUND', fallback='pushover'
                )

            except (KeyError, ValueError) as e:
                logging.error(
                    f"Invalid INI contents or type error: {e}. "
                    "Exiting."
                )
                sys.exit(1)

        except (IOError, FileNotFoundError) as e:
            logging.error(f"I/O error while checking config: {e}")
            sys.exit(1)

    def writeLog(self, init, msg):
        try:
            # ensure log directory exists
            logpath = Path(self.log_filePath)
            logpath.parent.mkdir(parents=True, exist_ok=True)
            mode = "w" if init else "a"
            with open(logpath, mode, encoding='utf-8') as logfile:
                logfile.write(f"{datetime.now()} - {msg}")
        except IOError:
            logging.error(
                f"Can't write file {self.log_filePath}."
            )

    def run(self):
        # Setting for PushOver
        self.appPushover = Application(self.pushover_token_api)
        self.userPushover = self.appPushover.get_user(self.pushover_user_key)

        if self.dry_run:
            logging.info(
                "*****************************************")
            logging.info(
                "**** DRY RUN, NOTHING WILL SET AWAKE ****")
            logging.info(
                "*****************************************")

            self.writeLog(
                False,
                "SeriesList - Dry run.\n"
            )

        # create an IMAP4 class with SSL
        imap = imaplib.IMAP4_SSL(self.mail_server)
        # authenticate
        imap.login(self.mail_login, self.mail_password)

        status, messages = imap.select("INBOX")

        # total number of emails
        messages = int(messages[0])

        for i in range(1, messages+1):

            # fetch the email message by ID
            res, msg = imap.fetch(str(i), "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    # parse a bytes email into a message object
                    msg = email.message_from_bytes(response[1])

                    # decode the email subject
                    subject, encoding = decode_header(msg["Subject"])[0]

                    if isinstance(subject, bytes):
                        # if it's a bytes, decode to str
                        if encoding:
                            subject = subject.decode(encoding)
                        else:
                            subject = subject.decode("utf-8")

                    # decode email sender
                    From, encoding = decode_header(msg.get("From"))[-1:][0]

                    if isinstance(From, bytes):
                        if encoding:
                            From = From.decode(encoding)
                        else:
                            From = From.decode("utf-8")

                    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', From)

                    if str.lower(subject) == self.keyword.lower():

                        if self.verbose_logging:
                            logging.info(
                                f"SeriesList - Found matching subject from "
                                f"{match.group(0)}"
                            )
                        self.writeLog(
                            False, f"SeriesList - Found matching subject from "
                            f"{match.group(0)}\n")

                        if match.group(0) in self.allowed_senders or \
                                match.group(0) in self.allowed_sendersdv:

                            if match.group(0) in self.allowed_senders:
                                local_list_filePath = self.list_filePath
                            else:
                                local_list_filePath = self.listdv_filePath

                            if not self.enabled:
                                if self.verbose_logging:
                                    logging.info(
                                        f"SeriesList - Service is disabled by "
                                        f"{match.group(0)}"
                                    )
                                self.writeLog(
                                    False,
                                    f"SeriesList - Service is disabled by "
                                    f"{match.group(0)}\n"
                                )

                            sender_email = self.mail_sender
                            receiver_email = match.group(0)

                            message = MIMEMultipart()
                            message["From"] = sender_email
                            message['To'] = receiver_email
                            message['Subject'] = (
                                f"Series Lijst - {self.nodename}"
                            )

                            # attachment = open(self.log_filePath, 'rb')
                            # obj = MIMEBase('application', 'octet-stream')
                            # obj.set_payload((attachment).read())
                            # encoders.encode_base64(obj)
                            # obj.add_header(
                            #     'Content-Disposition',
                            #     "attachment; filename= "+self.log_file
                            # )
                            # message.attach(obj)

                            if self.enabled:
                                try:
                                    with open(
                                            local_list_filePath, 'r') as file:
                                        body = file.read()

                                    logging.info(
                                        f"SeriesList - Sending serie list to"
                                        f" {match.group(0)}"
                                        )
                                    self.writeLog(
                                        False,
                                        f"SeriesList - Sending serie list to"
                                        f" {match.group(0)}\n"
                                    )

                                except FileNotFoundError:
                                    logging.error(
                                        f"Can't find file "
                                        f"{local_list_filePath}."
                                    )
                                except IOError:
                                    logging.error(
                                        f"Can't read file "
                                        f"{local_list_filePath}."
                                    )

                            else:
                                body = (
                                    f"Hi,\n\nDe service voor {self.nodename} "
                                    f"staat uit, je hoeft even geen "
                                    f"commando's te sturen.\n\n"
                                    f"Fijne dag!\n\n"
                                )

                            # logfile = open(self.log_filePath, "r")
                            # body += ''.join(logfile.readlines())
                            # logfile.close()

                            plain_text = MIMEText(
                                body, _subtype='plain', _charset='UTF-8')
                            message.attach(plain_text)

                            my_message = message.as_string()

                            try:
                                email_session = smtplib.SMTP(
                                    self.mail_server, self.mail_port)
                                email_session.starttls()
                                email_session.login(
                                    self.mail_login, self.mail_password)
                                email_session.sendmail(
                                    sender_email,
                                    [receiver_email],
                                    my_message
                                    )
                                email_session.quit()

                                if self.verbose_logging:
                                    logging.info(
                                        f"SeriesList - Mail Sent to "
                                        f"{receiver_email}."
                                    )

                                self.writeLog(
                                    False,
                                    f"SeriesList - Mail Sent to "
                                    f"{receiver_email}.\n"
                                )

                                self.message = \
                                    self.userPushover.send_message(
                                        message=f"SeriesList - "
                                        f"Series list sent to "
                                        f"{match.group(0)}\n",
                                        sound=self.pushover_sound
                                        )

                            except (gaierror, ConnectionRefusedError):
                                logging.error(
                                    "Failed to connect to the server. "
                                    "Bad connection settings?")
                            except smtplib.SMTPServerDisconnected:
                                logging.error(
                                    "Failed to connect to the server. "
                                    "Wrong user/password?"
                                )
                            except smtplib.SMTPException as e:
                                logging.error(
                                    f"SMTP error occurred: {str(e)}.")

                        else:
                            if self.verbose_logging:
                                logging.info(
                                    f"SeriesList - sender not in"
                                    f" list {match.group(0)}."
                                    )
                            self.writeLog(
                                False,
                                f"SeriesList - sender not in list "
                                f"{match.group(0)}.\n"
                            )

                        if self.verbose_logging:
                            logging.info(
                                "SeriesList - Marking message for delete.")
                        self.writeLog(
                            False, "SeriesList - Marking message for delete.\n"
                            )

                        if not self.dry_run:
                            imap.store(str(i), "+FLAGS", "\\Deleted")

                    else:
                        if self.verbose_logging:
                            logging.info(
                                f"SeriesList - Subject not recognized. "
                                f"Skipping message. "
                                f"{match.group(0)}"
                            )

                            self.writeLog(
                                False,
                                f"SeriesList - Subject not recognized. "
                                f"Skipping message. {match.group(0)}\n"
                            )

        # close the connection and logout
        imap.expunge()
        imap.close()
        imap.logout()


if __name__ == '__main__':

    embylistsbyemail = ELBE()
    embylistsbyemail.run()
    embylistsbyemail = None
