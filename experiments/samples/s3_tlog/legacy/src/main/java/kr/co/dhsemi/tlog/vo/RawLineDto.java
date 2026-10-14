package kr.co.dhsemi.tlog.vo;

/**
 * 파일에서 읽은 원본 라인
 */
public class RawLineDto {

    private FileInfo fileInfo;
    private int lineNo;
    private String line;

    public RawLineDto(FileInfo fileInfo, int lineNo, String line) {
        this.fileInfo = fileInfo;
        this.lineNo = lineNo;
        this.line = line;
    }

    public FileInfo getFileInfo() { return fileInfo; }
    public int getLineNo() { return lineNo; }
    public String getLine() { return line; }
}
