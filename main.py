#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" Gitlab Webhook Receiver """
# Based on: https://github.com/schickling/docker-hook

import json
import yaml
from subprocess import Popen, PIPE, STDOUT
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, FileType
from importlib import import_module
from multiprocessing import Process
try:
    # For Python 3.0 and later
    from http.server import HTTPServer
    from http.server import BaseHTTPRequestHandler
except ImportError:
    # Fall back to Python 2
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer as HTTPServer
import sys
import logging
import shlex

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.DEBUG,
                    stream=sys.stdout)

runningProcess = None

config = None

class RequestHandler(BaseHTTPRequestHandler):
    """A POST request handler."""

    def do_token_mgmt(self, gitlab_token_header, project):
        global runningProcess
        # Check if the gitlab token is valid
        if gitlab_token_header == config['webhook_secret']:
            print(project)
            if config['repo_name'] == project:
                logging.info("Updating repository.")
                try:
                    self.send_response(200, "OK")
                    if runningProcess.poll() is None:
                        try:
                            runningProcess.terminate()
                        except EnvironmentError as err:
                            print(err)
                    p = Popen(shlex.split('git pull origin master'), cwd = config['repo_dir'])
                    p.wait()
                    runningProcess = Popen(shlex.split(config['command']), cwd = config['repo_dir'])
                    #runningProcess.communicate()
                except OSError as err:
                    self.send_response(500, "OSError")
                    logging.error("Command could not run successfully.")
                    logging.error(err)
            else:
                logging.error("Wrong Repo")
                self.send_response(404, "Got request from wrong repo")
        else:
            logging.error("Not authorized, Gitlab_Token not authorized")
            self.send_response(401, "Gitlab Token not authorized")

    def do_POST(self):
        logging.info("Hook received")

        if sys.version_info >= (3,0):
            # get payload
            header_length = int(self.headers['Content-Length'])
            # get gitlab secret token
            gitlab_token_header = self.headers['X-Gitlab-Token']
        else:
            header_length = int(self.headers.getheader('content-length', "0"))
            gitlab_token_header = self.headers.getheader('X-Gitlab-Token')

        json_payload = self.rfile.read(header_length)
        json_params = {}
        if len(json_payload) > 0:
            json_params = json.loads(json_payload.decode('utf-8'))

        try:
            # get project homepage
            project = json_params['project']['name']
        except KeyError as err:
            self.send_response(500, "KeyError")
            logging.error("No project provided by the JSON payload")
            self.end_headers()
            return

        try:
            self.do_token_mgmt(gitlab_token_header, project)
        except KeyError as err:
            self.send_response(500, "KeyError")
            if err == project:
                logging.error("Wrong project's update received.")
            elif err == 'webhook_secret':
                logging.error("Key 'webhook_secret' not found.")
            else:
                logging.error("Unknown error")
        finally:
            self.end_headers()


def get_parser():
    """Get a command line parser."""
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument("--addr",
                        dest="addr",
                        default="0.0.0.0",
                        help="address where it listens")
    parser.add_argument("--port",
                        dest="port",
                        type=int,
                        default=8666,
                        metavar="PORT",
                        help="port where it listens")
    return parser


def main(addr, port):
    global runningProcess
    """Start a HTTPServer which waits for requests."""
    httpd = HTTPServer((addr, port), RequestHandler)
    print("Server started!")
    runningProcess = Popen(shlex.split(config['command']), cwd = config['repo_dir'])
    #runningProcess.communicate()
    httpd.serve_forever()


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()

    with open('config.json', 'r') as f:
        config = json.load(f)

    main(args.addr, args.port)
