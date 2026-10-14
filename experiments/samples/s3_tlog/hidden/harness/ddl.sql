-- =====================================================================
-- TLOG 배치 업무 테이블 DDL
--   * 운영 반영은 DBA 경유 (본 파일은 개발 참고용)
--   * 기준정보(제품/BIN룰/BIN코드/시스템설정)는 기준정보팀 관리
--   2015.08 최초작성
--   2016.03 TB_BIN_RULE.PRIORITY 추가
--   2017.04 TB_LOT_YIELD.ALERT_YN 추가 (ALERT 배치 통합)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 제품 기준정보
-- ---------------------------------------------------------------------
CREATE TABLE TB_PRODUCT (
    PROD_CD         VARCHAR2(8)     NOT NULL,
    PROD_NM         VARCHAR2(100)   NOT NULL,
    PROD_GRP        VARCHAR2(10),
    ALERT_YIELD     NUMBER(5,2),
    USE_YN          CHAR(1)         DEFAULT 'Y' NOT NULL,
    REG_DTM         DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_PRODUCT PRIMARY KEY (PROD_CD)
);
COMMENT ON TABLE TB_PRODUCT IS '제품 기준정보';
COMMENT ON COLUMN TB_PRODUCT.PROD_CD IS '제품코드';
COMMENT ON COLUMN TB_PRODUCT.PROD_NM IS '제품명';
COMMENT ON COLUMN TB_PRODUCT.PROD_GRP IS '제품군(CLIENT/ENT)';
COMMENT ON COLUMN TB_PRODUCT.ALERT_YIELD IS '수율 경보 기준(%)';
COMMENT ON COLUMN TB_PRODUCT.USE_YN IS '사용여부';

-- ---------------------------------------------------------------------
-- BIN 코드
-- ---------------------------------------------------------------------
CREATE TABLE TB_BIN_CODE (
    BIN_NO          NUMBER(2)       NOT NULL,
    BIN_NM          VARCHAR2(50)    NOT NULL,
    PASS_YN         CHAR(1)         DEFAULT 'N' NOT NULL,
    CONSTRAINT PK_BIN_CODE PRIMARY KEY (BIN_NO)
);
COMMENT ON TABLE TB_BIN_CODE IS 'BIN 코드';
COMMENT ON COLUMN TB_BIN_CODE.PASS_YN IS '양품 BIN 여부';

-- ---------------------------------------------------------------------
-- BIN 판정 룰
-- ---------------------------------------------------------------------
CREATE TABLE TB_BIN_RULE (
    RULE_ID         VARCHAR2(20)    NOT NULL,
    PROD_CD         VARCHAR2(8)     DEFAULT '*' NOT NULL,
    ITEM_CD         VARCHAR2(20)    NOT NULL,
    OPER_CD         VARCHAR2(2)     NOT NULL,
    THRESHOLD       NUMBER(12,2)    NOT NULL,
    BIN_NO          NUMBER(2)       NOT NULL,
    PRIORITY        NUMBER(4)       DEFAULT 100 NOT NULL,
    USE_YN          CHAR(1)         DEFAULT 'Y' NOT NULL,
    RULE_DESC       VARCHAR2(200),
    CONSTRAINT PK_BIN_RULE PRIMARY KEY (RULE_ID)
);
COMMENT ON TABLE TB_BIN_RULE IS 'BIN 판정 룰';
COMMENT ON COLUMN TB_BIN_RULE.PROD_CD IS '제품코드 (* = 전체)';
COMMENT ON COLUMN TB_BIN_RULE.ITEM_CD IS '판정항목 READ_MBPS/WRITE_MBPS/LAT_US/BAD_BLK/ECC_CNT/TEMP_MAX';
COMMENT ON COLUMN TB_BIN_RULE.OPER_CD IS '비교연산자 < <= > >=';
COMMENT ON COLUMN TB_BIN_RULE.PRIORITY IS '우선순위 (작을수록 먼저)';

-- ---------------------------------------------------------------------
-- 시스템 설정
-- ---------------------------------------------------------------------
CREATE TABLE TB_SYS_CONFIG (
    CFG_KEY         VARCHAR2(30)    NOT NULL,
    CFG_VAL         VARCHAR2(100),
    CFG_DESC        VARCHAR2(200),
    CONSTRAINT PK_SYS_CONFIG PRIMARY KEY (CFG_KEY)
);
COMMENT ON TABLE TB_SYS_CONFIG IS '시스템 설정';

