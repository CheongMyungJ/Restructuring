package kr.co.dhsemi.tlog.load;

import java.io.File;

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
import kr.co.dhsemi.tlog.vo.FileInfo;

/**
 * LOAD 3단계 : 파일 적재이력 기록 + archive 이동
 */
public class FileArchiveTasklet implements Tasklet {

    private static final Logger logger = LoggerFactory.getLogger(FileArchiveTasklet.class);

    @Autowired
    private LoadContext loadContext;

    private FileLogDao fileLogDao;

    private String bizDate;

    public void setFileLogDao(FileLogDao fileLogDao) {
        this.fileLogDao = fileLogDao;
    }

    public void setBizDate(String bizDate) {
        this.bizDate = bizDate;
    }

    public RepeatStatus execute(StepContribution contribution, ChunkContext chunkContext) throws Exception {
        File inbox = CommonUtil.getDir(Constants.DIR_INBOX);
        File archiveDir = new File(CommonUtil.getDir(Constants.DIR_ARCHIVE), bizDate);

        for (FileInfo info : loadContext.getFileList()) {
            if (info.isFileError()) {
                info.setStatusCd(Constants.FILE_STAT_ERR);
            } else if (info.getRejCnt() > 0) {
                info.setStatusCd(Constants.FILE_STAT_WARN);
            } else {
                info.setStatusCd(Constants.FILE_STAT_OK);
            }
            fileLogDao.insertFileLog(info);
            logger.info("[FILE] " + info + " status=" + info.getStatusCd());

            // archive 이동 (실패해도 배치는 정상 처리)
            boolean moved = CommonUtil.moveFile(new File(inbox, info.getFileNm()), archiveDir);
            if (!moved) {
                logger.warn("archive 이동 실패 : " + info.getFileNm());
            }
        }
        return RepeatStatus.FINISHED;
    }
}
