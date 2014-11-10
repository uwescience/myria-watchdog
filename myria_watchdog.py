#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import cgi
import sys
import subprocess
import os.path
import urllib2
from urllib2 import HTTPError
import base64

class myHandler(BaseHTTPRequestHandler):
    def check_key_in_form(self, form, key):
        if not key in form.keys():
            self.send_response(400)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write("Missing argument: " + key)
            return False
        else:
            return True

    def do_POST(self):
        form = cgi.FieldStorage(
            fp = self.rfile,
            headers = self.headers,
            environ = {'REQUEST_METHOD':'POST',
                       'CONTENT_TYPE':self.headers['Content-Type']
                      })

        if self.path == "/restart":
            if not self.check_key_in_form(form, 'master'):
                return
            if not self.check_key_in_form(form, 'protocol'):
                return
            if not self.check_key_in_form(form, 'port'):
                return
            if not self.check_key_in_form(form, 'user'):
                return
            if not self.check_key_in_form(form, 'password'):
                return
            master = form['master'].value
            protocol = form['protocol'].value
            port = form['port'].value
            user = form['user'].value
            password = form['password'].value
            request = urllib2.Request(protocol + "://" + master + ":" + port + "/server/deployment_cfg")
            base64string = base64.encodestring('%s:%s' % (user, password)).replace('\n', '')
            request.add_header("Authorization", "Basic %s" % base64string)
            try:
                response = urllib2.urlopen(request)
            except HTTPError as e:
                self.send_response(e.code)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                return

            result = response.read()
            pos = result.rfind('/')
            deployment_file = result[pos+1:]
            result = result[:pos]
            pos = result.rfind('/')
            working_dir = result[:pos]
            
            try:
                args = ["ssh", master, "cd", working_dir, "&& ./stop_all_by_force.py", deployment_file]
                subprocess.check_output(args)
                args = ["ssh", master, "cd", working_dir, "&& ./launch_cluster.sh", deployment_file]
                subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                self.send_response(400)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write("Error, return code: " + str(e.returncode));
                return

            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write("Restarted successfully.");
            return

def main(argv):
    # Usage
    if len(argv) > 3:
        print >> sys.stderr, "Usage: %s <port_number>" % (argv[0])
        print >> sys.stderr, "\tport_number: optional, using 8385 if not specified"
        sys.exit(1)

    if len(argv) == 2:
        port_number = int(argv[1])
    else:
        port_number = 8385

    server = HTTPServer(('', port_number), myHandler)
    print 'Started watchdog on port ' , port_number
    server.serve_forever()

if __name__ == "__main__":
    main(sys.argv)
