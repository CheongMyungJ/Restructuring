package kr.co.dhsemi.tlog.dao;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.support.JdbcDaoSupport;

import kr.co.dhsemi.tlog.vo.FileInfo;

/**
 * 파일 적재이력 / 시스템설정 DAO
 *
 * 2015년 최초 개발분 (JdbcTemplate). 신규 개발은 MyBatis Mapper 사용할 것.
 *
 * @author kimjh
 */
public class FileLogDao extends JdbcDaoSupport {

    private static final Logger logger = LoggerFactory.getLogger(FileLogDao.class);

    private static final String INSERT_FILE_LOG =
            "INSERT INTO TB_FILE_LOG (FILE_SEQ, FILE_NM, VENDOR_CD, BIZ_DT, TOTAL_CNT, LOAD_CNT, REJ_CNT, DUP_CNT, STATUS_CD, LOAD_DTM) "
          + "VALUES (SEQ_FILE_LOG.NEXTVAL, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATE)";

    private static final String SELECT_CONFIG =
            "SELECT CFG_VAL FROM TB_SYS_CONFIG WHERE CFG_KEY = ?";

    public int insertFileLog(FileInfo info) {
        logger.debug("insertFileLog : " + info);
        return getJdbcTemplate().update(INSERT_FILE_LOG, new Object[] {
                info.getFileNm(),
                info.getVendorCd(),
                info.getBizDt(),
                new Integer(info.getTotalCnt()),
                new Integer(info.getLoadCnt()),
                new Integer(info.getRejCnt()),
                new Integer(info.getDupCnt()),
                info.getStatusCd() });
    }

    /**
     * 시스템 설정값 조회 (없으면 기본값)
     */
    public String getConfig(String key, String defVal) {
        try {
            List<String> list = getJdbcTemplate().queryForList(SELECT_CONFIG, new Object[] { key }, String.class);
            if (list == null || list.isEmpty() || list.get(0) == null) {
                return defVal;
            }
            return list.get(0);
        } catch (Exception e) {
            logger.warn("설정 조회 실패 : " + key + " -> 기본값 사용 (" + defVal + ")");
            return defVal;
        }
    }
}
