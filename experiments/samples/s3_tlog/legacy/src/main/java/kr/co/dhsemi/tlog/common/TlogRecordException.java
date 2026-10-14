package kr.co.dhsemi.tlog.common;

/**
 * 레코드 검증 오류
 *
 * @author kimjh
 */
public class TlogRecordException extends Exception {

    private static final long serialVersionUID = 1L;

    private String errCd;

    public TlogRecordException(String errCd) {
        super(errCd);
        this.errCd = errCd;
    }

    public TlogRecordException(String errCd, String msg) {
        super(errCd + " : " + msg);
        this.errCd = errCd;
    }

    public String getErrCd() {
        return errCd;
    }
}
