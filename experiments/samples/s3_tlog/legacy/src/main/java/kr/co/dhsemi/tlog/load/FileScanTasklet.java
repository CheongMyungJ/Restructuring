package kr.co.dhsemi.tlog.load;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Pattern;

import org.apache.commons.io.FileUtils;
import org.apache.commons.lang.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.StepContribution;
import org.springframework.batch.core.scope.context.ChunkContext;
import org.springframework.batch.core.step.tasklet.Tasklet;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.vo.FileInfo;

/**
 * LOAD 1단계 : inbox 파일 스캔 + 트레일러 검증
 *
 * 대상 : ADV_{BIZ_DATE}_NN.dat , TER_{BIZ_DATE}_NN.csv
 * 트레일러 건수 불일치 파일은 전체 reject (E09) 처리하고 적재 대상에서 제외
 */
public class FileScanTasklet implements Tasklet {

    private static final Logger logger = LoggerFactory.getLogger(FileScanTasklet.class);

    @Autowired
    private LoadContext loadContext;

    @Autowired
    private RejectFileWriter rejectFileWriter;

    private String bizDate;

    public void setBizDate(String bizDate) {
        this.bizDate = bizDate;
    }

    public RepeatStatus execute(StepContribution contribution, ChunkContext chunkContext) throws Exception {
        loadContext.clear();

        File inbox = CommonUtil.getDir(Constants.DIR_INBOX);
        File[] files = inbox.listFiles();
        if (files == null) {
            logger.warn("inbox 디렉토리 없음 : " + inbox.getAbsolutePath());
            return RepeatStatus.FINISHED;
        }

        Pattern advPtn = Pattern.compile("^ADV_" + bizDate + "_\\d{2}\\.dat$");
        Pattern terPtn = Pattern.compile("^TER_" + bizDate + "_\\d{2}\\.csv$");

        List<String> names = new ArrayList<String>();
        for (int i = 0; i < files.length; i++) {
            if (files[i].isFile()) {
                String nm = files[i].getName();
                if (advPtn.matcher(nm).matches() || terPtn.matcher(nm).matches()) {
                    names.add(nm);
                }
            }
        }
        Collections.sort(names);
        logger.info("적재 대상 파일 " + names.size() + "건 : " + names);

        for (String nm : names) {
            File f = new File(inbox, nm);
            FileInfo info;
            if (nm.startsWith("ADV_")) {
                info = new FileInfo(nm, Constants.VENDOR_ADV, bizDate);
                checkAdvTrailer(f, info);
            } else {
                info = new FileInfo(nm, Constants.VENDOR_TER, bizDate);
                checkTerTrailer(f, info);
            }
            if (info.isFileError()) {
                logger.warn("트레일러 불일치 -> 파일 전체 reject : " + nm);
                info.setRejCnt(info.getTotalCnt());
                rejectFileWriter.writeFileError(info, Constants.ERR_TRAILER);
            }
            loadContext.addFile(info);
        }
        return RepeatStatus.FINISHED;
    }

    /**
     * ADV : 마지막 T 레코드의 건수(7자리)와 D 레코드 건수 비교
     */
    private void checkAdvTrailer(File f, FileInfo info) throws Exception {
        List<String> lines = FileUtils.readLines(f, Constants.ENC_ADV);
        int dCnt = 0;
        int detailCnt = 0;
        String trailer = null;
        for (String line : lines) {
            if (line.length() == 0) {
                continue;
            }
            char recType = line.charAt(0);
            if (recType == 'H') {
                continue;
            }
            if (recType == 'T') {
                trailer = line;
                continue;
            }
            detailCnt++;
            if (recType == 'D') {
                dCnt++;
            }
        }
        info.setTotalCnt(detailCnt);

        if (trailer == null) {
            logger.warn("ADV 트레일러 없음 : " + f.getName());
            info.setFileError(true);
            return;
        }
        String cntStr = StringUtils.substring(trailer, 1, 8);
        if (!StringUtils.isNumeric(cntStr) || cntStr.length() != 7 || Integer.parseInt(cntStr) != dCnt) {
            logger.warn("ADV 트레일러 건수 불일치 : trailer=" + cntStr + ", D=" + dCnt);
            info.setFileError(true);
        }
    }

    /**
     * TER : #EOF,건수 라인이 있으면 데이터 건수와 비교 (없으면 체크 안함)
     */
    private void checkTerTrailer(File f, FileInfo info) throws Exception {
        List<String> lines = FileUtils.readLines(f, Constants.ENC_TER);
        int dataCnt = 0;
        String eof = null;
        // 0번째 라인은 헤더
        for (int i = 1; i < lines.size(); i++) {
            String line = lines.get(i);
            if (StringUtils.isBlank(line)) {
                continue;
            }
            if (line.startsWith("#EOF")) {
                eof = line;
                continue;
            }
            dataCnt++;
        }
        info.setTotalCnt(dataCnt);

        if (eof != null) {
            String[] arr = StringUtils.split(eof, ',');
            if (arr.length < 2 || !StringUtils.isNumeric(arr[1].trim()) || arr[1].trim().length() == 0
                    || Integer.parseInt(arr[1].trim()) != dataCnt) {
                logger.warn("TER #EOF 건수 불일치 : " + eof + ", data=" + dataCnt);
                info.setFileError(true);
            }
        }
    }
}
