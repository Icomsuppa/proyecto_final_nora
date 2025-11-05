# flask_microservice/blueprints/time_bp.py
from flask import Blueprint, jsonify
from datetime import datetime

time_bp = Blueprint('time_bp', __name__, url_prefix='/time')

@time_bp.route('/', methods=['GET'])
def get_time():
    now = datetime.now()
    return jsonify({
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S'),
        'iso': now.isoformat()
    })
