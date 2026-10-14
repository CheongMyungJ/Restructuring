package kr.co.dhsemi.tlog.common.listener;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.ExitStatus;
import org.springframework.batch.core.StepExecution;
import org.springframework.batch.core.StepExecutionListener;

/**
 * 스텝 로그
 */
public class StepLogListener implements StepExecutionListener {

    private static final Logger log = LoggerFactory.getLogger(StepLogListener.class);

    public void beforeStep(StepExecution stepExecution) {
        log.info("[STEP] " + stepExecution.getStepName() + " start");
    }

    public ExitStatus afterStep(StepExecution stepExecution) {
        log.info("[STEP] " + stepExecution.getStepName() + " end - read:" + stepExecution.getReadCount()
                + ", filter:" + stepExecution.getFilterCount()
                + ", write:" + stepExecution.getWriteCount()
                + ", commit:" + stepExecution.getCommitCount());
        return stepExecution.getExitStatus();
    }
}
