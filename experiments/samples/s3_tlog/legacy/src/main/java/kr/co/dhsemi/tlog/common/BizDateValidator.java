package kr.co.dhsemi.tlog.common;

import org.springframework.batch.core.JobParameters;
import org.springframework.batch.core.JobParametersInvalidException;
import org.springframework.batch.core.JobParametersValidator;

/**
 * 잡 파라미터 BIZ_DATE 검증
 */
public class BizDateValidator implements JobParametersValidator {

    public void validate(JobParameters parameters) throws JobParametersInvalidException {
        if (parameters == null) {
            throw new JobParametersInvalidException("job parameter is null");
        }
        String bizDate = parameters.getString("BIZ_DATE");
        if (bizDate == null) {
            throw new JobParametersInvalidException("BIZ_DATE 파라미터 누락");
        }
        if (!CommonUtil.isValidYmd(bizDate)) {
            throw new JobParametersInvalidException("BIZ_DATE 형식 오류 : " + bizDate);
        }
    }
}
