package kr.co.dhsemi.tlog.vo;

import kr.co.dhsemi.tlog.common.Constants;

/**
 * 적재 대상 파일 정보 + 건수 집계 (TB_FILE_LOG)
 */
public class FileInfo {

    private String fileNm;
    private String vendorCd;
    private String bizDt;
    private String encoding;
    private int totalCnt;
    private int loadCnt;
    private int rejCnt;
    private int dupCnt;
    private boolean fileError = false;
    private String statusCd;

    public FileInfo(String fileNm, String vendorCd, String bizDt) {
        this.fileNm = fileNm;
        this.vendorCd = vendorCd;
        this.bizDt = bizDt;
        if (Constants.VENDOR_ADV.equals(vendorCd)) {
            this.encoding = Constants.ENC_ADV;
        } else {
            this.encoding = Constants.ENC_TER;
        }
    }

    public void addTotalCnt() { totalCnt++; }
    public void addLoadCnt() { loadCnt++; }
    public void addRejCnt() { rejCnt++; }
    public void addDupCnt() { dupCnt++; }

    public String getFileNm() { return fileNm; }
    public String getVendorCd() { return vendorCd; }
    public String getBizDt() { return bizDt; }
    public String getEncoding() { return encoding; }
    public int getTotalCnt() { return totalCnt; }
    public void setTotalCnt(int totalCnt) { this.totalCnt = totalCnt; }
    public int getLoadCnt() { return loadCnt; }
    public void setLoadCnt(int loadCnt) { this.loadCnt = loadCnt; }
    public int getRejCnt() { return rejCnt; }
    public void setRejCnt(int rejCnt) { this.rejCnt = rejCnt; }
    public int getDupCnt() { return dupCnt; }
    public void setDupCnt(int dupCnt) { this.dupCnt = dupCnt; }
    public boolean isFileError() { return fileError; }
    public void setFileError(boolean fileError) { this.fileError = fileError; }
    public String getStatusCd() { return statusCd; }
    public void setStatusCd(String statusCd) { this.statusCd = statusCd; }

    public boolean isAdv() {
        return Constants.VENDOR_ADV.equals(vendorCd);
    }

    @Override
    public String toString() {
        return fileNm + " total=" + totalCnt + " load=" + loadCnt + " rej=" + rejCnt + " dup=" + dupCnt
                + (fileError ? " [FILE ERROR]" : "");
    }
}
