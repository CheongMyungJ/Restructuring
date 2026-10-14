package kr.co.dhsemi.tlog.load;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Component;

import kr.co.dhsemi.tlog.vo.FileInfo;

/**
 * LOAD 잡 실행 중 공유 정보 (파일목록, 금회 적재키)
 *
 * 배치 1회 실행 = JVM 1개 이므로 singleton 으로 충분함.
 */
@Component
public class LoadContext {

    private List<FileInfo> fileList = new ArrayList<FileInfo>();

    /** 금회 실행에서 적재된 키 (SERIAL|STEP|START_DTM) */
    private Set<String> loadedKeys = new HashSet<String>();

    public void addFile(FileInfo info) {
        fileList.add(info);
    }

    public List<FileInfo> getFileList() {
        return fileList;
    }

    public List<FileInfo> getTargetFileList() {
        List<FileInfo> list = new ArrayList<FileInfo>();
        for (FileInfo f : fileList) {
            if (!f.isFileError()) {
                list.add(f);
            }
        }
        return list;
    }

    public boolean isLoaded(String key) {
        return loadedKeys.contains(key);
    }

    public void addLoaded(String key) {
        loadedKeys.add(key);
    }

    public void clear() {
        fileList.clear();
        loadedKeys.clear();
    }
}
