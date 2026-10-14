package kr.co.dhsemi.tlog.common.listener;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.JobExecution;
import org.springframework.batch.core.JobExecutionListener;
import org.springframework.batch.core.StepExecution;

import kr.co.dhsemi.tlog.common.CommonUtil;

/**
 * 잡 시작/종료 로그
 */
public class JobLogListener implements JobExecutionListener {

    private static final Logger logger = LoggerFactory.getLogger(JobLogListener.class);

    private long startTime;

    public void beforeJob(JobExecution jobExecution) {
        startTime = System.currentTimeMillis();
        logger.info("==========================================================");
        logger.info(" JOB START : " + jobExecution.getJobInstance().getJobName());
        logger.info(" PARAMS    : " + jobExecution.getJobParameters());
        logger.info(" TIME      : " + CommonUtil.getNow());
        logger.info("==========================================================");
    }

    public void afterJob(JobExecution jobExecution) {
        long elapsed = System.currentTimeMillis() - startTime;
        logger.info("==========================================================");
        logger.info(" JOB END   : " + jobExecution.getJobInstance().getJobName()
                + " status=" + jobExecution.getStatus() + " (" + elapsed + "ms)");
        for (StepExecution se : jobExecution.getStepExecutions()) {
            logger.info("   - " + se.getStepName() + " : " + se.getStatus()
                    + " read=" + se.getReadCount() + " write=" + se.getWriteCount()
                    + " filter=" + se.getFilterCount());
        }
        List<Throwable> errors = jobExecution.getAllFailureExceptions();
        if (errors != null && !errors.isEmpty()) {
            for (Throwable t : errors) {
                logger.error(" FAIL : " + t.getMessage(), t);
            }
        }
        logger.info("==========================================================");
    }
}
