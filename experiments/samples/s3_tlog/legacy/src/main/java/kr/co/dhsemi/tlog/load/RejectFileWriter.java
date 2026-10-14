package kr.co.dhsemi.tlog.load;

import java.io.File;
import java.io.IOException;

import org.apache.commons.io.FileUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.vo.FileInfo;

/**
 * 오류 레코드 reject 파일 기록
 *
 * reject/{원본파일명}.rej  -  "라인번호|에러코드|원본레코드"
 * 원본 파일과 동일한 인코딩으로 기록 (장비 업체 회신용)
 */
@Component
public class RejectFileWriter {

    private static final Logger logger = LoggerFactory.getLogger(RejectFileWriter.class);

    private static final String SEP = "|";

    public void write(FileInfo info, int lineNo, String errCd, String raw) {
        File rejFile = new File(CommonUtil.getDir(Constants.DIR_REJECT), info.getFileNm() + ".rej");
        StringBuffer sb = new StringBuffer();
        sb.append(lineNo).append(SEP).append(errCd).append(SEP).append(raw).append("\n");
        try {
            FileUtils.writeStringToFile(rejFile, sb.toString(), info.getEncoding(), true);
        } catch (IOException e) {
            logger.error("reject 파일 기록 실패 : " + rejFile.getName(), e);
        }
    }

    /**
     * 파일 전체 reject (트레일러 불일치)
     */
    public void writeFileError(FileInfo info, String errCd) {
        write(info, 0, errCd, info.getFileNm());
    }
}
