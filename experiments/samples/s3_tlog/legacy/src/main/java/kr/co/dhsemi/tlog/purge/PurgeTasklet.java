package kr.co.dhsemi.tlog.purge;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.StepContribution;
import org.springframework.batch.core.scope.context.ChunkContext;
import org.springframework.batch.core.step.tasklet.Tasklet;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.dao.FileLogDao;
import kr.co.dhsemi.tlog.mapper.TestResultMapper;

/**
 * 테스트 결과 보관기간 경과분 삭제
 * TB_SYS_CONFIG.RETENTION_DAYS (기본 90일) 기준
 *
 * @author parksy 2016.04
 */
public class PurgeTasklet implements Tasklet {

    private static final Logger logger = LoggerFactory.getLogger(PurgeTasklet.class);

    @Autowired
    private TestResultMapper testResultMapper;

    private FileLogDao fileLogDao;

    private String bizDate;

    public void setFileLogDao(FileLogDao fileLogDao) {
        this.fileLogDao = fileLogDao;
    }

    public void setBizDate(String bizDate) {
        this.bizDate = bizDate;
    }

    public RepeatStatus execute(StepContribution contribution, ChunkContext chunkContext) throws Exception {
        String val = fileLogDao.getConfig(Constants.CFG_RETENTION_DAYS, String.valueOf(Constants.DEFAULT_RETENTION_DAYS));
        int days = CommonUtil.toInt(val, Constants.DEFAULT_RETENTION_DAYS);
        String cutoff = CommonUtil.addDays(bizDate, -days);
        int cnt = testResultMapper.deleteBeforeWorkDt(cutoff);
        logger.info("PURGE : WORK_DT < " + cutoff + " (" + days + "일) 삭제 " + cnt + "건");
        contribution.incrementWriteCount(cnt);
        return RepeatStatus.FINISHED;
    }
}
