from flask import Flask, request, request
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import flask
import subprocess
import glob
import shutil
import io
from pathlib import Path

app = Flask(__name__)
sess = Session()


def allowed_file(filename: str):
    ALLOWED_EXTENSIONS = {'slp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <body>

    <h2>Upload File</h2>
    <form action = "/convert" method = "POST" 
    enctype = "multipart/form-data">
    <input type = "file" name = "file" />
    <input type = "submit"/>
    </form>

    </body>
    </html>
    '''


def convert_replay(slp_replay: Path):
    converted_file = bytes()
    tmpdir = Path(__file__).parent / ".tmp"
    if tmpdir.exists() and tmpdir.is_dir():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir(parents=True)
    subprocess.run(["slp2mp4", "--output-directory", tmpdir, "single", slp_replay], check=True)
    files = glob.glob(f"{tmpdir}/*")
    assert len(files) == 1
    converted_filepath = files[0]
    converted_file = open(converted_filepath, "r+b").read()
    shutil.rmtree(tmpdir)
    return converted_file


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(e):
    return 'File is too large', RequestEntityTooLarge.code


@app.route('/convert', methods=['POST'])
def upload_file():
    if "file" not in request.files:
        print("ERROR: No file uploaded.")
        return 'No file part in the request', 400

    file = request.files['file']
    # If the user does not select a file, the browser submits an empty file without a filename.
    if not file or file.filename == "":
        print("ERROR: File is empty.")
        return 'No selected file', 400
    if not allowed_file(file.filename):
        print("ERROR: File is not allowed.")
        return 'File type not allowed', 400

    # Save the replay file
    filename = secure_filename(file.filename)
    tmp_replay_file = "temp_file.slp"
    with open(tmp_replay_file, "wb") as f:
        pass
    file.save(tmp_replay_file)

    # Convert the replay file
    converted_file = io.BytesIO(convert_replay(tmp_replay_file))

    return flask.send_file(
        converted_file,
        as_attachment=True,
        download_name="processed_" + Path(filename).stem + ".mp4",
        mimetype="application/octet-stream",
    )


if __name__ == "__main__":
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MiB
    app.secret_key = "super secret key 123"
    app.config["SESSION_TYPE"] = "memcache"

    sess.init_app(app)

    app.debug = True
    app.run()
