# Store Monitoring System

 There are several restaurants and needs to monitor if the store is online or not. All restaurants are supposed to be online during their business hours. Due to some unknown reasons, a store might go inactive for a few hours. Restaurant owners want to get a report of the how often this happened in the past

The system provides two APIs:

1.  fetch_data.py. this script poll the data every hour and store in the db
    currently, in this code, it is fetching first 200 rows and then waiting for an hour
    (simulating the real scenario), this script can be triggered using cron every hour, and
    time.sleep can be removed from the code.

1.  /trigger_report endpoint that triggers the generation of a report
    from the data provided (stored in the database). The API has no
    input and returns a report ID (a random string). The report ID is
    used to poll the status of report completion.

2.  /get_report endpoint that returns the status of the report or the
    CSV. The API takes a report ID as input and returns the following:

    -   If report generation is not complete, return "Running" as the
        output
    -   If report generation is complete, return "Complete" in the headers and 
        the CSV file can be downloaded with the following schema: store_id,
        uptime_last_hour(in minutes), uptime_last_day(in hours),
        update_last_week(in hours), downtime_last_hour(in minutes),
        downtime_last_day(in hours), downtime_last_week(in hours) The
        uptime and downtime reported in the CSV only include
        observations within business hours. The system extrapolates
        uptime and downtime based on the periodic polls we have ingested
        to the entire time interval.

## Data Sources 

The system has the following three sources of data:

1.  A CSV file with three columns (store_id, timestamp_utc, status)
    where status is active or inactive. All timestamps are in UTC.

2.  A CSV file with data on the business hours of all the stores. The
    schema of this data is store_id, dayOfWeek(0=Monday, 6=Sunday),
    start_time_local, end_time_local. These times are in the local time
    zone. If data is missing for a store, assume it is open 24\*7.

3.  A CSV file with data on the timezone for each store. The schema is
    store_id, timezone_str. If data is missing for a store, assume it is
    America/Chicago. This is used so that data sources 1 and 2 can be
    compared against each other.
    
**_NOTE:_**  I've used the same data file which is given in the Notion(I have not pushed it on GitHub due to its large size).
     
         #### Here is data file structure 
         
         ```
            data/
            
              ├── business_hours.csv
              
              ├── store_status.csv
              
              └── timezones.csv
            ```

## Installation 

To install the required packages, run the following command in the project directory:
```
    pip install -r requirements.txt
```

## Usage

To start the server, run the following command in the project directory:
```
    python run.py

```

The server will start running on http://localhost:5000

Note: Remember to add url prefix in the api like http://localhost:5000/api

## API Documentation

- ### /trigger_report

    This endpoint triggers the generation of a report from the data provided (stored in the database).

    * Request
    ```
    endpoint: /api/trigger_report
    type: POST
    ```
    * Response
    ```
    {
        "report_id": "random_string"
    }

    ```

- ### /get_report

    This endpoint returns the status of the report or the CSV.
    
    * Request
    ```
    endpoint: /api/get_report?report_id=random_string
    type: GET
    ```
    * Response
    ```
        if report generation is not completed
        {
            'status': 'Running'
        }
        otherwise a csv file will be downloaded
    ```
