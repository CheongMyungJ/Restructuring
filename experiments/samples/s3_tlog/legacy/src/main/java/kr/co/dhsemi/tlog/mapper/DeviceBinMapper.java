package kr.co.dhsemi.tlog.mapper;

import org.apache.ibatis.annotations.Param;

import kr.co.dhsemi.tlog.vo.DeviceBinVO;

public interface DeviceBinMapper {

    int mergeDeviceBin(DeviceBinVO vo);

    int countPrevScrap(@Param("serial") String serial, @Param("workDt") String workDt);
}
