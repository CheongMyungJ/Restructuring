package kr.co.dhsemi.tlog.load;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.List;

import org.apache.commons.lang.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.item.ExecutionContext;
import org.springframework.batch.item.ItemStreamException;
import org.springframework.batch.item.ItemStreamReader;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.vo.FileInfo;
import kr.co.dhsemi.tlog.vo.RawLineDto;

/**
 * 적재 대상 파일들을 순서대로 한 라인씩 읽는 reader
 * (ADV: H/T 레코드 skip, TER: 헤더/#EOF skip)
 *
 * 재시작 미지원 (restartable=false)
 */
public class TlogRecordReader implements ItemStreamReader<RawLineDto> {

    private static final Logger logger = LoggerFactory.getLogger(TlogRecordReader.class);

    @Autowired
    private LoadContext loadContext;

    private List<FileInfo> targetList;
    private int fileIdx = -1;
    private FileInfo current;
    private BufferedReader br;
    private int lineNo = 0;

    public void open(ExecutionContext executionContext) throws ItemStreamException {
        targetList = loadContext.getTargetFileList();
        fileIdx = -1;
        logger.info("적재 대상(트레일러 정상) 파일 : " + targetList.size() + "건");
    }

    public RawLineDto read() throws Exception {
        while (true) {
            if (br == null) {
                if (!openNextFile()) {
                    return null;
                }
            }
            String line = br.readLine();
            if (line == null) {
                CommonUtil.closeQuietly(br);
                br = null;
                continue;
            }
            lineNo++;

            if (current.isAdv()) {
                if (line.length() == 0) {
                    continue;
                }
                char recType = line.charAt(0);
                if (recType == 'H' || recType == 'T') {
                    continue;
                }
            } else {
                // 1번 라인 = 헤더
                if (lineNo == 1) {
                    continue;
                }
                if (StringUtils.isBlank(line) || line.startsWith("#EOF")) {
                    continue;
                }
            }
            return new RawLineDto(current, lineNo, line);
        }
    }

    private boolean openNextFile() throws IOException {
        fileIdx++;
        if (targetList == null || fileIdx >= targetList.size()) {
            return false;
        }
        current = targetList.get(fileIdx);
        File f = new File(CommonUtil.getDir(Constants.DIR_INBOX), current.getFileNm());
        br = new BufferedReader(new InputStreamReader(new FileInputStream(f), current.getEncoding()));
        lineNo = 0;
        logger.info("파일 읽기 : " + current.getFileNm() + " (" + current.getEncoding() + ")");
        return true;
    }

    public void update(ExecutionContext executionContext) throws ItemStreamException {
        // 재시작 미지원
    }

    public void close() throws ItemStreamException {
        CommonUtil.closeQuietly(br);
        br = null;
    }
}
