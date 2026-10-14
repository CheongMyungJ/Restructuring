package kr.co.dhsemi.tlog.yield;

import java.io.IOException;
import java.io.Writer;

import org.apache.commons.lang.StringUtils;
import org.springframework.batch.item.file.FlatFileFooterCallback;
import org.springframework.batch.item.file.FlatFileHeaderCallback;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.mapper.LotYieldMapper;

/**
 * MES 수율 리포트 H / T 레코드
 *
 * H(1) + 기준일자(8) + 시스템명(10) + D건수(7) + filler
 * T(1) + D건수(7) + 양품합계(7, 끝 7자리) + filler
 */
public class YieldReportCallback implements FlatFileHeaderCallback, FlatFileFooterCallback {

    private static final int REC_LEN = 60;

    @Autowired
    private LotYieldMapper lotYieldMapper;

    private String bizDate;

    public void setBizDate(String bizDate) {
        this.bizDate = bizDate;
    }

    public void writeHeader(Writer writer) throws IOException {
        int cnt = lotYieldMapper.countLotYield(bizDate);
        StringBuffer sb = new StringBuffer();
        sb.append("H");
        sb.append(bizDate);
        sb.append(StringUtils.rightPad(Constants.SYS_NAME, 10));
        sb.append(CommonUtil.lpadZero(cnt, 7));
        writer.write(StringUtils.rightPad(sb.toString(), REC_LEN));
    }

    public void writeFooter(Writer writer) throws IOException {
        int cnt = lotYieldMapper.countLotYield(bizDate);
        Long sum = lotYieldMapper.sumPassQty(bizDate);
        long passSum = (sum == null) ? 0L : sum.longValue();
        StringBuffer sb = new StringBuffer();
        sb.append("T");
        sb.append(CommonUtil.lpadZero(cnt, 7));
        sb.append(CommonUtil.lpadZero(passSum % 10000000L, 7));
        writer.write(StringUtils.rightPad(sb.toString(), REC_LEN));
        // footer 뒤에는 FlatFileItemWriter 가 개행을 안 붙임 -> MES 수신 오류 (2016.05) 직접 추가
        writer.write("\r\n");
    }
}
