-- =====================================================================
-- 개발용 최소 기준정보 (로컬 테스트용)
--   ※ 운영 기준정보 아님. 운영 데이터는 기준정보팀에 요청
-- =====================================================================
INSERT INTO TB_PRODUCT (PROD_CD, PROD_NM, PROD_GRP, ALERT_YIELD, USE_YN) VALUES ('TST00001', '개발테스트 제품', 'CLIENT', 90.00, 'Y');
INSERT INTO TB_PRODUCT (PROD_CD, PROD_NM, PROD_GRP, ALERT_YIELD, USE_YN) VALUES ('ETS00001', '개발테스트 엔터프라이즈', 'ENT', 95.00, 'Y');

INSERT INTO TB_BIN_CODE (BIN_NO, BIN_NM, PASS_YN) VALUES (1, 'GOOD', 'Y');
INSERT INTO TB_BIN_CODE (BIN_NO, BIN_NM, PASS_YN) VALUES (7, 'FAIL', 'N');
INSERT INTO TB_BIN_CODE (BIN_NO, BIN_NM, PASS_YN) VALUES (8, 'ABORT', 'N');
INSERT INTO TB_BIN_CODE (BIN_NO, BIN_NM, PASS_YN) VALUES (9, 'SCRAP', 'N');

INSERT INTO TB_BIN_RULE (RULE_ID, PROD_CD, ITEM_CD, OPER_CD, THRESHOLD, BIN_NO, PRIORITY, USE_YN, RULE_DESC)
VALUES ('DEV_R01', '*', 'TEMP_MAX', '>=', 90, 7, 10, 'Y', '개발용');

INSERT INTO TB_SYS_CONFIG (CFG_KEY, CFG_VAL, CFG_DESC) VALUES ('RETENTION_DAYS', '30', '테스트결과 보관일수');

COMMIT;
