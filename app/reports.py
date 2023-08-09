
from app.models import Store, Report, Timezone, BusinessHours
from app.database import db
from datetime import datetime, timedelta
from app.models import Report
from sqlalchemy import text

import tempfile
from pytz import timezone as pytz_timezone
import csv
import os

def get_report_status_from_db(report_id):
    report = Report.query.filter_by(report_id=report_id).first()
    if report is None:
        return None
    else:
        return report.status

def get_report_data_from_db(report_id):
    """
        Fetch the report data from the database for a given report_id.
    """
    report = Report.query.filter_by(report_id=report_id).first()

    if report is None:
        raise ValueError(f"No report found for report_id: {report_id}")

    return report.report_url


def generate_report(report_id):
    report = Report(report_id=report_id, status='running', report_url='')
    db.session.add(report)
    db.session.commit()
    csv_data = []
    """
        only triggering report for first 200 stores
        otherwise it will take too much time
        in the real scenario, we will generate the 
        report for all the stores
    """
    stores_timezone = Timezone.query.limit(200).all()
    for store in stores_timezone:
        data = generate_report_data(store)
        csv_data.append(data)
    generate_csv_file(report, csv_data)
    return report


def generate_report_data(timezone):
    tz = timezone.timezone_str or 'America/Chicago'

    target_timezone = pytz_timezone(tz)

    query = text("""
            SELECT timestamp_utc
            FROM store
            ORDER BY timestamp_utc DESC
            LIMIT 1
        """)
    
    """
        In real case the 'time' should be datetime.now(), but in the csv
        the latest time is 25th January 2023, so if I generate the report for 
        past one hour/day/week by considering current time, there won't be any data, 
        because the current date is 9th August 2023
    """
    result = db.engine.execute(query)
    time_str = result.scalar()

    time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")
    local_time = time.astimezone(target_timezone)
    utc_timezone = pytz_timezone('UTC')
    utc_time = time.astimezone(utc_timezone)
    current_day = local_time.weekday()
    current_time = local_time.time()
    
    last_one_hour_data = get_last_one_hour_data(utc_time, current_day, current_time)
    last_one_day_data = get_last_one_day_data(utc_time, current_day, current_time)
    last_one_week_data = get_last_one_week_data(utc_time, current_day, current_time)

    data = []
    data.append(timezone.store_id)

    data.extend(list(last_one_hour_data.values()))
    data.extend(list(last_one_day_data.values()))
    data.extend(list(last_one_week_data.values()))

    return data

