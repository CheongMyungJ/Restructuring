package kr.co.dhsemi.tlog.judge;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.item.ItemWriter;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.mapper.DeviceBinMapper;
import kr.co.dhsemi.tlog.vo.DeviceBinVO;

/**
 * TB_DEVICE_BIN MERGE
 */
public class DeviceBinWriter implements ItemWriter<DeviceBinVO> {

    private static final Logger logger = LoggerFactory.getLogger(DeviceBinWriter.class);

    @Autowired
    private DeviceBinMapper deviceBinMapper;

    public void write(List<? extends DeviceBinVO> items) throws Exception {
        for (DeviceBinVO vo : items) {
            if (logger.isDebugEnabled()) {
                logger.debug("merge " + vo);
            }
            deviceBinMapper.mergeDeviceBin(vo);
        }
    }
}
