package kr.co.dhsemi.tlog.load.parser;

import java.math.BigDecimal;

import org.apache.commons.lang.StringUtils;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * ADV 로그 파서 V1 (구 레이아웃 128 byte)
 *
 * 2016.06 V2 레이아웃 전환 후 사용하지 않음. 혹시 몰라 남겨둠 - kimjh
 * @deprecated AdvRecordParser 사용
 */
public class AdvParserV1 {

    public static final int REC_LEN = 128;

    public TestResultVO parse(String line) {
        TestResultVO vo = new TestResultVO();
        try {
            byte[] b = line.getBytes("EUC-KR");
            if (b.length < REC_LEN) {
                return null;
            }
            vo.setSerial(StringUtils.trim(new String(b, 1, 16, "EUC-KR")));
            vo.setLotId(StringUtils.trim(new String(b, 17, 10, "EUC-KR")));
            vo.setProdCd(StringUtils.trim(new String(b, 27, 8, "EUC-KR")));
            vo.setStepCd(StringUtils.trim(new String(b, 35, 4, "EUC-KR")));
            vo.setStartDtm(new String(b, 39, 14, "EUC-KR"));
            vo.setEndDtm(new String(b, 53, 14, "EUC-KR"));
            vo.setWorkDt(vo.getStartDtm().substring(0, 8));   // V1 은 달력일자 기준
            vo.setTesterId(StringUtils.trim(new String(b, 67, 8, "EUC-KR")));
            vo.setOperNm(StringUtils.trim(new String(b, 75, 10, "EUC-KR")));
            vo.setResultCd(StringUtils.trim(new String(b, 85, 1, "EUC-KR")));
            vo.setReadMbps(new BigDecimal(new String(b, 86, 5, "EUC-KR").trim()));
            vo.setWriteMbps(new BigDecimal(new String(b, 91, 5, "EUC-KR").trim()));
            vo.setLatUs(Integer.valueOf(new String(b, 96, 6, "EUC-KR").trim()));
            vo.setBadBlk(Integer.valueOf(new String(b, 102, 5, "EUC-KR").trim()));
            vo.setEccCnt(Integer.valueOf(new String(b, 107, 8, "EUC-KR").trim()));
            vo.setMaxTempC(Integer.valueOf(CommonUtil.toInt(new String(b, 115, 3, "EUC-KR"), 0)));
            vo.setFwVer(StringUtils.trim(new String(b, 118, 6, "EUC-KR")));
        } catch (Exception e) {
            // 오류 레코드는 버림
            return null;
        }
        return vo;
    }
}
