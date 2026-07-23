# Network operator KPIs time series dataset

This dataset contains the measurements of different key performance indicators (KPIs) of the usage of a network operator's infrastructure. It provides time series with the evolution of the KPIs measured every 5 minutes for a time interval greather than one month. The measurements correspond to different operator locations. Four different KPIs are provided in the dataset: aggregated Internet traffic (in bits per second), downstream traffic (in bits per second), number of active client sessions, and Virtual Private Network (VPN) traffic (in bits per second).

The results have been anonymized, the time frame has been shifted so that the first timestamp of each time series is 0 and the values of the KPIs have been scaled, so that they range from 0 to 1000 in each time series.

## Files

```
.
├── README.md
├── data_real
│   └── r*.txt
|  
├── data_real_incidents.txt
├── data_real_info.txt
├── data_series
│   └── s*.txt
|  
└── data_series_info.txt
```

## Contents of each file

* `README.md`: Description of the dataset

* The `data_real` folder contains the time series for different KPIs in which real anomalies have been identified. Each time series is stored as a file named `rXXX.txt.ok`, where `rXXX` represents the id of the time series.

* The `data_series` folder contains the time series provided by the operator. Each time series is stored as a file named `sYYY.txt.ok` where `sYYY` represents the id of the time series.

* `data_real_incidents.txt`: Information about the location of the real anomalies. Each line of the file has three numbers separated by a whitespace representing an anomaly. The first number is the id of the time series in which real anomalies have been identified (e.g., rXXX), the second number is the sample in which the anomaly started and the third number is the sample in which the anomaly finished. Note that multiple rows may refer to different anomalies of the same time series.

* `data_real_info.txt`/`data_series_info.txt`: Information for the type of KPI of each time series. Each line of the file has two numbers separated by a whitespace. The first number is the id of the time series (e.g., rXXX, sYYY) and the second number is the type of KPI (e.g., internet, sessions, vpn, downstream).

* `rXXX.txt.ok`/`sYYY.txt.ok`: Time series for a given KPI and a given operator site, in which real anomalies have been identified. Each line of the file has two numbers separated by a whitespace. The first number is the timestamp in seconds (shifted so that every time series starts in 0) and the second number is the value of the KPI (scaled so that every value is in the range [0,1000]).

## LICENSE

This dataset is licensed under the Creative Commns Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0). To view a copy of this license, visit [https://creativecommons.org/licenses/by-nc/4.0/legalcode](https://creativecommons.org/licenses/by-nc/4.0/legalcode).
