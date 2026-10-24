## MyEQMS probe #2

JS bundles scanned: 7; endpoint strings: 10
- `api3/publicmapproxy`
- `publicportalapims/apimststation`
- `publicportalapims/apiranking`
- `publicportalapims/apitablehourly`
- `publicportalapims/currentapicurrentlocation`
- `publicportalapims/datatrendchart`
- `publicportalapims/getstationidbylonglat`
- `publicportalapims/mapcaqm`
- `publicportalapims/statelist`
- `publicportalmqims/mqimsstation`

### eqms.doe.gov.my calls seen in browser
- GET 200 https://eqms.doe.gov.my/api3/publicportalapims/mapcaqm?_ts=1792812223779 (17201 bytes)
- GET 200 https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly?stateid=16&datetime=2026-10-24T03:00:00& (6763 bytes)
- GET 200 https://eqms.doe.gov.my/api3/publicportalapims/apiranking (447 bytes)
- GET 200 https://eqms.doe.gov.my/api3/publicportalapims/statelist (2503 bytes)
- GET 200 https://eqms.doe.gov.my/api3/publicportalapims/datatrendchart?stateid=16&datetime=2026-10-24T03:00:00& (3818 bytes)
(+ 80 third-party calls, e.g. ArcGIS basemap)

### Plain HTTP test (no browser)
- /api3/publicportalapims/mapcaqm: HTTP 200, 17201 bytes
- /api3/publicportalapims/statelist: HTTP 200, 2503 bytes
- /api3/publicportalapims/apiranking: HTTP 200, 447 bytes
- `api_014_eqms_doe_gov_my_api3_publicportalapims_mapcaqm_ts_1792812223779.json` key `data`: 68 rows; fields: ['ID', 'STATE_ID', 'STATE_NAME', 'STATION_STATUS', 'STATION_ID', 'STATION_LOCATION', 'LONGITUDE', 'LATITUDE', 'API', 'PARAM_SYMBOL', 'CLASS', 'RECORD_DT']
- `api_015_eqms_doe_gov_my_api3_publicportalapims_apitablehourly_stateid_16_datetime_2026_1.json` key `api_table_hourly`: 25 rows; fields: ['PAGE_ROWNUM', 'PAGE_TOTALROW', 'PAGE', 'PAGE_TOTAL', 'STATION_ID', 'STATE_ID', 'STATION_NAME', 'STATION_LOCATION', 'LATITUDE', 'LONGITUDE', 'DATETIME', 'API', 'PARAM_SYMBOL']
- `api_031_eqms_doe_gov_my_api3_publicportalapims_apiranking.json` key `api_ranking`: 5 rows; fields: ['STATION_ID', 'API', 'LOCATION', 'PARAM_SYMBOL']
- `api_032_eqms_doe_gov_my_api3_publicportalapims_statelist.json`: 16 rows; fields: ['STATE_ID', 'STATE_NAME', 'STATE_NAME_CAPS', 'STATE_CODE', 'BASIN_CODE', 'REGION_ID', 'PREFIX', 'SORT_BY_STATE_NAME']
- `api_033_eqms_doe_gov_my_api3_publicportalapims_datatrendchart_stateid_16_datetime_2026_1.json` key `highcharts_bar`: 25 rows; fields: ['STATION_ID', 'DATETIME', 'STATE_ID', 'MONTH', 'API', 'EPOCHDATE', 'API_CATEGORY']
- `plain_apiranking.json` key `api_ranking`: 5 rows; fields: ['STATION_ID', 'API', 'LOCATION', 'PARAM_SYMBOL']
- `plain_mapcaqm.json` key `data`: 68 rows; fields: ['ID', 'STATE_ID', 'STATE_NAME', 'STATION_STATUS', 'STATION_ID', 'STATION_LOCATION', 'LONGITUDE', 'LATITUDE', 'API', 'PARAM_SYMBOL', 'CLASS', 'RECORD_DT']
- `plain_statelist.json`: 16 rows; fields: ['STATE_ID', 'STATE_NAME', 'STATE_NAME_CAPS', 'STATE_CODE', 'BASIN_CODE', 'REGION_ID', 'PREFIX', 'SORT_BY_STATE_NAME']