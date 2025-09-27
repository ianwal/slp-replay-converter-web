from flask import Flask, request, request, render_template, send_from_directory, jsonify
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import flask
import io
import uuid
from pathlib import Path
from .manager import Manager, ConvertTaskResult
import datetime

app = Flask(__name__)
sess = Session()
manager = Manager()


def allowed_file(filename: str):
    ALLOWED_EXTENSIONS = {'slp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(Path(app.root_path) / 'static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/")
def home():
    return render_template("index.html")


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(e):
    return 'File is too large', RequestEntityTooLarge.code


@app.route('/api/convert_queue_size', methods=['GET'])
def convert_queue_size():
    return jsonify({'size': manager.get_queue_size()})


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

    tmpdir = Path(__file__).parent / ".tmp"
    tmpdir.mkdir(exist_ok=True)

    tmp_replay_file = tmpdir / f"{uuid.uuid4()}.slp"
    with open(tmp_replay_file, "wb") as f:
        pass
    file.save(tmp_replay_file)

    # Convert the replay file
    converted_file = io.BytesIO(manager.convert_replay(tmp_replay_file))

    return flask.send_file(
        converted_file,
        as_attachment=True,
        download_name="slp_" + Path(filename).stem + ".mp4",
        mimetype="application/octet-stream",
    )


@app.route("/convert_async", methods=['POST'])
def upload_file_async():
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

    tmpdir = Path(__file__).parent / ".tmp"
    tmpdir.mkdir(exist_ok=True)

    tmp_replay_file = tmpdir / f"{uuid.uuid4()}.slp"
    with open(tmp_replay_file, "wb") as f:
        pass
    file.save(tmp_replay_file)

    task_id = manager.push_convert_task(tmp_replay_file, "slp_" + Path(filename).stem + ".mp4")

    return jsonify({"taskId": task_id, "createTimepoint": datetime.datetime.now(datetime.timezone.utc)})


@app.route("/api/task_result", methods=['POST'])
def task_result():
    content = request.json
    task_id = content["taskId"]
    task_result = manager.get_task_result(task_id)
    # TODO: This is a really bad way to handle errors.
    #       Probably should return json status with optional blob of the file to download, or split up this API.
    if task_result:
        return flask.send_file(
            io.BytesIO(task_result.converted_replay),
            as_attachment=True,
            download_name=task_result.filename,
            mimetype="application/octet-stream",
        )
    else:
        return "Task is not done", 404


if __name__ == "__main__":
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MiB
    app.secret_key = "super secret key 123"
    app.config["SESSION_TYPE"] = "memcache"

    sess.init_app(app)

    app.debug = True
    app.run()
