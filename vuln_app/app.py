import flask
import flask_compress
import os
import json
import uuid

with open("locations.json",'rb') as f:
    locations = json.loads(f.read().decode('utf-8'))

app = flask.Flask(__name__,template_folder=os.getcwd())

files = [f.name for f in os.scandir(".") if not f.is_dir() and f.name[:-3] != '.py' and f.name[:-5] != '.json']
files = set(files)

csrf = uuid.uuid4().hex

@app.route("/<path>")
@app.errorhandler(404)
def serve_file(path):
    if path in files:
        return flask.send_file(path)
    else:
        return "File not found", 404

@app.route('/')
def index():
    if 'location' in flask.request.args.keys():
        location = flask.request.args.get('location')
    else:
        location = 'US'

    if location in locations.keys():
        return flask.render_template('index.html',price=f"{location}: {locations[location]}",csrf=csrf,location=location,disabled='')
    else:
        return flask.render_template('index.html',price=f"Error: location not found!",csrf=csrf,location=location,disabled='disabled')

@app.route("/orders",methods=["POST"])
def buy():
    req_csrf = flask.request.form['csrf']
    location= flask.request.form['location']
    if location in locations.keys() and csrf == req_csrf:
        id = uuid.uuid4()
        return flask.render_template("ordered.html",id=id.hex)
    elif not location in locations.keys():
        return "Invalid location", 400
    else:
        return "Unauthorized", 401
    
app.config["COMPRESS_ALGORITHM"] = ['deflate']
flask_compress.Compress(app)
app.run("0.0.0.0",5000,ssl_context=('cert.pem','key.pem'))