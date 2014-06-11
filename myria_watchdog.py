#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import cgi
import sys
import pickle
import subprocess
import time
import socket
import os.path
import threading
import ConfigParser
import getpass

known_deployments = {}

def check_secret_code(form, deployment, self):
    if "secret_code" in form.keys():
        proposed_secret_code = form['secret_code'].value
    else:
        proposed_secret_code = None
    if "secret_code" in deployment.keys():
        correct_secret_code = deployment["secret_code"]
    else:
        correct_secret_code = None
    if not correct_secret_code == proposed_secret_code:
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write("Wrong secret code!")
        return False
    return True

class myHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/deployments":
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(str(known_deployments.keys()))
            return

    def do_POST(self):
        form = cgi.FieldStorage(
            fp = self.rfile,
            headers = self.headers,
            environ = {'REQUEST_METHOD':'POST',
                       'CONTENT_TYPE':self.headers['Content-Type']
                      })

        if not 'master' in form.keys():
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write("Missing argument: master")
            return
        master = form['master'].value

        if self.path == "/restart":
            # use IP address as the key since a machine can have multiple machine names
            host = socket.gethostbyname(master.split(":")[0])
            port = master.split(":")[1]
            master = host + ":" + port

            if not master in known_deployments.keys():
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write("Unknown deployment!")
                return

            working_dir = known_deployments[master]["working_dir"]
            deployment_file = known_deployments[master]["deployment_file"]
            if not check_secret_code(form, known_deployments[master], self):
                return
            
            try:
                args = ["ssh", host, "cd", working_dir, "&& ./stop_all_by_force.py", deployment_file]
                subprocess.check_output(args)
                args = ["ssh", host, "cd", working_dir, "&& ./launch_cluster.sh", deployment_file]
                subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write("Error, return code: " + e.returncode);
                return

            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write("Restarted successfully.");
            return

def getArg(config, deployment, key, required):
    try:
        return config.get(deployment, key)
    except ConfigParser.NoOptionError:
        if required:
            raise Exception("missing " + key + " in deployment " + deployment)
        return None
    
def loadDeployments(filename, port_number):
    if os.path.exists(filename):
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read([filename])
        global known_deployments
        for deployment in config.sections():
            # use IP address as the key since a machine can have multiple machine names
            master = socket.gethostbyname(getArg(config, deployment, 'master', True))
            port = getArg(config, deployment, 'rest_port', True)
            master = master + ":" + port
            known_deployments[master] = {}
            known_deployments[master]['working_dir'] = getArg(config, deployment, 'working_dir', True)
            known_deployments[master]['deployment_file'] = getArg(config, deployment, 'deployment_file', True)
            known_deployments[master]['secret_code'] = getArg(config, deployment, 'secret_code', False)
            print known_deployments[master]
    else:
        print "Can't find " + filename + ", quit."
        sys.exit(1)

def main(argv):
    # Usage
    if len(argv) > 3:
        print >> sys.stderr, "Usage: %s <registered_deployment_file> <port_number>" % (argv[0])
        print >> sys.stderr, "\tregistered_deployment_file: optional, using ./registered_deployments if not specified"
        print >> sys.stderr, "\tport_number: optional, using 8385 if not specified"
        sys.exit(1)

    if len(argv) == 3:
        port_number = int(argv[2])
    else:
        port_number = 8385
    if len(argv) >= 2:
        filename = argv[1]
    else:
        filename = "registered_deployments"

    loadDeployments(filename, port_number)

    server = HTTPServer(('', port_number), myHandler)
    print 'Started watchdog on port ' , port_number
    server.serve_forever()

if __name__ == "__main__":
    main(sys.argv)