def generate_csv_file(report, csv_data):
    """
        Now, I'm generating a csv file and saving to my local
        But in real case we can use cloud storage to store the files like S3.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        file_name = f"{report.report_id}.csv"
        temp_file_path = os.path.join(temp_dir, file_name)
        with open(temp_file_path, "w", newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["store_id", "last_one_hour_uptime", "last_one_hour_downtime", "last_one_hour_unit", "last_one_day_uptime", "last_one_day_downtime", "last_one_day_unit", "last_one_week_uptime", "last_one_week_downtime", "last_one_week_unit"])
            for data in csv_data:
                csv_writer.writerow(data)

        root_dir = os.path.dirname(os.path.abspath(__file__))
        root_file_path = os.path.join(f"{root_dir}/reports/", file_name)
        os.rename(temp_file_path, root_file_path)

        report.report_url = root_file_path
        report.status = "complete"
        report.completed_at = datetime.utcnow()
        db.session.commit()

def get_last_one_hour_data(utc_time, current_day, current_time):
    last_one_hour_data = {"uptime" : 0 , "downtime" : 0 , "unit" : "minutes"}
    
    # checking if store is open in last one hour
    is_store_open_query = db.session.query(BusinessHours).filter(
                        BusinessHours.day_of_week == current_day,
                        BusinessHours.start_time_local <= current_time,
                        BusinessHours.end_time_local >= current_time
                    ).exists()
    is_store_open = db.session.query(is_store_open_query).scalar()
    if not is_store_open:
        return last_one_hour_data
    
    # checking is store open in last one hour and last log status is active
    last_one_hour_logs = db.session.query(Store).filter(
        Store.timestamp_utc >= utc_time - timedelta(hours=1)
    ).order_by(Store.timestamp_utc.asc()).all()

    if last_one_hour_logs:
        last_one_hour_log_status = last_one_hour_logs[0].status
        if last_one_hour_log_status == 'active':
            last_one_hour_data["uptime"] = 60
        else:
            last_one_hour_data["downtime"] = 60

    return last_one_hour_data
    

def get_last_one_day_data(utc_time, current_day, current_time):
    last_one_day_data = {"uptime" : 0 , "downtime" : 0, "unit" : "hours"}
    one_day_ago = current_day - 1 if current_day > 0 else 6
    
    # checking is store open in last one day
    is_store_open_query = db.session.query(BusinessHours).filter(
                        BusinessHours.day_of_week >= one_day_ago,
                        BusinessHours.day_of_week <= current_day,
                        BusinessHours.start_time_local <= current_time,
                        BusinessHours.end_time_local >= current_time
                    ).exists()
    
    is_store_open = db.session.query(is_store_open_query).scalar()
    if not is_store_open:
        return last_one_day_data
    
    # Fetching all the logs in last one day
    last_one_day_logs = db.session.query(Store).filter(
        Store.timestamp_utc >= utc_time - timedelta(days=1)
    ).order_by(Store.timestamp_utc.asc()).all()
    
    for log in last_one_day_logs:
        # checkig is log in store business hours
        log_in_store_business_hours_query = db.session.query(BusinessHours).filter(
                        BusinessHours.day_of_week == log.timestamp_utc.weekday(),
                        BusinessHours.start_time_local <= log.timestamp_utc.time(),
                        BusinessHours.end_time_local >= log.timestamp_utc.time()
                    ).exists()
        log_in_store_business_hours = db.session.query(log_in_store_business_hours_query).scalar()
        
        # checking is log is in store business hours and status is active
        if not log_in_store_business_hours:
            continue
        if log.status == 'active':
            last_one_day_data["uptime"] += 1
        else:
            last_one_day_data["downtime"] += 1
    return last_one_day_data

def get_last_one_week_data(utc_time, current_day, current_time):
    last_one_week_data = {"uptime" : 0 , "downtime" : 0, "unit" : "hours"}
    one_week_ago = current_day - 7 if current_day > 0 else 0
    
    # checking is store open in last one week
    is_store_open_query = db.session.query(BusinessHours).filter(
                    BusinessHours.day_of_week >= one_week_ago,
                    BusinessHours.day_of_week <= current_day,
                    BusinessHours.start_time_local <= current_time,
                    BusinessHours.end_time_local >= current_time
                ).exists()
    
    is_store_open = db.session.query(is_store_open_query).scalar()
        
    if not is_store_open:
        return last_one_week_data

    # fetching all the logs in last one week
    last_one_week_logs = db.session.query(Store).filter(
        Store.timestamp_utc >= utc_time - timedelta(days=7)
    ).order_by(Store.timestamp_utc.asc()).all()

    for log in last_one_week_logs:
        # checkig is log in store business hours
        log_in_store_business_hours_query = db.session.query(BusinessHours).filter(
                        BusinessHours.day_of_week == log.timestamp_utc.weekday(),
                        BusinessHours.start_time_local <= log.timestamp_utc.time(),
                        BusinessHours.end_time_local >= log.timestamp_utc.time()
                    ).exists()
        log_in_store_business_hours = db.session.query(log_in_store_business_hours_query).scalar()

        # checking is log in store business hours and status is active
        if not log_in_store_business_hours:
            continue
        if log.status == 'active':
            last_one_week_data["uptime"] += 1
        else:
            last_one_week_data["downtime"] += 1
    
    return last_one_week_data