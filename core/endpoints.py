# D:\github\1968_SMART_CHAT_BACK\core\endpoints.py

ENDPOINTS = {
    # =========================
    # 已實作（本階段要用）
    # =========================

    # 5. 路況事件／施工事件／出口壅塞
    "incidents": {
        "north":   "http://210.241.131.244/xml/1min_incident_data_north.xml",
        "center":  "http://210.241.131.244/xml/1min_incident_data_center.xml",
        "south":   "http://210.241.131.244/xml/1min_incident_data_south.xml",
        "pinglin": "http://210.241.131.244/xml/1min_incident_data_pinglin.xml",
    },

    # 6. 替代道路／旅行時間
    "alt_routes": "http://210.241.131.244/xml/30min_alternative_data.xml",

    # 7. 開放路肩（Operation + Config）
    "scs": {
        "op":  "http://210.241.131.244/xml/1min_scs_operation_data.xml",
        "cfg": "http://210.241.131.244/xml/1day_scs_config_data.xml",
    },

    # 8. 服務區停車位
    "parking": "https://tisv.tcloud.freeway.gov.tw/xml/motc_parking/availbility_freeway.xml",

    # 10. 天氣資訊（此處保留 Open-Meteo；你也可改用 CWA）
    "weather": {
        "openmeteo_base": "https://api.open-meteo.com/v1/forecast",
        # 若日後切 CWA，請在 config / service 接上：
        # "cwa_stations": "https://opendata.cwa.gov.tw/dataset/observation/O-A0003-001",
        # "cwa_towns":    "https://opendata.cwa.gov.tw/dataset/observation/O-A0002-001",
    },

    # =========================
    # 尚未實作（先掛清單，未連動）
    # =========================

    # 1. 交流道路段績效
    "section_perf": "http://210.241.131.244/xml/section_1968_traffic_data.xml",

    # 2. 高速公路 CCTV 座標與影像
    "cctv": {
        "config_https": "http://210.241.131.244/xml/1day_cctv_config_data_https.xml",
        "thb_maintain": "https://cctv-maintain.thb.gov.tw/opendataCCTVs.xml",
    },

    # 3. 高速公路 CMS（設備配置與即時內容）
    "cms": {
        "1day_north":   "http://210.241.131.244/xml/1day_eq_config_data_north.xml",
        "1day_center":  "http://210.241.131.244/xml/1day_eq_config_data_center.xml",
        "1day_south":   "http://210.241.131.244/xml/1day_eq_config_data_south.xml",
        "1day_pinglin": "http://210.241.131.244/xml/1day_eq_config_data_pinglin.xml",
        "1min_north":   "http://210.241.131.244/xml/1min_eq_operation_data_north.xml",
        "1min_center":  "http://210.241.131.244/xml/1min_eq_operation_data_center.xml",
        "1min_south":   "http://210.241.131.244/xml/1min_eq_operation_data_south.xml",
        "1min_pinglin": "http://210.241.131.244/xml/1min_eq_operation_data_pinglin.xml",
    },

    # 4. 公路局 CMS
    "thb_cms": {
        "info": "https://thbapp.thb.gov.tw/opendata/cms/info/CMSList.xml",
        "live": "https://thbapp.thb.gov.tw/opendata/cms/two/CMSLiveList.xml",
    },

    # 9. 服務區充電樁（TDX，日後接 OAuth 後再實作）
    "ev": {
        "station":   "https://tdx.transportdata.tw/api/basic/v1/EV/Station/Freeway/ServiceArea?$top=30&$format=XML",
        "operator":  "https://tdx.transportdata.tw/api/basic/v1/EV/Operator/Freeway/ServiceArea?$top=30&$format=XML",
        "live":      "https://tdx.transportdata.tw/api/basic/v1/EV/ConnectorLiveStatus/Freeway/ServiceArea?$top=30&$format=XML",
    },

    # 11. 累積雨量（CWA 資料集入口；實作時請換實際 API path）
    "cwa_rain_accum": "https://opendata.cwa.gov.tw/dataset/observation/O-A0040-002",

    # 12. 雷達回波（靜態 S3 目錄；實作需挑選檔名規則）
    "cwa_radar_root": "https://cwbopendata.s3.ap-northeast-1.amazonaws.com/MSC/",

    # 13. 高速公路績效（單位別）
    "unit_perf": "http://210.241.131.244/xml/unit_1968_traffic_data.xml",

    # 14. 公路局即時路段資料
    "thb_live_section": "https://thbtrafficapp.thb.gov.tw/opendata/section/livetrafficdata/LiveTrafficList.xml",

    # 15. 即時行程規劃（1968 TravelTime Prediction）
    "tt_predict": {
        "dates": "https://1968mail.freeway.gov.tw/TravelTimePrediction/getPredictDates",
        "info":  "https://1968mail.freeway.gov.tw/TravelTimePrediction/getFreewayInfo",
        "tt":    "https://1968mail.freeway.gov.tw/TravelTimePrediction/getTravelTime",
    },

    # 16. 未來日旅行預測（CWA，資料集入口）
    "cwa_future_tt": "https://opendata.cwa.gov.tw/dataset/forecast/F-D0047-093",

    # 17. 國道 5 號路況（csv）
    "n5_csv": "http://210.241.131.244/xml/taipei_local.csv",

    # 18. 桃園機場路況（csv）
    "to_airport_csv": "http://210.241.131.244/xml/to_airport.csv",

    # 19. 後台管理單元
    "backend_event_list": "https://1968mgt.freeway.gov.tw/xml/EventList.xml",
}
