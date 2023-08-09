
import uuid
from flask import Blueprint, jsonify, request, send_from_directory, make_response, Flask
from app.reports import get_report_status_from_db, get_report_data_from_db, generate_report

import os

report_bp = Blueprint('report_bp', __name__, url_prefix='/api')

@report_bp.route('/trigger_report', methods=['POST'])
def trigger_report():
    try:
        # generating a unique string for the report
        unique_id = uuid.uuid4()
        report_id = str(unique_id)

        """
            we can use threading or celery to run this as background
        """
        generate_report(report_id)

        return jsonify({'report_id': report_id})
    except Exception as e:
        return jsonify({ "error_message": "Something went Wrong", "Error_code":500, "error":str(e)})


@report_bp.route('/get_report', methods=['GET'])
def get_report():
    try:
        report_id = request.args.get('report_id')
        if not report_id:
            return jsonify({'error': 'Missing report ID', "error_code": 400})

        report_status = get_report_status_from_db(report_id)
        if not report_status:
            return jsonify({'error': 'Invalid report ID',"error_code": 400})

        if report_status == 'running':
            return jsonify({'status': 'Running'})
        elif report_status == 'complete':
            report_data = get_report_data_from_db(report_id)
            if report_data:
                root_dir = os.path.dirname(os.path.abspath(__file__))
                response = make_response(send_from_directory(f"{root_dir}/reports/", report_id + ".csv"))
                response.headers["status"] = "Complete"
                return response
            else:
                return jsonify({'error': 'Failed to retrieve report data',"error_code": 400})
        else:
            return jsonify({'error': 'Invalid report status',"error_code": 400})
    except Exception as e:
        return jsonify({ "error_message": "Something went Wrong", "Error_code":500, "error":str(e)})
        