-- ---------------------------------------------------------------------
-- 테스트 결과 (장비 로그 적재)
-- ---------------------------------------------------------------------
CREATE TABLE TB_TEST_RESULT (
    SERIAL          VARCHAR2(20)    NOT NULL,
    STEP_CD         VARCHAR2(4)     NOT NULL,
    START_DTM       VARCHAR2(14)    NOT NULL,
    END_DTM         VARCHAR2(14)    NOT NULL,
    WORK_DT         VARCHAR2(8)     NOT NULL,
    LOT_ID          VARCHAR2(10),
    PROD_CD         VARCHAR2(8),
    TESTER_ID       VARCHAR2(8),
    OPER_NM         VARCHAR2(10),
    RESULT_CD       CHAR(1)         NOT NULL,
    READ_MBPS       NUMBER(7,1),
    WRITE_MBPS      NUMBER(7,1),
    LAT_US          NUMBER(7),
    BAD_BLK         NUMBER(6),
    ECC_CNT         NUMBER(10),
    MAX_TEMP_C      NUMBER(4),
    FW_VER          VARCHAR2(8),
    VENDOR_CD       VARCHAR2(3)     NOT NULL,
    SRC_FILE_NM     VARCHAR2(50),
    REG_DTM         DATE            DEFAULT SYSDATE,
    UPD_DTM         DATE,
    CONSTRAINT PK_TEST_RESULT PRIMARY KEY (SERIAL, STEP_CD, START_DTM)
);
CREATE INDEX IX_TEST_RESULT_01 ON TB_TEST_RESULT (WORK_DT, SERIAL);
COMMENT ON TABLE TB_TEST_RESULT IS '테스트 결과';
COMMENT ON COLUMN TB_TEST_RESULT.START_DTM IS '시작일시 yyyyMMddHHmmss (KST)';
COMMENT ON COLUMN TB_TEST_RESULT.END_DTM IS '종료일시 yyyyMMddHHmmss (KST)';
COMMENT ON COLUMN TB_TEST_RESULT.WORK_DT IS '근무일자 (06시 기준)';
COMMENT ON COLUMN TB_TEST_RESULT.RESULT_CD IS 'P/F/A';
COMMENT ON COLUMN TB_TEST_RESULT.MAX_TEMP_C IS '최고온도(섭씨)';

-- ---------------------------------------------------------------------
-- 파일 적재 이력
-- ---------------------------------------------------------------------
CREATE TABLE TB_FILE_LOG (
    FILE_SEQ        NUMBER(10)      NOT NULL,
    FILE_NM         VARCHAR2(50)    NOT NULL,
    VENDOR_CD       VARCHAR2(3)     NOT NULL,
    BIZ_DT          VARCHAR2(8)     NOT NULL,
    TOTAL_CNT       NUMBER(7)       DEFAULT 0,
    LOAD_CNT        NUMBER(7)       DEFAULT 0,
    REJ_CNT         NUMBER(7)       DEFAULT 0,
    DUP_CNT         NUMBER(7)       DEFAULT 0,
    STATUS_CD       CHAR(1),
    LOAD_DTM        DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_FILE_LOG PRIMARY KEY (FILE_SEQ)
);
CREATE SEQUENCE SEQ_FILE_LOG START WITH 1 INCREMENT BY 1 NOCACHE;
COMMENT ON TABLE TB_FILE_LOG IS '파일 적재 이력';
COMMENT ON COLUMN TB_FILE_LOG.STATUS_CD IS 'S:정상 W:일부오류 E:파일오류';

-- ---------------------------------------------------------------------
-- 디바이스 최종 BIN
-- ---------------------------------------------------------------------
CREATE TABLE TB_DEVICE_BIN (
    SERIAL          VARCHAR2(20)    NOT NULL,
    WORK_DT         VARCHAR2(8)     NOT NULL,
    PROD_CD         VARCHAR2(8),
    LOT_ID          VARCHAR2(10),
    BIN_NO          NUMBER(2)       NOT NULL,
    RULE_ID         VARCHAR2(20),
    EXCL_YN         CHAR(1)         DEFAULT 'N' NOT NULL,
    REG_DTM         DATE            DEFAULT SYSDATE,
    UPD_DTM         DATE,
    CONSTRAINT PK_DEVICE_BIN PRIMARY KEY (SERIAL, WORK_DT)
);
COMMENT ON TABLE TB_DEVICE_BIN IS '디바이스 최종 BIN';
COMMENT ON COLUMN TB_DEVICE_BIN.EXCL_YN IS '수율 집계 제외여부';

-- ---------------------------------------------------------------------
-- LOT 수율
-- ---------------------------------------------------------------------
CREATE TABLE TB_LOT_YIELD (
    WORK_DT         VARCHAR2(8)     NOT NULL,
    PROD_CD         VARCHAR2(8)     NOT NULL,
    LOT_ID          VARCHAR2(10)    NOT NULL,
    IN_QTY          NUMBER(7)       NOT NULL,
    PASS_QTY        NUMBER(7)       NOT NULL,
    YIELD_PCT       NUMBER(5,2)     NOT NULL,
    BIN1_QTY        NUMBER(7)       DEFAULT 0,
    BIN2_QTY        NUMBER(7)       DEFAULT 0,
    BIN3_QTY        NUMBER(7)       DEFAULT 0,
    BIN4_QTY        NUMBER(7)       DEFAULT 0,
    BIN5_QTY        NUMBER(7)       DEFAULT 0,
    BIN6_QTY        NUMBER(7)       DEFAULT 0,
    BIN7_QTY        NUMBER(7)       DEFAULT 0,
    BIN8_QTY        NUMBER(7)       DEFAULT 0,
    BIN9_QTY        NUMBER(7)       DEFAULT 0,
    ALERT_YN        CHAR(1)         DEFAULT 'N',
    REG_DTM         DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_LOT_YIELD PRIMARY KEY (WORK_DT, PROD_CD, LOT_ID)
);
COMMENT ON TABLE TB_LOT_YIELD IS 'LOT 수율';
COMMENT ON COLUMN TB_LOT_YIELD.YIELD_PCT IS '수율(%) 소수점 2자리';
