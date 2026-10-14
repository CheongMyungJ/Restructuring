package kr.co.dhsemi.tlog.common;

/**
 * TLOG 공통 상수
 *
 * @author kimjh
 * @since 2015.08
 */
public class Constants {

    /* 장비 벤더 */
    public static final String VENDOR_ADV = "ADV";
    public static final String VENDOR_TER = "TER";

    /* 인코딩 */
    public static final String ENC_ADV = "MS949";
    public static final String ENC_TER = "UTF-8";
    public static final String ENC_REPORT = "MS949";
    public static final String ENC_ALERT = "UTF-8";
    public static final String ENC_DB = "MS949";   // 운영 DB 캐릭터셋 (KO16MSWIN949)

    /* 디렉토리 */
    public static final String DIR_INBOX = "inbox";
    public static final String DIR_OUTBOX = "outbox";
    public static final String DIR_REJECT = "reject";
    public static final String DIR_ARCHIVE = "archive";

    /* 테스트 STEP */
    public static final String STEP_FT1 = "FT1";
    public static final String STEP_BI = "BI";
    public static final String STEP_FT2 = "FT2";
    public static final String[] STEP_LIST = { STEP_FT1, STEP_BI, STEP_FT2 };

    /* 결과코드 */
    public static final String RSLT_PASS = "P";
    public static final String RSLT_FAIL = "F";
    public static final String RSLT_ABORT = "A";

    /** 재테스트 허용 횟수 */
    public static final int MAX_RETEST = 5;

    /* BIN */
    public static final int BIN_GOOD = 1;
    public static final int BIN_OVR_E = 5;
    public static final int BIN_FAIL = 7;
    public static final int BIN_ABORT = 8;
    public static final int BIN_SCRAP = 9;

    public static final String RULE_ABORT = "ABORT";
    public static final String RULE_OVR_E = "OVR_E";
    public static final String RULE_DEFAULT = "DEFAULT";
    public static final String RULE_DEFAULT_F = "DEFAULT_F";
    public static final String RULE_SCRAP_KEEP = "SCRAP_KEEP";

    /* 에러코드 */
    public static final String ERR_LENGTH = "E01";
    public static final String ERR_SERIAL = "E02";
    public static final String ERR_DATE = "E03";
    public static final String ERR_DATE_RANGE = "E04";
    public static final String ERR_RESULT = "E05";
    public static final String ERR_NUMBER = "E06";
    public static final String ERR_PRODUCT = "E07";
    public static final String ERR_STEP = "E08";
    public static final String ERR_TRAILER = "E09";

    /* 파일 처리 상태 */
    public static final String FILE_STAT_OK = "S";
    public static final String FILE_STAT_WARN = "W";
    public static final String FILE_STAT_ERR = "E";

    /* 중복 처리 */
    public static final String DUP_POLICY_KEY = "tlog.dup.policy";
    public static final String DUP_FIRST = "FIRST";
    public static final String DUP_LAST = "LAST";

    /* 리포트 */
    public static final String SYS_NAME = "TLOGBATCH";
    public static final String REPORT_PREFIX = "YIELD_";
    public static final String ALERT_PREFIX = "ALERT_";

    public static final String YES = "Y";
    public static final String NO = "N";

    /* 시스템설정 키 */
    public static final String CFG_RETENTION_DAYS = "RETENTION_DAYS";
    public static final int DEFAULT_RETENTION_DAYS = 90;

    // 2016.11 이전 MES 직접 연계용 - 사용안함
    // public static final String MES_IF_TABLE = "IF_MES_YIELD";
    // public static final String MES_IF_FLAG = "N";
}
