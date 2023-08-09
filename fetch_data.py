import time
import pandas as pd
import pytz
from app import create_app
from app.models import Store, BusinessHours, Timezone
from app.database import db

batch_size = 200

# polling data every hour
wait_time = 3600

app = create_app()

def insert_timezones(timezones_csv):
    for timezones_df in timezones_csv:
        for i, row in timezones_df.iterrows():
            timezone = Timezone(store_id=row['store_id'], timezone_str=row['timezone_str'])
            db.session.add(timezone)
            """
                I'm creating batches of 200 and commiting 
                that data to the database
                because if I do it for each row, it will 
                be very slow
            """
            if (i+1) % batch_size == 0:
                db.session.commit()

        db.session.commit()

def insert_stores(stores_csv, timezones_csv):
    timezone_dict = {}
    for _, row in pd.concat(timezones_csv).iterrows():
        timezone_dict[row['store_id']] = pytz.timezone(row['timezone_str'])

    for stores_df in stores_csv:
        stores_df = stores_df.dropna(subset=['timestamp_utc'])
        stores_df['timestamp_utc'] = pd.to_datetime(stores_df['timestamp_utc'])

        for i, row in stores_df.iterrows():
            store_id = row['store_id']
            status = row['status']
            store = Store(store_id=store_id, timestamp_utc=row['timestamp_utc'], status=status)
            db.session.add(store)

            if (i+1) % batch_size == 0:
                db.session.commit()
                time.sleep(wait_time)

        db.session.commit()

def insert_business_hours(business_hours_csv):
    for business_hours_df in business_hours_csv:
        for i, row in business_hours_df.iterrows():
            start_time = pd.to_datetime(row['start_time_local']).time()
            end_time = pd.to_datetime(row['end_time_local']).time()
            business_hours = BusinessHours(store_id=row['store_id'], day_of_week=row['day'], start_time_local=start_time, end_time_local=end_time)
            db.session.add(business_hours)
            if (i+1) % batch_size == 0:
                db.session.commit()

        db.session.commit()

def poll_data():
    timezones_csv = pd.read_csv('data/timezones.csv', chunksize=batch_size)
    stores_csv = pd.read_csv('data/store_status.csv', chunksize=batch_size)
    business_hours_csv = pd.read_csv('data/business_hours.csv', chunksize=batch_size)

    with app.app_context():
        db.create_all()
        # insert_business_hours(business_hours_csv)
        # insert_timezones(timezones_csv)
        insert_stores(stores_csv, timezones_csv)

if __name__ == '__main__':
    """
        We are fetching store data every hour, so we can setup a cron job for this script
        which will run every hour.
        cron syntax would be:  `0 * * * * /path/to/python3 /path/to/fetch_data.py`

        Currently I'm polling data for all the csvs inside this single script
        But business hour and timezone info doesn't needs to be polled every hours
        They will be provided by the client once(and won't change very frequently)
        So, A separate script can be written to insert the data for business hours
        and timezone, but I have kept the code in the same file for the demo purpose.

        Store status needs to be fetched every hour, and currently the csv contains the whole data
        But I'm fetching 200 rows, storing that in db and then waiting for an hour (For the demo purpose only).
        In real case scenario we need to fetch all the available data every hour, and we can setup cronjob for this.
    """
    poll_data()
