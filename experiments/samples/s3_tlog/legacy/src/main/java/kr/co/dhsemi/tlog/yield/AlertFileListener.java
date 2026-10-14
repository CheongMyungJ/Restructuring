package kr.co.dhsemi.tlog.yield;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

import org.apache.commons.io.FileUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.ExitStatus;
import org.springframework.batch.core.StepExecution;
import org.springframework.batch.core.StepExecutionListener;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.mapper.LotYieldMapper;
import kr.co.dhsemi.tlog.vo.LotYieldVO;

/**
 * 수율 경보 파일 생성 (구 yieldAlertJob 을 2017.04 YIELD 잡에 통합)
 *
 * outbox/ALERT_{BIZ_DATE}.csv (UTF-8) - 경보 대상 있을 때만 생성
 */
public class AlertFileListener implements StepExecutionListener {

    private static final Logger logger = LoggerFactory.getLogger(AlertFileListener.class);

    private static final String HEADER = "BIZ_DATE,PROD_CD,PROD_NM,LOT_ID,IN_QTY,PASS_QTY,YIELD_PCT,ALERT_YIELD";

    @Autowired
    private LotYieldMapper lotYieldMapper;

    private String bizDate;

    public void setBizDate(String bizDate) {
        this.bizDate = bizDate;
    }

    public void beforeStep(StepExecution stepExecution) {
    }

    public ExitStatus afterStep(StepExecution stepExecution) {
        List<LotYieldVO> list = lotYieldMapper.selectAlertList(bizDate);
        if (list == null || list.isEmpty()) {
            logger.info("수율 경보 대상 없음");
            return null;
        }
        List<String> lines = new ArrayList<String>();
        lines.add(HEADER);
        for (LotYieldVO vo : list) {
            StringBuffer sb = new StringBuffer();
            sb.append(bizDate).append(',');
            sb.append(vo.getProdCd()).append(',');
            sb.append('"').append(CommonUtil.nvl(vo.getProdNm(), "")).append('"').append(',');
            sb.append(vo.getLotId()).append(',');
            sb.append(vo.getInQty()).append(',');
            sb.append(vo.getPassQty()).append(',');
            sb.append(vo.getYieldPct().setScale(2).toPlainString()).append(',');
            sb.append(vo.getAlertYield() == null ? "" : vo.getAlertYield().setScale(2).toPlainString());
            lines.add(sb.toString());
        }
        File f = new File(CommonUtil.getDir(Constants.DIR_OUTBOX), Constants.ALERT_PREFIX + bizDate + ".csv");
        try {
            FileUtils.writeLines(f, Constants.ENC_ALERT, lines, "\n");
            logger.info("수율 경보 파일 생성 : " + f.getName() + " (" + list.size() + "건)");
        } catch (Exception e) {
            logger.error("수율 경보 파일 생성 실패", e);
            return ExitStatus.FAILED;
        }
        return null;
    }
}
